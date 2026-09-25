"""Endpoints de Instituicao (topo da hierarquia multi-tenant).

* listar/criar: só superadmin;
* detalhe: superadmin, ou qualquer usuário da própria instituição;
* editar: superadmin, ou o ADMIN da própria instituição — e o admin não mexe
  em `ativa` (ativar/desativar uma rede é decisão da plataforma).
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo
from api.models import Instituicao
from api.serializers import InstituicaoSerializer
from api.tenancy import is_superadmin

# Campos que só o superadmin altera.
CAMPOS_SO_SUPERADMIN = ('ativa',)


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _instituicao_ou_erro(user, instituicao_id, editar=False):
    """Retorna (instituicao, erro). Checa a permissão ANTES de buscar, para não
    revelar se o id de outra rede existe."""
    if not is_superadmin(user):
        if str(user.instituicao_id) != str(instituicao_id):
            return None, _sem_permissao()
        if editar and user.nivel != 'admin':
            return None, _sem_permissao()

    instituicao = buscar_no_escopo(Instituicao, instituicao_id)
    if instituicao is None:
        return None, Response({'error': 'Instituição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return instituicao, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_instituicoes(request):
    """Lista todas as instituições. Só superadmin."""
    if not is_superadmin(request.user):
        return _sem_permissao()

    instituicoes = Instituicao.objects.all().order_by('nome')
    return Response(InstituicaoSerializer(instituicoes, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_instituicao(request):
    """Cria uma nova instituição. Só superadmin."""
    if not is_superadmin(request.user):
        return _sem_permissao()

    serializer = InstituicaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_instituicao(request, instituicao_id):
    """Superadmin vê qualquer uma; os demais, só a própria."""
    instituicao, erro = _instituicao_ou_erro(request.user, instituicao_id)
    if erro:
        return erro
    return Response(InstituicaoSerializer(instituicao).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_instituicao(request, instituicao_id):
    """Superadmin edita qualquer uma; admin só a própria, sem os CAMPOS_SO_SUPERADMIN."""
    user = request.user
    instituicao, erro = _instituicao_ou_erro(user, instituicao_id, editar=True)
    if erro:
        return erro

    data = request.data
    if not is_superadmin(user):
        data = request.data.copy()
        for campo in CAMPOS_SO_SUPERADMIN:
            data.pop(campo, None)

    partial = request.method == 'PATCH'
    serializer = InstituicaoSerializer(instituicao, data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)