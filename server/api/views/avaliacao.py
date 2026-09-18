"""Endpoints de PeriodoAvaliativo, RelatorioTemplate e Relatorio."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import PeriodoAvaliativo, RelatorioTemplate, Relatorio, Aluno, UsuarioTurma
from api.serializers import PeriodoAvaliativoSerializer, RelatorioTemplateSerializer, RelatorioSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar_geral(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


def _professor_vinculado_turma(usuario, turma):
    return UsuarioTurma.objects.filter(usuario=usuario, turma=turma).exists()


def _escola_instituicao_por_escopo(user, request):
    """Resolve (escola_id, instituicao_id) pra criação, ou (None, None, Response) se inválido."""
    if _is_superadmin(user):
        instituicao_id = request.data.get('instituicao')
        escola_id = request.data.get('escola')
        if not instituicao_id or not escola_id:
            return None, None, Response(
                {'error': 'Campos instituicao e escola são obrigatórios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return escola_id, instituicao_id, None
    if user.nivel == 'admin':
        if user.instituicao_id is None:
            return None, None, Response(
                {'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        escola_id = request.data.get('escola')
        return escola_id, user.instituicao_id, None
    # coordenador
    if user.escola_id is None:
        return None, None, Response(
            {'error': 'Usuário sem escola vinculada.'}, status=status.HTTP_400_BAD_REQUEST,
        )
    return user.escola_id, user.instituicao_id, None


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
    user = request.user
    if not _pode_gerenciar_geral(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id, instituicao_id, erro = _escola_instituicao_por_escopo(user, request)
    if erro:
        return erro

    serializer = PeriodoAvaliativoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    periodo = serializer.save(escola_id=escola_id, instituicao_id=instituicao_id)
    return Response(PeriodoAvaliativoSerializer(periodo).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_periodo_avaliativo(request, periodo_id):
    try:
        periodo = PeriodoAvaliativo.objects.get(id=periodo_id)
    except PeriodoAvaliativo.DoesNotExist:
        return Response({'error': 'Período avaliativo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(PeriodoAvaliativoSerializer(periodo).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_periodo_avaliativo(request, periodo_id):
    if not _pode_gerenciar_geral(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        periodo = PeriodoAvaliativo.objects.get(id=periodo_id)
    except PeriodoAvaliativo.DoesNotExist:
        return Response({'error': 'Período avaliativo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = PeriodoAvaliativoSerializer(periodo, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


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
    user = request.user
    if not _pode_gerenciar_geral(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id, instituicao_id, erro = _escola_instituicao_por_escopo(user, request)
    if erro:
        return erro

    serializer = RelatorioTemplateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    template = serializer.save(escola_id=escola_id, instituicao_id=instituicao_id)
    return Response(RelatorioTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_relatorio_template(request, template_id):
    try:
        template = RelatorioTemplate.objects.get(id=template_id)
    except RelatorioTemplate.DoesNotExist:
        return Response({'error': 'Template não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RelatorioTemplateSerializer(template).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_relatorio_template(request, template_id):
    if not _pode_gerenciar_geral(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        template = RelatorioTemplate.objects.get(id=template_id)
    except RelatorioTemplate.DoesNotExist:
        return Response({'error': 'Template não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = RelatorioTemplateSerializer(template, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# Relatorio
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_relatorios(request):
    relatorios = Relatorio.objects.all()
    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        relatorios = relatorios.filter(aluno_id=aluno_id)
    return Response(RelatorioSerializer(relatorios.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_relatorio(request):
    user = request.user
    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        aluno = Aluno.objects.get(id=aluno_id)
    except Aluno.DoesNotExist:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_gerenciar_geral(user) and not _professor_vinculado_turma(user, aluno.turma):
        return Response({'error': 'Você não está vinculado à turma desse aluno.'},
                         status=status.HTTP_403_FORBIDDEN)

    serializer = RelatorioSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    relatorio = serializer.save(
        aluno=aluno, escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(RelatorioSerializer(relatorio).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_relatorio(request, relatorio_id):
    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
    except Relatorio.DoesNotExist:
        return Response({'error': 'Relatório não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RelatorioSerializer(relatorio).data)


def _pode_editar_relatorio(user, relatorio):
    if _pode_gerenciar_geral(user):
        return True
    return _professor_vinculado_turma(user, relatorio.aluno.turma)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_relatorio(request, relatorio_id):
    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
    except Relatorio.DoesNotExist:
        return Response({'error': 'Relatório não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_relatorio(request.user, relatorio):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

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
    if not _pode_gerenciar_geral(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
    except Relatorio.DoesNotExist:
        return Response({'error': 'Relatório não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    relatorio.revisado_por = user
    relatorio.save(update_fields=['revisado_por', 'atualizado_em'])
    return Response(RelatorioSerializer(relatorio).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_relatorio(request, relatorio_id):
    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
    except Relatorio.DoesNotExist:
        return Response({'error': 'Relatório não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_relatorio(request.user, relatorio):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    relatorio.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)