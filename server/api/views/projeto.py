"""Endpoints de Projeto."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import resolver_escopo_criacao
from api.models import Projeto
from api.serializers import ProjetoSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_projetos(request):
    """Já filtrado pelo TenantManager."""
    projetos = Projeto.objects.all().order_by('-criado_em')
    return Response(ProjetoSerializer(projetos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_projeto(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    serializer = ProjetoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    projeto = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(ProjetoSerializer(projeto).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_projeto(request, projeto_id):
    try:
        projeto = Projeto.objects.get(id=projeto_id)
    except Projeto.DoesNotExist:
        return Response({'error': 'Projeto não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ProjetoSerializer(projeto).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_projeto(request, projeto_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        projeto = Projeto.objects.get(id=projeto_id)
    except Projeto.DoesNotExist:
        return Response({'error': 'Projeto não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = ProjetoSerializer(projeto, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)