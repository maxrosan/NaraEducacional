"""Endpoints de PromptCategoria e PromptTemplate (biblioteca de prompts de IA)."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import PromptCategoria, PromptTemplate
from api.serializers import PromptCategoriaSerializer, PromptTemplateSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar_biblioteca(user):
    """Só superadmin mexe na taxonomia (categorias) — é compartilhada por
    todas as instituições."""
    return _is_superadmin(user)


def _pode_personalizar(user):
    """admin/coordenador/superadmin podem personalizar o template da
    própria instituição."""
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_prompt_categorias(request):
    """?todas=1 inclui categorias inativas (tela de admin)."""
    if not _pode_personalizar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    todas = request.GET.get('todas') == '1'
    qs = PromptCategoria.objects.prefetch_related('templates').order_by('titulo')
    if not todas:
        qs = qs.filter(ativo=True)

    data = PromptCategoriaSerializer(
        qs, many=True, context={'instituicao_id': request.user.instituicao_id},
    ).data
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def salvar_prompt_template(request):
    """
    Body: {categoria, prompt_global, personalizado}.

    Regras herdadas do legado:
    - 1 PromptTemplate por categoria (por ora — preparado pra virar N:1 por
      instituição quando fizer sentido); nunca duplica via get_or_create,
      sempre reaproveita o registro mais recente da categoria.
    - prompt_global sempre grava o valor recebido, independente de quem
      está logado (o frontend manda os dois campos juntos).
    - personalizado grava o valor recebido; a instituicao do registro só é
      sobrescrita quando o usuário logado tiver uma (evita apagar a
      instituição de um registro já personalizado por outra).
    """
    user = request.user
    if not _pode_personalizar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    categoria_id = request.data.get('categoria')
    if not categoria_id:
        return Response({'error': 'categoria é obrigatória.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        categoria = PromptCategoria.objects.get(id=categoria_id, ativo=True)
    except PromptCategoria.DoesNotExist:
        return Response({'error': 'Categoria não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    template = PromptTemplate.objects.filter(categoria=categoria).order_by('-criado_em').first()
    if template is None:
        template = PromptTemplate.objects.create(categoria=categoria, prompt_global='', personalizado='')

    template.prompt_global = request.data.get('prompt_global', '')
    template.personalizado = request.data.get('personalizado', '')
    if user.instituicao_id is not None:
        template.instituicao_id = user.instituicao_id
        template.escola_id = user.escola_id
    template.save()

    return Response(PromptTemplateSerializer(template).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_prompt_categoria(request):
    if not _pode_gerenciar_biblioteca(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    titulo = (request.data.get('titulo') or '').strip()
    if not titulo:
        return Response({'error': 'titulo é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
    if PromptCategoria.objects.filter(titulo__iexact=titulo).exists():
        return Response({'error': 'Já existe uma categoria com este título.'}, status=status.HTTP_400_BAD_REQUEST)

    categoria = PromptCategoria.objects.create(titulo=titulo, ativo=request.data.get('ativo', True))
    return Response(PromptCategoriaSerializer(categoria, context={}).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_prompt_categoria(request, categoria_id):
    if not _pode_gerenciar_biblioteca(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        categoria = PromptCategoria.objects.get(id=categoria_id)
    except PromptCategoria.DoesNotExist:
        return Response({'error': 'Categoria não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if 'titulo' in request.data:
        titulo = (request.data['titulo'] or '').strip()
        if not titulo:
            return Response({'error': 'titulo não pode ser vazio.'}, status=status.HTTP_400_BAD_REQUEST)
        categoria.titulo = titulo
    if 'ativo' in request.data:
        categoria.ativo = bool(request.data['ativo'])
    categoria.save()

    return Response(PromptCategoriaSerializer(categoria, context={}).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_prompt_categoria(request, categoria_id):
    if not _pode_gerenciar_biblioteca(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        categoria = PromptCategoria.objects.get(id=categoria_id)
    except PromptCategoria.DoesNotExist:
        return Response({'error': 'Categoria não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    categoria.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)