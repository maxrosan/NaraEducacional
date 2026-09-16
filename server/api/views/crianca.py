"""Views REST para o recurso `criancas`."""

import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.serializers import CriancaListSerializer
from api.services.crianca import listar_criancas_filtradas

logger = logging.getLogger(__name__)


@api_view(['GET'])
def listar_criancas(request):
    """
    Lista crianças com filtros opcionais.
    Query params: id, id__in, turma_id, turma_id__in, instituicao_id,
    status_vinculo, nome, page, page_size

    Quando `page` é enviado, a resposta vem paginada:
    {"results": [...], "count": N, "page": P, "page_size": S, "total_pages": T}

    Sem `page`, o comportamento é o de sempre: array puro com todos os
    registros que casam com os filtros (usado pelo drill-down do
    coordenador via id__in/turma_id__in, que não deve ser paginado).
    """
    try:
        page_param = request.GET.get('page')
        page_size_param = request.GET.get('page_size')
        page = int(page_param) if page_param else None
        page_size = int(page_size_param) if page_size_param else None

        criancas, turma_names, total = listar_criancas_filtradas(
            crianca_id=request.GET.get('id'),
            crianca_id_in=request.GET.get('id__in'),
            turma_id=request.GET.get('turma_id'),
            turma_id_in=request.GET.get('turma_id__in'),
            instituicao_id=request.GET.get('instituicao_id'),
            status_vinculo=request.GET.get('status_vinculo'),
            nome=request.GET.get('nome'),
            page=page,
            page_size=page_size,
        )
        serializer = CriancaListSerializer(
            criancas, many=True, context={'turma_names': turma_names}
        )

        if page:
            effective_page_size = page_size or 20
            total_pages = -(-total // effective_page_size) if total else 0  # ceil division
            return Response({
                'results': serializer.data,
                'count': total,
                'page': page,
                'page_size': effective_page_size,
                'total_pages': total_pages,
            }, status=status.HTTP_200_OK)

        return Response(serializer.data, status=status.HTTP_200_OK)
    except (TypeError, ValueError):
        return Response(
            {'error': 'Parâmetros page/page_size inválidos, devem ser inteiros.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.exception("Erro ao listar crianças.")
        return Response(
            {'error': 'Erro ao listar crianças', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )