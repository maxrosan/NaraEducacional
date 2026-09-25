"""Endpoints de Turma."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import resolver_escopo_criacao
from api.models import Turma, Usuario, UsuarioTurma
from api.serializers import TurmaSerializer, UsuarioTurmaSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_turmas(request):
    """
    Já vem filtrado pelo TenantManager: admin vê as da instituição,
    demais níveis vêem as da própria escola, superadmin vê tudo.
    """
    turmas = Turma.objects.all().order_by('nome')
    return Response(TurmaSerializer(turmas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_turma(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    serializer = TurmaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    turma = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(TurmaSerializer(turma).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_turma(request, turma_id):
    try:
        turma = Turma.objects.get(id=turma_id)
    except Turma.DoesNotExist:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(TurmaSerializer(turma).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_turma(request, turma_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        turma = Turma.objects.get(id=turma_id)
    except Turma.DoesNotExist:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = TurmaSerializer(turma, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


def _turma_do_escopo(user, turma_id):
    """Busca a turma já respeitando o escopo do TenantManager (404 se fora do escopo)."""
    try:
        return Turma.objects.get(id=turma_id)
    except Turma.DoesNotExist:
        return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_professores_turma(request, turma_id):
    turma = _turma_do_escopo(request.user, turma_id)
    if turma is None:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    vinculos = UsuarioTurma.objects.filter(turma=turma).select_related('usuario')
    return Response(UsuarioTurmaSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_professor_turma(request, turma_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma = _turma_do_escopo(user, turma_id)
    if turma is None:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    usuario_id = request.data.get('usuario')
    if not usuario_id:
        return Response({'error': 'Campo usuario é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if str(usuario.escola_id) != str(turma.escola_id):
        return Response({'error': 'O usuário precisa pertencer à mesma escola da turma.'},
                         status=status.HTTP_400_BAD_REQUEST)

    vinculo, criado = UsuarioTurma.objects.get_or_create(usuario=usuario, turma=turma)
    status_code = status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    return Response(UsuarioTurmaSerializer(vinculo).data, status=status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_professor_turma(request, turma_id, usuario_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma = _turma_do_escopo(user, turma_id)
    if turma is None:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    deletados, _ = UsuarioTurma.objects.filter(turma=turma, usuario_id=usuario_id).delete()
    if not deletados:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)