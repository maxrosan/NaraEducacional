"""Endpoints de PromptCategoria e PromptTemplate (biblioteca de prompts de IA).

Modelo de dados (o mesmo que `services/prompt_resolver.resolver_prompt` lê):

* **Global** — 1 PromptTemplate por categoria com `escola` e `instituicao`
  nulas; o texto está em `prompt_global`. Vale para todas as escolas que não
  personalizaram. Só o superadmin edita.
* **Personalizado** — 1 PromptTemplate por (categoria, ESCOLA); o texto está
  em `personalizado` (a `instituicao` é a da escola, só para o recorte de
  tenant). Quando preenchido, tem prioridade sobre o global PARA AQUELA escola.

Qual escola: o coordenador sempre edita/vê a própria; admin e superadmin
informam a escola (`escola` no body / `?escola_id=`), e o admin só as da
própria rede.

Todas as consultas usam `PromptTemplate._base_manager`: o TenantManager
esconderia o global (sem escola) de quem tem escopo de escola.
"""

from django.db.models import Prefetch, Q
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar, pode_ver_escola
from api.models import Escola, PromptCategoria, PromptTemplate
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


_GLOBAL = Q(escola__isnull=True, instituicao__isnull=True)


def _escola_do_contexto(user, escola_informada):
    """Escola cujo prompt personalizado se lê/edita. Retorna (escola, erro).

    Coordenador: sempre a própria (o informado é ignorado). Admin/superadmin:
    a informada, que o admin só pode usar se for da rede dele. Nada informado
    → (None, None): só o global.
    """
    if user.nivel == 'coordenador':
        return user.escola, None
    if not escola_informada:
        return None, None
    escola = buscar_no_escopo(Escola, escola_informada)
    if escola is None or not pode_ver_escola(user, escola):
        return None, Response({'error': 'Escola não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return escola, None


def _template_global(categoria, criar=False):
    tpl = PromptTemplate._base_manager.filter(_GLOBAL, categoria=categoria).order_by('-criado_em').first()
    if tpl is None and criar:
        tpl = PromptTemplate._base_manager.create(categoria=categoria, prompt_global='', personalizado='')
    return tpl


def _template_da_escola(categoria, escola):
    tpl = (
        PromptTemplate._base_manager.filter(categoria=categoria, escola=escola)
        .order_by('-criado_em').first()
    )
    if tpl is None:
        tpl = PromptTemplate._base_manager.create(
            categoria=categoria, escola=escola, instituicao_id=escola.instituicao_id,
            prompt_global='', personalizado='',
        )
    return tpl


# ============================================================
# Templates
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_prompt_categorias(request):
    """?todas=1 inclui categorias inativas (tela de admin).
    ?escola_id= (admin/superadmin): mostra o que vale para aquela escola."""
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola, erro = _escola_do_contexto(user, request.GET.get('escola_id'))
    if erro:
        return erro

    # Só o global e o da escola do contexto — o serializer não precisa (nem
    # deve) receber os personalizados das outras escolas.
    visiveis = _GLOBAL
    if escola is not None:
        visiveis |= Q(escola=escola)

    qs = PromptCategoria.objects.prefetch_related(
        Prefetch('templates', queryset=PromptTemplate._base_manager.filter(visiveis).order_by('-criado_em')),
    ).order_by('titulo')
    if request.GET.get('todas') != '1':
        qs = qs.filter(ativo=True)

    contexto = {'escola_id': escola.id if escola else None}
    return Response(PromptCategoriaSerializer(qs, many=True, context=contexto).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def salvar_prompt_template(request):
    """
    Body: {categoria, prompt_global, personalizado, escola?}.

    O frontend manda os dois textos juntos. Cada um vai para o SEU registro:
    * `prompt_global` → template global da categoria — só se quem salva é
      superadmin (dos demais, o campo é ignorado);
    * `personalizado` → template da escola do contexto (`_escola_do_contexto`).
      Admin precisa informar `escola`; superadmin sem `escola` só edita o global.

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

    escola, erro = _escola_do_contexto(user, request.data.get('escola'))
    if erro:
        return erro
    if 'personalizado' in request.data and escola is None and not is_superadmin(user):
        return Response({'error': 'Informe a escola do prompt personalizado.'}, status=status.HTTP_400_BAD_REQUEST)

    global_tpl = _template_global(categoria)
    if is_superadmin(user) and 'prompt_global' in request.data:
        global_tpl = global_tpl or _template_global(categoria, criar=True)
        global_tpl.prompt_global = request.data.get('prompt_global') or ''
        global_tpl.save(update_fields=['prompt_global', 'atualizado_em'])

    proprio_tpl = None
    if escola is not None and 'personalizado' in request.data:
        proprio_tpl = _template_da_escola(categoria, escola)
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