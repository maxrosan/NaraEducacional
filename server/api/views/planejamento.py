"""
Views do Planejamento: upload de arquivo, assistente de IA, sugestão de
habilidades BNCC, e o CRUD de planejamento semanal/diário.

Portado do legado com os seguintes ajustes pro schema multi-tenant novo:
- `professora_id`/`professora_nome` (strings soltas) viraram `professor`
  (FK pra Usuario) — o nome já vem de lá, não precisa duplicar.
- `planejamento.dias` (related_name antigo) virou `planejamento.planejamentos_diarios`.
- `data_modificacao` virou `atualizado_em`.
- `resolver_habilidade_bncc` não materializa mais nada a partir de
  perguntas — busca direto no catálogo `HabilidadeBNCC`, que agora é FK
  de verdade em `Pergunta.habilidade_bncc`.
- Criação/atualização agora respeitam o mesmo controle de permissão do
  resto da API (professor só mexe na própria turma, admin/coordenador
  têm escopo mais amplo).

Regras de integridade:
- `professor` informado no body: só a gestão pode apontar outro professor, e
  ele precisa ser da escola da turma. Os demais sempre gravam como autores.
- `arquivo_storage_key` vindo do body precisa ser um arquivo desta turma
  (`planejamentos/<turma_id>/...`, formato de `salvar_arquivo_planejamento`)
  — senão daria para apontar o planejamento para o arquivo de outra escola.
- O mesmo arquivo pode estar em vários dias/semanas (`aplicar_em_semanas`):
  ele só é apagado do storage quando nenhum dia o referencia mais, e só
  depois do commit.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    buscar_no_escopo, dono_ou_gestao, pode_gerenciar, professor_vinculado_turma,
)
from api.models import PlanejamentoDiario, PlanejamentoHabilidade, PlanejamentoSemanal, Turma, Usuario
from api.serializers import PlanejamentoSemanalSerializer
from api.throttles import UploadRateThrottle
from api.services.planejamento import listar_planejamentos_filtrados, resolver_habilidade_bncc
from api.services.planejamento_ia import (
    ALLOWED_PLANEJAMENTO_EXTENSIONS,
    ALLOWED_PLANEJAMENTO_MIME_TYPES,
    MAX_PLANEJAMENTO_SIZE_BYTES,
    extrair_atividades_por_dia,
    extrair_texto_arquivo,
    salvar_arquivo_planejamento,
    sugerir_atividades_a_partir_de_prompt,
    sugerir_habilidades_bncc,
    remover_arquivo_planejamento,
)
from api.ia_utils import IA_REQUEST_TIMEOUT_SECONDS, run_with_timeout, validate_uploaded_file

DIAS_SEMANA_ORDENADOS = ["segunda", "terca", "quarta", "quinta", "sexta"]
DIAS_SEMANA_VALIDOS = set(DIAS_SEMANA_ORDENADOS)

logger = logging.getLogger(__name__)


def _erro(mensagem, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({"error": mensagem}, status=codigo)


def _turma_com_permissao(user, turma_id):
    """Turma do escopo em que o usuário pode planejar. Retorna (turma, erro)."""
    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return None, _erro("Turma não encontrada.", status.HTTP_404_NOT_FOUND)
    if not pode_gerenciar(user) and not professor_vinculado_turma(user, turma.id):
        return None, _erro("Você não está vinculado a essa turma.", status.HTTP_403_FORBIDDEN)
    return turma, None


def _professor_do_planejamento(user, turma, professor_id):
    """Autor do planejamento. Retorna (professor_id, erro).

    Sem `professor_id` no body → o próprio usuário. Só a gestão pode informar
    outro — e ele precisa existir no escopo e ser da escola da turma.
    """
    if not professor_id or str(professor_id) == str(user.id):
        return user.id, None
    if not pode_gerenciar(user):
        return None, _erro("Você só pode criar planejamentos em seu nome.", status.HTTP_403_FORBIDDEN)
    professor = buscar_no_escopo(Usuario, professor_id)
    if professor is None or professor.escola_id != turma.escola_id:
        return None, _erro("Professor não encontrado na escola da turma.")
    return professor.id, None


def _escola_do_prompt(request):
    """Escola cujo prompt personalizado vale na sugestão de IA: a da turma
    (`turma_id` opcional no body — necessário para admin/superadmin, que não
    têm escola) ou, sem turma, a escola do próprio usuário."""
    turma_id = (request.data or {}).get("turma_id")
    if turma_id:
        turma = buscar_no_escopo(Turma, turma_id)
        if turma is not None:
            return turma.escola_id
    return getattr(request.user, "escola_id", None)


def _chave_invalida(turma, chave):
    """`arquivo_storage_key` do body precisa ser um arquivo desta turma."""
    if chave and not str(chave).startswith(f"planejamentos/{turma.id}/"):
        return _erro("Arquivo de planejamento inválido para esta turma.")
    return None


def _descartar_arquivo_se_orfao(chave):
    """Apaga o arquivo do storage se nenhum dia o referencia mais. Agendado
    com `on_commit`: se a transação falhar, o arquivo continua lá."""
    if not chave:
        return

    def _apagar():
        if not PlanejamentoDiario._base_manager.filter(arquivo_storage_key=chave).exists():
            remover_arquivo_planejamento(chave)

    transaction.on_commit(_apagar)


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def listar_planejamentos(request):
    """
    Lista planejamentos semanais com filtros. Já vem filtrado pelo
    TenantManager (escola/instituição do usuário); os query params abaixo
    refinam ainda mais dentro desse escopo.

    Query params: instituicao_id, semana_referencia__gte, semana_referencia__lte,
                  turma_id, professora_id (ou o alias id_professor), ordering.
    """
    try:
        queryset = listar_planejamentos_filtrados(
            instituicao_id=request.GET.get("instituicao_id"),
            turma_id=request.GET.get("turma_id"),
            professora_id=request.GET.get("professora_id")
            or request.GET.get("id_professor"),
            semana_gte=request.GET.get("semana_referencia__gte"),
            semana_lte=request.GET.get("semana_referencia__lte"),
            ordering=request.GET.get("ordering", "-semana_inicio"),
        )
        serializer = PlanejamentoSemanalSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception:
        logger.exception("Erro ao listar planejamentos.")
        return _erro("Erro ao listar planejamentos", status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Upload + extração + sugestão de atividades
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def processar_arquivo_planejamento(request):
    """
    Recebe um PDF/DOC/DOCX, sobe para o S3, extrai o texto e gera uma
    sugestão de "Atividades Propostas". Não persiste nada no
    PlanejamentoDiario — o frontend decide quando salvar.
    """
    if "arquivo" not in request.FILES:
        return Response(
            {"error": "Nenhum arquivo foi enviado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    arquivo = request.FILES["arquivo"]
    turma_id = (request.POST.get("turma_id") or "").strip()
    dia_semana = (request.POST.get("dia_semana") or "").strip()

    erro_validacao = validate_uploaded_file(
        arquivo,
        ALLOWED_PLANEJAMENTO_MIME_TYPES,
        ALLOWED_PLANEJAMENTO_EXTENSIONS,
        MAX_PLANEJAMENTO_SIZE_BYTES,
        "planejamento",
    )
    if erro_validacao:
        mensagem, status_code = erro_validacao
        return Response({"error": mensagem}, status=status_code)

    if not turma_id or not dia_semana:
        return _erro("Campos obrigatórios: turma_id e dia_semana.")
    if dia_semana not in DIAS_SEMANA_VALIDOS:
        return _erro(f"dia_semana inválido. Use: {', '.join(DIAS_SEMANA_ORDENADOS)}.")

    turma, erro = _turma_com_permissao(request.user, turma_id)
    if erro:
        return erro

    # 1) Extrai texto antes de subir para o S3 — se o arquivo for inválido, não
    # faz sentido pagar storage por ele.
    try:
        texto_extraido = extrair_texto_arquivo(arquivo)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # 2) Sobe para o S3.
    try:
        meta_arquivo = salvar_arquivo_planejamento(arquivo, str(turma.id), dia_semana)
    except RuntimeError as exc:
        logger.exception("Falha ao subir arquivo de planejamento para o S3.")
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    # 3) Extrai atividades por dia + janela de datas em uma chamada à IA.
    extracao = None
    try:
        extracao = run_with_timeout(
            extrair_atividades_por_dia,
            IA_REQUEST_TIMEOUT_SECONDS,
            texto_extraido,
        )
    except TimeoutError:
        return Response(
            {
                "error": "Tempo limite excedido ao gerar sugestões de atividades.",
                "storage_key": meta_arquivo["storage_key"],
                "arquivo_url": meta_arquivo["arquivo_url"],
                "arquivo_nome_original": meta_arquivo["arquivo_nome_original"],
                "arquivo_content_type": meta_arquivo["arquivo_content_type"],
                "texto_extraido": texto_extraido,
                "atividades_por_dia": [],
                "atividades_sugeridas": "",
                "data_detectada": None,
            },
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except (ValueError, RuntimeError) as exc:
        logger.warning("Falha ao extrair atividades por dia: %s", exc)
        extracao = None

    extracao = extracao or {
        "dias": [],
        "data_inicio": None,
        "data_fim": None,
        "evidencia": "",
        "confianca": None,
        "fallback_texto_unico": "",
    }

    if extracao["dias"]:
        partes = []
        for d in extracao["dias"]:
            label = (d.get("dia_semana") or "").capitalize()
            if d.get("data"):
                label = f"{label} ({d['data']})" if label else d["data"]
            cabecalho = f"{label}:" if label else ""
            partes.append(f"{cabecalho}\n{d['atividades']}".strip())
        atividades_sugeridas = "\n\n".join(partes)
    else:
        atividades_sugeridas = extracao.get("fallback_texto_unico") or ""

    data_detectada = None
    if extracao.get("data_inicio"):
        data_detectada = {
            "data_inicio": extracao["data_inicio"],
            "data_fim": extracao["data_fim"],
            "evidencia": extracao["evidencia"],
            "confianca": extracao["confianca"] or "media",
        }

    return Response(
        {
            "success": True,
            "storage_key": meta_arquivo["storage_key"],
            "arquivo_url": meta_arquivo["arquivo_url"],
            "arquivo_nome_original": meta_arquivo["arquivo_nome_original"],
            "arquivo_content_type": meta_arquivo["arquivo_content_type"],
            "texto_extraido": texto_extraido,
            "atividades_por_dia": extracao["dias"],
            "atividades_sugeridas": atividades_sugeridas,
            "data_detectada": data_detectada,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sugerir_atividades_planejamento(request):
    """
    Assistente de IA livre. Recebe ``{prompt, ano_serie?, contexto?, turma_id?}``
    e devolve ``{atividades_sugeridas}``.
    O prompt é resolvido do banco (categoria "Planejamento") pela escola.
    """
    payload = request.data or {}
    prompt = (payload.get("prompt") or "").strip()
    ano_serie = (payload.get("ano_serie") or "").strip()
    contexto = (payload.get("contexto") or "").strip()

    contexto_turma = " | ".join(filter(None, [
        f"Ano/série: {ano_serie}" if ano_serie else "",
        contexto,
    ]))

    escola_id = _escola_do_prompt(request)

    try:
        atividades_sugeridas = run_with_timeout(
            sugerir_atividades_a_partir_de_prompt,
            IA_REQUEST_TIMEOUT_SECONDS,
            prompt,
            contexto_turma,
            escola_id,
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except TimeoutError:
        return Response(
            {"error": "Tempo limite excedido ao gerar sugestões."},
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except RuntimeError as exc:
        logger.warning("OpenAI indisponível para assistente de planejamento: %s", exc)
        return Response(
            {"error": "Assistente de IA indisponível no momento."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {"success": True, "atividades_sugeridas": atividades_sugeridas},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sugerir_bncc_planejamento(request):
    """
    Recebe ``{atividades_texto, ano_serie?, limite?, turma_id?}`` e devolve as
    habilidades BNCC sugeridas, com origem ('ia' ou 'fallback'), buscadas
    no catálogo `HabilidadeBNCC`.
    """
    payload = request.data or {}
    atividades_texto = (payload.get("atividades_texto") or "").strip()
    ano_serie = (payload.get("ano_serie") or "").strip()
    try:
        limite = int(payload.get("limite", 6))
    except (TypeError, ValueError):
        limite = 6

    escola_id = _escola_do_prompt(request)

    try:
        resultado = run_with_timeout(
            sugerir_habilidades_bncc,
            IA_REQUEST_TIMEOUT_SECONDS,
            atividades_texto,
            ano_serie,
            limite,
            escola_id,
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except TimeoutError:
        return Response(
            {"error": "Tempo limite excedido ao gerar sugestões de BNCC."},
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )

    return Response({"success": True, **resultado}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# CRUD de PlanejamentoSemanal
# ---------------------------------------------------------------------------

def _persistir_habilidades(dia_obj: PlanejamentoDiario, refs) -> None:
    """Recria os vínculos BNCC do dia."""
    if not isinstance(refs, list):
        return
    for ref in refs:
        habilidade = resolver_habilidade_bncc(ref)
        if habilidade is None:
            logger.warning("Habilidade BNCC não encontrada: %s", ref)
            continue
        PlanejamentoHabilidade.objects.get_or_create(
            planejamento_diario=dia_obj,
            habilidade_bncc=habilidade,
        )


def _aplicar_arquivo(dia_obj, chave, nome, content_type):
    """Troca o arquivo do dia; o anterior é apagado se ficar órfão."""
    chave_anterior = dia_obj.arquivo_storage_key
    dia_obj.arquivo_storage_key = chave
    dia_obj.arquivo_nome_original = nome
    dia_obj.arquivo_content_type = content_type
    if chave_anterior and chave_anterior != chave:
        _descartar_arquivo_se_orfao(chave_anterior)


def _parse_semana(valor):
    try:
        return parse_date(valor or "")
    except (TypeError, ValueError):
        return None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def criar_planejamento_semanal(request):
    """
    Cria um novo planejamento semanal (formato simplificado: cada dia tem
    apenas atividades_propostas, prompt_ia, arquivo_* e habilidades).
    `professor` é opcional no body — se não vier, assume o usuário logado
    (admin/coordenador podem informar outro professor explicitamente).
    """
    user = request.user
    turma_id = request.data.get("turma_id") or request.data.get("turma")
    semana_inicio_raw = request.data.get("semana_inicio")
    planejamento_dias = request.data.get("dias", {}) or {}
    if not isinstance(planejamento_dias, dict):
        planejamento_dias = {}

    if not turma_id or not semana_inicio_raw:
        return _erro("Campos obrigatórios: turma_id, semana_inicio")

    turma, erro = _turma_com_permissao(user, turma_id)
    if erro:
        return erro

    professor_id, erro = _professor_do_planejamento(
        user, turma, request.data.get("professor_id") or request.data.get("professora_id"),
    )
    if erro:
        return erro

    semana_inicio = _parse_semana(semana_inicio_raw)
    if not semana_inicio:
        return _erro("semana_inicio inválida. Use o formato YYYY-MM-DD.")

    for dados_dia in planejamento_dias.values():
        if isinstance(dados_dia, dict):
            erro = _chave_invalida(turma, dados_dia.get("arquivo_storage_key"))
            if erro:
                return erro

    # Sexta-feira da mesma semana (segunda=0 ... sexta=4).
    semana_fim = semana_inicio + timedelta(days=4 - semana_inicio.weekday())

    if PlanejamentoSemanal.objects.filter(turma=turma, semana_inicio=semana_inicio).exists():
        return _erro("Já existe um planejamento para esta turma nesta semana")

    try:
        with transaction.atomic():
            planejamento = PlanejamentoSemanal.objects.create(
                turma=turma,
                semana_inicio=semana_inicio,
                semana_fim=semana_fim,
                professor_id=professor_id,
                escola_id=turma.escola_id,
                instituicao_id=turma.instituicao_id,
            )

            dias_criados = []
            for i, dia_nome in enumerate(DIAS_SEMANA_ORDENADOS):
                data_dia = semana_inicio + timedelta(days=i)
                dados_dia = planejamento_dias.get(dia_nome) or {}
                if not isinstance(dados_dia, dict):
                    dados_dia = {}

                dia_obj = PlanejamentoDiario.objects.create(
                    planejamento_semanal=planejamento,
                    dia_semana=dia_nome,
                    data=data_dia,
                    atividades_propostas=dados_dia.get("atividades_propostas") or "",
                    prompt_ia=dados_dia.get("prompt_ia") or "",
                    arquivo_storage_key=dados_dia.get("arquivo_storage_key") or None,
                    arquivo_nome_original=dados_dia.get("arquivo_nome_original") or None,
                    arquivo_content_type=dados_dia.get("arquivo_content_type") or None,
                    escola_id=turma.escola_id,
                    instituicao_id=turma.instituicao_id,
                )

                habilidades_refs = dados_dia.get("habilidades") or []
                _persistir_habilidades(dia_obj, habilidades_refs)

                dias_criados.append(
                    {
                        "dia": dia_nome,
                        "data": data_dia.isoformat(),
                        "habilidades_count": len(habilidades_refs),
                    }
                )
    except IntegrityError:
        # Outra requisição criou a mesma semana entre o exists() e o create().
        return _erro("Já existe um planejamento para esta turma nesta semana")
    except Exception:
        logger.exception("Erro ao criar planejamento semanal.")
        return _erro("Erro ao criar planejamento semanal", status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(
        {
            "success": True,
            "planejamento_id": planejamento.id,
            "turma_id": str(turma.id),
            "semana_inicio": semana_inicio.isoformat(),
            "semana_fim": semana_fim.isoformat(),
            "dias_criados": dias_criados,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def atualizar_planejamento_semanal(request, planejamento_id):
    """
    Atualiza um planejamento semanal existente. Quando o arquivo de um dia
    troca (ou é removido), o objeto antigo é apagado do storage — se nenhum
    outro dia o usar.
    """
    planejamento = buscar_no_escopo(PlanejamentoSemanal, planejamento_id)
    if planejamento is None:
        return _erro("Planejamento não encontrado", status.HTTP_404_NOT_FOUND)

    if not dono_ou_gestao(request.user, planejamento):
        return _erro("Sem permissão.", status.HTTP_403_FORBIDDEN)

    planejamento_dias = request.data.get("dias", {}) or {}
    if not isinstance(planejamento_dias, dict):
        planejamento_dias = {}

    for dados_dia in planejamento_dias.values():
        if isinstance(dados_dia, dict):
            erro = _chave_invalida(planejamento.turma, dados_dia.get("arquivo_storage_key"))
            if erro:
                return erro

    try:
        with transaction.atomic():
            for dia_nome, dados_dia in planejamento_dias.items():
                if not isinstance(dados_dia, dict):
                    continue
                dia_obj = planejamento.planejamentos_diarios.filter(dia_semana=dia_nome).first()
                if not dia_obj:
                    continue

                if "atividades_propostas" in dados_dia:
                    dia_obj.atividades_propostas = dados_dia.get("atividades_propostas") or ""
                if "prompt_ia" in dados_dia:
                    dia_obj.prompt_ia = dados_dia.get("prompt_ia") or ""

                if "arquivo_storage_key" in dados_dia:
                    _aplicar_arquivo(
                        dia_obj,
                        dados_dia.get("arquivo_storage_key") or None,
                        dados_dia.get("arquivo_nome_original") or None,
                        dados_dia.get("arquivo_content_type") or None,
                    )

                dia_obj.save()

                if "habilidades" in dados_dia:
                    dia_obj.planejamentos_habilidades.all().delete()
                    _persistir_habilidades(dia_obj, dados_dia.get("habilidades") or [])

            planejamento.save(update_fields=["atualizado_em"])
    except Exception:
        logger.exception("Erro ao atualizar planejamento semanal.")
        return _erro("Erro ao atualizar planejamento", status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(
        {
            "success": True,
            "message": "Planejamento atualizado com sucesso",
            "planejamento_id": planejamento.id,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def aplicar_planejamento_em_semanas(request):
    """
    Cria/atualiza ``PlanejamentoSemanal`` para uma ou mais semanas,
    sobrescrevendo apenas os dias informados em cada semana.

    Usado quando o upload de arquivo cobre mais de uma semana e o frontend
    precisa persistir as semanas extras sem que a professora navegue até elas.

    Tudo é validado ANTES de gravar (datas, permissão sobre semanas que já
    existem, arquivo da turma) e a gravação é atômica: ou todas as semanas
    são aplicadas, ou nenhuma.
    """
    user = request.user
    payload = request.data or {}
    turma_id = str(payload.get("turma_id") or "").strip()
    arquivo_meta = payload.get("arquivo") or {}
    semanas_payload = payload.get("semanas") or []

    if not turma_id:
        return _erro("Campo obrigatório: turma_id.")
    if not isinstance(semanas_payload, list) or not semanas_payload:
        return _erro("Campo 'semanas' deve ser uma lista não vazia.")

    turma, erro = _turma_com_permissao(user, turma_id)
    if erro:
        return erro

    professor_id, erro = _professor_do_planejamento(
        user, turma, payload.get("professor_id") or payload.get("professora_id"),
    )
    if erro:
        return erro

    if not isinstance(arquivo_meta, dict):
        arquivo_meta = {}
    arquivo_storage_key = arquivo_meta.get("storage_key") or None
    arquivo_nome = arquivo_meta.get("arquivo_nome_original") or None
    arquivo_content_type = arquivo_meta.get("arquivo_content_type") or None
    erro = _chave_invalida(turma, arquivo_storage_key)
    if erro:
        return erro

    # 1ª passada: valida tudo sem gravar nada.
    semanas = []
    for semana_item in semanas_payload:
        if not isinstance(semana_item, dict):
            continue
        semana_inicio_raw = str(semana_item.get("semana_inicio") or "").strip()
        semana_inicio = _parse_semana(semana_inicio_raw)
        if not semana_inicio:
            return _erro(f"semana_inicio inválida: {semana_inicio_raw!r}. Use YYYY-MM-DD.")
        if semana_inicio.weekday() != 0:
            return _erro(f"semana_inicio {semana_inicio.isoformat()} não é segunda-feira.")

        existente = PlanejamentoSemanal.objects.filter(turma=turma, semana_inicio=semana_inicio).first()
        if existente and not dono_ou_gestao(user, existente):
            return _erro(
                f"Sem permissão para alterar o planejamento da semana {semana_inicio.isoformat()}.",
                status.HTTP_403_FORBIDDEN,
            )

        dias_input = semana_item.get("dias") or {}
        semanas.append((semana_inicio, dias_input if isinstance(dias_input, dict) else {}))

    # 2ª passada: grava.
    semanas_afetadas = []
    try:
        with transaction.atomic():
            for semana_inicio, dias_input in semanas:
                semana_fim = semana_inicio + timedelta(days=4)

                planejamento, criado = PlanejamentoSemanal.objects.get_or_create(
                    turma=turma,
                    semana_inicio=semana_inicio,
                    defaults={
                        "semana_fim": semana_fim,
                        "professor_id": professor_id,
                        "escola_id": turma.escola_id,
                        "instituicao_id": turma.instituicao_id,
                    },
                )

                # Garante que existem 5 PlanejamentoDiario para esta semana.
                for i, dia_nome in enumerate(DIAS_SEMANA_ORDENADOS):
                    PlanejamentoDiario.objects.get_or_create(
                        planejamento_semanal=planejamento,
                        dia_semana=dia_nome,
                        defaults={
                            "data": semana_inicio + timedelta(days=i),
                            "escola_id": turma.escola_id,
                            "instituicao_id": turma.instituicao_id,
                        },
                    )

                dias_aplicados = []
                for dia_nome, dados_dia in dias_input.items():
                    if dia_nome not in DIAS_SEMANA_VALIDOS or not isinstance(dados_dia, dict):
                        continue
                    dia_obj = planejamento.planejamentos_diarios.filter(dia_semana=dia_nome).first()
                    if not dia_obj:
                        continue

                    dia_obj.atividades_propostas = (dados_dia.get("atividades_propostas") or "").strip()
                    if arquivo_storage_key:
                        _aplicar_arquivo(dia_obj, arquivo_storage_key, arquivo_nome, arquivo_content_type)

                    dia_obj.save()
                    dias_aplicados.append(dia_nome)

                planejamento.save(update_fields=["atualizado_em"])

                semanas_afetadas.append(
                    {
                        "planejamento_id": planejamento.id,
                        "semana_inicio": semana_inicio.isoformat(),
                        "semana_fim": semana_fim.isoformat(),
                        "criado": criado,
                        "dias_aplicados": dias_aplicados,
                    }
                )
    except Exception:
        logger.exception("Erro ao aplicar planejamento em semanas.")
        return _erro("Erro ao aplicar planejamento", status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"success": True, "semanas_afetadas": semanas_afetadas}, status=status.HTTP_200_OK)