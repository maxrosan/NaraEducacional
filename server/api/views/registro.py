"""Endpoints de RegistroEscrita e RegistroDesenho (RegistroLeitura fica em views/leitura.py)."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import RegistroEscrita, RegistroDesenho, Aluno, UsuarioTurma
from api.serializers import RegistroEscritaSerializer, RegistroDesenhoSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar_geral(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


def _professor_vinculado_turma(usuario, turma):
    return UsuarioTurma.objects.filter(usuario=usuario, turma=turma).exists()


def _pode_editar_registro(user, registro):
    if _pode_gerenciar_geral(user):
        return True
    return registro.professor_id == user.id


def _resolver_aluno_para_criacao(request, user):
    """Valida o aluno informado e retorna (aluno, erro). Comum às 3 entidades."""
    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return None, Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        aluno = Aluno.objects.get(id=aluno_id)  # já respeita o escopo do TenantManager
    except Aluno.DoesNotExist:
        return None, Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_gerenciar_geral(user) and not _professor_vinculado_turma(user, aluno.turma):
        return None, Response({'error': 'Você não está vinculado à turma desse aluno.'},
                               status=status.HTTP_403_FORBIDDEN)

    return aluno, None


# ============================================================
# RegistroEscrita
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_escrita(request):
    registros = RegistroEscrita.objects.all()
    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        registros = registros.filter(aluno_id=aluno_id)
    return Response(RegistroEscritaSerializer(registros.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_registro_escrita(request):
    aluno, erro = _resolver_aluno_para_criacao(request, request.user)
    if erro:
        return erro

    serializer = RegistroEscritaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    registro = serializer.save(
        aluno=aluno, turma=aluno.turma, professor=request.user,
        escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(RegistroEscritaSerializer(registro).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_registro_escrita(request, registro_id):
    try:
        registro = RegistroEscrita.objects.get(id=registro_id)
    except RegistroEscrita.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RegistroEscritaSerializer(registro).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_registro_escrita(request, registro_id):
    try:
        registro = RegistroEscrita.objects.get(id=registro_id)
    except RegistroEscrita.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar_registro(request.user, registro):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = RegistroEscritaSerializer(registro, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_escrita(request, registro_id):
    try:
        registro = RegistroEscrita.objects.get(id=registro_id)
    except RegistroEscrita.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar_registro(request.user, registro):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    registro.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# RegistroDesenho
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_desenho(request):
    registros = RegistroDesenho.objects.all()
    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        registros = registros.filter(aluno_id=aluno_id)
    return Response(RegistroDesenhoSerializer(registros.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_registro_desenho(request):
    aluno, erro = _resolver_aluno_para_criacao(request, request.user)
    if erro:
        return erro

    serializer = RegistroDesenhoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    registro = serializer.save(
        aluno=aluno, turma=aluno.turma, professor=request.user,
        escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(RegistroDesenhoSerializer(registro).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_registro_desenho(request, registro_id):
    try:
        registro = RegistroDesenho.objects.get(id=registro_id)
    except RegistroDesenho.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RegistroDesenhoSerializer(registro).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_registro_desenho(request, registro_id):
    try:
        registro = RegistroDesenho.objects.get(id=registro_id)
    except RegistroDesenho.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar_registro(request.user, registro):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = RegistroDesenhoSerializer(registro, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_desenho(request, registro_id):
    try:
        registro = RegistroDesenho.objects.get(id=registro_id)
    except RegistroDesenho.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar_registro(request.user, registro):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    registro.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)