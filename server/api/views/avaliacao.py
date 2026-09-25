"""Endpoints de PeriodoAvaliativo, RelatorioTemplate e Relatorio."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    buscar_no_escopo, filtrar_por, pode_gerenciar, professor_vinculado_turma, resolver_escopo_criacao,
)
from api.models import PeriodoAvaliativo, RelatorioTemplate, Relatorio, Aluno
from api.serializers import PeriodoAvaliativoSerializer, RelatorioTemplateSerializer, RelatorioSerializer
from api.services.relatorio import refresh_img_urls_in_html


def _sem_permissao(mensagem='Sem permissão.'):
    return Response({'error': mensagem}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado(mensagem):
    return Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)


# ============================================================
# CRUD de cadastro da escola (período e template)
# ============================================================
# PeriodoAvaliativo e RelatorioTemplate têm exatamente as mesmas regras:
# todos do escopo leem; só gestão cria/edita; escola/instituição vêm de
# `resolver_escopo_criacao`. Os helpers abaixo evitam repetir isso 2x.

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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_periodos_avaliativos(request):
    periodos = PeriodoAvaliativo.objects.all()
    return Response(PeriodoAvaliativoSerializer(periodos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_periodo_avaliativo(request):
    return _criar_cadastro_escola(request, PeriodoAvaliativoSerializer)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_periodo_avaliativo(request, periodo_id):
    return _detalhe_cadastro_escola(
        PeriodoAvaliativo, PeriodoAvaliativoSerializer, periodo_id, 'Período avaliativo não encontrado.',
    )


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_periodo_avaliativo(request, periodo_id):
    return _atualizar_cadastro_escola(
        request, PeriodoAvaliativo, PeriodoAvaliativoSerializer, periodo_id, 'Período avaliativo não encontrado.',
    )


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