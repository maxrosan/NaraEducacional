"""Endpoints de RegistroEscrita e RegistroDesenho (RegistroLeitura fica em views/leitura.py).

As duas entidades têm exatamente as mesmas regras, então as rotas delegam
para os helpers genéricos abaixo:
  * leitura: todos do escopo (TenantManager);
  * edição/exclusão: gestão, ou o professor autor do registro.

Não há rota de criação: os registros nascem no fluxo de análise por IA
(`views/analise_producao.py` → `services.analise_producao.salvar_registro_*`),
que é quem sobe o arquivo e preenche os campos `arquivo_*` (read-only aqui).
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, dono_ou_gestao, filtrar_por
from api.models import RegistroEscrita, RegistroDesenho, Aluno
from api.serializers import RegistroEscritaSerializer, RegistroDesenhoSerializer

_NAO_ENCONTRADO = 'Registro não encontrado.'


# ============================================================
# Helpers genéricos (escrita e desenho)
# ============================================================

def _listar(request, model, serializer_class):
    registros = filtrar_por(model.objects.all(), request, 'aluno', Aluno, 'aluno')
    return Response(serializer_class(registros.order_by('-criado_em'), many=True).data)


def _registro_ou_erro(request, model, registro_id, editar=False):
    """Retorna (registro, erro). Com `editar=True` também checa a permissão."""
    registro = buscar_no_escopo(model, registro_id)
    if registro is None:
        return None, Response({'error': _NAO_ENCONTRADO}, status=status.HTTP_404_NOT_FOUND)
    if editar and not dono_ou_gestao(request.user, registro):
        return None, Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    return registro, None


def _detalhe(request, model, serializer_class, registro_id):
    registro, erro = _registro_ou_erro(request, model, registro_id)
    if erro:
        return erro
    return Response(serializer_class(registro).data)


def _atualizar(request, model, serializer_class, registro_id):
    registro, erro = _registro_ou_erro(request, model, registro_id, editar=True)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = serializer_class(registro, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


def _deletar(request, model, registro_id):
    registro, erro = _registro_ou_erro(request, model, registro_id, editar=True)
    if erro:
        return erro
    registro.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# RegistroEscrita
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_escrita(request):
    return _listar(request, RegistroEscrita, RegistroEscritaSerializer)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_registro_escrita(request, registro_id):
    return _detalhe(request, RegistroEscrita, RegistroEscritaSerializer, registro_id)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_registro_escrita(request, registro_id):
    return _atualizar(request, RegistroEscrita, RegistroEscritaSerializer, registro_id)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_escrita(request, registro_id):
    return _deletar(request, RegistroEscrita, registro_id)


# ============================================================
# RegistroDesenho
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_desenho(request):
    return _listar(request, RegistroDesenho, RegistroDesenhoSerializer)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_registro_desenho(request, registro_id):
    return _detalhe(request, RegistroDesenho, RegistroDesenhoSerializer, registro_id)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_registro_desenho(request, registro_id):
    return _atualizar(request, RegistroDesenho, RegistroDesenhoSerializer, registro_id)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_desenho(request, registro_id):
    return _deletar(request, RegistroDesenho, registro_id)