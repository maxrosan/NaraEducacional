"""Endpoints de Ticket, RespostaTicket e AnexoTicket (suporte)."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Ticket, RespostaTicket
from api.serializers import TicketSerializer, RespostaTicketSerializer, AnexoTicketSerializer

PROTOCOLO_PREFIXO = 'NARA'


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _e_suporte(user):
    return _is_superadmin(user) or user.nivel == 'suporte'


def _pode_gerenciar(user):
    return _e_suporte(user) or user.nivel in ('admin', 'coordenador')


def _pode_ver_ticket(user, ticket):
    if _e_suporte(user) or _pode_gerenciar(user):
        return True
    return ticket.usuario_solicitante_id == user.id


def _gerar_protocolo():
    ultimo = Ticket.objects.order_by('-criado_em').first()
    proximo = 1
    if ultimo and ultimo.protocolo.startswith(f'{PROTOCOLO_PREFIXO}-'):
        try:
            proximo = int(ultimo.protocolo.split('-')[-1]) + 1
        except ValueError:
            pass
    return f'{PROTOCOLO_PREFIXO}-{proximo:04d}'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_tickets(request):
    """Suporte/superadmin veem tudo. admin/coordenador veem o escopo deles
    (via TenantManager). Demais níveis veem só os próprios tickets."""
    user = request.user
    if _e_suporte(user):
        tickets = Ticket.objects.all()
    elif user.nivel in ('admin', 'coordenador'):
        tickets = Ticket.objects.all()  # já filtrado pelo TenantManager
    else:
        tickets = Ticket.objects.filter(usuario_solicitante=user)
    return Response(TicketSerializer(tickets.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_ticket(request):
    """Qualquer usuário autenticado pode abrir um ticket."""
    user = request.user
    serializer = TicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ticket = serializer.save(
        protocolo=_gerar_protocolo(),
        usuario_solicitante=user,
        escola_id=user.escola_id,
        instituicao_id=user.instituicao_id,
    )
    return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_ticket(request, ticket_id):
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_ver_ticket(request.user, ticket):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    return Response(TicketSerializer(ticket).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_ticket(request, ticket_id):
    """Status/prioridade/responsável só quem gerencia suporte."""
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = TicketSerializer(ticket, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_respostas_ticket(request, ticket_id):
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_ver_ticket(request.user, ticket):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    respostas = RespostaTicket.objects.filter(ticket=ticket).order_by('criado_em')
    return Response(RespostaTicketSerializer(respostas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def responder_ticket(request, ticket_id):
    """O solicitante ou quem gerencia suporte pode responder."""
    user = request.user
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_ver_ticket(user, ticket):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = RespostaTicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    resposta = serializer.save(usuario=user, ticket=ticket, escola_id=user.escola_id)
    return Response(RespostaTicketSerializer(resposta).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def anexar_arquivo_ticket(request, ticket_id):
    """Anexo na abertura do ticket (ticket_reply fica nulo)."""
    user = request.user
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_ver_ticket(user, ticket):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AnexoTicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    anexo = serializer.save(ticket=ticket)
    return Response(AnexoTicketSerializer(anexo).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def anexar_arquivo_resposta(request, resposta_id):
    """Anexo numa resposta específica."""
    user = request.user
    try:
        resposta = RespostaTicket.objects.get(id=resposta_id)
    except RespostaTicket.DoesNotExist:
        return Response({'error': 'Resposta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_ver_ticket(user, resposta.ticket):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AnexoTicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    anexo = serializer.save(ticket_reply=resposta)
    return Response(AnexoTicketSerializer(anexo).data, status=status.HTTP_201_CREATED)