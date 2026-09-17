"""Endpoints de Usuario."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Usuario, Escola
from api.serializers import UsuarioSerializer, UsuarioWriteSerializer

# Papéis internos do NARA — sem vínculo com instituição/escola.
# Nem admin nem coordenador podem atribuir/criar usuários com esses níveis.
NIVEIS_SISTEMA = {'superadmin', 'vendedor', 'suporte'}

# O que um coordenador pode criar dentro da própria escola.
NIVEIS_QUE_COORDENADOR_CRIA = {
    'professor_infantil', 'professor_fundamental', 'professor_especialista', 'especialista',
}


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_usuarios(request):
    """Superadmin vê todos. Admin vê os da própria instituição. Coordenador vê os da própria escola."""
    user = request.user

    if _is_superadmin(user):
        usuarios = Usuario.objects.all()
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response([])
        usuarios = Usuario.objects.filter(instituicao_id=user.instituicao_id)
    elif user.nivel == 'coordenador':
        if user.escola_id is None:
            return Response([])
        usuarios = Usuario.objects.filter(escola_id=user.escola_id)
    else:
        return Response({'error': 'Sem permissão. Use /api/me/ para ver seus próprios dados.'},
                         status=status.HTTP_403_FORBIDDEN)

    return Response(UsuarioSerializer(usuarios.order_by('nome'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_usuario(request):
    """Cria um usuário, respeitando quem pode criar quem (ver NIVEIS_SISTEMA / NIVEIS_QUE_COORDENADOR_CRIA)."""
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    nivel_alvo = request.data.get('nivel')
    data = dict(request.data)

    if _is_superadmin(user):
        pass  # superadmin: sem restrição de nivel/instituicao/escola (mas ainda precisa vir no body)

    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        if nivel_alvo in NIVEIS_SISTEMA:
            return Response(
                {'error': f'Admin não pode criar usuários de nível "{nivel_alvo}".'},
                status=status.HTTP_403_FORBIDDEN,
            )
        data['instituicao'] = user.instituicao_id
        escola_id = data.get('escola')
        if escola_id and not Escola.objects.filter(id=escola_id, instituicao_id=user.instituicao_id).exists():
            return Response({'error': 'Escola informada não pertence à sua instituição.'},
                             status=status.HTTP_400_BAD_REQUEST)

    elif user.nivel == 'coordenador':
        if user.escola_id is None:
            return Response({'error': 'Usuário sem escola vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        if nivel_alvo not in NIVEIS_QUE_COORDENADOR_CRIA:
            return Response(
                {'error': f'Coordenador só pode criar: {", ".join(sorted(NIVEIS_QUE_COORDENADOR_CRIA))}.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        data['instituicao'] = user.instituicao_id
        data['escola'] = user.escola_id

    serializer = UsuarioWriteSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    usuario = serializer.save()
    return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)


def _pode_acessar(user, alvo):
    if _is_superadmin(user) or user.id == alvo.id:
        return True
    if user.nivel == 'admin':
        return str(alvo.instituicao_id) == str(user.instituicao_id)
    if user.nivel == 'coordenador':
        return str(alvo.escola_id) == str(user.escola_id)
    return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_usuario(request, usuario_id):
    try:
        alvo = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_acessar(request.user, alvo):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    return Response(UsuarioSerializer(alvo).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_usuario(request, usuario_id):
    user = request.user
    try:
        alvo = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    is_self = user.id == alvo.id
    if not is_self and not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    if not is_self and not _pode_acessar(user, alvo):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    data = dict(request.data)
    novo_nivel = data.get('nivel')

    # Ninguém edita o próprio nivel/instituicao/escola por essa rota — evita
    # auto-promoção. Superadmin pode mudar de qualquer um.
    if is_self and not _is_superadmin(user):
        data.pop('nivel', None)
        data.pop('instituicao', None)
        data.pop('escola', None)
    elif not _is_superadmin(user) and novo_nivel in NIVEIS_SISTEMA:
        return Response({'error': f'Você não pode atribuir o nível "{novo_nivel}".'},
                         status=status.HTTP_403_FORBIDDEN)
    elif not _is_superadmin(user) and user.nivel == 'coordenador' and novo_nivel and novo_nivel not in NIVEIS_QUE_COORDENADOR_CRIA:
        return Response({'error': f'Coordenador só pode atribuir: {", ".join(sorted(NIVEIS_QUE_COORDENADOR_CRIA))}.'},
                         status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = UsuarioWriteSerializer(alvo, data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    usuario = serializer.save()
    return Response(UsuarioSerializer(usuario).data)