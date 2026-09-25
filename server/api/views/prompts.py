"""Endpoints de PromptCategoria e PromptTemplate (biblioteca de prompts de IA).

Modelo de dados (o mesmo que `services/prompt_resolver.resolver_prompt` lê):

* **Global** — 1 PromptTemplate por categoria com `instituicao` e `escola`
  nulas; o texto está em `prompt_global`. Vale para todas as instituições.
  Só o superadmin edita.
* **Personalizado** — 1 PromptTemplate por (categoria, instituição), com
  `escola` nula (vale para a rede inteira); o texto está em `personalizado`.
  Quando preenchido, tem prioridade sobre o global PARA AQUELA instituição.
  Admin/coordenador editam o da própria instituição.

Todas as consultas usam `PromptTemplate._base_manager`: o TenantManager
esconderia o global (sem escola) de quem tem escopo de escola.
"""

from django.db.models import Prefetch, Q
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar
from api.models import PromptCategoria, PromptTemplate
from api.serializers import PromptCategoriaSerializer, PromptTemplateSerializer
from api.tenancy import is_superadmin

_para_bool = serializers.BooleanField().to_internal_value  # "false" → False (bool("false") seria True)


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _categoria_ou_404(categoria_id, **filtros):
    """Retorna (categoria, erro). PromptCategoria é global (sem tenant)."""
    categoria = buscar_no_escopo(PromptCategoria, categoria_id)
    if categoria is None or any(getattr(categoria, k) != v for k, v in filtros.items()):
        return None, Response({'error': 'Categoria não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return categoria, None


def _titulo_invalido(titulo, ignorar_id=None):
    """Título obrigatório e único (o resolver localiza a categoria pelo título)."""
    if not titulo:
        return Response({'error': 'titulo é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
    qs = PromptCategoria.objects.filter(titulo__iexact=titulo)
    if ignorar_id:
        qs = qs.exclude(pk=ignorar_id)
    if qs.exists():
        return Response({'error': 'Já existe uma categoria com este título.'}, status=status.HTTP_400_BAD_REQUEST)
    return None


def _template_de(categoria, instituicao_id, criar=False):
    """Template mais recente da categoria para a instituição (None = global)."""
    tpl = (
        PromptTemplate._base_manager
        .filter(categoria=categoria, instituicao_id=instituicao_id)
        .order_by('-criado_em')
        .first()
    )
    if tpl is None and criar:
        tpl = PromptTemplate._base_manager.create(
            categoria=categoria, instituicao_id=instituicao_id, escola_id=None,
            prompt_global='', personalizado='',
        )
    return tpl


# ============================================================
# Templates
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_prompt_categorias(request):
    """?todas=1 inclui categorias inativas (tela de admin)."""
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    # Só o global e o da instituição do usuário — o serializer não precisa
    # (nem deve) receber os personalizados das outras redes.
    visiveis = Q(instituicao__isnull=True)
    if user.instituicao_id:
        visiveis |= Q(instituicao_id=user.instituicao_id)

    qs = PromptCategoria.objects.prefetch_related(
        Prefetch('templates', queryset=PromptTemplate._base_manager.filter(visiveis).order_by('-criado_em')),
    ).order_by('titulo')
    if request.GET.get('todas') != '1':
        qs = qs.filter(ativo=True)

    data = PromptCategoriaSerializer(qs, many=True, context={'instituicao_id': user.instituicao_id}).data
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def salvar_prompt_template(request):
    """
    Body: {categoria, prompt_global, personalizado}.

    O frontend manda os dois textos juntos. Cada um vai para o SEU registro:
    * `prompt_global` → template global da categoria — só se quem salva é
      superadmin (dos demais, o campo é ignorado);
    * `personalizado` → template da instituição do usuário (se ele tiver uma).

    A resposta mantém o formato de antes (um PromptTemplate), com o
    `prompt_global` sempre vindo do registro global.
    """
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    categoria_id = request.data.get('categoria')
    if not categoria_id:
        return Response({'error': 'categoria é obrigatória.'}, status=status.HTTP_400_BAD_REQUEST)

    categoria, erro = _categoria_ou_404(categoria_id, ativo=True)
    if erro:
        return erro

    global_tpl = _template_de(categoria, None)
    if is_superadmin(user) and 'prompt_global' in request.data:
        global_tpl = global_tpl or _template_de(categoria, None, criar=True)
        global_tpl.prompt_global = request.data.get('prompt_global') or ''
        global_tpl.save(update_fields=['prompt_global', 'atualizado_em'])

    proprio_tpl = None
    if user.instituicao_id and 'personalizado' in request.data:
        proprio_tpl = _template_de(categoria, user.instituicao_id, criar=True)
        proprio_tpl.personalizado = request.data.get('personalizado') or ''
        proprio_tpl.save(update_fields=['personalizado', 'atualizado_em'])

    tpl_resposta = proprio_tpl or global_tpl
    if tpl_resposta is None:
        return Response({'error': 'Nada para salvar.'}, status=status.HTTP_400_BAD_REQUEST)

    data = dict(PromptTemplateSerializer(tpl_resposta).data)
    data['prompt_global'] = global_tpl.prompt_global if global_tpl else ''
    return Response(data)


# ============================================================
# Categorias (taxonomia compartilhada — só superadmin)
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_prompt_categoria(request):
    if not is_superadmin(request.user):
        return _sem_permissao()

    titulo = (request.data.get('titulo') or '').strip()
    erro = _titulo_invalido(titulo)
    if erro:
        return erro

    categoria = PromptCategoria.objects.create(titulo=titulo, ativo=_para_bool(request.data.get('ativo', True)))
    return Response(PromptCategoriaSerializer(categoria, context={}).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_prompt_categoria(request, categoria_id):
    if not is_superadmin(request.user):
        return _sem_permissao()

    categoria, erro = _categoria_ou_404(categoria_id)
    if erro:
        return erro

    if 'titulo' in request.data:
        titulo = (request.data['titulo'] or '').strip()
        erro = _titulo_invalido(titulo, ignorar_id=categoria.id)
        if erro:
            return erro
        categoria.titulo = titulo
    if 'ativo' in request.data:
        categoria.ativo = _para_bool(request.data['ativo'])
    categoria.save()

    return Response(PromptCategoriaSerializer(categoria, context={}).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_prompt_categoria(request, categoria_id):
    if not is_superadmin(request.user):
        return _sem_permissao()

    categoria, erro = _categoria_ou_404(categoria_id)
    if erro:
        return erro

    categoria.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)