"""Endpoints de Disciplina e do vínculo Usuario-Disciplina."""

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar, resolver_escopo_criacao
from api.models import Disciplina, UsuarioDisciplina, Usuario
from api.serializers import DisciplinaSerializer, UsuarioDisciplinaSerializer

# Regra herdada do legado: só professor_fundamental pode ser vinculado a
# disciplinas (educação infantil não trabalha com disciplinas separadas).
NIVEL_COM_DISCIPLINA = 'professor_fundamental'


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _disciplina_ou_404(disciplina_id):
    """Retorna (disciplina, erro)."""
    disciplina = buscar_no_escopo(Disciplina, disciplina_id)
    if disciplina is None:
        return None, Response({'error': 'Disciplina não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return disciplina, None


def _nome_duplicado(escola_id, nome, ignorar_id=None):
    """Há `UniqueConstraint(escola, nome)`, mas o serializer não a valida
    (escola é read-only) — sem esta checagem, nome repetido vira 500."""
    if not nome:
        return None
    qs = Disciplina._base_manager.filter(escola_id=escola_id, nome=nome)
    if ignorar_id:
        qs = qs.exclude(pk=ignorar_id)
    if qs.exists():
        return Response({'error': 'Já existe uma disciplina com esse nome nesta escola.'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


# ============================================================
# Disciplina
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_disciplinas(request):
    """Já filtrado pelo TenantManager (escola/instituição do usuário)."""
    disciplinas = Disciplina.objects.all().order_by('nome')
    return Response(DisciplinaSerializer(disciplinas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_disciplina(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    erro = _nome_duplicado(escola_id, request.data.get('nome'))
    if erro:
        return erro

    serializer = DisciplinaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    disciplina = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(DisciplinaSerializer(disciplina).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_disciplina(request, disciplina_id):
    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro
    return Response(DisciplinaSerializer(disciplina).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_disciplina(request, disciplina_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    erro = _nome_duplicado(disciplina.escola_id, request.data.get('nome'), ignorar_id=disciplina.id)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = DisciplinaSerializer(disciplina, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# Vínculo usuário ↔ disciplina
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_professores_disciplina(request, disciplina_id):
    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    vinculos = UsuarioDisciplina.objects.filter(disciplina=disciplina).select_related('usuario')
    return Response(UsuarioDisciplinaSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_usuario_disciplina(request, disciplina_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    usuario_id = request.data.get('usuario')
    if not usuario_id:
        return Response({'error': 'Campo usuario é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    usuario = buscar_no_escopo(Usuario, usuario_id)
    if usuario is None:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if usuario.nivel != NIVEL_COM_DISCIPLINA:
        return Response(
            {'error': f'Apenas usuários com nível {NIVEL_COM_DISCIPLINA} podem ser vinculados a disciplinas.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if usuario.escola_id != disciplina.escola_id:
        return Response({'error': 'O usuário precisa pertencer à mesma escola da disciplina.'},
                        status=status.HTTP_400_BAD_REQUEST)

    vinculo, criado = UsuarioDisciplina.objects.get_or_create(
        usuario=usuario, disciplina=disciplina,
        defaults={'escola_id': disciplina.escola_id, 'instituicao_id': disciplina.instituicao_id},
    )
    status_code = status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    return Response(UsuarioDisciplinaSerializer(vinculo).data, status=status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_usuario_disciplina(request, disciplina_id, usuario_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    try:
        deletados, _ = UsuarioDisciplina.objects.filter(disciplina=disciplina, usuario_id=usuario_id).delete()
    except (ValidationError, ValueError):  # usuario_id malformado
        deletados = 0
    if not deletados:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)