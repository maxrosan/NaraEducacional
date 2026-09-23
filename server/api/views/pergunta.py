"""Endpoints de Pergunta e PerguntaEspecialista."""

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Pergunta, PerguntaEspecialista
from api.serializers import PerguntaSerializer, PerguntaEspecialistaSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas(request):
    user = request.user

    if _is_superadmin(user):
        perguntas = Pergunta.todos.all()
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            perguntas = Pergunta.todos.filter(escola__isnull=True)
        else:
            perguntas = Pergunta.todos.filter(
                Q(instituicao_id=user.instituicao_id) | Q(escola__isnull=True, instituicao__isnull=True),
            )
    else:
        if user.escola_id is None:
            perguntas = Pergunta.todos.filter(escola__isnull=True)
        else:
            perguntas = Pergunta.todos.filter(
                Q(escola_id=user.escola_id) | Q(escola__isnull=True),
            )

    faixa_etaria = request.query_params.get('faixa_etaria')
    if faixa_etaria:
        perguntas = perguntas.filter(faixa_etaria=faixa_etaria)

    return Response(PerguntaSerializer(perguntas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_pergunta(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    if _is_superadmin(user):
        escola_id = request.data.get('escola')
        instituicao_id = request.data.get('instituicao')
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
        escola_id = request.data.get('escola')
    else:  # coordenador
        if user.escola_id is None:
            return Response({'error': 'Usuário sem escola vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
        escola_id = user.escola_id

    serializer = PerguntaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pergunta = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(PerguntaSerializer(pergunta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_pergunta(request, pergunta_id):
    user = request.user
    try:
        pergunta = Pergunta.todos.get(id=pergunta_id)
    except Pergunta.DoesNotExist:
        return Response({'error': 'Pergunta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if pergunta.escola_id is not None and not _is_superadmin(user) \
            and str(pergunta.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    return Response(PerguntaSerializer(pergunta).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_pergunta(request, pergunta_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        pergunta = Pergunta.todos.get(id=pergunta_id)
    except Pergunta.DoesNotExist:
        return Response({'error': 'Pergunta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if pergunta.escola_id is None and not _is_superadmin(user):
        return Response({'error': 'Só superadmin pode editar perguntas oficiais.'}, status=status.HTTP_403_FORBIDDEN)
    if not _is_superadmin(user) and str(pergunta.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = PerguntaSerializer(pergunta, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas_especialistas(request):
    perguntas = PerguntaEspecialista.objects.all().order_by('-criado_em')
    return Response(PerguntaEspecialistaSerializer(perguntas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_pergunta_especialista(request):
    user = request.user
    if user.nivel not in ('especialista', 'professor_especialista') and not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    if user.escola_id is None or user.instituicao_id is None:
        return Response({'error': 'Usuário sem escola/instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = PerguntaEspecialistaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pergunta = serializer.save(
        usuario_especialista=user, escola_id=user.escola_id, instituicao_id=user.instituicao_id,
    )
    return Response(PerguntaEspecialistaSerializer(pergunta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_pergunta_especialista(request, pergunta_id):
    try:
        pergunta = PerguntaEspecialista.objects.get(id=pergunta_id)
    except PerguntaEspecialista.DoesNotExist:
        return Response({'error': 'Pergunta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(PerguntaEspecialistaSerializer(pergunta).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_pergunta_especialista(request, pergunta_id):
    user = request.user
    try:
        pergunta = PerguntaEspecialista.objects.get(id=pergunta_id)
    except PerguntaEspecialista.DoesNotExist:
        return Response({'error': 'Pergunta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_gerenciar(user) and pergunta.usuario_especialista_id != user.id:
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = PerguntaEspecialistaSerializer(pergunta, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)