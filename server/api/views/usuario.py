"""Endpoints de Usuario."""

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, filtrar_por, pode_gerenciar, validar_vinculos_usuario
from api.models import Escola, Usuario, UsuarioDisciplina, UsuarioTurma
from api.serializers import UsuarioListaSerializer, UsuarioSerializer, UsuarioWriteSerializer
from api.tenancy import is_superadmin

# Papéis internos do NARA — sem vínculo com instituição/escola.
# Nem admin nem coordenador podem atribuir/criar usuários com esses níveis.
NIVEIS_SISTEMA = {'superadmin', 'vendedor', 'suporte'}

# O que um coordenador pode criar dentro da própria escola — e, pelo mesmo
# critério, os únicos usuários (além de si mesmo) que ele pode editar.
NIVEIS_QUE_COORDENADOR_CRIA = {
    'professor_infantil', 'professor_fundamental', 'professor_especialista', 'especialista',
}

# Campos que ninguém (exceto superadmin) altera em si mesmo por esta rota:
# evita auto-promoção, trocar de escola e se vincular sozinho a turmas ou
# disciplinas (o que daria acesso aos alunos delas).
CAMPOS_BLOQUEADOS_NA_AUTOEDICAO = (
    'nivel', 'instituicao', 'escola', 'especialista', 'tipo_especialista',
    'turmas', 'disciplinas', 'is_active',
)

USUARIOS_POR_PAGINA = 10
USUARIOS_POR_PAGINA_MAX = 50


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


def _niveis_que_pode_atribuir(user):
    """Mesma regra de `_nivel_permitido`, em forma de lista (para o front
    montar o select de perfil sem duplicar a regra)."""
    todos = [valor for valor, _ in Usuario._meta.get_field('nivel').choices]
    return [n for n in todos if _nivel_permitido(user, n) is None]


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


def _param_bool(valor):
    """'true'/'false' (e variações) → bool; ausente ou inválido → None (sem filtro)."""
    if valor is None:
        return None
    valor = valor.strip().lower()
    if valor in ('true', '1', 'sim'):
        return True
    if valor in ('false', '0', 'nao', 'não'):
        return False
    return None


def _param_int(valor, padrao, minimo, maximo):
    try:
        return max(minimo, min(int(valor), maximo))
    except (TypeError, ValueError):
        return padrao


def _salvar(serializer):
    """Usuário + vínculos (turmas, disciplinas, especialista) numa transação:
    ou grava tudo, ou nada."""
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        return serializer.save()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_usuarios(request):
    """
    GET /usuarios/ — superadmin vê todos; admin, os da própria instituição;
    coordenador, os da própria escola. O recorte é do TenantManager (usuário
    sem o vínculo exigido recebe lista vazia).

    Query params (todos opcionais):
      ativo=true|false   filtra por is_active
      escola=<uuid>      fora do escopo/malformado → vazio
      nivel=<nivel>      ex.: professor_fundamental
      busca=<texto>      parte do nome ou do e-mail
      page=<n>           liga a paginação (fora do intervalo → última)
      page_size=<n>      padrão 10, máximo 50

    SEM `page`: array simples, como antes (formulários de turma e disciplina
    usam a lista completa), já com os filtros acima aplicados no servidor.

    COM `page`:
      {
        "count": 37, "pagina": 1, "total_paginas": 4, "page_size": 10,
        "totais": {"ativos": 30, "inativos": 7},        # p/ as abas
        "niveis_permitidos": ["admin", "coordenador", ...],  # o que QUEM PEDE pode atribuir
        "usuario_atual": "<uuid>",                       # p/ a tela não oferecer auto-desativação
        "results": [ ...UsuarioListaSerializer (com turmas e disciplinas)... ]
      }
    """
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao('Sem permissão. Use /api/me/ para ver seus próprios dados.')

    base = filtrar_por(Usuario.objects.all(), request, 'escola', Escola, 'escola')
    nivel = request.query_params.get('nivel')
    if nivel:
        base = base.filter(nivel=nivel)
    busca = (request.query_params.get('busca') or '').strip()
    if busca:
        base = base.filter(Q(nome__icontains=busca) | Q(email__icontains=busca))

    ativo = _param_bool(request.query_params.get('ativo'))
    usuarios = base if ativo is None else base.filter(is_active=ativo)
    usuarios = usuarios.select_related('escola', 'instituicao', 'especialista').order_by('nome', 'id')

    if 'page' not in request.query_params:
        return Response(UsuarioSerializer(usuarios, many=True).data)

    usuarios = usuarios.prefetch_related(
        Prefetch(
            'usuario_turmas',
            queryset=UsuarioTurma.objects.select_related('turma').order_by('turma__nome'),
            to_attr='turmas_listagem',
        ),
        Prefetch(
            'usuario_disciplinas',
            queryset=UsuarioDisciplina.objects.select_related('disciplina').order_by('disciplina__nome'),
            to_attr='disciplinas_listagem',
        ),
    )

    page_size = _param_int(
        request.query_params.get('page_size'),
        USUARIOS_POR_PAGINA, 1, USUARIOS_POR_PAGINA_MAX,
    )
    pagina = Paginator(usuarios, page_size).get_page(request.query_params.get('page'))

    # Totais das abas respeitam escola/nível/busca, mas não o filtro `ativo`.
    totais = base.aggregate(
        ativos=Count('id', filter=Q(is_active=True)),
        inativos=Count('id', filter=Q(is_active=False)),
    )
    totais = {chave: valor or 0 for chave, valor in totais.items()}

    return Response({
        'count': pagina.paginator.count,
        'pagina': pagina.number,
        'total_paginas': pagina.paginator.num_pages,
        'page_size': page_size,
        'totais': totais,
        'niveis_permitidos': _niveis_que_pode_atribuir(user),
        'usuario_atual': str(user.id),
        'results': UsuarioListaSerializer(pagina.object_list, many=True).data,
    })


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

    usuario = _salvar(UsuarioWriteSerializer(data=data))
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

    # Na autoedição, só dados pessoais (nome, e-mail, senha...). Superadmin
    # pode mudar tudo de qualquer um.
    if is_self and not is_superadmin(user):
        for campo in CAMPOS_BLOQUEADOS_NA_AUTOEDICAO:
            data.pop(campo, None)
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
    usuario = _salvar(UsuarioWriteSerializer(alvo, data=data, partial=partial))
    return Response(UsuarioSerializer(usuario).data)