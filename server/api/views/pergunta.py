"""Endpoints de Pergunta e PerguntaEspecialista.

Pergunta é um cadastro "oficial OU customizado": as oficiais (escola e
instituição nulas) valem para todas as escolas, sem exceção; cada escola pode
criar perguntas a mais. PerguntaEspecialista pertence sempre a uma escola.

O `campo_experiencia` de uma pergunta segue a mesma regra: precisa ser um
campo oficial ou da própria escola da pergunta (pergunta oficial → só campo
oficial). O serializer aceita qualquer id (`CampoPedagogico.todos`) para não
barrar os oficiais; o recorte é feito aqui, em `_campo_invalido`.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    SEM_ESCOLA_OFICIAL, buscar_no_escopo, buscar_oficial_ou_da_escola, buscar_visivel, dono_ou_gestao,
    eh_especialista, filtro_visiveis, pode_editar, pode_gerenciar, resolver_escopo_criacao,
)
from api.models import CampoPedagogico, Pergunta, PerguntaEspecialista
from api.serializers import PerguntaSerializer, PerguntaEspecialistaSerializer


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado():
    return Response({'error': 'Pergunta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)


def _campo_invalido(request, escola_id):
    """Se o body informa `campo_experiencia`, ele precisa ser oficial ou da
    escola `escola_id` (None = pergunta oficial → só campo oficial).
    Retorna `erro` ou None."""
    campo_id = request.data.get('campo_experiencia')
    if not campo_id:
        return None
    if buscar_oficial_ou_da_escola(CampoPedagogico, campo_id, escola_id) is None:
        return Response({'error': 'Campo de experiência não encontrado para esta escola.'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


def _salvar_edicao(request, obj, serializer_class):
    partial = request.method == 'PATCH'
    serializer = serializer_class(obj, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# Pergunta
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas(request):
    perguntas = Pergunta.todos.filter(filtro_visiveis(request.user))

    faixa_etaria = request.query_params.get('faixa_etaria')
    if faixa_etaria:
        perguntas = perguntas.filter(faixa_etaria=faixa_etaria)

    return Response(PerguntaSerializer(perguntas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_pergunta(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data, sem_escola=SEM_ESCOLA_OFICIAL)
    if erro:
        return erro

    erro = _campo_invalido(request, escola_id)
    if erro:
        return erro

    serializer = PerguntaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pergunta = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(PerguntaSerializer(pergunta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_pergunta(request, pergunta_id):
    pergunta = buscar_visivel(Pergunta, pergunta_id, request.user)
    if pergunta is None:
        return _nao_encontrado()
    return Response(PerguntaSerializer(pergunta).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_pergunta(request, pergunta_id):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    pergunta = buscar_visivel(Pergunta, pergunta_id, user)
    if pergunta is None:
        return _nao_encontrado()

    erro = pode_editar(user, pergunta)  # oficial: só superadmin
    if erro:
        return erro

    erro = _campo_invalido(request, pergunta.escola_id)
    if erro:
        return erro
    return _salvar_edicao(request, pergunta, PerguntaSerializer)


# ============================================================
# PerguntaEspecialista (sempre de uma escola; TenantManager)
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas_especialistas(request):
    perguntas = PerguntaEspecialista.objects.all().order_by('-criado_em')
    return Response(PerguntaEspecialistaSerializer(perguntas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_pergunta_especialista(request):
    user = request.user
    if not (eh_especialista(user) or pode_gerenciar(user)):
        return _sem_permissao()

    if user.escola_id is None or user.instituicao_id is None:
        return Response({'error': 'Usuário sem escola/instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)

    erro = _campo_invalido(request, user.escola_id)
    if erro:
        return erro

    serializer = PerguntaEspecialistaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pergunta = serializer.save(
        usuario_especialista=user, escola_id=user.escola_id, instituicao_id=user.instituicao_id,
    )
    return Response(PerguntaEspecialistaSerializer(pergunta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_pergunta_especialista(request, pergunta_id):
    pergunta = buscar_no_escopo(PerguntaEspecialista, pergunta_id)
    if pergunta is None:
        return _nao_encontrado()
    return Response(PerguntaEspecialistaSerializer(pergunta).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_pergunta_especialista(request, pergunta_id):
    pergunta = buscar_no_escopo(PerguntaEspecialista, pergunta_id)
    if pergunta is None:
        return _nao_encontrado()

    if not dono_ou_gestao(request.user, pergunta, campo_dono='usuario_especialista_id'):
        return _sem_permissao()

    erro = _campo_invalido(request, pergunta.escola_id)
    if erro:
        return erro
    return _salvar_edicao(request, pergunta, PerguntaEspecialistaSerializer)