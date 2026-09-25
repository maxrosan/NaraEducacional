"""Endpoints de Especialista.

Um especialista é da REDE (escola nula, atende todas as escolas da
instituição) ou de uma escola específica. Quem vê o quê:
  * superadmin: todos;
  * admin: todos da própria instituição;
  * demais: os da própria escola + os da rede.

O `TenantManager` do model não serve aqui: para quem tem escopo de escola ele
filtra `escola_id = <a dele>` e esconde justamente os da rede. Por isso a
busca usa `_base_manager` + o filtro explícito de `_visiveis`.
"""

from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import pode_administrar, resolver_instituicao_cadastro
from api.models import Especialista
from api.serializers import EspecialistaSerializer
from api.tenancy import is_superadmin


def _visiveis(user):
    qs = Especialista._base_manager.all()
    if is_superadmin(user):
        return qs
    if not user.instituicao_id:
        return qs.none()
    qs = qs.filter(instituicao_id=user.instituicao_id)
    if user.nivel == 'admin':
        return qs
    return qs.filter(Q(escola_id=user.escola_id) | Q(escola__isnull=True))


def _especialista_ou_404(user, especialista_id):
    """Retorna (especialista, erro). Fora do escopo ou id malformado → 404."""
    try:
        especialista = _visiveis(user).filter(pk=especialista_id).first()
    except (ValidationError, ValueError):
        especialista = None
    if especialista is None:
        return None, Response({'error': 'Especialista não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return especialista, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_especialistas(request):
    return Response(EspecialistaSerializer(_visiveis(request.user), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_especialista(request):
    """Cria um especialista. Superadmin informa `instituicao` no body; admin usa sempre a própria."""
    user = request.user
    if not pode_administrar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    instituicao_id, erro = resolver_instituicao_cadastro(user, request.data)
    if erro:
        return erro

    serializer = EspecialistaSerializer(data=request.data, context={'instituicao_id': instituicao_id})
    serializer.is_valid(raise_exception=True)
    serializer.save(instituicao_id=instituicao_id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_especialista(request, especialista_id):
    especialista, erro = _especialista_ou_404(request.user, especialista_id)
    if erro:
        return erro
    return Response(EspecialistaSerializer(especialista).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_especialista(request, especialista_id):
    user = request.user
    if not pode_administrar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    especialista, erro = _especialista_ou_404(user, especialista_id)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = EspecialistaSerializer(
        especialista, data=request.data, partial=partial,
        context={'instituicao_id': especialista.instituicao_id},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)