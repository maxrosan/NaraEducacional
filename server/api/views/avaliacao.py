"""Endpoints de PeriodoAvaliativo, RelatorioTemplate e Relatorio."""

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    buscar_no_escopo, filtrar_por, pode_gerenciar, professor_vinculado_turma, resolver_escopo_criacao,
)
from api.models import PeriodoAvaliativo, RelatorioTemplate, Relatorio, Aluno, Escola
from api.serializers import PeriodoAvaliativoSerializer, RelatorioTemplateSerializer, RelatorioSerializer
from api.services.relatorio import refresh_img_urls_in_html


def _sem_permissao(mensagem='Sem permissão.'):
    return Response({'error': mensagem}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado(mensagem):
    return Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)


# ============================================================
# CRUD de cadastro da escola (template; detalhe também do período)
# ============================================================
# RelatorioTemplate usa os três helpers abaixo: todos do escopo leem; só
# gestão cria/edita; escola/instituição vêm de `resolver_escopo_criacao`.
# PeriodoAvaliativo usa só o de detalhe: criar/editar têm validação própria
# (sobreposição de datas) e ficam na seção dele.

def _criar_cadastro_escola(request, serializer_class):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(escola_id=escola_id, instituicao_id=instituicao_id)
    return Response(serializer_class(obj).data, status=status.HTTP_201_CREATED)


def _detalhe_cadastro_escola(model, serializer_class, obj_id, msg_nao_encontrado):
    obj = buscar_no_escopo(model, obj_id)
    if obj is None:
        return _nao_encontrado(msg_nao_encontrado)
    return Response(serializer_class(obj).data)


