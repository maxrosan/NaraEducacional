from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from datetime import date, timedelta

from api.services.analytics import contar_registros_instituicao, get_participacao_docente
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contagem_registros(request):
    instituicao_id = request.query_params.get('instituicao_id')

    if not instituicao_id:
        return Response({'error': 'instituicao_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

    data_inicio = request.query_params.get('data_inicio')
    data_fim = request.query_params.get('data_fim')

    contagens = contar_registros_instituicao(instituicao_id, data_inicio, data_fim)
    return Response(contagens)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def participacao_docente(request):
    """
    Retorna estatísticas de participação por professor de uma instituição.
    Query params: instituicao_id
    """
    instituicao_id = request.GET.get('instituicao_id')
    if not instituicao_id:
        return Response(
            {'error': 'instituicao_id é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        data_inicio = date.today() - timedelta(days=30)
        resultado = get_participacao_docente(instituicao_id, data_inicio=data_inicio)
        return Response(resultado, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erro ao buscar participação docente: {str(e)}")
        return Response(
            {'error': 'Erro ao buscar dados', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
