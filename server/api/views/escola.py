"""Endpoints de Escola.

`Escola` não tem TenantManager (é o próprio tenant), então o recorte por
escopo é feito aqui: superadmin vê todas, admin as da própria instituição,
os demais só a própria escola. Criar/editar: superadmin ou admin.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_administrar, pode_ver_escola, resolver_instituicao_cadastro
from api.models import Escola
from api.serializers import EscolaSerializer
from api.tenancy import is_superadmin


def _escola_ou_erro(user, escola_id):
    """Retorna (escola, erro): 404 inexistente/malformada, 403 fora do escopo."""
    escola = buscar_no_escopo(Escola, escola_id)
    if escola is None:
        return None, Response({'error': 'Escola não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if not pode_ver_escola(user, escola):
        return None, Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    return escola, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_escolas(request):
    """
    Superadmin vê todas. Admin vê as da própria instituição.
    Demais níveis (coordenador, professor, especialista) veem só a própria escola.
    """
    user = request.user

    if is_superadmin(user):
        escolas = Escola.objects.all()
    elif user.nivel == 'admin':
        escolas = Escola.objects.filter(instituicao_id=user.instituicao_id) if user.instituicao_id else Escola.objects.none()
    else:
        escolas = Escola.objects.filter(id=user.escola_id) if user.escola_id else Escola.objects.none()

    return Response(EscolaSerializer(escolas.order_by('nome'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_escola(request):
    """Cria uma escola. Superadmin informa `instituicao` no body; admin usa sempre a própria."""
    user = request.user
    if not pode_administrar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    instituicao_id, erro = resolver_instituicao_cadastro(user, request.data)
    if erro:
        return erro

    serializer = EscolaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(instituicao_id=instituicao_id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_escola(request, escola_id):
    escola, erro = _escola_ou_erro(request.user, escola_id)
    if erro:
        return erro
    return Response(EscolaSerializer(escola).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_escola(request, escola_id):
    user = request.user
    if not pode_administrar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola, erro = _escola_ou_erro(user, escola_id)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = EscolaSerializer(escola, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)