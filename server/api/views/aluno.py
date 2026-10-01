"""Endpoints de Aluno."""

import io
import logging
import uuid

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, filtrar_por, pode_gerenciar, pode_ver_escola
from api.models import Aluno, Escola, Turma
from api.serializers import AlunoSerializer
from api.storage import delete_from_storage, upload_bytes_to_storage

logger = logging.getLogger(__name__)

ALUNOS_POR_PAGINA = 10
ALUNOS_POR_PAGINA_MAX = 50
STATUS_VINCULO = ('ativo', 'inativo', 'transferido')

FOTO_TAMANHO_MAX = 10 * 1024 * 1024   # 10MB, o mesmo limite que o front anuncia
FOTO_LADO_MAX = 800                    # px; a foto aparece em avatar e no relatório
FOTO_QUALIDADE_JPEG = 85


def _aluno_nao_encontrado():
    return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)


def _param_int(valor, padrao, minimo, maximo):
    try:
        return max(minimo, min(int(valor), maximo))
    except (TypeError, ValueError):
        return padrao


def _validar_e_salvar(serializer, escola_travada_id, **extra):
    """Valida e salva o aluno numa transação, com a linha da escola travada.

    A checagem de aluno duplicado (nome + nascimento na escola) é feita só no
    serializer, sem constraint no banco. A trava (SELECT ... FOR UPDATE) faz
    saves de alunos da MESMA escola entrarem em fila, para duas requisições
    simultâneas (ex.: importação em lote rodando duas vezes) não passarem
    ambas pela checagem.

    `escola_travada_id` tem esse nome (e não `escola_id`) porque `escola_id`
    também chega em `**extra` para o serializer.save() na criação.
    """
    with transaction.atomic():
        list(Escola._base_manager.select_for_update().filter(pk=escola_travada_id).values_list('pk', flat=True))
        serializer.is_valid(raise_exception=True)
        return serializer.save(**extra)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_alunos(request):
    """
    GET /alunos/ — já vem recortado pelo TenantManager.

    Query params (todos opcionais):
      status=ativo|inativo|transferido   filtra pelo status_vinculo; aceita vários
                                         separados por vírgula (ex.: inativo,transferido)
      escola=<uuid>, turma=<uuid>        fora do escopo/malformado → vazio
      busca=<texto>                      parte do nome do aluno (sem diferenciar maiúsculas)
      page=<n>                           liga a paginação (fora do intervalo → última)
      page_size=<n>                      padrão 10, máximo 50

    SEM `page`: devolve um array simples, como antes — outras telas chamam
    listarCriancas() e esperam o array.

    COM `page`:
      {
        "count": 37, "pagina": 1, "total_paginas": 4, "page_size": 10,
        "totais": {"ativo": 30, "inativo": 5, "transferido": 2},  # p/ as abas
        "results": [ ...AlunoSerializer... ]
      }

    Custo fixo por página: count, página (com turma e escola) e totais.
    """
    base = Aluno.objects.all()
    base = filtrar_por(base, request, 'escola', Escola, 'escola')
    base = filtrar_por(base, request, 'turma', Turma, 'turma')
    busca = (request.query_params.get('busca') or '').strip()
    if busca:
        base = base.filter(nome_completo__icontains=busca)

    status_pedidos = [
        s for s in (request.query_params.get('status') or '').split(',') if s in STATUS_VINCULO
    ]
    alunos = base.filter(status_vinculo__in=status_pedidos) if status_pedidos else base
    # `id` no fim deixa a ordem estável entre páginas quando há homônimos.
    alunos = alunos.select_related('turma', 'escola').order_by('nome_completo', 'id')

    if 'page' not in request.query_params:
        return Response(AlunoSerializer(alunos, many=True).data)

    page_size = _param_int(
        request.query_params.get('page_size'),
        ALUNOS_POR_PAGINA, 1, ALUNOS_POR_PAGINA_MAX,
    )
    pagina = Paginator(alunos, page_size).get_page(request.query_params.get('page'))

    # Totais das abas respeitam escola/turma/busca, mas não o status.
    totais = base.aggregate(**{
        s: Count('id', filter=Q(status_vinculo=s)) for s in STATUS_VINCULO
    })
    totais = {chave: valor or 0 for chave, valor in totais.items()}

    return Response({
        'count': pagina.paginator.count,
        'pagina': pagina.number,
        'total_paginas': pagina.paginator.num_pages,
        'page_size': page_size,
        'totais': totais,
        'results': AlunoSerializer(pagina.object_list, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_aluno(request):
    user = request.user
    if not pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma_id = request.data.get('turma')
    if not turma_id:
        return Response({'error': 'Campo turma é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    # O TenantManager já barrou turmas fora do escopo; isto é a segunda camada.
    if not pode_ver_escola(user, turma.escola):
        return Response({'error': 'Turma fora do seu escopo.'}, status=status.HTTP_403_FORBIDDEN)

    if not turma.escola.ativa:
        return Response({'error': 'Não é possível cadastrar alunos em uma escola desativada.'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Turma desativada é recusada no serializer (_checar_turma).
    serializer = AlunoSerializer(data=request.data, context={'escola_id': turma.escola_id})
    aluno = _validar_e_salvar(
        serializer, turma.escola_id,
        turma=turma, escola_id=turma.escola_id, instituicao_id=turma.instituicao_id,
    )
    return Response(AlunoSerializer(aluno).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_aluno(request, aluno_id):
    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado()
    return Response(AlunoSerializer(aluno).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_aluno(request, aluno_id):
    if not pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado()

    # 404 (e não 400 genérico do serializer) para turma inexistente ou fora do
    # escopo. Mesma escola e turma ativa são checadas no serializer.
    nova_turma_id = request.data.get('turma')
    if nova_turma_id and str(nova_turma_id) != str(aluno.turma_id):
        if buscar_no_escopo(Turma, nova_turma_id) is None:
            return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = AlunoSerializer(aluno, data=request.data, partial=partial)
    aluno = _validar_e_salvar(serializer, aluno.escola_id)
    return Response(AlunoSerializer(aluno).data)


def _foto_em_jpeg(arquivo):
    """Abre a imagem enviada e devolve bytes JPEG reduzidos, ou None se não
    for uma imagem válida.

    Abrir com o Pillow (e não confiar no content-type do navegador) é a
    validação: um arquivo qualquer renomeado para .png é recusado. Converter
    para JPEG também resolve HEIC/HEIF (fotos de iPhone), que a maioria dos
    navegadores não exibe; o registro do HEIC no Pillow é feito em storage.py.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        imagem = Image.open(arquivo)
        imagem.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None

    imagem = ImageOps.exif_transpose(imagem)  # foto de celular "deitada"
    if imagem.mode not in ('RGB', 'L'):
        imagem = imagem.convert('RGB')
    imagem.thumbnail((FOTO_LADO_MAX, FOTO_LADO_MAX))

    saida = io.BytesIO()
    imagem.save(saida, format='JPEG', quality=FOTO_QUALIDADE_JPEG, optimize=True)
    return saida.getvalue()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def enviar_foto_aluno(request, aluno_id):
    """
    POST /alunos/<id>/foto/ (multipart, campo `foto`) — envia ou troca a foto.

    Mesmas permissões da edição do aluno. A imagem é validada, convertida para
    JPEG e reduzida (lado maior até 800px). A foto anterior é apagada do
    armazenamento depois que a nova foi salva. Responde com o aluno atualizado.
    """
    if not pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado()

    arquivo = request.FILES.get('foto')
    if arquivo is None:
        return Response({'foto': ['Envie a imagem no campo "foto".']}, status=status.HTTP_400_BAD_REQUEST)
    if arquivo.size > FOTO_TAMANHO_MAX:
        return Response({'foto': ['A imagem deve ter no máximo 10MB.']}, status=status.HTTP_400_BAD_REQUEST)

    conteudo = _foto_em_jpeg(arquivo)
    if conteudo is None:
        return Response({'foto': ['O arquivo enviado não é uma imagem válida.']},
                        status=status.HTTP_400_BAD_REQUEST)

    # Nome novo a cada envio: a URL antiga (em cache no navegador) não mostra a foto velha.
    chave = f'alunos/{aluno.instituicao_id}/{aluno.escola_id}/{aluno.id}/foto-{uuid.uuid4().hex}.jpg'
    try:
        chave_salva, url = upload_bytes_to_storage(chave, conteudo, content_type='image/jpeg')
    except RuntimeError as erro:
        logger.error('Falha ao enviar foto do aluno %s: %s', aluno.id, erro)
        return Response({'error': 'Não foi possível salvar a foto. Tente novamente.'},
                        status=status.HTTP_502_BAD_GATEWAY)

    chave_anterior = aluno.foto_storage_key
    aluno.foto_storage_key = chave_salva
    aluno.foto_url = url
    aluno.save(update_fields=['foto_storage_key', 'foto_url'])

    # Best-effort: delete_from_storage nunca levanta; uma sobra não falha o envio.
    if chave_anterior and chave_anterior != chave_salva and not delete_from_storage(chave_anterior):
        logger.warning('Não foi possível apagar a foto antiga %s', chave_anterior)

    return Response(AlunoSerializer(aluno).data)