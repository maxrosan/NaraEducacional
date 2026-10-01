"""Endpoints de CampoPedagogico e HabilidadeBNCC (tabela global).

CampoPedagogico é um cadastro "oficial OU customizado": os oficiais (escola e
instituição nulas) valem para todas as escolas; cada escola pode criar os
seus. Leitura/busca pelo manager `todos` + `escopo.filtro_visiveis`.

Não há exclusão de campo: perguntas (dos dois tipos) apontam para ele com
SET_NULL e perderiam o campo em silêncio. O campo é desativado, remanejando
antes as perguntas para outro campo (`desativar_campo_pedagogico`).
"""

from django.db import transaction
from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    SEM_ESCOLA_OFICIAL, buscar_no_escopo, buscar_visivel, filtro_visiveis, pode_editar, pode_gerenciar,
    resolver_escopo_criacao,
)
from api.models import CampoPedagogico, HabilidadeBNCC, Pergunta, PerguntaEspecialista
from api.serializers import CampoPedagogicoSerializer, HabilidadeBNCCSerializer
from api.tenancy import is_superadmin


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado(mensagem):
    return Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)


def _salvar_edicao(request, obj, serializer_class):
    partial = request.method == 'PATCH'
    serializer = serializer_class(obj, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# CampoPedagogico
# ============================================================

_CAMPO_NAO_ENCONTRADO = 'Campo pedagógico não encontrado.'


def _uso_por_campo(user):
    """{str(campo_id): nº de perguntas} contando só as perguntas que `user` vê
    (BNCC oficiais + do escopo, e as de especialista do escopo). Assim um
    campo oficial não revela quantas perguntas outras redes têm nele."""
    uso = {}
    consultas = (
        Pergunta.todos.filter(filtro_visiveis(user)),
        PerguntaEspecialista.objects.all(),  # TenantManager: só o escopo
    )
    for qs in consultas:
        for linha in qs.exclude(campo_experiencia__isnull=True).values('campo_experiencia').annotate(n=Count('id')):
            chave = str(linha['campo_experiencia'])  # o serializer devolve o id como texto
            uso[chave] = uso.get(chave, 0) + linha['n']
    return uso


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_campos_pedagogicos(request):
    """
    GET /campos-pedagogicos/ — oficiais + os do escopo, por nome.

    Query params (opcionais):
      ativo=true|false   filtra pelo status
      com_uso=1          acrescenta `total_perguntas` (perguntas visíveis que usam o campo)
    """
    campos = CampoPedagogico.todos.filter(filtro_visiveis(request.user)).select_related('escola')
    ativo = request.query_params.get('ativo')
    if ativo in ('true', 'false'):
        campos = campos.filter(ativo=(ativo == 'true'))
    dados = CampoPedagogicoSerializer(campos.order_by('nome', 'id'), many=True).data

    if request.query_params.get('com_uso') in ('1', 'true'):
        uso = _uso_por_campo(request.user)
        for item in dados:
            item['total_perguntas'] = uso.get(str(item['id']), 0)
    return Response(dados)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_campo_pedagogico(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data, sem_escola=SEM_ESCOLA_OFICIAL)
    if erro:
        return erro

    serializer = CampoPedagogicoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    campo = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(CampoPedagogicoSerializer(campo).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_campo_pedagogico(request, campo_id):
    campo = buscar_visivel(CampoPedagogico, campo_id, request.user)
    if campo is None:
        return _nao_encontrado(_CAMPO_NAO_ENCONTRADO)
    return Response(CampoPedagogicoSerializer(campo).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_campo_pedagogico(request, campo_id):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    campo = buscar_visivel(CampoPedagogico, campo_id, user)
    if campo is None:
        return _nao_encontrado(_CAMPO_NAO_ENCONTRADO)

    erro = pode_editar(user, campo)  # oficial: só superadmin
    if erro:
        return erro
    return _salvar_edicao(request, campo, CampoPedagogicoSerializer)


def _destino_invalido(campo, destino):
    """O campo de destino precisa servir para TODAS as perguntas do campo de
    origem: se a origem é oficial (perguntas de várias escolas), o destino
    também tem de ser oficial; se é de uma escola, o destino é oficial ou da
    mesma escola. Retorna a mensagem de erro ou None."""
    if destino.pk == campo.pk:
        return 'Escolha um campo de destino diferente do que será desativado.'
    if not destino.ativo:
        return 'O campo de destino está desativado.'
    if campo.escola_id is None and destino.escola_id is not None:
        return 'As perguntas de um campo oficial só podem ir para outro campo oficial.'
    if campo.escola_id is not None and destino.escola_id not in (None, campo.escola_id):
        return 'O campo de destino precisa ser oficial ou da mesma escola.'
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def desativar_campo_pedagogico(request, campo_id):
    """
    POST /campos-pedagogicos/<id>/desativar/ — body: {"remanejar_para": <uuid> | null}

    Se há perguntas (BNCC ou de especialista) no campo, `remanejar_para` é
    obrigatório: elas passam para esse campo, e só então o campo é
    desativado — tudo numa transação. Sem destino e com perguntas → 409 com
    `total_vinculos`. Reativar: PATCH /atualizar/ com {"ativo": true}.
    Campo oficial: só superadmin (mesma regra da edição).
    """
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    campo = buscar_visivel(CampoPedagogico, campo_id, user)
    if campo is None:
        return _nao_encontrado(_CAMPO_NAO_ENCONTRADO)
    erro = pode_editar(user, campo)
    if erro:
        return erro

    # Todas as perguntas do campo (managers sem tenant): um campo de escola só
    # é usado por perguntas dessa escola (ver pergunta._campo_invalido), e um
    # oficial só chega até aqui com superadmin.
    perguntas_bncc = Pergunta.todos.filter(campo_experiencia=campo)
    perguntas_esp = PerguntaEspecialista._base_manager.filter(campo_experiencia=campo)
    total = perguntas_bncc.count() + perguntas_esp.count()

    destino = None
    destino_id = request.data.get('remanejar_para')
    if destino_id:
        destino = buscar_visivel(CampoPedagogico, destino_id, user)
        if destino is None:
            return _nao_encontrado('Campo de destino não encontrado.')
        mensagem = _destino_invalido(campo, destino)
        if mensagem:
            return Response({'error': mensagem}, status=status.HTTP_400_BAD_REQUEST)
    elif total:
        return Response(
            {'error': f'Existem {total} pergunta(s) neste campo. Escolha para qual campo remanejá-las.',
             'total_vinculos': total},
            status=status.HTTP_409_CONFLICT,
        )

    with transaction.atomic():
        remanejadas = 0
        if destino is not None:
            remanejadas = perguntas_bncc.update(campo_experiencia=destino)
            remanejadas += perguntas_esp.update(campo_experiencia=destino)
        campo.ativo = False
        campo.save(update_fields=['ativo', 'atualizado_em'])

    return Response({
        'campo': CampoPedagogicoSerializer(campo).data,
        'perguntas_remanejadas': remanejadas,
    })


# ============================================================
# HabilidadeBNCC — tabela 100% global, sem escola/instituicao.
# Leitura livre pra qualquer autenticado; escrita só superadmin
# (é o catálogo oficial da BNCC, não algo que cada escola edita).
# ============================================================

_HABILIDADE_NAO_ENCONTRADA = 'Habilidade não encontrada.'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_habilidades_bncc(request):
    habilidades = HabilidadeBNCC.objects.all().order_by('codigo')
    componente = request.query_params.get('componente_curricular')
    if componente:
        habilidades = habilidades.filter(componente_curricular=componente)
    return Response(HabilidadeBNCCSerializer(habilidades, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_habilidade_bncc(request):
    if not is_superadmin(request.user):
        return _sem_permissao()

    serializer = HabilidadeBNCCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    habilidade = serializer.save()
    return Response(HabilidadeBNCCSerializer(habilidade).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_habilidade_bncc(request, habilidade_id):
    habilidade = buscar_no_escopo(HabilidadeBNCC, habilidade_id)  # tabela global: só trata id malformado
    if habilidade is None:
        return _nao_encontrado(_HABILIDADE_NAO_ENCONTRADA)
    return Response(HabilidadeBNCCSerializer(habilidade).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_habilidade_bncc(request, habilidade_id):
    if not is_superadmin(request.user):
        return _sem_permissao()

    habilidade = buscar_no_escopo(HabilidadeBNCC, habilidade_id)
    if habilidade is None:
        return _nao_encontrado(_HABILIDADE_NAO_ENCONTRADA)
    return _salvar_edicao(request, habilidade, HabilidadeBNCCSerializer)