"""Endpoints de Disciplina e do vínculo Usuario-Disciplina."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import resolver_escopo_criacao
from api.models import Disciplina, UsuarioDisciplina, Usuario
from api.serializers import DisciplinaSerializer, UsuarioDisciplinaSerializer
from api.escopo import pode_gerenciar as _pode_gerenciar


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
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    serializer = DisciplinaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    disciplina = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(DisciplinaSerializer(disciplina).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_disciplina(request, disciplina_id):
    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
    except Disciplina.DoesNotExist:
        return Response({'error': 'Disciplina não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(DisciplinaSerializer(disciplina).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_disciplina(request, disciplina_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
    except Disciplina.DoesNotExist:
        return Response({'error': 'Disciplina não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = DisciplinaSerializer(disciplina, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_professores_disciplina(request, disciplina_id):
    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
    except Disciplina.DoesNotExist:
        return Response({'error': 'Disciplina não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    vinculos = UsuarioDisciplina.objects.filter(disciplina=disciplina).select_related('usuario')
    return Response(UsuarioDisciplinaSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_usuario_disciplina(request, disciplina_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
    except Disciplina.DoesNotExist:
        return Response({'error': 'Disciplina não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    usuario_id = request.data.get('usuario')
    if not usuario_id:
        return Response({'error': 'Campo usuario é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    # Regra herdada do legado: só professor_fundamental pode ser vinculado a
    # disciplinas (educação infantil não trabalha com disciplinas separadas).
    if usuario.nivel != 'professor_fundamental':
        return Response(
            {'error': 'Apenas usuários com nível professor_fundamental podem ser vinculados a disciplinas.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if str(usuario.escola_id) != str(disciplina.escola_id):
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
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
    except Disciplina.DoesNotExist:
        return Response({'error': 'Disciplina não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    deletados, _ = UsuarioDisciplina.objects.filter(disciplina=disciplina, usuario_id=usuario_id).delete()
    if not deletados:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)