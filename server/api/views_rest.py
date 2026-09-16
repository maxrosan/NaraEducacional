"""
Views REST para CRUD de entidades no Postgres via Django.
Estas views substituem as chamadas diretas ao client de dados no frontend.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from api.throttles import UploadRateThrottle
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db import IntegrityError, transaction
from django.db.models import Q, Count, Max, Subquery, OuterRef
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404

from api.storage import upload_bytes_to_storage, compress_image

import hashlib
import logging
from .decorators import requer_perfil

from .services.password_reset import solicitar_recuperacao, confirmar_nova_senha

logger = logging.getLogger(__name__)

from api.views_legacy import (
    validate_uploaded_file,
    ALLOWED_IMAGE_MIME_TYPES,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE_BYTES,
)

from .storage import (
    delete_from_s3,
    extract_storage_key_from_url,
    generate_presigned_url,
    is_s3_configured,
    upload_bytes_to_storage,
)

from .models import (
    Crianca,
    Relatorio,
    RelatorioTemplate,
    PerguntaBNCC,
    PerguntaEspecialista,
    RegistroObservacao,
    RegistroEscrita,
    RegistroDesenho,
    ProducaoCrianca,
    Projeto,
    CalendarioBimestre,
    PeriodoAvaliativo,
    Turma,
    ConfiguracaoRegistro,
    Instituicao,
    Usuario,
    UsuarioTurma,
    MensagemCoordenacao,
    MensagemLida,
    AlertaLido,
    ObservacaoTranscricao,
    CampoExperienciaCustomizado,
    SerieConfig,
    MetaPAEE,
    Disciplina,           
    UsuarioDisciplina,
    PromptCategoria, 
    PromptTemplate,
)
from .serializers import (
    CriancaSerializer,
    CriancaListSerializer,
    RelatorioSerializer,
    RelatorioListSerializer,
    RelatorioCreateSerializer,
    RelatorioTemplateSerializer,
    RelatorioTemplateListSerializer,
    PerguntaBNCCSerializer,
    PerguntaEspecialistaSerializer,
    RegistroObservacaoSerializer,
    ProducaoCriancaSerializer,
    ProjetoSerializer,
    CalendarioBimestreSerializer,
    PeriodoAvaliativoSerializer,
    TurmaSerializer,
    ConfiguracaoRegistroSerializer,
    InstituicaoSerializer,
    UsuarioSerializer,
    UsuarioTurmaSerializer,
    MensagemCoordenacaoSerializer,
    MensagemLidaSerializer,
    AlertaLidoSerializer,
    CampoExperienciaCustomizadoSerializer,
    SerieConfigSerializer,
    DisciplinaSerializer,
    UsuarioDisciplinaSerializer,
    PromptCategoriaSerializer,
    PromptTemplateSerializer
)

from .services.alerts import gerar_alertas_coordenacao, gerar_alertas_professor
from .services.language_development import calcular_desenvolvimento_linguagem, obter_periodo_ativo
from rest_framework.pagination import PageNumberPagination


class PadraoPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

ORDENACAO_PERMITIDA = {
    'created_at', '-created_at',
    'nome', '-nome',
    'email', '-email',
}

# =============================================================================
# CRIANCAS (Alunos)
# =============================================================================

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_foto_crianca(request, crianca_id):
    """
    Upload de foto da criança para S3: comprime a imagem antes de enviar
    para reduzir o tamanho armazenado.
    """
    try:
        if request.user.perfil not in [
            'admin', 'coordenador', 'professor',
            'professor_infantil', 'professor_fundamental', 'professor_especialista'
        ]:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        arquivo = request.FILES['arquivo']
        validation_error = validate_uploaded_file(
            arquivo,
            ALLOWED_IMAGE_MIME_TYPES,
            ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES,
            "foto"
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)

        crianca = Crianca.objects.get(id=crianca_id)

        arquivo.seek(0)
        conteudo_original = arquivo.read()

        # Comprime/redimensiona antes de subir — reduz de MBs para dezenas/centenas de KB.
        conteudo_comprimido, content_type = compress_image(conteudo_original)

        file_hash = hashlib.sha256(conteudo_comprimido).hexdigest()
        storage_path = f"fotos-criancas/{crianca_id}/{file_hash}.jpg"

        storage_key, arquivo_url = upload_bytes_to_storage(
            storage_path,
            conteudo_comprimido,
            content_type
        )

        crianca.foto_storage_key = storage_key
        crianca.foto_url = arquivo_url
        crianca.save(update_fields=['foto_storage_key', 'foto_url'])

        logger.info(
            "Foto da criança atualizada.",
            extra={
                "crianca_id": str(crianca_id),
                "storage_key": storage_key,
                "tamanho_original": len(conteudo_original),
                "tamanho_comprimido": len(conteudo_comprimido),
            },
        )

        return Response({'success': True, 'foto_url': arquivo_url}, status=status.HTTP_200_OK)
    except Crianca.DoesNotExist:
        return Response(
            {'error': 'Criança não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception("Erro ao fazer upload da foto da criança.")
        return Response(
            {'error': 'Erro ao fazer upload da foto', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['GET'])
def detalhe_crianca(request, crianca_id):
    """Retorna detalhes de uma criança específica."""
    try:
        crianca = Crianca.objects.get(id=crianca_id)
        serializer = CriancaSerializer(crianca)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Crianca.DoesNotExist:
        return Response(
            {'error': 'Criança não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao buscar criança', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def criar_crianca(request):
    """Cria uma nova criança."""
    try:

        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CriancaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar criança', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
def atualizar_crianca(request, crianca_id):
    """Atualiza dados de uma criança."""
    try:

        crianca = Crianca.objects.get(id=crianca_id)
        serializer = CriancaSerializer(
            crianca,
            data=request.data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Crianca.DoesNotExist:
        return Response(
            {'error': 'Criança não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar criança', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_crianca(request, crianca_id):
    """Remove uma criança (soft delete via status)."""
    try:

        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        crianca = Crianca.objects.get(id=crianca_id)
        # Soft delete - apenas marca como inativo
        crianca.status_vinculo = 'inativo'
        crianca.save()
        return Response(
            {'success': True, 'message': 'Criança desativada'},
            status=status.HTTP_200_OK
        )
    except Crianca.DoesNotExist:
        return Response(
            {'error': 'Criança não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao deletar criança', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_criancas_especialista(request):
    """
    Lista as crianças vinculadas a um especialista através da tabela
    SessaoEspecialista (ou seja: crianças para as quais o especialista já
    registrou ao menos uma sessão de atendimento).

    Query params:
      - especialista_id (obrigatório)
      - turma_id (opcional) — restringe às crianças dessa turma
        (campo direto Crianca.turma_id, a mesma turma selecionada na navbar).

    Retorna, por criança: dados básicos + `ultima_sessao_em` (data do
    atendimento mais recente) + `sessoes_realizadas` (contagem total de
    sessões registradas).
    """
    try:
        especialista_id = request.GET.get('especialista_id')
        if not especialista_id:
            return Response(
                {'error': 'especialista_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        turma_id = request.GET.get('turma_id')

        filtros = {'sessoes_especialista__especialista_id': especialista_id}
        if turma_id:
            filtros['turma_id'] = turma_id

        criancas = (
            Crianca.objects.filter(**filtros)
            .distinct()
            .annotate(
                ultima_sessao_em=Max('sessoes_especialista__data_atendimento'),
                sessoes_realizadas=Count('sessoes_especialista', distinct=True),
            )
            .values('id', 'nome_completo', 'ultima_sessao_em', 'sessoes_realizadas')
            .order_by('nome_completo')
        )

        return Response(list(criancas), status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erro ao listar crianças do especialista: {str(e)}")
        return Response(
            {'error': 'Erro ao listar crianças do especialista', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_registros_voz_especialista(request):
    """
    Lista os registros de voz (ObservacaoTranscricao, tipo_observacao=
    'TRANSCRICAO_IA') feitos pela professora, restritos aos alunos
    acompanhados pelo especialista (crianças com ao menos uma
    SessaoEspecialista registrada por ele). Suporta busca textual, filtro
    por intervalo de datas e paginação — usado tanto no card resumido da
    home quanto na página de listagem completa.

    Nota: ObservacaoTranscricao.crianca_id é um CharField opcional (nem
    sempre preenchido pelo frontend no momento do salvamento) — não é uma
    FK real para Crianca. Quando ausente, o vínculo cai para
    ObservacaoTranscricao.aluno_nome (string, comparado com
    Crianca.nome_completo) como alternativa — por isso um registro sem
    crianca_id ainda pode aparecer aqui, desde que o nome bata exatamente.

    Query params:
      - especialista_id (obrigatório)
      - turma_id (opcional) — restringe às crianças dessa turma
        (campo direto Crianca.turma_id, a mesma turma selecionada na navbar)
      - busca (opcional) — filtra por nome do aluno, nome da professora
        ou texto do resumo (case-insensitive, icontains)
      - data_inicio (opcional, formato YYYY-MM-DD) — filtra
        data_observacao >= data_inicio
      - data_fim (opcional, formato YYYY-MM-DD) — filtra
        data_observacao <= data_fim
      - limite (opcional, default 10)
      - offset (opcional, default 0)

    Resposta: { resultados, total, offset, limite, tem_mais }
    """
    try:
        especialista_id = request.GET.get('especialista_id')
        if not especialista_id:
            return Response(
                {'error': 'especialista_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            limite = int(request.GET.get('limite', 10))
        except (TypeError, ValueError):
            limite = 10

        try:
            offset = int(request.GET.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0

        turma_id = request.GET.get('turma_id')
        busca = request.GET.get('busca', '').strip()
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')

        filtros_criancas = {'sessoes_especialista__especialista_id': especialista_id}
        if turma_id:
            filtros_criancas['turma_id'] = turma_id

        criancas_vinculadas = (
            Crianca.objects.filter(**filtros_criancas)
            .values('id', 'nome_completo')
            .distinct()
        )
        # ObservacaoTranscricao.crianca_id é CharField (não FK) -> comparar como string.
        crianca_ids_str = [str(c['id']) for c in criancas_vinculadas]
        nomes_criancas = [c['nome_completo'] for c in criancas_vinculadas if c['nome_completo']]

        if not crianca_ids_str:
            return Response(
                {'resultados': [], 'total': 0, 'offset': offset, 'limite': limite, 'tem_mais': False},
                status=status.HTTP_200_OK,
            )

        # Vínculo por crianca_id (FK-like) OU, na ausência/falha dele, por
        # aluno_nome (string) batendo com o nome da criança.
        base_queryset = ObservacaoTranscricao.objects.filter(
            Q(crianca_id__in=crianca_ids_str) | Q(aluno_nome__in=nomes_criancas),
            tipo_observacao='TRANSCRICAO_IA',
        )

        if busca:
            base_queryset = base_queryset.filter(
                Q(aluno_nome__icontains=busca) |
                Q(professora_nome__icontains=busca) |
                Q(observacao_texto__icontains=busca)
            )

        if data_inicio:
            base_queryset = base_queryset.filter(data_observacao__gte=data_inicio)
        if data_fim:
            base_queryset = base_queryset.filter(data_observacao__lte=data_fim)

        base_queryset = base_queryset.order_by('-data_criacao')

        total = base_queryset.count()
        pagina = base_queryset[offset:offset + limite]

        registros = [
            {
                'id': obs.id,
                'crianca_id': obs.crianca_id,
                'aluno_nome': obs.aluno_nome,
                'resumo': obs.observacao_texto,
                'professora_nome': obs.professora_nome,
                'turma_nome': obs.turma_nome,
                'data_observacao': obs.data_observacao.isoformat() if obs.data_observacao else None,
                'data_criacao': obs.data_criacao.isoformat() if obs.data_criacao else None,
            }
            for obs in pagina
        ]

        return Response(
            {
                'resultados': registros,
                'total': total,
                'offset': offset,
                'limite': limite,
                'tem_mais': offset + limite < total,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Erro ao listar registros de voz do especialista: {str(e)}")
        return Response(
            {'error': 'Erro ao listar registros de voz', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_observacoes_transcricao_crianca(request, crianca_id):
    """
    Lista os registros de voz (ObservacaoTranscricao, tipo_observacao=
    'TRANSCRICAO_IA') de uma criança específica, paginados (mais recentes
    primeiro). Usado na aba "Da escola" do perfil da criança na visão do
    especialista, com paginação incremental ("Carregar mais").

    Vínculo com a criança: ObservacaoTranscricao.crianca_id é CharField
    (não FK) — usado como vínculo primário, comparado como string. Quando
    ausente/não bate, cai para ObservacaoTranscricao.aluno_nome (string)
    comparado com Crianca.nome_completo, para não perder registros antigos
    que só têm o nome preenchido.

    Query params:
      - limite (opcional, default 10)
      - offset (opcional, default 0)
    """
    try:
        try:
            limite = int(request.GET.get('limite', 10))
        except (TypeError, ValueError):
            limite = 10

        try:
            offset = int(request.GET.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0

        nome_crianca = (
            Crianca.objects.filter(id=crianca_id)
            .values_list('nome_completo', flat=True)
            .first()
        )

        filtro_vinculo = Q(crianca_id=str(crianca_id))
        if nome_crianca:
            filtro_vinculo |= Q(aluno_nome=nome_crianca)

        base_queryset = ObservacaoTranscricao.objects.filter(
            filtro_vinculo,
            tipo_observacao='TRANSCRICAO_IA',
        ).order_by('-data_criacao')

        total = base_queryset.count()
        pagina = base_queryset[offset:offset + limite]

        registros = [
            {
                'id': obs.id,
                'aluno_nome': obs.aluno_nome,
                'resumo': obs.observacao_texto,
                'professora_nome': obs.professora_nome,
                'turma_nome': obs.turma_nome,
                'data_observacao': obs.data_observacao.isoformat() if obs.data_observacao else None,
                'data_criacao': obs.data_criacao.isoformat() if obs.data_criacao else None,
            }
            for obs in pagina
        ]

        return Response(
            {
                'resultados': registros,
                'total': total,
                'offset': offset,
                'limite': limite,
                'tem_mais': offset + limite < total,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Erro ao listar observações de transcrição da criança: {str(e)}")
        return Response(
            {'error': 'Erro ao listar observações da criança', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_observacao_transcricao(request, observacao_id):
    """Exclui um relato individual (ObservacaoTranscricao).

    Podem excluir: a professora autora do relato e a coordenação (perfis
    'coordenador' e 'admin').

    Exclusão definitiva, sem lixeira. A remoção passa pelo ORM de propósito:
    `AudioDispositivo.observacao` aponta para cá com `on_delete=SET_NULL`, e é
    o Django que anula esse vínculo antes do DELETE. Em SQL cru a FK
    `audios_dispositivo_observacao_id_...` barraria a operação.
    """
    try:
        observacao = ObservacaoTranscricao.objects.get(id=observacao_id)

        perfil = getattr(request.user, 'perfil', '')
        eh_autora = str(observacao.professora_id) == str(request.user.id)
        if not eh_autora and perfil not in ['coordenador', 'admin']:
            return Response(
                {'error': 'Sem permissão para excluir este relato'},
                status=status.HTTP_403_FORBIDDEN
            )

        logger.info(
            "Relato individual excluido: id=%s aluno=%s autora=%s por=%s (%s)",
            observacao.id, observacao.aluno_nome, observacao.professora_id,
            request.user.id, perfil,
        )
        observacao.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)

    except ObservacaoTranscricao.DoesNotExist:
        return Response(
            {'error': 'Relato não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erro ao excluir relato individual: {str(e)}")
        return Response(
            {'error': 'Erro ao excluir relato', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_metas_paee_crianca(request, crianca_id):
    """
    Lista as metas do PAEE (MetaPAEE) de uma criança específica, mais
    recentes primeiro. Usado na aba "PAEE" do perfil da criança na visão
    do especialista.
    """
    try:
        categoria_labels = dict(MetaPAEE.CATEGORIAS)
        status_labels = dict(MetaPAEE.STATUS_CHOICES)

        metas = MetaPAEE.objects.filter(crianca_id=crianca_id).order_by('-data_criacao')

        resultado = [
            {
                'id': str(m.id),
                'categoria': m.categoria,
                'categoria_label': categoria_labels.get(m.categoria, m.categoria),
                'inicio': m.inicio.isoformat() if m.inicio else None,
                'fim': m.fim.isoformat() if m.fim else None,
                'objetivo': m.objetivo,
                'criterio': m.criterio,
                'estrategia': m.estrategia,
                'status': m.status,
                'status_label': status_labels.get(m.status, m.status),
                'data_criacao': m.data_criacao.isoformat() if m.data_criacao else None,
                'data_atualizacao': m.data_atualizacao.isoformat() if m.data_atualizacao else None,
            }
            for m in metas
        ]

        return Response(resultado, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erro ao listar metas PAEE da criança: {str(e)}")
        return Response(
            {'error': 'Erro ao listar metas PAEE', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# RELATORIOS
# =============================================================================

@api_view(['GET'])
def listar_relatorios(request):
    """
    Lista relatórios com filtros opcionais.
    Query params: id_crianca, instituicao_id, data_inicio (ou data_criacao__gte),
    data_fim (ou data_criacao__lte)

    O campo `conteudo` (TextField pesado) é omitido da listagem. Em seu lugar
    vai `finalizado: bool`, derivado de `LENGTH(SUBSTRING(conteudo, 1, 51)) > 50`:
    só os primeiros 51 caracteres são lidos, evitando o detoast da coluna inteira
    no Postgres. Para obter o HTML completo, use GET /relatorios/<id>/.
    """
    from django.db.models.functions import Length, Substr

    try:
        queryset = Relatorio.objects.annotate(
            conteudo_length=Length(Substr('conteudo', 1, 51))
        ).select_related('template').defer('conteudo')

        id_crianca = request.GET.get('id_crianca')
        instituicao_id = request.GET.get('instituicao_id')
        data_inicio = (
            request.GET.get('data_inicio')
            or request.GET.get('data_criacao__gte')
        )
        data_fim = (
            request.GET.get('data_fim')
            or request.GET.get('data_criacao__lte')
        )

        if id_crianca:
            queryset = queryset.filter(id_crianca=id_crianca)
        if instituicao_id:
            queryset = queryset.filter(instituicao_id=instituicao_id)
        if data_inicio:
            queryset = queryset.filter(data_criacao__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_criacao__lte=data_fim)

        serializer = RelatorioListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar relatórios', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def salvar_relatorio(request):
    """
    Salva um novo relatório no banco.
    Substitui a chamada direta ao banco no frontend.
    """
    try:
        id_crianca = request.data.get('id_crianca')
        periodo = request.data.get('periodo')
        instituicao_id = getattr(request.user, 'instituicao_id', None)

        if not instituicao_id:
            return Response(
                {'error': 'Usuário sem instituição associada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if id_crianca and periodo:
            relatorio_existente = Relatorio.objects.filter(
                id_crianca=id_crianca,
                periodo=periodo,
                instituicao_id=instituicao_id,
            ).order_by('-data_criacao').first()

            if relatorio_existente:
                logger.info(
                    "Relatório já existente para criança e período.",
                    extra={
                        "id_crianca": str(id_crianca),
                        "periodo": periodo,
                    },
                )

                return Response(
                    {
                        "already_exists": True,
                        "relatorio": RelatorioSerializer(
                            relatorio_existente
                        ).data,
                    },
                    status=status.HTTP_200_OK,
                )

        serializer = RelatorioCreateSerializer(
            data=request.data,
            context={'instituicao_id': instituicao_id},
        )

        if serializer.is_valid():
            try:
                save_kwargs = {}

                # Se o payload não informar um template,
                # utiliza o template ativo da instituição.
                if not serializer.validated_data.get('template'):
                    template_ativo = RelatorioTemplate.objects.filter(
                        instituicao_id=instituicao_id,
                        ativo=True,
                    ).first()

                    if template_ativo:
                        save_kwargs['template'] = template_ativo

                relatorio = serializer.save(
                    instituicao_id=instituicao_id,
                    **save_kwargs,
                )

                return Response(
                    RelatorioSerializer(relatorio).data,
                    status=status.HTTP_201_CREATED,
                )

            except IntegrityError:
                relatorio_existente = Relatorio.objects.filter(
                    id_crianca=id_crianca,
                    periodo=periodo,
                    instituicao_id=instituicao_id,
                ).order_by('-data_criacao').first()

                if relatorio_existente:
                    return Response(
                        {
                            "already_exists": True,
                            "relatorio": RelatorioSerializer(
                                relatorio_existente
                            ).data,
                        },
                        status=status.HTTP_200_OK,
                    )

                return Response(
                    {'error': 'Relatório duplicado não permitido.'},
                    status=status.HTTP_409_CONFLICT,
                )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.exception("Erro ao salvar relatório.")

        return Response(
            {
                'error': 'Erro ao salvar relatório',
                'details': str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_pdf_relatorio(request, relatorio_id):
    """
    Recebe um PDF gerado no frontend, envia ao S3
    e atualiza o pdf_url do relatório.
    """
    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
    except Relatorio.DoesNotExist:
        return Response(
            {'error': 'Relatório não encontrado'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        if not is_s3_configured():
            return Response(
                {'error': 'S3 não configurado. Verifique as credenciais.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(request.user, "instituicao_id") and relatorio.instituicao_id:
            if request.user.instituicao_id != relatorio.instituicao_id:
                return Response(
                    {'error': 'Permissão negada para este relatório.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        pdf_file = request.FILES.get('file')

        if not pdf_file:
            return Response(
                {'error': 'Arquivo PDF não enviado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = (
            getattr(pdf_file, 'content_type', None)
            or 'application/pdf'
        )

        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        storage_key = f"relatorios/{relatorio_id}/{timestamp}.pdf"

        stored_key, pdf_url = upload_bytes_to_storage(
            storage_key,
            pdf_file.read(),
            content_type=content_type,
        )

        relatorio.pdf_url = pdf_url
        relatorio.pdf_storage_key = stored_key

        relatorio.save(
            update_fields=[
                'pdf_url',
                'pdf_storage_key',
            ]
        )

        logger.info(
            "PDF do relatório atualizado.",
            extra={
                "relatorio_id": str(relatorio_id),
                "storage_key": storage_key,
            },
        )

        return Response(
            {'pdf_url': pdf_url},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.exception(
            "Erro ao salvar PDF do relatório.",
            extra={"relatorio_id": str(relatorio_id)},
        )

        return Response(
            {
                'error': 'Erro ao salvar PDF do relatório',
                'details': str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_pdf_relatorio(request, relatorio_id):
    """
    Regenera a URL presigned do PDF do relatório
    a partir da chave no storage.
    """
    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
    except Relatorio.DoesNotExist:
        return Response(
            {'error': 'Relatório não encontrado'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        if not is_s3_configured():
            return Response(
                {'error': 'S3 não configurado. Verifique as credenciais.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(request.user, "instituicao_id") and relatorio.instituicao_id:
            if request.user.instituicao_id != relatorio.instituicao_id:
                return Response(
                    {'error': 'Permissão negada para este relatório.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        storage_key = relatorio.pdf_storage_key

        if not storage_key and relatorio.pdf_url:
            storage_key = extract_storage_key_from_url(
                relatorio.pdf_url
            )

            if storage_key:
                relatorio.pdf_storage_key = storage_key

        if not storage_key:
            return Response(
                {'error': 'Chave do PDF não encontrada para atualização.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_url = generate_presigned_url(storage_key)

        if not new_url:
            return Response(
                {'error': 'Falha ao gerar URL do PDF.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        relatorio.pdf_url = new_url

        update_fields = ['pdf_url']

        if relatorio.pdf_storage_key != storage_key:
            relatorio.pdf_storage_key = storage_key
            update_fields.append('pdf_storage_key')

        relatorio.save(update_fields=update_fields)

        logger.info(
            "URL presigned do relatório regenerada.",
            extra={
                "relatorio_id": str(relatorio_id),
                "storage_key": storage_key,
            },
        )

        return Response(
            {'pdf_url': new_url},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.exception(
            "Erro ao regenerar PDF do relatório.",
            extra={"relatorio_id": str(relatorio_id)},
        )

        return Response(
            {
                'error': 'Erro ao regenerar PDF do relatório',
                'details': str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_templates_relatorio(request):
    instituicao_id = getattr(request.user, 'instituicao_id', None)
    if not instituicao_id:
        return Response({'error': 'Usuário sem instituição associada.'}, status=status.HTTP_400_BAD_REQUEST)
 
    qs = RelatorioTemplate.objects.filter(instituicao_id=instituicao_id)
 
    leve = request.query_params.get('leve') == '1'
    serializer_cls = RelatorioTemplateListSerializer if leve else RelatorioTemplateSerializer
    return Response(serializer_cls(qs, many=True).data)
 
 
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_template_relatorio(request):
    instituicao_id = getattr(request.user, 'instituicao_id', None)

    if not instituicao_id:
        return Response(
            {'error': 'Usuário sem instituição associada.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    dados = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

    dados.pop('instituicao_id', None)
    dados.pop('ativo', None)

    modelo = dados.get('modelo')

    if not modelo:
        return Response(
            {'error': 'O modelo do template é obrigatório.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    existente = RelatorioTemplate.objects.filter(
        instituicao_id=instituicao_id,
        modelo=modelo,
    ).first()

    if existente:
        return Response(
            {
                'error': 'Já existe um template para este modelo.',
                'template_id': str(existente.id),
            },
            status=status.HTTP_409_CONFLICT
        )

    dados['ativo'] = True
    serializer = RelatorioTemplateSerializer(data=dados)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        RelatorioTemplate.objects.select_for_update().filter(
            instituicao_id=instituicao_id,
            ativo=True,
        ).update(ativo=False)
        template = serializer.save(
            instituicao_id=instituicao_id,
            ativo=True,
        )

    logger.info(
        "Template de relatório criado e ativado.",
        extra={
            "template_id": str(template.id),
            "instituicao_id": str(instituicao_id),
        },
    )

    return Response(
        RelatorioTemplateSerializer(template).data,
        status=status.HTTP_201_CREATED
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_template_relatorio(request, template_id):
    instituicao_id = getattr(request.user, 'instituicao_id', None)
    template = RelatorioTemplate.objects.filter(id=template_id, instituicao_id=instituicao_id).first()
    if not template:
        return Response({'error': 'Template não encontrado'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RelatorioTemplateSerializer(template).data)
 
 
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def atualizar_template_relatorio(request, template_id):
    instituicao_id = getattr(request.user, 'instituicao_id', None)
    template = RelatorioTemplate.objects.filter(id=template_id, instituicao_id=instituicao_id).first()
    if not template:
        return Response({'error': 'Template não encontrado'}, status=status.HTTP_404_NOT_FOUND)
 
    dados = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    dados.pop('instituicao_id', None)
    dados.pop('ativo', None)
 
    serializer = RelatorioTemplateSerializer(template, data=dados, partial=True)
    serializer.is_valid(raise_exception=True)
    template = serializer.save()
 
    logger.info("Template de relatório atualizado.", extra={"template_id": str(template.id)})
    return Response(RelatorioTemplateSerializer(template).data)
 
 
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_template_relatorio(request, template_id):
    instituicao_id = getattr(request.user, 'instituicao_id', None)
    template = RelatorioTemplate.objects.filter(id=template_id, instituicao_id=instituicao_id).first()
    if not template:
        return Response({'error': 'Template não encontrado'}, status=status.HTTP_404_NOT_FOUND)
 
    if template.ativo:
        return Response(
            {'error': 'Não é possível excluir o template ativo. Ative outro template antes de excluir este.'},
            status=status.HTTP_409_CONFLICT,
        )
 
    em_uso = template.relatorios.exists()
    if em_uso:
        return Response(
            {'error': 'Este template já foi usado em relatórios existentes e não pode ser excluído.'},
            status=status.HTTP_409_CONFLICT,
        )
 
    template.delete()
    logger.info("Template de relatório deletado.", extra={"template_id": str(template_id)})
    return Response({'success': True})
 
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ativar_template_relatorio(request, template_id):
    instituicao_id = getattr(request.user, 'instituicao_id', None)

    if not instituicao_id:
        return Response(
            {'error': 'Usuário sem instituição associada.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        template = RelatorioTemplate.objects.select_for_update().filter(
            id=template_id,
            instituicao_id=instituicao_id,
        ).first()

        if not template:
            return Response(
                {'error': 'Template não encontrado'},
                status=status.HTTP_404_NOT_FOUND,
            )

        RelatorioTemplate.objects.select_for_update().filter(
            instituicao_id=instituicao_id,
            ativo=True,
        ).exclude(
            id=template.id,
        ).update(
            ativo=False,
        )

        if not template.ativo:
            template.ativo = True
            template.save(update_fields=['ativo', 'updated_at'])

    logger.info(
        "Template de relatório ativado.",
        extra={
            "template_id": str(template.id),
            "instituicao_id": str(instituicao_id),
        },
    )

    return Response(
        RelatorioTemplateSerializer(template).data,
    )
 
# =============================================================================
# REGISTROS DE OBSERVACAO
# =============================================================================

@api_view(['GET'])
def listar_registros_observacao(request):
    """
    Lista registros de observação com filtros.
    Query params: crianca_id, crianca_id__in, turma_id, turma_id__in, instituicao_id, professor_id, data_inicio, data_fim
    """
    try:
        queryset = RegistroObservacao.objects.all()

        crianca_id = request.GET.get('crianca_id')
        crianca_id_in = request.GET.get('crianca_id__in')
        turma_id = request.GET.get('turma_id')
        turma_id_in = request.GET.get('turma_id__in')
        instituicao_id = (
            request.GET.get('instituicao_id')
            or request.GET.get('turmas.instituicao_id')
            or request.GET.get('criancas.instituicao_id')
        )
        professor_id = request.GET.get('professor_id')
        data_inicio = (
            request.GET.get('data_inicio')
            or request.GET.get('data_observacao__gte')
        )
        data_fim = (
            request.GET.get('data_fim')
            or request.GET.get('data_observacao__lte')
        )

        def split_csv(value: str):
            return [item for item in value.split(',') if item]

        requires_crianca_lookup = any([turma_id, turma_id_in, instituicao_id])
        if requires_crianca_lookup:
            criancas = Crianca.objects.all()

            if turma_id:
                criancas = criancas.filter(turma_id=turma_id)
            if turma_id_in:
                criancas = criancas.filter(turma_id__in=split_csv(turma_id_in))
            if instituicao_id:
                criancas = criancas.filter(instituicao_id=instituicao_id)
            if crianca_id:
                criancas = criancas.filter(id=crianca_id)
            if crianca_id_in:
                criancas = criancas.filter(id__in=split_csv(crianca_id_in))

            queryset = queryset.filter(crianca_id__in=criancas.values_list('id', flat=True))
        else:
            if crianca_id:
                queryset = queryset.filter(crianca_id=crianca_id)
            if crianca_id_in:
                queryset = queryset.filter(crianca_id__in=split_csv(crianca_id_in))

        if professor_id:
            queryset = queryset.filter(professor_id=professor_id)
        if data_inicio:
            queryset = queryset.filter(data_observacao__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_observacao__lte=data_fim)

        serializer = RegistroObservacaoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar registros de observação', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def criar_registro_observacao(request):
    """Cria um novo registro de observação."""
    try:
        serializer = RegistroObservacaoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar registro de observação', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def criar_registros_observacao_lote(request):
    """Cria múltiplos registros de observação em lote."""
    try:
        payload = request.data
        registros = payload if isinstance(payload, list) else payload.get('registros', [])
        if not registros:
            return Response(
                {'error': 'Nenhum registro fornecido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        criados = []
        erros = []

        def normalize_registro(raw):
            if not isinstance(raw, dict):
                return None
            normalized = {}
            if 'professor_id' in raw:
                normalized['professor_id'] = raw['professor_id']
            elif 'usuario_id' in raw:
                normalized['professor_id'] = raw['usuario_id']
            if 'observacao' in raw:
                normalized['observacao'] = raw['observacao']
            elif 'comentario' in raw:
                normalized['observacao'] = raw['comentario']
            for field in ('crianca_id', 'pergunta_id', 'resposta', 'data_observacao'):
                if field in raw:
                    normalized[field] = raw[field]
            return normalized

        for index, registro in enumerate(registros):
            normalized = normalize_registro(registro)
            if normalized is None:
                erros.append({
                    'indice': index,
                    'registro': registro,
                    'erros': {'registro': ['Formato inválido, esperado objeto JSON.']}
                })
                continue
            serializer = RegistroObservacaoSerializer(data=normalized)
            if serializer.is_valid():
                serializer.save()
                criados.append(serializer.data)
            else:
                erros.append({'indice': index, 'registro': registro, 'erros': serializer.errors})

        return Response({
            'success': True,
            'criados': len(criados),
            'erros': len(erros),
            'detalhes_erros': erros if erros else None
        }, status=status.HTTP_201_CREATED if criados else status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception('Erro ao criar registros de observacao em lote')
        return Response(
            {'error': 'Erro ao criar registros em lote', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# PRODUCOES (Portfolio)
# =============================================================================

@api_view(['GET'])
def listar_producoes_crianca(request):
    """
    Lista produções das crianças (portfólio).
    Query params: crianca_id, crianca_id__in, turma_id, turma_id__in, instituicao_id
    """
    try:
        queryset = ProducaoCrianca.objects.all()

        crianca_id = request.GET.get('crianca_id')
        crianca_id_in = request.GET.get('crianca_id__in')
        turma_id = request.GET.get('turma_id')
        turma_id_in = request.GET.get('turma_id__in')
        instituicao_id = request.GET.get('instituicao_id')

        def split_csv(value: str):
            return [item for item in value.split(',') if item]

        if crianca_id:
            queryset = queryset.filter(crianca_id=crianca_id)
        if crianca_id_in:
            queryset = queryset.filter(crianca_id__in=split_csv(crianca_id_in))
        if turma_id:
            queryset = queryset.filter(turma_id=turma_id)
        if turma_id_in:
            queryset = queryset.filter(turma_id__in=split_csv(turma_id_in))
        if instituicao_id:
            queryset = queryset.filter(instituicao_id=instituicao_id)

        serializer = ProducaoCriancaSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar produções', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def criar_producao_crianca(request):
    """Cria uma nova produção de criança."""
    try:
        serializer = ProducaoCriancaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar produção', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
def atualizar_producao_crianca(request, producao_id):
    """Atualiza uma produção existente."""
    try:
        producao = ProducaoCrianca.objects.get(id=producao_id)
        serializer = ProducaoCriancaSerializer(
            producao,
            data=request.data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except ProducaoCrianca.DoesNotExist:
        return Response(
            {'error': 'Produção não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar produção', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
def deletar_producao_crianca(request, producao_id):
    """Remove uma produção."""
    try:
        producao = ProducaoCrianca.objects.get(id=producao_id)
        producao.delete()
        return Response(
            {'success': True, 'message': 'Produção removida'},
            status=status.HTTP_200_OK
        )
    except ProducaoCrianca.DoesNotExist:
        return Response(
            {'error': 'Produção não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao deletar produção', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# PERGUNTAS BNCC
# =============================================================================

@api_view(['GET'])
def listar_perguntas_bncc(request):
    """
    Lista perguntas BNCC com filtros.
    Query params: faixa_etaria, campo_experiencia, ids (CSV)
    """
    try:
        queryset = PerguntaBNCC.objects.all()

        faixa_etaria = request.GET.get('faixa_etaria')
        faixa_etaria_icontains = request.GET.get('faixa_etaria__icontains')
        campo_experiencia = request.GET.get('campo_experiencia')
        ids = request.GET.get('ids')

        def split_csv(value: str):
            return [item for item in value.split(',') if item]

        if faixa_etaria:
            queryset = queryset.filter(faixa_etaria=faixa_etaria)
        elif faixa_etaria_icontains:
            queryset = queryset.filter(faixa_etaria__icontains=faixa_etaria_icontains)
        if campo_experiencia:
            queryset = queryset.filter(campo_experiencia__icontains=campo_experiencia)
        if ids:
            queryset = queryset.filter(id__in=split_csv(ids))

        serializer = PerguntaBNCCSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar perguntas BNCC', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def criar_pergunta_bncc(request):
    """
    Cria uma nova pergunta BNCC.
    """
    try:
        serializer = PerguntaBNCCSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(
            {'error': 'Dados inválidos', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar pergunta BNCC', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_pergunta_bncc(request, pergunta_id):
    """
    Atualiza uma pergunta BNCC existente.
    """
    try:
        pergunta = PerguntaBNCC.objects.get(id=pergunta_id)
        serializer = PerguntaBNCCSerializer(pergunta, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {'error': 'Dados inválidos', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    except PerguntaBNCC.DoesNotExist:
        return Response(
            {'error': 'Pergunta não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar pergunta BNCC', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def deletar_pergunta_bncc(request, pergunta_id):
    """
    Remove uma pergunta BNCC.
    """
    try:
        pergunta = PerguntaBNCC.objects.get(id=pergunta_id)
        pergunta.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)
    except PerguntaBNCC.DoesNotExist:
        return Response(
            {'error': 'Pergunta não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao deletar pergunta BNCC', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# PERGUNTAS DE ESPECIALISTAS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas_especialistas(request):
    """
    Lista perguntas de especialistas com filtros opcionais.
    Query params: instituicao_id, nivel, especialidade, status
    """
    try:
        user = request.user
        queryset = PerguntaEspecialista.objects.all()

        instituicao_id_param = request.GET.get('instituicao_id')
        nivel = request.GET.get('nivel')
        especialidade = request.GET.get('especialidade')
        status_filter = request.GET.get('status')

        user_instituicao_id = getattr(user, 'instituicao_id', None)
        if user_instituicao_id:
            if instituicao_id_param and str(instituicao_id_param) != str(user_instituicao_id):
                logger.warning(
                    "Tentativa de listar perguntas de outra instituição.",
                    extra={
                        "user_id": str(user.id),
                        "perfil": user.perfil,
                        "instituicao_id_param": str(instituicao_id_param),
                        "instituicao_id_user": str(user_instituicao_id),
                    },
                )
                return Response(
                    {'error': 'Acesso negado para a instituição informada.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            queryset = queryset.filter(
                Q(instituicao_id=user_instituicao_id) | Q(instituicao_id__isnull=True)
            )
        elif instituicao_id_param:
            queryset = queryset.filter(instituicao_id=instituicao_id_param)
        if nivel:
            queryset = queryset.filter(nivel=nivel)
        if especialidade:
            queryset = queryset.filter(especialidade=especialidade)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = PerguntaEspecialistaSerializer(queryset, many=True)
        logger.info(
            "Perguntas de especialistas listadas com sucesso.",
            extra={
                "user_id": str(user.id),
                "perfil": user.perfil,
                "total_perguntas": len(serializer.data),
            },
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(
            "Erro inesperado ao listar perguntas de especialistas.",
            extra={
                "user_id": str(getattr(request.user, 'id', 'anon')),
                "perfil": getattr(request.user, 'perfil', 'anon'),
            },
        )
        return Response(
            {'error': 'Erro ao listar perguntas de especialistas', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def criar_pergunta_especialista(request):
    """Cria uma nova pergunta de especialista."""
    try:
        user = request.user
        user_instituicao_id = getattr(user, 'instituicao_id', None)
        instituicao_id_param = request.data.get('instituicao_id')

        if user_instituicao_id:
            if instituicao_id_param and str(instituicao_id_param) != str(user_instituicao_id):
                logger.warning(
                    "Tentativa de criar pergunta para outra instituição.",
                    extra={
                        "user_id": str(user.id),
                        "perfil": user.perfil,
                        "instituicao_id_param": str(instituicao_id_param),
                        "instituicao_id_user": str(user_instituicao_id),
                    },
                )
                return Response(
                    {'error': 'Acesso negado para a instituição informada.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        data = request.data.copy()
        if user_instituicao_id:
            data['instituicao_id'] = str(user_instituicao_id)

        for field in ('especialidade', 'nivel', 'pergunta', 'pergunta_facilitadora', 'referencia_norma', 'status'):
            value = data.get(field)
            if isinstance(value, str):
                data[field] = value.strip()

        serializer = PerguntaEspecialistaSerializer(data=data)
        if serializer.is_valid():
            pergunta = serializer.save()
            logger.info(
                "Pergunta de especialista criada com sucesso.",
                extra={
                    "user_id": str(user.id),
                    "perfil": user.perfil,
                    "pergunta_id": str(pergunta.id),
                    "instituicao_id": str(pergunta.instituicao_id) if pergunta.instituicao_id else None,
                },
            )
            return Response(PerguntaEspecialistaSerializer(pergunta).data, status=status.HTTP_201_CREATED)
        return Response(
            {'error': 'Dados inválidos para criar pergunta', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    except IntegrityError as e:
        logger.exception("Erro de integridade ao criar pergunta de especialista.")
        return Response(
            {'error': 'Erro de integridade ao criar pergunta', 'details': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.exception(
            "Erro inesperado ao criar pergunta de especialista.",
            extra={
                "user_id": str(getattr(request.user, 'id', 'anon')),
                "perfil": getattr(request.user, 'perfil', 'anon'),
            },
        )
        return Response(
            {'error': 'Erro ao criar pergunta de especialista', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def atualizar_pergunta_especialista(request, pergunta_id):
    """Atualiza uma pergunta de especialista."""
    try:
        user = request.user
        pergunta = PerguntaEspecialista.objects.get(id=pergunta_id)
        user_instituicao_id = getattr(user, 'instituicao_id', None)

        if user_instituicao_id and pergunta.instituicao_id and str(pergunta.instituicao_id) != str(user_instituicao_id):
            logger.warning(
                "Tentativa de atualizar pergunta de outra instituição.",
                extra={
                    "user_id": str(user.id),
                    "perfil": user.perfil,
                    "pergunta_id": str(pergunta_id),
                    "instituicao_id_pergunta": str(pergunta.instituicao_id),
                    "instituicao_id_user": str(user_instituicao_id),
                },
            )
            return Response(
                {'error': 'Acesso negado para a pergunta informada.'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        if user_instituicao_id:
            data['instituicao_id'] = str(user_instituicao_id)

        for field in ('especialidade', 'nivel', 'pergunta', 'pergunta_facilitadora', 'referencia_norma', 'status'):
            value = data.get(field)
            if isinstance(value, str):
                data[field] = value.strip()

        serializer = PerguntaEspecialistaSerializer(
            pergunta,
            data=data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            pergunta = serializer.save()
            logger.info(
                "Pergunta de especialista atualizada com sucesso.",
                extra={
                    "user_id": str(user.id),
                    "perfil": user.perfil,
                    "pergunta_id": str(pergunta.id),
                },
            )
            return Response(PerguntaEspecialistaSerializer(pergunta).data, status=status.HTTP_200_OK)
        return Response(
            {'error': 'Dados inválidos para atualizar pergunta', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    except PerguntaEspecialista.DoesNotExist:
        return Response(
            {'error': 'Pergunta não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception(
            "Erro inesperado ao atualizar pergunta de especialista.",
            extra={
                "user_id": str(getattr(request.user, 'id', 'anon')),
                "perfil": getattr(request.user, 'perfil', 'anon'),
                "pergunta_id": str(pergunta_id),
            },
        )
        return Response(
            {'error': 'Erro ao atualizar pergunta de especialista', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_pergunta_especialista(request, pergunta_id):
    """Remove uma pergunta de especialista."""
    try:
        user = request.user
        pergunta = PerguntaEspecialista.objects.get(id=pergunta_id)
        user_instituicao_id = getattr(user, 'instituicao_id', None)

        if user_instituicao_id and pergunta.instituicao_id and str(pergunta.instituicao_id) != str(user_instituicao_id):
            logger.warning(
                "Tentativa de deletar pergunta de outra instituição.",
                extra={
                    "user_id": str(user.id),
                    "perfil": user.perfil,
                    "pergunta_id": str(pergunta_id),
                    "instituicao_id_pergunta": str(pergunta.instituicao_id),
                    "instituicao_id_user": str(user_instituicao_id),
                },
            )
            return Response(
                {'error': 'Acesso negado para a pergunta informada.'},
                status=status.HTTP_403_FORBIDDEN
            )

        pergunta.delete()
        logger.info(
            "Pergunta de especialista removida com sucesso.",
            extra={
                "user_id": str(user.id),
                "perfil": user.perfil,
                "pergunta_id": str(pergunta_id),
            },
        )
        return Response(
            {'success': True, 'message': 'Pergunta removida'},
            status=status.HTTP_200_OK
        )
    except PerguntaEspecialista.DoesNotExist:
        return Response(
            {'error': 'Pergunta não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception(
            "Erro inesperado ao deletar pergunta de especialista.",
            extra={
                "user_id": str(getattr(request.user, 'id', 'anon')),
                "perfil": getattr(request.user, 'perfil', 'anon'),
                "pergunta_id": str(pergunta_id),
            },
        )
        return Response(
            {'error': 'Erro ao deletar pergunta de especialista', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# CALENDARIO BIMESTRES
# =============================================================================

@api_view(['GET'])
def listar_calendario_bimestres(request):
    """
    Lista calendário de bimestres.
    Query params: ano, instituicao_id, data_inicio__lte, data_fim__gte
    """
    try:
        queryset = CalendarioBimestre.objects.all()

        ano = request.GET.get('ano')
        instituicao_id = request.GET.get('instituicao_id')
        data_inicio_lte = request.GET.get('data_inicio__lte')
        data_fim_gte = request.GET.get('data_fim__gte')

        if ano:
            queryset = queryset.filter(ano=ano)
        if instituicao_id:
            queryset = queryset.filter(instituicao_id=instituicao_id)
        if data_inicio_lte:
            queryset = queryset.filter(data_inicio__lte=data_inicio_lte)
        if data_fim_gte:
            queryset = queryset.filter(data_fim__gte=data_fim_gte)

        serializer = CalendarioBimestreSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar calendário', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# PERIODOS AVALIATIVOS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_periodos_avaliativos(request):
    """
    Lista períodos avaliativos com filtros.
    Query params: instituicao_id, data_inicio__lte, data_fim__gte
    """
    try:
        queryset = PeriodoAvaliativo.objects.all()

        instituicao_id = request.GET.get('instituicao_id')
        data_inicio_lte = request.GET.get('data_inicio__lte')
        data_fim_gte = request.GET.get('data_fim__gte')

        if instituicao_id:
            queryset = queryset.filter(instituicao_id=instituicao_id)
        if data_inicio_lte:
            queryset = queryset.filter(data_inicio__lte=data_inicio_lte)
        if data_fim_gte:
            queryset = queryset.filter(data_fim__gte=data_fim_gte)

        serializer = PeriodoAvaliativoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("Erro ao listar períodos avaliativos.")
        return Response(
            {'error': 'Erro ao listar períodos avaliativos', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_periodo_avaliativo(request):
    """Cria um novo período avaliativo."""
    try:
        serializer = PeriodoAvaliativoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Erro ao criar período avaliativo.")
        return Response(
            {'error': 'Erro ao criar período avaliativo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_periodo_avaliativo(request, periodo_id):
    """Atualiza um período avaliativo existente."""
    try:
        periodo = PeriodoAvaliativo.objects.get(id=periodo_id)
        serializer = PeriodoAvaliativoSerializer(periodo, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except PeriodoAvaliativo.DoesNotExist:
        return Response(
            {'error': 'Período avaliativo não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception("Erro ao atualizar período avaliativo.")
        return Response(
            {'error': 'Erro ao atualizar período avaliativo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_periodo_avaliativo(request, periodo_id):
    """Remove um período avaliativo."""
    try:
        periodo = PeriodoAvaliativo.objects.get(id=periodo_id)
        periodo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except PeriodoAvaliativo.DoesNotExist:
        return Response(
            {'error': 'Período avaliativo não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception("Erro ao deletar período avaliativo.")
        return Response(
            {'error': 'Erro ao deletar período avaliativo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# TURMAS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_turmas(request):
    """
    Lista turmas com filtros.
    Query params: id, instituicao_id, ativa, usuario_turmas.usuario_id
    """
    try:
        user = request.user
        queryset = Turma.objects.all()

        turma_id = request.GET.get('id')
        instituicao_id_param = request.GET.get('instituicao_id')
        ativa = request.GET.get('ativa')
        usuario_id_param = request.GET.get('usuario_turmas.usuario_id') or request.GET.get('usuario_id')

        user_instituicao_id = getattr(user, 'instituicao_id', None)
        if user_instituicao_id:
            if instituicao_id_param and str(instituicao_id_param) != str(user_instituicao_id):
                logger.warning(
                    "Tentativa de acesso a turmas de outra instituição.",
                    extra={
                        "user_id": str(user.id),
                        "perfil": user.perfil,
                        "instituicao_id_param": str(instituicao_id_param),
                        "instituicao_id_user": str(user_instituicao_id),
                    },
                )
                return Response(
                    {'error': 'Acesso negado para a instituição informada.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            queryset = queryset.filter(instituicao_id=user_instituicao_id)
        elif instituicao_id_param:
            queryset = queryset.filter(instituicao_id=instituicao_id_param)

        if turma_id:
            queryset = queryset.filter(id=turma_id)

        if ativa is not None:
            ativa_normalizada = str(ativa).strip().lower() in {'true', '1', 'yes', 'sim'}
            queryset = queryset.filter(ativa=ativa_normalizada)

        is_professor = getattr(user, 'perfil', None) in Usuario.PERFIS_PROFESSOR
        usuario_id_efetivo = None

        if is_professor:
            usuario_id_efetivo = user.id
            if usuario_id_param and str(usuario_id_param) != str(user.id):
                logger.warning(
                    "Professor tentou filtrar turmas por outro usuário. Filtro será ignorado.",
                    extra={
                        "user_id": str(user.id),
                        "usuario_id_param": str(usuario_id_param),
                    },
                )
        elif usuario_id_param:
            usuario_id_efetivo = usuario_id_param

        if usuario_id_efetivo:
            turma_ids = UsuarioTurma.objects.filter(
                usuario_id=usuario_id_efetivo
            ).values_list('turma_id', flat=True)
            queryset = queryset.filter(id__in=turma_ids)

        turmas = list(queryset)
        serializer = TurmaSerializer(turmas, many=True)
        data = serializer.data

        turma_ids = [item.get('id') for item in data if item.get('id')]
        if turma_ids:
            vinculos = UsuarioTurma.objects.filter(turma_id__in=turma_ids).select_related('usuario')
            if is_professor:
                vinculos = vinculos.filter(usuario_id=user.id)
            vinculados_por_turma = {}
            for vinculo in vinculos:
                turma_key = str(vinculo.turma_id)
                vinculados_por_turma.setdefault(turma_key, []).append({
                    'usuarios': {
                        'id': str(vinculo.usuario_id),
                        'nome': vinculo.usuario.nome,
                        'perfil': vinculo.usuario.perfil,
                    }
                })

            for turma in data:
                turma_id = turma.get('id')
                turma['usuario_turmas'] = vinculados_por_turma.get(turma_id, [])

        logger.info(
            "Turmas listadas com sucesso.",
            extra={
                "user_id": str(user.id),
                "perfil": user.perfil,
                "total_turmas": len(data),
                "filtros": {
                    "turma_id": str(turma_id) if turma_id else None,
                    "instituicao_id": str(user_instituicao_id) if user_instituicao_id else str(instituicao_id_param) if instituicao_id_param else None,
                    "ativa": ativa,
                    "usuario_id_efetivo": str(usuario_id_efetivo) if usuario_id_efetivo else None,
                },
            },
        )
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(
            "Erro inesperado ao listar turmas.",
            extra={
                "user_id": str(getattr(request.user, 'id', 'anon')),
                "perfil": getattr(request.user, 'perfil', 'anon'),
            },
        )
        return Response(
            {'error': 'Erro ao listar turmas', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def detalhe_turma(request, turma_id):
    """Retorna detalhes de uma turma específica."""
    try:
        turma = Turma.objects.get(id=turma_id)
        serializer = TurmaSerializer(turma)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Turma.DoesNotExist:
        return Response(
            {'error': 'Turma não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao buscar turma', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_turma(request):
    """Cria uma nova turma."""
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        serializer = TurmaSerializer(data=request.data)
        if serializer.is_valid():
            turma = serializer.save()
            return Response(TurmaSerializer(turma).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar turma', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_turma(request, turma_id):
    """Atualiza uma turma existente."""
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        turma = Turma.objects.get(id=turma_id)
        serializer = TurmaSerializer(
            turma,
            data=request.data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            turma = serializer.save()
            return Response(TurmaSerializer(turma).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Turma.DoesNotExist:
        return Response(
            {'error': 'Turma não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar turma', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_turma(request, turma_id):
    """Remove uma turma."""
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        turma = Turma.objects.get(id=turma_id)
        turma.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)
    except Turma.DoesNotExist:
        return Response(
            {'error': 'Turma não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao deletar turma', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# CONFIGURAÇÕES DE REGISTRO
# =============================================================================

@api_view(['GET'])
def listar_configuracoes_registro(request):
    """
    Lista configurações de registro por turma.
    Query params: turma_id, turma_id__in
    """
    try:
        queryset = ConfiguracaoRegistro.objects.all()

        turma_id = request.GET.get('turma_id')
        turma_ids = request.GET.get('turma_id__in')

        if turma_id:
            queryset = queryset.filter(turma_id=turma_id)
        if turma_ids:
            ids = [item for item in turma_ids.split(',') if item]
            queryset = queryset.filter(turma_id__in=ids)

        serializer = ConfiguracaoRegistroSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar configurações de registro', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_configuracao_registro(request):
    """Cria ou atualiza a configuração de registro por turma."""
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ConfiguracaoRegistroSerializer(data=request.data)
        if serializer.is_valid():
            turma_id = serializer.validated_data['turma_id']
            frequencia = serializer.validated_data['frequencia_registro']

            configuracao, created = ConfiguracaoRegistro.objects.update_or_create(
                turma_id=turma_id,
                defaults={'frequencia_registro': frequencia},
            )

            response_serializer = ConfiguracaoRegistroSerializer(configuracao)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except IntegrityError as e:
        return Response(
            {'error': 'Erro de integridade ao salvar configuração', 'details': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao salvar configuração de registro', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_configuracao_registro(request, configuracao_id):
    """Atualiza uma configuração de registro existente."""
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        configuracao = ConfiguracaoRegistro.objects.get(id=configuracao_id)
        serializer = ConfiguracaoRegistroSerializer(
            configuracao,
            data=request.data,
            partial=(request.method == 'PATCH')
        )

        if serializer.is_valid():
            configuracao = serializer.save()
            return Response(
                ConfiguracaoRegistroSerializer(configuracao).data,
                status=status.HTTP_200_OK
            )

        return Response(
            {'error': 'Dados inválidos para atualizar configuração', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    except ConfiguracaoRegistro.DoesNotExist:
        return Response(
            {'error': 'Configuração não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except IntegrityError as e:
        logger.exception("Erro de integridade ao atualizar configuração de registro.")
        return Response(
            {'error': 'Erro de integridade ao atualizar configuração', 'details': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar configuração de registro', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# PROJETOS
# =============================================================================

@api_view(['GET'])
def listar_projetos(request):
    """
    Lista projetos com filtros.
    Query params: instituicao_id, status
    """
    try:
        queryset = Projeto.objects.all()

        instituicao_id = request.GET.get('instituicao_id')
        projeto_status = request.GET.get('status')

        if instituicao_id:
            queryset = queryset.filter(instituicao_id=instituicao_id)
        if projeto_status:
            queryset = queryset.filter(status=projeto_status)

        serializer = ProjetoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar projetos', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def criar_projeto(request):
    """Cria um novo projeto."""
    try:
        serializer = ProjetoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar projeto', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
def atualizar_projeto(request, projeto_id):
    """Atualiza um projeto existente."""
    try:
        projeto = Projeto.objects.get(id=projeto_id)
        serializer = ProjetoSerializer(
            projeto,
            data=request.data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Projeto.DoesNotExist:
        return Response(
            {'error': 'Projeto não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar projeto', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
def deletar_projeto(request, projeto_id):
    """Remove um projeto."""
    try:
        projeto = Projeto.objects.get(id=projeto_id)
        projeto.delete()
        return Response(
            {'success': True, 'message': 'Projeto removido'},
            status=status.HTTP_200_OK
        )
    except Projeto.DoesNotExist:
        return Response(
            {'error': 'Projeto não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao deletar projeto', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# INSTITUICOES
# =============================================================================

@api_view(['GET'])
def listar_instituicoes(request):
    """Lista instituições."""
    try:
        queryset = Instituicao.objects.all()
        ativa = request.GET.get('ativa')
        if ativa is not None:
            queryset = queryset.filter(ativa=(ativa.lower() == 'true'))
        serializer = InstituicaoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar instituições', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def detalhe_instituicao(request, instituicao_id):
    """Retorna detalhes de uma instituição."""
    try:
        instituicao = Instituicao.objects.get(id=instituicao_id)
        serializer = InstituicaoSerializer(instituicao)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Instituicao.DoesNotExist:
        return Response(
            {'error': 'Instituição não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao buscar instituição', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def criar_instituicao(request):
    """Cria uma nova instituição."""
    try:
        serializer = InstituicaoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar instituição', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def atualizar_instituicao(request, instituicao_id):
    """Atualiza uma instituição."""
    try:
        instituicao = Instituicao.objects.get(id=instituicao_id)
        serializer = InstituicaoSerializer(
            instituicao,
            data=request.data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Instituicao.DoesNotExist:
        return Response(
            {'error': 'Instituição não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar instituição', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# USUARIOS
# =============================================================================

@api_view(['GET'])
def listar_usuarios(request):
    """
    Lista usuários com filtros, ordenação e paginação.
    Query params: instituicao_id, perfil, ativo, ordering, page, page_size
    """
    try:
        queryset = Usuario.objects.all()

        instituicao_id = request.GET.get('instituicao_id')
        perfil = request.GET.get('perfil')
        ativo = request.GET.get('ativo')

        if instituicao_id:
            queryset = queryset.filter(instituicao_id=instituicao_id)
        if perfil:
            queryset = queryset.filter(perfil=perfil)
        if ativo is not None:
            queryset = queryset.filter(ativo=(ativo.lower() == 'true'))

        queryset = queryset.prefetch_related('turmas')

        # Whitelist evita FieldError se vier um valor inesperado em `ordering`
        # (e também evita expor ordenação por colunas sensíveis não previstas aqui).
        ordering = request.GET.get('ordering')
        if ordering in ORDENACAO_PERMITIDA:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')  # padrão: mais recentes primeiro

        paginator = PadraoPagination()
        pagina = paginator.paginate_queryset(queryset, request)
        serializer = UsuarioSerializer(pagina, many=True)
        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar usuários', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def detalhe_usuario(request, usuario_id):
    """Retorna detalhes de um usuário."""
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        serializer = UsuarioSerializer(usuario)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Usuario.DoesNotExist:
        return Response(
            {'error': 'Usuário não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao buscar usuário', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def criar_usuario(request):
    """Cria um novo usuário."""
    try:

        data = request.data.copy()
        password = data.pop('password', None)

        serializer = UsuarioSerializer(data=data)
        if serializer.is_valid():
            usuario = serializer.save()
            if password:
                usuario.set_password(password)
                usuario.save()
            return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar usuário', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def atualizar_usuario(request, usuario_id):
    """Atualiza um usuário."""
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        data = request.data.copy()
        password = data.pop('password', None)

        serializer = UsuarioSerializer(
            usuario,
            data=data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            usuario = serializer.save()
            if password:
                usuario.set_password(password)
                usuario.save()
            return Response(UsuarioSerializer(usuario).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Usuario.DoesNotExist:
        return Response(
            {'error': 'Usuário não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao atualizar usuário', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def deletar_usuario(request, usuario_id):
    """Remove um usuário (soft delete)."""
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        usuario.ativo = False
        usuario.save()
        return Response(
            {'success': True, 'message': 'Usuário desativado'},
            status=status.HTTP_200_OK
        )
    except Usuario.DoesNotExist:
        return Response(
            {'error': 'Usuário não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Erro ao deletar usuário', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# AUTENTICACAO
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def get_csrf_token(request):
    """
    Retorna o token CSRF para ser usado em requisições POST.
    Também configura o cookie CSRF no navegador.
    """
    return Response({
        'csrfToken': get_token(request),
        'message': 'CSRF cookie configurado'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login(request):
    """
    Autentica usuário via email e senha.
    Retorna dados do usuário e inicia sessão.
    """
    try:
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')

        remember_me = request.data.get('remember_me', False)

        if not email or not password:
            return Response(
                {'error': 'Email e senha são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar usuário pelo email
        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            logger.warning(f"Tentativa de login com email inexistente: {email}")
            return Response(
                {'error': 'Credenciais inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Verificar se usuário está ativo
        if not usuario.ativo:
            return Response(
                {'error': 'Usuário desativado. Contate o administrador.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Autenticar com Django
        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            logger.info(f"Login bem-sucedido: {email}")

            if remember_me:
                request.session.set_expiry(3 * 24 * 3600)  # 3 dias
            else:
                request.session.set_expiry(0)  # expira ao fechar o navegador

            # Retornar dados do usuário no formato esperado pelo frontend
            return Response({
                'user': {
                    'id': str(usuario.id),
                    'email': usuario.email,
                    'user_metadata': {
                        'nome': usuario.nome,
                    }
                },
                'session': {
                    'access_token': 'django-session',  # Placeholder para compatibilidade
                },
                'perfil': usuario.perfil,
                'nome': usuario.nome,
                'instituicao_id': str(usuario.instituicao_id) if usuario.instituicao_id else None,
            })
        else:
            logger.warning(f"Senha incorreta para: {email}")
            return Response(
                {'error': 'Credenciais inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    except Exception as e:
        logger.error(f"Erro no login: {str(e)}")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def auth_logout(request):
    """Encerra a sessão do usuário."""
    try:
        logout(request)
        return Response({'message': 'Logout realizado com sucesso'})
    except Exception as e:
        return Response(
            {'error': 'Erro ao fazer logout', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_me(request):
    """
    Retorna dados do usuário autenticado.
    Usado para verificar sessão e obter perfil.
    """
    try:
        if not request.user.is_authenticated:
            return Response(
                {'user': None, 'session': None},
                status=status.HTTP_200_OK
            )

        usuario = request.user

        return Response({
            'user': {
                'id': str(usuario.id),
                'email': usuario.email,
                'user_metadata': {
                    'nome': usuario.nome,
                }
            },
            'session': {
                'access_token': 'django-session',
            },
            'perfil': usuario.perfil,
            'nome': usuario.nome,
            'instituicao_id': str(usuario.instituicao_id) if usuario.instituicao_id else None,
            'tipo_especialista': usuario.tipo_especialista,
        })

    except Exception as e:
        logger.error(f"Erro em auth_me: {str(e)}")
        return Response(
            {'error': 'Erro ao buscar usuário', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# ENDPOINTS AUXILIARES (compatibilidade com frontend)
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def listar_usuario_turmas(request):
    """
    Lista turmas associadas a um usuário.
    Query params: usuario_id
    """
    try:
        usuario_id = request.GET.get('usuario_id')
        if not usuario_id:
            return Response([], status=status.HTTP_200_OK)

        vinculos = UsuarioTurma.objects.filter(usuario_id=usuario_id).select_related('turma')
        serializer = UsuarioTurmaSerializer(vinculos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar turmas do usuário', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_usuario_turma(request):
    """Cria vínculo usuário-turma."""
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        usuario_id = request.data.get('usuario_id')
        turma_id = request.data.get('turma_id')
        if not usuario_id or not turma_id:
            return Response({'error': 'usuario_id e turma_id são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

        vinculo, created = UsuarioTurma.objects.get_or_create(
            usuario_id=usuario_id,
            turma_id=turma_id
        )
        serializer = UsuarioTurmaSerializer(vinculo)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
    except IntegrityError:
        return Response({'error': 'Vínculo já existe'}, status=status.HTTP_409_CONFLICT)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar vínculo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_usuario_turma(request):
    """Remove vínculo usuário-turma."""
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        usuario_id = request.data.get('usuario_id') or request.GET.get('usuario_id')
        turma_id = request.data.get('turma_id') or request.GET.get('turma_id')
        turma_id_in = request.data.get('turma_id__in') or request.GET.get('turma_id__in')

        if not usuario_id or (not turma_id and not turma_id_in):
            return Response(
                {'error': 'usuario_id e turma_id (ou turma_id__in) são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = UsuarioTurma.objects.filter(usuario_id=usuario_id)
        if turma_id_in:
            if isinstance(turma_id_in, str):
                turma_ids = [tid for tid in turma_id_in.split(',') if tid]
            else:
                turma_ids = turma_id_in
            queryset = queryset.filter(turma_id__in=turma_ids)
        else:
            queryset = queryset.filter(turma_id=turma_id)

        deleted, _ = queryset.delete()
        if deleted == 0:
            return Response({'error': 'Vínculo não encontrado'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Erro ao remover vínculo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# MENSAGENS DA COORDENAÇÃO
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def listar_mensagens_coordenacao(request):
    """
    Lista mensagens da coordenação.
    Query params: instituicao_id, ordering
    """
    try:
        queryset = MensagemCoordenacao.objects.all()

        instituicao_id = request.GET.get('instituicao_id')
        ordering = request.GET.get('ordering', '-created_at')

        if instituicao_id:
            queryset = queryset.filter(instituicao_id=instituicao_id)

        # Suportar ordenação
        if ordering.startswith('-'):
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by(ordering)

        serializer = MensagemCoordenacaoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar mensagens', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def criar_mensagem_coordenacao(request):
    """Cria uma nova mensagem da coordenação."""
    try:
        serializer = MensagemCoordenacaoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar mensagem', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def listar_mensagens_lidas(request):
    """
    Lista mensagens lidas pelo usuário.
    Query params: usuario_id
    """
    try:
        usuario_id = request.GET.get('usuario_id')
        if not usuario_id:
            return Response([], status=status.HTTP_200_OK)

        queryset = MensagemLida.objects.filter(usuario_id=usuario_id)
        serializer = MensagemLidaSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar mensagens lidas', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def marcar_mensagem_lida(request):
    """Marca uma mensagem como lida pelo usuário."""
    try:
        mensagem_id = request.data.get('mensagem_id')
        usuario_id = request.data.get('usuario_id')

        if not mensagem_id or not usuario_id:
            return Response(
                {'error': 'mensagem_id e usuario_id são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar se já foi lida
        existing = MensagemLida.objects.filter(
            mensagem_id=mensagem_id,
            usuario_id=usuario_id
        ).first()

        if existing:
            return Response(
                MensagemLidaSerializer(existing).data,
                status=status.HTTP_200_OK
            )

        # Criar registro
        try:
            mensagem = MensagemCoordenacao.objects.get(id=mensagem_id)
        except MensagemCoordenacao.DoesNotExist:
            return Response(
                {'error': 'Mensagem não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        lida = MensagemLida.objects.create(
            mensagem=mensagem,
            usuario_id=usuario_id
        )

        return Response(
            MensagemLidaSerializer(lida).data,
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return Response(
            {'error': 'Erro ao marcar mensagem como lida', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# ALERTAS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_alertas(request):
    """
    Lista alertas não lidos conforme o perfil do usuário autenticado.
    """
    try:
        user = request.user
        instituicao_id = getattr(user, 'instituicao_id', None) or request.GET.get('instituicao_id')

        if not instituicao_id:
            return Response([], status=status.HTTP_200_OK)

        if user.perfil in Usuario.PERFIS_PROFESSOR:
            alertas = gerar_alertas_professor(user.id, instituicao_id)
        elif user.perfil == 'coordenador':
            alertas = gerar_alertas_coordenacao(instituicao_id)
        else:
            alertas = []

        lidos = set(
            AlertaLido.objects.filter(
                usuario_id=user.id,
                alerta_tipo__in=['registro-semanal', 'registro-frequencia'],
            ).values_list('alerta_chave', flat=True)
        )
        pendentes = [alerta for alerta in alertas if alerta['id'] not in lidos]

        logger.info(
            "Alertas gerados para usuário.",
            extra={
                "usuario_id": str(user.id),
                "perfil": user.perfil,
                "total_alertas": len(alertas),
                "nao_lidos": len(pendentes),
            },
        )

        return Response(pendentes, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception("Erro ao listar alertas.")
        return Response(
            {'error': 'Erro ao listar alertas', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_alerta(request):
    """
    Retorna o conteúdo completo de um alerta específico.
    Query params: alerta_tipo, alerta_chave
    """
    try:
        alerta_tipo = request.GET.get('alerta_tipo')
        alerta_chave = request.GET.get('alerta_chave')

        if not alerta_tipo or not alerta_chave:
            return Response(
                {'error': 'alerta_tipo e alerta_chave são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        instituicao_id = getattr(user, 'instituicao_id', None) or request.GET.get('instituicao_id')

        if not instituicao_id:
            return Response(
                {'error': 'Instituição não encontrada para o usuário.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.perfil in Usuario.PERFIS_PROFESSOR:
            alertas = gerar_alertas_professor(user.id, instituicao_id)
        elif user.perfil == 'coordenador':
            alertas = gerar_alertas_coordenacao(instituicao_id)
        else:
            alertas = []

        alerta = next(
            (item for item in alertas if item['id'] == alerta_chave and item['tipo'] == alerta_tipo),
            None
        )

        if not alerta:
            return Response(
                {'error': 'Alerta não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(alerta, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception("Erro ao buscar detalhe do alerta.")
        return Response(
            {'error': 'Erro ao buscar detalhe do alerta', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# ALERTAS LIDOS
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def listar_alertas_lidos(request):
    """
    Lista alertas lidos pelo usuário.
    Query params: usuario_id, alerta_tipo
    """
    try:
        queryset = AlertaLido.objects.all()

        usuario_id = request.GET.get('usuario_id')
        alerta_tipo = request.GET.get('alerta_tipo')

        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        if alerta_tipo:
            queryset = queryset.filter(alerta_tipo=alerta_tipo)

        serializer = AlertaLidoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'Erro ao listar alertas lidos', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def criar_alerta_lido(request):
    """Marca um alerta como lido pelo usuário (idempotente)."""
    try:
        serializer = AlertaLidoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lookup = {
            'usuario_id': serializer.validated_data['usuario_id'],
            'alerta_tipo': serializer.validated_data['alerta_tipo'],
            'alerta_chave': serializer.validated_data['alerta_chave'],
        }

        existing = AlertaLido.objects.filter(**lookup).first()
        if existing:
            logger.info("Alerta já marcado como lido.", extra={
                "usuario_id": str(existing.usuario_id),
                "alerta_tipo": existing.alerta_tipo,
                "alerta_chave": existing.alerta_chave,
            })
            return Response(
                AlertaLidoSerializer(existing).data,
                status=status.HTTP_200_OK
            )

        try:
            serializer.save()
        except IntegrityError:
            # Corrida: outra requisição inseriu o mesmo (usuario, tipo, chave)
            # entre o filter() acima e o save(). Devolve o registro existente
            # em vez de propagar o erro de constraint para o cliente.
            existing = AlertaLido.objects.filter(**lookup).first()
            if existing:
                return Response(
                    AlertaLidoSerializer(existing).data,
                    status=status.HTTP_200_OK
                )
            raise

        logger.info("Alerta marcado como lido.", extra={
            "usuario_id": str(lookup['usuario_id']),
            "alerta_tipo": lookup['alerta_tipo'],
            "alerta_chave": lookup['alerta_chave'],
        })
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar alerta lido', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# INDICADORES - DESENVOLVIMENTO DE LINGUAGEM
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_indicador_linguagem(request):
    """
    Retorna o indicador de desenvolvimento de linguagem por turma.
    Query params: instituicao_id, turma_id, periodo_id
    """
    try:
        user = request.user
        instituicao_id = request.GET.get('instituicao_id') or getattr(user, 'instituicao_id', None)

        if not instituicao_id:
            return Response(
                {'error': 'Instituição não encontrada para o usuário.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.perfil not in ['coordenador', 'admin']:
            return Response(
                {'error': 'Perfil sem permissão para acessar indicadores.'},
                status=status.HTTP_403_FORBIDDEN
            )

        turma_id = request.GET.get('turma_id')
        periodo_id = request.GET.get('periodo_id')

        periodo = obter_periodo_ativo(instituicao_id, periodo_id=periodo_id)
        if not periodo:
            logger.warning(
                "Período avaliativo não encontrado para indicador de linguagem.",
                extra={"instituicao_id": str(instituicao_id)},
            )
            return Response(
                {'periodo': None, 'turmas': []},
                status=status.HTTP_200_OK
            )

        turma_ids = [turma_id] if turma_id else None
        resultados = calcular_desenvolvimento_linguagem(instituicao_id, periodo, turma_ids=turma_ids)

        logger.info(
            "Indicador de linguagem calculado.",
            extra={
                "instituicao_id": str(instituicao_id),
                "turmas": len(resultados),
                "periodo_id": str(periodo.id),
            },
        )

        return Response(
            {
                'periodo': {
                    'id': str(periodo.id),
                    'descricao': periodo.descricao,
                    'tipo_periodo': periodo.tipo_periodo,
                    'data_inicio': periodo.data_inicio.isoformat(),
                    'data_fim': periodo.data_fim.isoformat(),
                },
                'turmas': resultados,
            },
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.exception("Erro ao calcular indicador de linguagem.")
        return Response(
            {'error': 'Erro ao calcular indicador de linguagem', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# CAMPOS DE EXPERIÊNCIA CUSTOMIZADOS
# =============================================================================

@api_view(['GET'])
def listar_campos_experiencia_customizados(request):
    """
    Lista campos de experiência customizados com filtros opcionais.
    Query params: instituicao_id, ativo
    """
    try:
        queryset = CampoExperienciaCustomizado.objects.all()

        instituicao_id = request.GET.get('instituicao_id')
        ativo = request.GET.get('ativo')

        if instituicao_id:
            # Inclui campos globais (instituicao_id=None) e campos da instituição
            queryset = queryset.filter(
                Q(instituicao_id=instituicao_id) | Q(instituicao_id__isnull=True)
            )

        if ativo is not None:
            ativo_bool = ativo.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(ativo=ativo_bool)

        queryset = queryset.order_by('nome')
        serializer = CampoExperienciaCustomizadoSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erro ao listar campos de experiência: {str(e)}")
        return Response(
            {'error': 'Erro ao listar campos de experiência', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def criar_campo_experiencia_customizado(request):
    """
    Cria um novo campo de experiência customizado.
    Campos obrigatórios: nome
    Campos opcionais: instituicao_id, icone, cor, ativo
    """
    try:
        serializer = CampoExperienciaCustomizadoSerializer(data=request.data)
        if serializer.is_valid():
            campo = serializer.save()
            return Response(
                CampoExperienciaCustomizadoSerializer(campo).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except IntegrityError as e:
        return Response(
            {'error': 'Campo de experiência já existe', 'details': str(e)},
            status=status.HTTP_409_CONFLICT
        )
    except Exception as e:
        logger.error(f"Erro ao criar campo de experiência: {str(e)}")
        return Response(
            {'error': 'Erro ao criar campo de experiência', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
def atualizar_campo_experiencia_customizado(request, campo_id):
    """Atualiza um campo de experiência customizado."""
    try:
        campo = CampoExperienciaCustomizado.objects.get(id=campo_id)
        payload = request.data.copy()
        nome_novo = payload.get('nome')
        if isinstance(nome_novo, str):
            nome_novo = nome_novo.strip()
            payload['nome'] = nome_novo
            if not nome_novo:
                return Response(
                    {'error': 'Nome do campo de experiência é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        nome_anterior = campo.nome
        serializer = CampoExperienciaCustomizadoSerializer(
            campo, data=payload, partial=True
        )
        if serializer.is_valid():
            with transaction.atomic():
                campo_atualizado = serializer.save()
                total_atualizadas = 0
                if nome_novo and nome_novo != nome_anterior:
                    total_atualizadas = PerguntaBNCC.objects.filter(
                        campo_experiencia=nome_anterior
                    ).update(campo_experiencia=nome_novo)
                    logger.info(
                        "Campo de experiência renomeado de '%s' para '%s'. Perguntas atualizadas: %s",
                        nome_anterior,
                        nome_novo,
                        total_atualizadas,
                    )
            response_payload = CampoExperienciaCustomizadoSerializer(campo_atualizado).data
            response_payload['perguntas_atualizadas'] = total_atualizadas
            return Response(response_payload, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except CampoExperienciaCustomizado.DoesNotExist:
        return Response(
            {'error': 'Campo de experiência não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except IntegrityError as e:
        return Response(
            {'error': 'Campo de experiência já existe', 'details': str(e)},
            status=status.HTTP_409_CONFLICT
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar campo de experiência: {str(e)}")
        return Response(
            {'error': 'Erro ao atualizar campo de experiência', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
def deletar_campo_experiencia_customizado(request, campo_id):
    """Deleta (ou desativa) um campo de experiência customizado."""
    try:
        campo = CampoExperienciaCustomizado.objects.get(id=campo_id)
        nome_atual = campo.nome
        remanejar_para = request.data.get('remanejar_para') or request.GET.get('remanejar_para')
        if isinstance(remanejar_para, str):
            remanejar_para = remanejar_para.strip()
            if not remanejar_para:
                remanejar_para = None

        total_vinculos = PerguntaBNCC.objects.filter(campo_experiencia=nome_atual).count()
        if total_vinculos > 0 and not remanejar_para:
            return Response(
                {
                    'error': 'Campo de experiência possui perguntas vinculadas',
                    'total_vinculos': total_vinculos,
                },
                status=status.HTTP_409_CONFLICT
            )

        if remanejar_para and remanejar_para == nome_atual:
            return Response(
                {'error': 'O campo de remanejamento deve ser diferente do campo atual'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            total_remanejadas = 0
            if total_vinculos > 0 and remanejar_para:
                total_remanejadas = PerguntaBNCC.objects.filter(
                    campo_experiencia=nome_atual
                ).update(campo_experiencia=remanejar_para)

            # Soft delete: apenas desativa
            campo.ativo = False
            campo.save(update_fields=['ativo'])

        return Response(
            {
                'message': 'Campo de experiência desativado com sucesso',
                'perguntas_remanejadas': total_remanejadas,
            },
            status=status.HTTP_200_OK
        )
    except CampoExperienciaCustomizado.DoesNotExist:
        return Response(
            {'error': 'Campo de experiência não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erro ao deletar campo de experiência: {str(e)}")
        return Response(
            {'error': 'Erro ao deletar campo de experiência', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# SÉRIES / CONFIGURAÇÃO DE FAIXAS ETÁRIAS
# =============================================================================

@api_view(['GET'])
def listar_series_config(request):
    """
    Lista configurações de séries.
    Query params: ativa (default: true)
    """
    try:
        queryset = SerieConfig.objects.all()

        ativa = request.GET.get('ativa')
        if ativa is not None:
            ativa_bool = ativa.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(ativa=ativa_bool)
        else:
            queryset = queryset.filter(ativa=True)

        serializer = SerieConfigSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erro ao listar séries: {str(e)}")
        return Response(
            {'error': 'Erro ao listar séries', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_serie_config(request):
    """
    Cria uma nova configuração de série.
    Campos obrigatórios: nome, etapa, ordem
    """
    try:
        serializer = SerieConfigSerializer(data=request.data)
        if serializer.is_valid():
            serie = serializer.save()
            return Response(
                SerieConfigSerializer(serie).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except IntegrityError as e:
        return Response(
            {'error': 'Série já existe', 'details': str(e)},
            status=status.HTTP_409_CONFLICT
        )
    except Exception as e:
        logger.error(f"Erro ao criar série: {str(e)}")
        return Response(
            {'error': 'Erro ao criar série', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
def atualizar_serie_config(request, serie_id):
    """Atualiza uma configuração de série."""
    try:
        serie = SerieConfig.objects.get(id=serie_id)
        serializer = SerieConfigSerializer(serie, data=request.data, partial=True)
        if serializer.is_valid():
            serie_atualizada = serializer.save()
            return Response(
                SerieConfigSerializer(serie_atualizada).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except SerieConfig.DoesNotExist:
        return Response(
            {'error': 'Série não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar série: {str(e)}")
        return Response(
            {'error': 'Erro ao atualizar série', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def deletar_serie_config(request, serie_id):
    """Desativa uma configuração de série (soft delete)."""
    try:
        serie = SerieConfig.objects.get(id=serie_id)
        serie.ativa = False
        serie.save(update_fields=['ativa'])
        return Response(
            {'message': 'Série desativada com sucesso'},
            status=status.HTTP_200_OK
        )
    except SerieConfig.DoesNotExist:
        return Response(
            {'error': 'Série não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erro ao desativar série: {str(e)}")
        return Response(
            {'error': 'Erro ao desativar série', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_escrita(request, registro_id):
    """Remove um registro de análise de escrita."""
    try:
        registro = RegistroEscrita.objects.get(id=registro_id)
        registro.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)
    except RegistroEscrita.DoesNotExist:
        return Response(
            {'error': 'Registro de escrita não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erro ao deletar registro de escrita: {str(e)}")
        return Response(
            {'error': 'Erro ao deletar registro', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_desenho(request, registro_id):
    """Remove um registro de análise de desenho."""
    try:
        registro = RegistroDesenho.objects.get(id=registro_id)
        registro.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)
    except RegistroDesenho.DoesNotExist:
        return Response(
            {'error': 'Registro de desenho não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erro ao deletar registro de desenho: {str(e)}")
        return Response(
            {'error': 'Erro ao deletar registro', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def recuperar_senha(request):
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
    solicitar_recuperacao(email)
    return Response({'message': 'Se o e-mail existir, você receberá as instruções.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def confirmar_senha(request):
    uid = request.data.get('uid', '')
    token = request.data.get('token', '')
    nova_senha = request.data.get('nova_senha', '')

    if not all([uid, token, nova_senha]):
        return Response({'error': 'Dados incompletos'}, status=status.HTTP_400_BAD_REQUEST)
    if len(nova_senha) < 8:
        return Response({'error': 'A senha deve ter pelo menos 8 caracteres'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        confirmar_nova_senha(uid, token, nova_senha)
        return Response({'message': 'Senha redefinida com sucesso!'})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def listar_planejamentos(request):
    """
    STUB TEMPORÁRIO — devolve lista vazia (200), não 501.

    CoordinatorDataContext.fetchData() trata QUALQUER erro entre as chamadas
    paralelas (turmas/planejamentos/criancas/usuarios) como falha fatal do
    carregamento inteiro do painel do coordenador — um 501 aqui derruba a
    tela inteira (todas as abas), não só Planejamentos. 200 + [] evita isso
    enquanto a implementação real não é recuperada do histórico do git.
    """
    return Response([], status=status.HTTP_200_OK)


# =============================================================================
# Disciplinas
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_disciplinas(request):
    instituicao_id = request.query_params.get('instituicao_id')
    qs = Disciplina.objects.all()
    if instituicao_id:
        qs = qs.filter(instituicao_id=instituicao_id)

    paginator = PadraoPagination()
    pagina = paginator.paginate_queryset(qs, request)
    serializer = DisciplinaSerializer(pagina, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def criar_disciplina(request):
    serializer = DisciplinaSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def atualizar_disciplina(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    serializer = DisciplinaSerializer(disciplina, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def deletar_disciplina(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    disciplina.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_usuario_disciplinas(request):
    usuario_id = request.query_params.get('usuario_id')
    instituicao_id = request.query_params.get('instituicao_id')
    qs = (
        UsuarioDisciplina.objects
        .select_related('disciplina')
        .only('id', 'usuario_id', 'disciplina_id', 'disciplina__nome', 'instituicao_id', 'created_at')
    )
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if instituicao_id:
        qs = qs.filter(instituicao_id=instituicao_id)

    paginator = PadraoPagination()
    pagina = paginator.paginate_queryset(qs, request)
    serializer = UsuarioDisciplinaSerializer(pagina, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def criar_usuario_disciplina(request):
    serializer = UsuarioDisciplinaSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@requer_perfil('admin')
def deletar_usuario_disciplina(request, vinculo_id):
    vinculo = get_object_or_404(UsuarioDisciplina, id=vinculo_id)
    vinculo.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


#PROMPTS 

def _cliente_id_do_usuario(request):
    """instituicao_id do usuário logado, como string — é a chave usada em PromptTemplate.cliente_id."""
    if request.user.is_authenticated and getattr(request.user, 'instituicao_id', None):
        return str(request.user.instituicao_id)
    return None


@api_view(['GET'])
def listar_categorias_prompt(request):
    categorias = (
        PromptCategoria.objects
        .filter(ativo=True)
        .order_by('id')
        .prefetch_related('templates')
    )
    serializer = PromptCategoriaSerializer(
        categorias, many=True,
        context={'cliente_id': _cliente_id_do_usuario(request)},
    )
    return Response(serializer.data)


@api_view(['POST'])
def criar_categoria_prompt(request):
    titulo = (request.data.get('titulo') or '').strip()
    if not titulo:
        return Response({'error': 'O título é obrigatório.'}, status=400)

    categoria = PromptCategoria.objects.create(
        titulo=titulo,
        ativo=request.data.get('ativo', True),
    )
    # Só cria a categoria aqui — o PromptsTab faz uma 2ª chamada pra
    # /prompts/salvar/ logo em seguida, que cria o template com o
    # cliente_id correto (ver criar_categoria_prompt em ModalCriarCategoria).
    serializer = PromptCategoriaSerializer(
        categoria,
        context={'cliente_id': _cliente_id_do_usuario(request)},
    )
    return Response(serializer.data, status=201)


@api_view(['POST'])
def salvar_prompt(request):
    categoria_id = request.data.get('categoria_id')
    if not categoria_id:
        return Response({'error': 'categoria_id é obrigatório.'}, status=400)

    try:
        categoria = PromptCategoria.objects.get(id=categoria_id)
    except PromptCategoria.DoesNotExist:
        return Response({'error': 'Categoria não encontrada.'}, status=404)

    cliente_id = _cliente_id_do_usuario(request)
    prompt_global = request.data.get('prompt_global', '')
    personalizado = request.data.get('personalizado', '')

    # filter(cliente_id=None) equivale a cliente_id__isnull=True no Django ORM,
    # então isso funciona tanto pra usuário com instituição quanto sem.
    template = (
        PromptTemplate.objects
        .filter(categoria=categoria, cliente_id=cliente_id)
        .order_by('-id')
        .first()
    )
    if template:
        template.prompt_global = prompt_global
        template.personalizado = personalizado
        template.save(update_fields=['prompt_global', 'personalizado'])
    else:
        template = PromptTemplate.objects.create(
            categoria=categoria,
            cliente_id=cliente_id,
            prompt_global=prompt_global,
            personalizado=personalizado,
        )

    return Response(PromptTemplateSerializer(template).data)