def _atualizar_cadastro_escola(request, model, serializer_class, obj_id, msg_nao_encontrado):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    obj = buscar_no_escopo(model, obj_id)
    if obj is None:
        return _nao_encontrado(msg_nao_encontrado)

    partial = request.method == 'PATCH'
    serializer = serializer_class(obj, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# PeriodoAvaliativo
# ============================================================

PERIODOS_POR_PAGINA = 10
PERIODOS_POR_PAGINA_MAX = 50
_PERIODO_NAO_ENCONTRADO = 'Período avaliativo não encontrado.'


def _param_int_periodo(valor, padrao, minimo, maximo):
    try:
        return max(minimo, min(int(valor), maximo))
    except (TypeError, ValueError):
        return padrao


def _validar_e_salvar_periodo(serializer, escola_travada_id, **extra):
    """Valida e salva o período numa transação, com a linha da escola travada.

    A regra de sobreposição (mesmo tipo, mesma escola, datas em comum) é
    checada no serializer; a trava (SELECT ... FOR UPDATE) impede que duas
    requisições simultâneas passem ambas pela checagem.

    `escola_travada_id` tem esse nome (e não `escola_id`) porque `escola_id`
    também chega em `**extra` para o serializer.save() na criação.
    """
    with transaction.atomic():
        list(Escola._base_manager.select_for_update().filter(pk=escola_travada_id).values_list('pk', flat=True))
        serializer.is_valid(raise_exception=True)
        return serializer.save(**extra)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_periodos_avaliativos(request):
    """
    GET /periodos-avaliativos/ — já vem recortado pelo TenantManager.

    Query params (todos opcionais):
      situacao=vigentes|encerrados   vigentes = em andamento ou futuros (fim >= hoje)
      escola=<uuid>                  fora do escopo/malformado → vazio
      page=<n>                       liga a paginação (fora do intervalo → última)
      page_size=<n>                  padrão 10, máximo 50

    SEM `page`: devolve um array simples (mais recente primeiro), como antes —
    outras telas (relatórios, coordenação) usam a lista completa.

    COM `page`:
      {
        "count": 8, "pagina": 1, "total_paginas": 1, "page_size": 10,
        "totais": {"vigentes": 4, "encerrados": 4},   # p/ as abas
        "results": [ ...PeriodoAvaliativoSerializer (com escola_nome)... ]
      }

    Ordem: vigentes do mais próximo ao mais distante (o que está em andamento
    primeiro); encerrados do mais recente ao mais antigo.
    """
    base = filtrar_por(PeriodoAvaliativo.objects.all(), request, 'escola', Escola, 'escola')
    base = base.select_related('escola')

    if 'page' not in request.query_params:
        return Response(PeriodoAvaliativoSerializer(base.order_by('-data_inicio', 'id'), many=True).data)

    hoje = timezone.localdate()
    situacao = request.query_params.get('situacao')
    if situacao == 'vigentes':
        periodos = base.filter(data_fim__gte=hoje).order_by('data_inicio', 'escola__nome', 'id')
    elif situacao == 'encerrados':
        periodos = base.filter(data_fim__lt=hoje).order_by('-data_inicio', 'escola__nome', 'id')
    else:
        periodos = base.order_by('-data_inicio', 'escola__nome', 'id')

    page_size = _param_int_periodo(
        request.query_params.get('page_size'),
        PERIODOS_POR_PAGINA, 1, PERIODOS_POR_PAGINA_MAX,
    )
    pagina = Paginator(periodos, page_size).get_page(request.query_params.get('page'))

    # Totais das abas respeitam o filtro de escola, mas não o de situação.
    totais = base.aggregate(
        vigentes=Count('id', filter=Q(data_fim__gte=hoje)),
        encerrados=Count('id', filter=Q(data_fim__lt=hoje)),
    )
    totais = {chave: valor or 0 for chave, valor in totais.items()}

    return Response({
        'count': pagina.paginator.count,
        'pagina': pagina.number,
        'total_paginas': pagina.paginator.num_pages,
        'page_size': page_size,
        'totais': totais,
        'results': PeriodoAvaliativoSerializer(pagina.object_list, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_periodo_avaliativo(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    # _base_manager: o resolver já garantiu que a escola é do escopo do usuário.
    if not Escola._base_manager.filter(id=escola_id, ativa=True).exists():
        return Response({'error': 'Não é possível criar períodos em uma escola desativada.'},
                        status=status.HTTP_400_BAD_REQUEST)

    serializer = PeriodoAvaliativoSerializer(data=request.data, context={'escola_id': escola_id})
    periodo = _validar_e_salvar_periodo(
        serializer, escola_id, escola_id=escola_id, instituicao_id=instituicao_id,
    )
    return Response(PeriodoAvaliativoSerializer(periodo).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_periodo_avaliativo(request, periodo_id):
    return _detalhe_cadastro_escola(
        PeriodoAvaliativo, PeriodoAvaliativoSerializer, periodo_id, _PERIODO_NAO_ENCONTRADO,
    )


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_periodo_avaliativo(request, periodo_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    periodo = buscar_no_escopo(PeriodoAvaliativo, periodo_id)
    if periodo is None:
        return _nao_encontrado(_PERIODO_NAO_ENCONTRADO)

    # escola/instituicao são read_only: o período não muda de escola.
    partial = request.method == 'PATCH'
    serializer = PeriodoAvaliativoSerializer(periodo, data=request.data, partial=partial)
    periodo = _validar_e_salvar_periodo(serializer, periodo.escola_id)
    return Response(PeriodoAvaliativoSerializer(periodo).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def excluir_periodo_avaliativo(request, periodo_id):
    """Exclusão definitiva. Nenhuma tabela tem chave estrangeira para período
    (o `periodo` do Relatorio é texto), então não há nada para quebrar em
    cascata; relatórios antigos continuam com o texto do período."""
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    periodo = buscar_no_escopo(PeriodoAvaliativo, periodo_id)
    if periodo is None:
        return _nao_encontrado(_PERIODO_NAO_ENCONTRADO)

    periodo.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# RelatorioTemplate
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_relatorio_templates(request):
    templates = RelatorioTemplate.objects.all()
    return Response(RelatorioTemplateSerializer(templates, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_relatorio_template(request):
    return _criar_cadastro_escola(request, RelatorioTemplateSerializer)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_relatorio_template(request, template_id):
    return _detalhe_cadastro_escola(
        RelatorioTemplate, RelatorioTemplateSerializer, template_id, 'Template não encontrado.',
    )


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_relatorio_template(request, template_id):
    return _atualizar_cadastro_escola(
        request, RelatorioTemplate, RelatorioTemplateSerializer, template_id, 'Template não encontrado.',
    )


# ============================================================
# Relatorio
# ============================================================

def _pode_editar_relatorio(user, relatorio):
    """Gestão edita qualquer um; professor, os de alunos das turmas dele."""
    return pode_gerenciar(user) or professor_vinculado_turma(user, relatorio.aluno.turma_id)


def _relatorio_ou_404(relatorio_id):
    """Retorna (relatorio, erro)."""
    relatorio = buscar_no_escopo(Relatorio, relatorio_id)
    if relatorio is None:
        return None, _nao_encontrado('Relatório não encontrado.')
    return relatorio, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_relatorios(request):
    relatorios = filtrar_por(Relatorio.objects.all(), request, 'aluno', Aluno, 'aluno')
    return Response(RelatorioSerializer(relatorios.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_relatorio(request):
    user = request.user
    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return _nao_encontrado('Aluno não encontrado.')

    if not pode_gerenciar(user) and not professor_vinculado_turma(user, aluno.turma_id):
        return _sem_permissao('Você não está vinculado à turma desse aluno.')

    serializer = RelatorioSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    relatorio = serializer.save(
        aluno=aluno, escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(RelatorioSerializer(relatorio).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_relatorio(request, relatorio_id):
    relatorio, erro = _relatorio_ou_404(relatorio_id)
    if erro:
        return erro
    data = dict(RelatorioSerializer(relatorio).data)
    # As <img> do HTML guardam URLs pré-assinadas do S3 que expiram em ~1h.
    # Re-assinar aqui evita fotos quebradas na tela do relatório.
    if data.get('conteudo'):
        data['conteudo'] = refresh_img_urls_in_html(data['conteudo'])
    return Response(data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_relatorio(request, relatorio_id):
    relatorio, erro = _relatorio_ou_404(relatorio_id)
    if erro:
        return erro
    if not _pode_editar_relatorio(request.user, relatorio):
        return _sem_permissao()

    partial = request.method == 'PATCH'
    serializer = RelatorioSerializer(relatorio, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revisar_relatorio(request, relatorio_id):
    """Marca o relatório como revisado pelo usuário atual. Só admin/coordenador/superadmin."""
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    relatorio, erro = _relatorio_ou_404(relatorio_id)
    if erro:
        return erro

    relatorio.revisado_por = user
    relatorio.save(update_fields=['revisado_por', 'atualizado_em'])
    return Response(RelatorioSerializer(relatorio).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_relatorio(request, relatorio_id):
    relatorio, erro = _relatorio_ou_404(relatorio_id)
    if erro:
        return erro
    if not _pode_editar_relatorio(request.user, relatorio):
        return _sem_permissao()

    relatorio.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)