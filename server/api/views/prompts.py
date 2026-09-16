import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from ..models import PromptCategoria, PromptTemplate
from ..serializers import PromptCategoriaSerializer, PromptTemplateSerializer


def _cliente_id(request):
    """
    Resolve o cliente_id a partir da instituição do usuário autenticado.

    Busca o instituicao_id direto do banco (não confia apenas no objeto
    request.user da sessão), pois a sessão do Django pode manter uma cópia
    desatualizada do usuário entre logins. Se o instituicao_id do usuário
    for alterado diretamente no banco (ex.: correção manual), uma sessão já
    aberta só refletiria a mudança em um novo login, fazendo o prompt ser
    salvo incorretamente como global (cliente_id=None) em vez de
    personalizado para a instituição correta.

    Fallback: se o usuário autenticado não tiver instituicao_id (NULL),
    usa o instituicao_id do primeiro usuário com perfil='coordenador'
    encontrado no banco — assume-se que, num banco isolado por escola,
    o coordenador sempre está corretamente vinculado à instituição.
    """
    from django.contrib.auth import get_user_model

    user = getattr(request, 'user', None)
    if not user or user.is_anonymous:
        return None

    UserModel = get_user_model()

    instituicao_id = UserModel.objects.filter(pk=user.pk).values_list(
        'instituicao_id', flat=True
    ).first()

    if not instituicao_id:
        instituicao_id = UserModel.objects.filter(
            perfil='coordenador',
        ).exclude(
            instituicao_id__isnull=True,
        ).values_list('instituicao_id', flat=True).first()

    return str(instituicao_id) if instituicao_id else None


@require_http_methods(["GET"])
def listar_prompt_categorias(request):
    """
    GET /api/prompts/categorias/
    Retorna categorias ativas com o template resolvido para o cliente.
    """
    cliente_id = _cliente_id(request)
    todas = request.GET.get('todas') == '1'
    qs = PromptCategoria.objects.prefetch_related('templates').order_by('id')
    if not todas:
        qs = qs.filter(ativo=True)
    data = PromptCategoriaSerializer(
        qs, many=True, context={'cliente_id': cliente_id}
    ).data
    return JsonResponse(data, safe=False)


@require_http_methods(["POST"])
def salvar_prompt_template(request):
    """
    POST /api/prompts/salvar/
    Body JSON: { categoria_id, prompt_global, personalizado }

    O frontend sempre envia os dois campos juntos (prompt_global e
    personalizado), sem indicar qual deles o usuário de fato editou na
    tela. Por isso a view grava ambos os valores recebidos, em vez de
    escolher um campo com base no cliente_id do usuário logado — fazer
    essa escolha causava o bug em que editar o campo Global era
    silenciosamente ignorado para usuários vinculados a uma instituição
    (o valor digitado nunca era persistido, e a tela voltava a mostrar o
    texto antigo após recarregar).

    Regras:
    - Cada categoria deve ter APENAS UM registro de PromptTemplate
      (1:1 hoje; preparado para evoluir a N:1 por cliente quando o
      multi-tenant compartilhar banco entre instituições).
    - prompt_global é sempre atualizado com o valor recebido.
    - personalizado é atualizado com o valor recebido; o cliente_id do
      registro é gravado/atualizado com o cliente_id do usuário logado
      apenas quando ele existir (preserva o cliente que personalizou,
      mesmo que um admin sem instituição edite o global depois).
    - Nunca cria um novo registro via get_or_create filtrando por
      cliente_id — isso duplicava a linha sempre que o cliente_id mudava
      de None para um UUID. Em vez disso, usa o registro mais recente
      (-id) já existente para a categoria, e cria um único registro novo
      apenas se a categoria ainda não tiver nenhum.
    """
    try:
        body         = json.loads(request.body)
        categoria_id = body.get('categoria_id')
        prompt_global = body.get('prompt_global', '')
        personalizado = body.get('personalizado', '')
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Payload inválido.'}, status=400)

    if not categoria_id:
        return JsonResponse({'error': 'categoria_id é obrigatório.'}, status=400)

    try:
        categoria = PromptCategoria.objects.get(pk=categoria_id, ativo=True)
    except PromptCategoria.DoesNotExist:
        return JsonResponse({'error': 'Categoria não encontrada.'}, status=404)

    cliente_id = _cliente_id(request)

    # Usa o registro mais recente já existente para a categoria (resiliente
    # a duplicados legados); cria um novo apenas se não existir nenhum.
    template = PromptTemplate.objects.filter(categoria=categoria).order_by('-id').first()
    if template is None:
        template = PromptTemplate.objects.create(
            categoria=categoria, prompt_global='', personalizado='',
        )

    # Sempre grava o global recebido — independente do cliente_id do
    # usuário logado, pois o frontend manda os dois campos juntos.
    template.prompt_global = prompt_global

    # Grava o personalizado recebido. Só associa/atualiza o cliente_id
    # quando o usuário logado tiver um (evita sobrescrever com None o
    # cliente_id de um registro já personalizado por outra instituição).
    template.personalizado = personalizado
    if cliente_id is not None:
        template.cliente_id = cliente_id

    template.save()

    return JsonResponse(PromptTemplateSerializer(template).data, status=200)


@require_http_methods(["POST"])
def criar_prompt_categoria(request):
    """
    POST /api/prompts/categorias/criar/
    Body JSON: { titulo, ativo? }
    """
    try:
        body   = json.loads(request.body)
        titulo = body.get('titulo', '').strip()
        ativo  = body.get('ativo', True)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Payload inválido.'}, status=400)

    if not titulo:
        return JsonResponse({'error': 'titulo é obrigatório.'}, status=400)

    if PromptCategoria.objects.filter(titulo__iexact=titulo).exists():
        return JsonResponse({'error': 'Já existe uma categoria com este título.'}, status=400)

    categoria = PromptCategoria.objects.create(titulo=titulo, ativo=ativo)
    return JsonResponse({'id': categoria.id, 'titulo': categoria.titulo, 'ativo': categoria.ativo}, status=201)


@require_http_methods(["PATCH"])
def atualizar_prompt_categoria(request, categoria_id):
    """
    PATCH /api/prompts/categorias/<id>/atualizar/
    Body JSON: { titulo?, ativo? }
    """
    try:
        categoria = PromptCategoria.objects.get(pk=categoria_id)
    except PromptCategoria.DoesNotExist:
        return JsonResponse({'error': 'Categoria não encontrada.'}, status=404)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Payload inválido.'}, status=400)

    if 'titulo' in body:
        titulo = body['titulo'].strip()
        if not titulo:
            return JsonResponse({'error': 'titulo não pode ser vazio.'}, status=400)
        categoria.titulo = titulo
    if 'ativo' in body:
        categoria.ativo = bool(body['ativo'])
    categoria.save()

    return JsonResponse({'id': categoria.id, 'titulo': categoria.titulo, 'ativo': categoria.ativo})


@require_http_methods(["DELETE"])
def deletar_prompt_categoria(request, categoria_id):
    """
    DELETE /api/prompts/categorias/<id>/deletar/
    """
    try:
        categoria = PromptCategoria.objects.get(pk=categoria_id)
    except PromptCategoria.DoesNotExist:
        return JsonResponse({'error': 'Categoria não encontrada.'}, status=404)
    categoria.delete()
    return JsonResponse({'deleted': True})