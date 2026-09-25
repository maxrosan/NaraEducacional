"""Endpoints de Usuario."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar, validar_vinculos_usuario
from api.models import Usuario
from api.serializers import UsuarioSerializer, UsuarioWriteSerializer
from api.tenancy import is_superadmin

# Papéis internos do NARA — sem vínculo com instituição/escola.
# Nem admin nem coordenador podem atribuir/criar usuários com esses níveis.
NIVEIS_SISTEMA = {'superadmin', 'vendedor', 'suporte'}

# O que um coordenador pode criar dentro da própria escola — e, pelo mesmo
# critério, os únicos usuários (além de si mesmo) que ele pode editar.
NIVEIS_QUE_COORDENADOR_CRIA = {
    'professor_infantil', 'professor_fundamental', 'professor_especialista', 'especialista',
}


def _sem_permissao(mensagem='Sem permissão.'):
    return Response({'error': mensagem}, status=status.HTTP_403_FORBIDDEN)


def _nivel_permitido(user, nivel, obrigatorio=False) -> Response | None:
    """Quem pode dar qual nível (na criação e na edição). None = permitido.

    `obrigatorio=True` (criação): coordenador precisa informar o nível — sem
    isso o usuário nasceria com o default do model, fora da lista permitida.
    """
    if is_superadmin(user):
        return None
    if not nivel:
        if obrigatorio and user.nivel == 'coordenador':
            return _sem_permissao(
                f'Coordenador só pode criar: {", ".join(sorted(NIVEIS_QUE_COORDENADOR_CRIA))}.'
            )
        return None
    if nivel in NIVEIS_SISTEMA:
        return _sem_permissao(f'Você não pode atribuir o nível "{nivel}".')
    if user.nivel == 'coordenador' and nivel not in NIVEIS_QUE_COORDENADOR_CRIA:
        return _sem_permissao(
            f'Coordenador só pode atribuir: {", ".join(sorted(NIVEIS_QUE_COORDENADOR_CRIA))}.'
        )
    return None


def _pode_ver(user, alvo) -> bool:
    """Ver outro usuário. O TenantManager já limita a busca ao escopo; aqui
    entra a regra por papel (professor não vê colegas)."""
    if is_superadmin(user) or user.id == alvo.id:
        return True
    if user.nivel == 'admin':
        return user.instituicao_id is not None and alvo.instituicao_id == user.instituicao_id
    if user.nivel == 'coordenador':
        return user.escola_id is not None and alvo.escola_id == user.escola_id
    return False


def _pode_editar(user, alvo) -> bool:
    """Editar outro usuário (dados, e-mail, senha). Além de poder vê-lo:
    ninguém além do superadmin mexe em usuário de sistema, e coordenador só
    edita os níveis que ele mesmo pode criar — senão trocaria e-mail/senha de
    um admin ou de outro coordenador da escola e assumiria a conta."""
    if is_superadmin(user) or user.id == alvo.id:
        return True
    if not (pode_gerenciar(user) and _pode_ver(user, alvo)):
        return False
    if alvo.nivel in NIVEIS_SISTEMA:
        return False
    if user.nivel == 'coordenador' and alvo.nivel not in NIVEIS_QUE_COORDENADOR_CRIA:
        return False
    return True


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_usuarios(request):
    """Superadmin vê todos. Admin vê os da própria instituição. Coordenador vê os da própria escola.

    O recorte por instituição/escola é do TenantManager (usuário sem o vínculo
    exigido recebe lista vazia).
    """
    if not pode_gerenciar(request.user):
        return _sem_permissao('Sem permissão. Use /api/me/ para ver seus próprios dados.')

    usuarios = Usuario.objects.all().order_by('nome')
    return Response(UsuarioSerializer(usuarios, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_usuario(request):
    """Cria um usuário, respeitando quem pode criar quem (ver NIVEIS_SISTEMA / NIVEIS_QUE_COORDENADOR_CRIA)."""
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    if user.nivel == 'admin' and user.instituicao_id is None:
        return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
    if user.nivel == 'coordenador' and user.escola_id is None:
        return Response({'error': 'Usuário sem escola vinculada.'}, status=status.HTTP_400_BAD_REQUEST)

    erro = _nivel_permitido(user, request.data.get('nivel'), obrigatorio=True)
    if erro:
        return erro

    # Mesma regra da edição: escola/instituição/especialista dentro do escopo
    # de quem cria, e escola sempre consistente com a instituição.
    data = request.data.copy()
    erro = validar_vinculos_usuario(user, data)
    if erro:
        return erro

    serializer = UsuarioWriteSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    usuario = serializer.save()
    return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_usuario(request, usuario_id):
    alvo = buscar_no_escopo(Usuario, usuario_id)
    if alvo is None:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_ver(request.user, alvo):
        return _sem_permissao()

    return Response(UsuarioSerializer(alvo).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_usuario(request, usuario_id):
    user = request.user
    alvo = buscar_no_escopo(Usuario, usuario_id)
    if alvo is None:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar(user, alvo):
        return _sem_permissao()
    is_self = user.id == alvo.id

    data = request.data.copy()

    # Ninguém edita o próprio nivel/instituicao/escola por essa rota — evita
    # auto-promoção. Superadmin pode mudar de qualquer um.
    if is_self and not is_superadmin(user):
        data.pop('nivel', None)
        data.pop('instituicao', None)
        data.pop('escola', None)
    else:
        erro = _nivel_permitido(user, data.get('nivel'))
        if erro:
            return erro

    # Antes só a auto-edição era travada: um admin podia mover OUTRO usuário
    # para outra rede (inclusive como admin, com senha nova).
    erro = validar_vinculos_usuario(user, data, alvo=alvo)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = UsuarioWriteSerializer(alvo, data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    usuario = serializer.save()
    return Response(UsuarioSerializer(usuario).data)