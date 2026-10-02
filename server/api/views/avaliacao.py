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
# Detalhe de cadastro da escola (template e período)
# ============================================================

def _detalhe_cadastro_escola(model, serializer_class, obj_id, msg_nao_encontrado):
    obj = buscar_no_escopo(model, obj_id)
    if obj is None:
        return _nao_encontrado(msg_nao_encontrado)
    return Response(serializer_class(obj).data)


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
# Regras:
#   * o template pertence a uma ESCOLA (unique escola+modelo);
#   * no máximo UM ativo por escola (índice único parcial no banco) — é o que
#     o gerador usa. Ativar um desativa os outros da mesma escola, na mesma
#     transação, com a linha da escola travada (duas ativações simultâneas
#     não furam a regra);
#   * todos do escopo leem; só gestão cria/edita.

_TEMPLATE_NAO_ENCONTRADO = 'Template não encontrado.'


def _dados_com_escola_padrao(user, data):
    """Admin que não informa `escola` usa a própria, se tiver.
    (Coordenador sempre usa a própria — resolver_escopo_criacao ignora o body.)"""
    dados = data.copy() if hasattr(data, 'copy') else dict(data)
    if not dados.get('escola') and user.nivel == 'admin' and user.escola_id:
        dados['escola'] = str(user.escola_id)
    return dados


def _salvar_template(serializer, escola_id, **extra):
    """Valida e salva com a escola travada; se o template fica ativo,
    desativa os demais da escola antes de gravar."""
    with transaction.atomic():
        list(Escola._base_manager.select_for_update().filter(pk=escola_id).values_list('pk', flat=True))
        serializer.is_valid(raise_exception=True)

        modelo = serializer.validated_data.get('modelo', getattr(serializer.instance, 'modelo', None))
        repetido = RelatorioTemplate._base_manager.filter(escola_id=escola_id, modelo=modelo)
        if serializer.instance is not None:
            repetido = repetido.exclude(pk=serializer.instance.pk)
        if repetido.exists():
            return None, Response(
                {'error': f'Esta escola já tem um template do modelo "{modelo}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ficara_ativo = serializer.validated_data.get('ativo', getattr(serializer.instance, 'ativo', False))
        if ficara_ativo:
            outros = RelatorioTemplate._base_manager.filter(escola_id=escola_id, ativo=True)
            if serializer.instance is not None:
                outros = outros.exclude(pk=serializer.instance.pk)
            outros.update(ativo=False, atualizado_em=timezone.now())

        return serializer.save(**extra), None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_relatorio_templates(request):
    """GET /relatorio-templates/ — recortado pelo TenantManager.
    ?escola=<uuid> filtra uma escola; ?ativo=1 só o ativo. O ativo vem primeiro."""
    templates = filtrar_por(RelatorioTemplate.objects.all(), request, 'escola', Escola, 'escola')
    if request.query_params.get('ativo') == '1':
        templates = templates.filter(ativo=True)
    templates = templates.order_by('-ativo', '-atualizado_em')
    return Response(RelatorioTemplateSerializer(templates, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_relatorio_template(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    dados = _dados_com_escola_padrao(user, request.data)
    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, dados)
    if erro:
        return erro

    serializer = RelatorioTemplateSerializer(data=dados)
    template, erro = _salvar_template(serializer, escola_id, escola_id=escola_id, instituicao_id=instituicao_id)
    if erro:
        return erro
    return Response(RelatorioTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_relatorio_template(request, template_id):
    return _detalhe_cadastro_escola(
        RelatorioTemplate, RelatorioTemplateSerializer, template_id, _TEMPLATE_NAO_ENCONTRADO,
    )


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_relatorio_template(request, template_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    template = buscar_no_escopo(RelatorioTemplate, template_id)
    if template is None:
        return _nao_encontrado(_TEMPLATE_NAO_ENCONTRADO)

    # escola/instituicao são read_only: o template não muda de escola.
    serializer = RelatorioTemplateSerializer(template, data=request.data, partial=request.method == 'PATCH')
    template, erro = _salvar_template(serializer, template.escola_id)
    if erro:
        return erro
    return Response(RelatorioTemplateSerializer(template).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_relatorio_template(request, template_id):
    """Exclusão definitiva. Relatórios já gerados com ele ficam com
    template=NULL (FK SET_NULL) e o PDF passa a usar o tema padrão. Se era o
    ativo, a escola volta para a capa/ordem padrão até ativar outro."""
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    template = buscar_no_escopo(RelatorioTemplate, template_id)
    if template is None:
        return _nao_encontrado(_TEMPLATE_NAO_ENCONTRADO)

    template.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


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