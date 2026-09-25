"""Endpoints de Ticket, RespostaTicket e AnexoTicket (suporte).

Quem vê/responde um ticket: suporte e superadmin (todos), gestão da escola/rede
(os do escopo, via TenantManager) e o próprio solicitante.

As respostas herdam escola/instituição do TICKET, não de quem responde: a
resposta do suporte (usuário sem escola) precisa aparecer para a escola que
abriu o chamado. A listagem das respostas usa `_base_manager` filtrado pelo
ticket — a permissão já foi checada no ticket.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar
from api.models import Ticket, RespostaTicket
from api.serializers import TicketSerializer, RespostaTicketSerializer, AnexoTicketSerializer
from api.tenancy import is_superadmin

PROTOCOLO_PREFIXO = 'NARA'
_TENTATIVAS_PROTOCOLO = 5


def _e_suporte(user):
    return is_superadmin(user) or user.nivel == 'suporte'


def _pode_gerenciar_ticket(user):
    """Muda status/prioridade/responsável: suporte, superadmin e gestão."""
    return _e_suporte(user) or pode_gerenciar(user)


def _pode_ver_ticket(user, ticket):
    return _pode_gerenciar_ticket(user) or ticket.usuario_solicitante_id == user.id


def _ticket_ou_erro(request, ticket_id):
    """Retorna (ticket, erro): 404 fora do escopo/malformado, 403 sem permissão."""
    ticket = buscar_no_escopo(Ticket, ticket_id)
    if ticket is None:
        return None, Response({'error': 'Ticket não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_ver_ticket(request.user, ticket):
        return None, Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    return ticket, None


def _proximo_protocolo():
    """Sequencial GLOBAL (`_base_manager`): pelo TenantManager cada rede só
    veria os próprios tickets e geraria números que já existem em outra —
    `protocolo` é unique, isso virava 500."""
    ultimo = (
        Ticket._base_manager.filter(protocolo__startswith=f'{PROTOCOLO_PREFIXO}-')
        .order_by('-criado_em').values_list('protocolo', flat=True).first()
    )
    proximo = 1
    if ultimo:
        try:
            proximo = int(ultimo.rsplit('-', 1)[-1]) + 1
        except ValueError:
            pass
    return f'{PROTOCOLO_PREFIXO}-{proximo:04d}'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_tickets(request):
    """Suporte/superadmin veem tudo. Gestão vê o escopo dela (TenantManager).
    Demais níveis veem só os próprios tickets."""
    user = request.user
    tickets = Ticket.objects.all()
    if not _pode_gerenciar_ticket(user):
        tickets = tickets.filter(usuario_solicitante=user)
    return Response(TicketSerializer(tickets.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_ticket(request):
    """Qualquer usuário autenticado pode abrir um ticket."""
    user = request.user
    serializer = TicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Dois tickets abertos ao mesmo tempo podem calcular o mesmo número:
    # tenta de novo com o seguinte em vez de devolver 500.
    for tentativa in range(_TENTATIVAS_PROTOCOLO):
        try:
            with transaction.atomic():
                ticket = serializer.save(
                    protocolo=_proximo_protocolo(),
                    usuario_solicitante=user,
                    escola_id=user.escola_id,
                    instituicao_id=user.instituicao_id,
                )
            break
        except IntegrityError:
            if tentativa == _TENTATIVAS_PROTOCOLO - 1:
                raise
            serializer.instance = None
    return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_ticket(request, ticket_id):
    ticket, erro = _ticket_ou_erro(request, ticket_id)
    if erro:
        return erro
    return Response(TicketSerializer(ticket).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_ticket(request, ticket_id):
    """Status/prioridade/responsável só quem gerencia suporte."""
    if not _pode_gerenciar_ticket(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    ticket, erro = _ticket_ou_erro(request, ticket_id)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = TicketSerializer(ticket, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_respostas_ticket(request, ticket_id):
    ticket, erro = _ticket_ou_erro(request, ticket_id)
    if erro:
        return erro

    respostas = RespostaTicket._base_manager.filter(ticket=ticket).order_by('criado_em')
    return Response(RespostaTicketSerializer(respostas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def responder_ticket(request, ticket_id):
    """O solicitante ou quem gerencia suporte pode responder."""
    ticket, erro = _ticket_ou_erro(request, ticket_id)
    if erro:
        return erro

    serializer = RespostaTicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    resposta = serializer.save(
        usuario=request.user, ticket=ticket,
        escola_id=ticket.escola_id, instituicao_id=ticket.instituicao_id,
    )
    return Response(RespostaTicketSerializer(resposta).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def anexar_arquivo_ticket(request, ticket_id):
    """Anexo na abertura do ticket (ticket_reply fica nulo)."""
    ticket, erro = _ticket_ou_erro(request, ticket_id)
    if erro:
        return erro

    serializer = AnexoTicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    anexo = serializer.save(ticket=ticket)
    return Response(AnexoTicketSerializer(anexo).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def anexar_arquivo_resposta(request, resposta_id):
    """Anexo numa resposta específica. O escopo vem do ticket da resposta."""
    # `_base_manager`: respostas antigas do suporte (sem escola) não passam
    # pelo TenantManager. A permissão é checada logo abaixo, pelo ticket.
    try:
        resposta = RespostaTicket._base_manager.filter(pk=resposta_id).first()
    except (ValidationError, ValueError, TypeError):
        resposta = None
    if resposta is None:
        return Response({'error': 'Resposta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    _, erro = _ticket_ou_erro(request, resposta.ticket_id)
    if erro:
        return erro

    serializer = AnexoTicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    anexo = serializer.save(ticket_reply=resposta)
    return Response(AnexoTicketSerializer(anexo).data, status=status.HTTP_201_CREATED)