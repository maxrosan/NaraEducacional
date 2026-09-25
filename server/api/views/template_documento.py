"""Endpoints de TemplateDocumento e Contrato.

Só superadmin e admin (`escopo.pode_administrar`). Template pode ser da rede
inteira (escola nula) ou de uma escola; contrato é sempre de uma escola, e a
instituição de ambos vem SEMPRE da escola / do escopo (`resolver_escopo_criacao`).
"""

from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import SEM_ESCOLA_INSTITUICAO, buscar_no_escopo, pode_administrar, resolver_escopo_criacao
from api.models import TemplateDocumento, Contrato
from api.serializers import TemplateDocumentoSerializer, ContratoSerializer


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _obj_ou_404(model, obj_id, mensagem):
    """Retorna (obj, erro)."""
    obj = buscar_no_escopo(model, obj_id)
    if obj is None:
        return None, Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)
    return obj, None


def _salvar_edicao(request, obj, serializer_class):
    partial = request.method == 'PATCH'
    serializer = serializer_class(obj, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save(atualizado_por=request.user)
    return Response(serializer.data)


# ============================================================
# TemplateDocumento
# ============================================================

_TEMPLATE_NAO_ENCONTRADO = 'Template não encontrado.'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_templates_documento(request):
    if not pode_administrar(request.user):
        return _sem_permissao()
    templates = TemplateDocumento.objects.all()
    return Response(TemplateDocumentoSerializer(templates, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_template_documento(request):
    user = request.user
    if not pode_administrar(user):
        return _sem_permissao()

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
    if not pode_administrar(request.user):
        return _sem_permissao()
    template, erro = _obj_ou_404(TemplateDocumento, template_id, _TEMPLATE_NAO_ENCONTRADO)
    if erro:
        return erro
    return Response(TemplateDocumentoSerializer(template).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_template_documento(request, template_id):
    if not pode_administrar(request.user):
        return _sem_permissao()
    template, erro = _obj_ou_404(TemplateDocumento, template_id, _TEMPLATE_NAO_ENCONTRADO)
    if erro:
        return erro
    return _salvar_edicao(request, template, TemplateDocumentoSerializer)


# ============================================================
# Contrato
# ============================================================

_CONTRATO_NAO_ENCONTRADO = 'Contrato não encontrado.'


def _template_invalido(request, escola_id, instituicao_id):
    """Se o body informa `template`, ele precisa ser da mesma rede do contrato
    e ser da rede inteira ou da própria escola do contrato. Retorna `erro` ou None."""
    template_id = request.data.get('template')
    if not template_id:
        return None
    try:
        ok = TemplateDocumento._base_manager.filter(
            Q(escola__isnull=True) | Q(escola_id=escola_id),
            pk=template_id, instituicao_id=instituicao_id,
        ).exists()
    except (ValidationError, ValueError):
        ok = False
    if not ok:
        return Response({'error': 'Template não encontrado para a escola deste contrato.'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_contratos(request):
    if not pode_administrar(request.user):
        return _sem_permissao()
    contratos = Contrato.objects.all()
    return Response(ContratoSerializer(contratos.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_contrato(request):
    user = request.user
    if not pode_administrar(user):
        return _sem_permissao()

    # Escola obrigatória; instituição derivada dela (superadmin) ou a do admin.
    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    erro = _template_invalido(request, escola_id, instituicao_id)
    if erro:
        return erro

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
    if not pode_administrar(request.user):
        return _sem_permissao()
    contrato, erro = _obj_ou_404(Contrato, contrato_id, _CONTRATO_NAO_ENCONTRADO)
    if erro:
        return erro
    return Response(ContratoSerializer(contrato).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_contrato(request, contrato_id):
    if not pode_administrar(request.user):
        return _sem_permissao()
    contrato, erro = _obj_ou_404(Contrato, contrato_id, _CONTRATO_NAO_ENCONTRADO)
    if erro:
        return erro

    erro = _template_invalido(request, contrato.escola_id, contrato.instituicao_id)
    if erro:
        return erro
    return _salvar_edicao(request, contrato, ContratoSerializer)