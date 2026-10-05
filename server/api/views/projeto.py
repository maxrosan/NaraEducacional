"""Endpoints de Projeto."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar, resolver_escopo_criacao
from api.models import Projeto
from api.serializers import ProjetoSerializer


def _projeto_ou_404(projeto_id):
    """Retorna (projeto, erro)."""
    projeto = buscar_no_escopo(Projeto, projeto_id)
    if projeto is None:
        return None, Response({'error': 'Projeto não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return projeto, None


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
    if not pode_gerenciar(user):
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
    projeto, erro = _projeto_ou_404(projeto_id)
    if erro:
        return erro
    return Response(ProjetoSerializer(projeto).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_projeto(request, projeto_id):
    if not pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    projeto, erro = _projeto_ou_404(projeto_id)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = ProjetoSerializer(projeto, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)