"""
Views novas do Planejamento simplificado: upload de arquivo, assistente de IA,
sugestão de habilidades BNCC, e os endpoints de criar/atualizar planejamento
semanal (sobrescrevendo as versões legadas via ``views/__init__.py``).

A reimplementação de criar/atualizar mora aqui porque eles dependem do
resolver de habilidades BNCC que materializa entradas em ``habilidades_bncc``
a partir de ``perguntas_bncc`` — assim as sugestões da IA (cujos códigos vêm
de ``perguntas_bncc``) deixam de cair em "Habilidade BNCC não encontrada"
durante o save e os relatórios passam a mostrar as habilidades selecionadas.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.models import (
    PlanejamentoDiario,
    PlanejamentoHabilidade,
    PlanejamentoSemanal,
)
from api.serializers import PlanejamentoSemanalSerializer
from api.throttles import UploadRateThrottle
from api.services.planejamento import (
    listar_planejamentos_filtrados,
    resolver_habilidade_bncc,
)
from api.services.planejamento_ia import (
    ALLOWED_PLANEJAMENTO_EXTENSIONS,
    ALLOWED_PLANEJAMENTO_MIME_TYPES,
    MAX_PLANEJAMENTO_SIZE_BYTES,
    extrair_atividades_por_dia,
    extrair_texto_arquivo,
    salvar_arquivo_planejamento,
    sugerir_atividades_a_partir_de_prompt,
    sugerir_habilidades_bncc,
)
from api.views_legacy import (
    IA_REQUEST_TIMEOUT_SECONDS,
    run_with_timeout,
    validate_uploaded_file,
)

DIAS_SEMANA_ORDENADOS = ["segunda", "terca", "quarta", "quinta", "sexta"]
DIAS_SEMANA_VALIDOS = set(DIAS_SEMANA_ORDENADOS)

logger = logging.getLogger(__name__)


def _get_cliente_id(request):
    """Extrai cliente_id (instituicao_id) do usuário autenticado."""
    return str(request.user.instituicao_id) if getattr(request.user, 'instituicao_id', None) else None


@api_view(["GET"])
@permission_classes([AllowAny])
def listar_planejamentos(request):
    """
    Lista planejamentos semanais com filtros.
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
    except Exception as exc:
        logger.exception("Erro ao listar planejamentos.")
        return Response(
            {"error": "Erro ao listar planejamentos", "details": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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
        return Response(
            {"error": "Campos obrigatórios: turma_id e dia_semana."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 1) Extrai texto antes de subir para o S3 — se o arquivo for inválido, não
    # faz sentido pagar storage por ele.
    try:
        texto_extraido = extrair_texto_arquivo(arquivo)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # 2) Sobe para o S3.
    try:
        meta_arquivo = salvar_arquivo_planejamento(arquivo, turma_id, dia_semana)
    except RuntimeError as exc:
        logger.exception("Falha ao subir arquivo de planejamento para o S3.")
        return Response(
            {"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY
        )

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

    # Compat: string consolidada para callers antigos.
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
    Assistente de IA livre. Recebe ``{prompt, ano_serie?, contexto?}`` e
    devolve ``{atividades_sugeridas}``.
    O prompt é resolvido do banco (categoria "Planejamento") via cliente_id.
    """
    payload = request.data or {}
    prompt = (payload.get("prompt") or "").strip()
    ano_serie = (payload.get("ano_serie") or "").strip()
    contexto = (payload.get("contexto") or "").strip()

    contexto_turma = " | ".join(filter(None, [
        f"Ano/série: {ano_serie}" if ano_serie else "",
        contexto,
    ]))

    cliente_id = _get_cliente_id(request)

    try:
        atividades_sugeridas = run_with_timeout(
            sugerir_atividades_a_partir_de_prompt,
            IA_REQUEST_TIMEOUT_SECONDS,
            prompt,
            contexto_turma,
            cliente_id,
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
def aplicar_planejamento_em_semanas(request):
    """
    Cria/atualiza ``PlanejamentoSemanal`` para uma ou mais semanas, sobrescrevendo
    apenas os dias informados em cada semana.

    Usado quando o upload de arquivo cobre mais de uma semana e o frontend
    precisa persistir as semanas extras sem que a professora navegue até elas.

    Body:
        {
          "turma_id": "...",
          "professora_id": "...",
          "professora_nome": "...",
          "arquivo": {                     # opcional — metadados aplicados a
            "storage_key": "...",          # cada dia que receber atividades
            "arquivo_nome_original": "...",
            "arquivo_content_type": "..."
          },
          "semanas": [
            {
              "semana_inicio": "YYYY-MM-DD",   # segunda-feira
              "dias": {
                "segunda": {"atividades_propostas": "..."},
                "terca":   {"atividades_propostas": "..."},
                ...
              }
            }
          ]
        }
    """
    payload = request.data or {}
    turma_id = (payload.get("turma_id") or "").strip()
    professora_id = (payload.get("professora_id") or "").strip()
    professora_nome = (payload.get("professora_nome") or "").strip()
    arquivo_meta = payload.get("arquivo") or {}
    semanas_payload = payload.get("semanas") or []

    if not turma_id:
        return Response(
            {"error": "Campo obrigatório: turma_id."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(semanas_payload, list) or not semanas_payload:
        return Response(
            {"error": "Campo 'semanas' deve ser uma lista não vazia."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    arquivo_storage_key = (arquivo_meta.get("storage_key") or None) if isinstance(
        arquivo_meta, dict
    ) else None
    arquivo_nome = (arquivo_meta.get("arquivo_nome_original") or None) if isinstance(
        arquivo_meta, dict
    ) else None
    arquivo_content_type = (arquivo_meta.get("arquivo_content_type") or None) if isinstance(
        arquivo_meta, dict
    ) else None

    semanas_afetadas = []

    for semana_item in semanas_payload:
        if not isinstance(semana_item, dict):
            continue
        semana_inicio_raw = (semana_item.get("semana_inicio") or "").strip()
        try:
            semana_inicio = parse_date(semana_inicio_raw)
        except (TypeError, ValueError):
            semana_inicio = None
        if not semana_inicio:
            return Response(
                {
                    "error": (
                        f"semana_inicio inválida: {semana_inicio_raw!r}. "
                        "Use YYYY-MM-DD."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if semana_inicio.weekday() != 0:
            return Response(
                {
                    "error": (
                        f"semana_inicio {semana_inicio.isoformat()} não é "
                        "segunda-feira."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        semana_fim = semana_inicio + timedelta(days=4)

        planejamento, criado = PlanejamentoSemanal.objects.get_or_create(
            turma_id=turma_id,
            semana_inicio=semana_inicio,
            defaults={
                "semana_fim": semana_fim,
                "professora_id": professora_id or "",
                "professora_nome": professora_nome or "",
            },
        )

        # Garante que existem 5 PlanejamentoDiario para esta semana.
        for i, dia_nome in enumerate(DIAS_SEMANA_ORDENADOS):
            data_dia = semana_inicio + timedelta(days=i)
            PlanejamentoDiario.objects.get_or_create(
                planejamento_semanal=planejamento,
                dia_semana=dia_nome,
                defaults={"data": data_dia},
            )

        dias_input = semana_item.get("dias") or {}
        if not isinstance(dias_input, dict):
            dias_input = {}

        dias_aplicados = []
        for dia_nome, dados_dia in dias_input.items():
            if dia_nome not in DIAS_SEMANA_VALIDOS or not isinstance(dados_dia, dict):
                continue
            dia_obj = planejamento.dias.filter(dia_semana=dia_nome).first()
            if not dia_obj:
                continue

            atividades = (dados_dia.get("atividades_propostas") or "").strip()
            dia_obj.atividades_propostas = atividades

            # Aplica metadados do arquivo (se houver) ao dia preenchido.
            if arquivo_storage_key:
                dia_obj.arquivo_storage_key = arquivo_storage_key
                dia_obj.arquivo_nome_original = arquivo_nome
                dia_obj.arquivo_content_type = arquivo_content_type

            dia_obj.save()
            dias_aplicados.append(dia_nome)

        planejamento.save(update_fields=["data_modificacao"])

        semanas_afetadas.append(
            {
                "planejamento_id": planejamento.id,
                "semana_inicio": semana_inicio.isoformat(),
                "semana_fim": semana_fim.isoformat(),
                "criado": criado,
                "dias_aplicados": dias_aplicados,
            }
        )

    return Response(
        {"success": True, "semanas_afetadas": semanas_afetadas},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sugerir_bncc_planejamento(request):
    """
    Recebe ``{atividades_texto, ano_serie?, limite?}`` e devolve as
    habilidades BNCC sugeridas, com origem ('ia' ou 'fallback').
    Substitui o antigo ``/api/planejamento/sugestoes-ia/`` mas usa as
    candidatas vindas de ``perguntas_bncc.habilidade_bncc``.
    O prompt é resolvido do banco (categoria "Planejamento") via cliente_id.
    """
    payload = request.data or {}
    atividades_texto = (payload.get("atividades_texto") or "").strip()
    ano_serie = (payload.get("ano_serie") or "").strip()
    try:
        limite = int(payload.get("limite", 6))
    except (TypeError, ValueError):
        limite = 6

    cliente_id = _get_cliente_id(request)

    try:
        resultado = run_with_timeout(
            sugerir_habilidades_bncc,
            IA_REQUEST_TIMEOUT_SECONDS,
            atividades_texto,
            ano_serie,
            limite,
            cliente_id,
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
# CRUD de PlanejamentoSemanal (sobrescreve as versões em views_legacy.py)
# ---------------------------------------------------------------------------


def _persistir_habilidades(dia_obj: PlanejamentoDiario, refs) -> None:
    """Recria os vínculos BNCC do dia, materializando códigos novos no catálogo."""
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


@api_view(["POST"])
def criar_planejamento_semanal(request):
    """
    Cria um novo planejamento semanal (formato simplificado: cada dia tem
    apenas atividades_propostas, prompt_ia, arquivo_* e habilidades).
    """
    try:
        turma_id = request.data.get("turma_id")
        semana_inicio_raw = request.data.get("semana_inicio")
        professora_id = request.data.get("professora_id")
        professora_nome = request.data.get("professora_nome")
        planejamento_dias = request.data.get("dias", {}) or {}

        if not all([turma_id, semana_inicio_raw, professora_id, professora_nome]):
            return Response(
                {
                    "error": (
                        "Campos obrigatórios: turma_id, semana_inicio, "
                        "professora_id, professora_nome"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            semana_inicio = parse_date(semana_inicio_raw)
        except (TypeError, ValueError):
            semana_inicio = None
        if not semana_inicio:
            return Response(
                {"error": "semana_inicio inválida. Use o formato YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sexta-feira da mesma semana (segunda=0 ... sexta=4).
        dias_ate_sexta = 4 - semana_inicio.weekday()
        semana_fim = semana_inicio + timedelta(days=dias_ate_sexta)

        if PlanejamentoSemanal.objects.filter(
            turma_id=turma_id,
            semana_inicio=semana_inicio,
        ).exists():
            return Response(
                {"error": "Já existe um planejamento para esta turma nesta semana"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planejamento = PlanejamentoSemanal.objects.create(
            turma_id=turma_id,
            semana_inicio=semana_inicio,
            semana_fim=semana_fim,
            professora_id=professora_id,
            professora_nome=professora_nome,
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

        return Response(
            {
                "success": True,
                "planejamento_id": planejamento.id,
                "turma_id": turma_id,
                "semana_inicio": semana_inicio.isoformat(),
                "semana_fim": semana_fim.isoformat(),
                "dias_criados": dias_criados,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as exc:
        logger.exception("Erro ao criar planejamento semanal.")
        return Response(
            {"error": "Erro ao criar planejamento semanal", "details": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT"])
def atualizar_planejamento_semanal(request, planejamento_id):
    """
    Atualiza um planejamento semanal existente. Quando o arquivo de um dia
    troca (ou é removido), o objeto antigo é apagado do S3 para evitar lixo.
    """
    from api.services.planejamento_ia import remover_arquivo_planejamento

    try:
        planejamento = PlanejamentoSemanal.objects.get(id=planejamento_id)
    except PlanejamentoSemanal.DoesNotExist:
        return Response(
            {"error": "Planejamento não encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        planejamento_dias = request.data.get("dias", {}) or {}

        for dia_nome, dados_dia in planejamento_dias.items():
            if not isinstance(dados_dia, dict):
                continue
            dia_obj = planejamento.dias.filter(dia_semana=dia_nome).first()
            if not dia_obj:
                continue

            if "atividades_propostas" in dados_dia:
                dia_obj.atividades_propostas = dados_dia.get("atividades_propostas") or ""
            if "prompt_ia" in dados_dia:
                dia_obj.prompt_ia = dados_dia.get("prompt_ia") or ""

            if "arquivo_storage_key" in dados_dia:
                novo_key = dados_dia.get("arquivo_storage_key") or None
                key_anterior = dia_obj.arquivo_storage_key
                if key_anterior and key_anterior != novo_key:
                    remover_arquivo_planejamento(key_anterior)
                dia_obj.arquivo_storage_key = novo_key
                dia_obj.arquivo_nome_original = dados_dia.get("arquivo_nome_original") or None
                dia_obj.arquivo_content_type = dados_dia.get("arquivo_content_type") or None

            dia_obj.save()

            if "habilidades" in dados_dia:
                dia_obj.habilidades.all().delete()
                _persistir_habilidades(dia_obj, dados_dia.get("habilidades") or [])

        planejamento.save(update_fields=["data_modificacao"])

        return Response(
            {
                "success": True,
                "message": "Planejamento atualizado com sucesso",
                "planejamento_id": planejamento.id,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as exc:
        logger.exception("Erro ao atualizar planejamento semanal.")
        return Response(
            {"error": "Erro ao atualizar planejamento", "details": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )