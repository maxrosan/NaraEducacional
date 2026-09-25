"""Endpoints de Pergunta e PerguntaEspecialista."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import SEM_ESCOLA_OFICIAL, filtro_visiveis, pode_editar, pode_ver, resolver_escopo_criacao
from api.models import Pergunta, PerguntaEspecialista
from api.serializers import PerguntaSerializer, PerguntaEspecialistaSerializer
from api.escopo import pode_gerenciar as _pode_gerenciar


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas(request):
    user = request.user

    perguntas = Pergunta.todos.filter(filtro_visiveis(user))

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

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data, sem_escola=SEM_ESCOLA_OFICIAL)
    if erro:
        return erro

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

    if not pode_ver(user, pergunta):
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

    erro = pode_editar(user, pergunta)
    if erro:
        return erro

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