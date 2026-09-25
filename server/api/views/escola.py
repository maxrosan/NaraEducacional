"""Endpoints de Escola."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Escola
from api.serializers import EscolaSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar(user):
    """Só superadmin e admin podem criar/editar escolas."""
    return _is_superadmin(user) or user.nivel == 'admin'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_escolas(request):
    """
    Superadmin vê todas. Admin vê as da própria instituição.
    Demais níveis (coordenador, professor, especialista) veem só a própria escola.
    """
    user = request.user

    if _is_superadmin(user):
        escolas = Escola.objects.all()
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response([])
        escolas = Escola.objects.filter(instituicao_id=user.instituicao_id)
    else:
        if user.escola_id is None:
            return Response([])
        escolas = Escola.objects.filter(id=user.escola_id)

    return Response(EscolaSerializer(escolas.order_by('nome'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_escola(request):
    """Cria uma escola. Superadmin precisa informar instituicao_id no body; admin usa sempre a própria."""
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    if user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
    else:
        instituicao_id = request.data.get('instituicao')
        if not instituicao_id:
            return Response({'error': 'Campo instituicao é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = EscolaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(instituicao_id=instituicao_id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_escola(request, escola_id):
    user = request.user
    try:
        escola = Escola.objects.get(id=escola_id)
    except Escola.DoesNotExist:
        return Response({'error': 'Escola não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if _is_superadmin(user):
        pass
    elif user.nivel == 'admin':
        if str(escola.instituicao_id) != str(user.instituicao_id):
            return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    else:
        if str(escola.id) != str(user.escola_id):
            return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    return Response(EscolaSerializer(escola).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_escola(request, escola_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        escola = Escola.objects.get(id=escola_id)
    except Escola.DoesNotExist:
        return Response({'error': 'Escola não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _is_superadmin(user) and str(escola.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = EscolaSerializer(escola, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)