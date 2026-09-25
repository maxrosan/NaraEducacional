"""Endpoints de TemplateDocumento e Contrato."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import SEM_ESCOLA_INSTITUICAO, resolver_escopo_criacao
from api.models import TemplateDocumento, Contrato, Escola
from api.serializers import TemplateDocumentoSerializer, ContratoSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel == 'admin'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_templates_documento(request):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    templates = TemplateDocumento.objects.all()
    return Response(TemplateDocumentoSerializer(templates, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_template_documento(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id, instituicao_id, erro = resolver_escopo_criacao(
        user, request.data, sem_escola=SEM_ESCOLA_INSTITUICAO,
    )
    if erro:
        return erro

    serializer = TemplateDocumentoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    template = serializer.save(
        responsavel=user, criado_por=user, escola_id=escola_id, instituicao_id=instituicao_id,
    )
    return Response(TemplateDocumentoSerializer(template).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_template_documento(request, template_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        template = TemplateDocumento.objects.get(id=template_id)
    except TemplateDocumento.DoesNotExist:
        return Response({'error': 'Template não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(TemplateDocumentoSerializer(template).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_template_documento(request, template_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        template = TemplateDocumento.objects.get(id=template_id)
    except TemplateDocumento.DoesNotExist:
        return Response({'error': 'Template não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = TemplateDocumentoSerializer(template, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save(atualizado_por=user)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_contratos(request):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    contratos = Contrato.objects.all()
    return Response(ContratoSerializer(contratos.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_contrato(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    if _is_superadmin(user):
        escola_id = request.data.get('escola')
        instituicao_id = request.data.get('instituicao')
        if not escola_id or not instituicao_id:
            return Response({'error': 'Campos escola e instituicao são obrigatórios.'},
                             status=status.HTTP_400_BAD_REQUEST)
    else:
        if user.instituicao_id is None:
            return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
        escola_id = request.data.get('escola')
        if not escola_id or not Escola.objects.filter(id=escola_id, instituicao_id=instituicao_id).exists():
            return Response({'error': 'Campo escola é obrigatório e precisa pertencer à sua instituição.'},
                             status=status.HTTP_400_BAD_REQUEST)

    serializer = ContratoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    contrato = serializer.save(
        escola_id=escola_id, instituicao_id=instituicao_id,
        responsavel=user, gerado_por=user,
    )
    return Response(ContratoSerializer(contrato).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_contrato(request, contrato_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        contrato = Contrato.objects.get(id=contrato_id)
    except Contrato.DoesNotExist:
        return Response({'error': 'Contrato não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ContratoSerializer(contrato).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_contrato(request, contrato_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        contrato = Contrato.objects.get(id=contrato_id)
    except Contrato.DoesNotExist:
        return Response({'error': 'Contrato não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = ContratoSerializer(contrato, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save(atualizado_por=user)
    return Response(serializer.data)