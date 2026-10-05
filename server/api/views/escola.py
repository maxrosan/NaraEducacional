"""Endpoints de Escola.

`Escola` não tem TenantManager (é o próprio tenant), então o recorte por
escopo é feito aqui: superadmin vê todas, admin as da própria instituição,
os demais só a própria escola. Criar/editar: superadmin ou admin.
"""

from datetime import timedelta

from django.db.models import Count, DateTimeField, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    buscar_no_escopo, pode_administrar, pode_gerenciar, pode_ver_escola, resolver_instituicao_cadastro,
)
from api.models import (
    Aluno, Escola, RegistroDesenho, RegistroEscrita, RegistroLeitura, RegistroObservacao, Turma, Usuario,
)
from api.serializers import EscolaSerializer
from api.tenancy import is_superadmin


def _escola_ou_erro(user, escola_id):
    """Retorna (escola, erro): 404 inexistente/malformada, 403 fora do escopo."""
    escola = buscar_no_escopo(Escola, escola_id)
    if escola is None:
        return None, Response({'error': 'Escola não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if not pode_ver_escola(user, escola):
        return None, Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    return escola, None


def _escolas_no_escopo(user):
    """Superadmin: todas. Admin: as da própria instituição. Demais: só a própria escola."""
    if is_superadmin(user):
        return Escola.objects.all()
    if user.nivel == 'admin':
        return Escola.objects.filter(instituicao_id=user.instituicao_id) if user.instituicao_id else Escola.objects.none()
    return Escola.objects.filter(id=user.escola_id) if user.escola_id else Escola.objects.none()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_escolas(request):
    """
    Superadmin vê todas. Admin vê as da própria instituição.
    Demais níveis (coordenador, professor, especialista) veem só a própria escola.
    """
    escolas = _escolas_no_escopo(request.user)
    return Response(EscolaSerializer(escolas.order_by('nome'), many=True).data)


# Níveis contados como "professor" no resumo. Usa a lista do model quando existe,
# para não divergir se um novo tipo de professor for criado.
NIVEIS_PROFESSOR = tuple(getattr(
    Usuario, 'PERFIS_PROFESSOR',
    ('professor_infantil', 'professor_fundamental', 'professor_especialista'),
))


def _contagem_por_escola(queryset):
    """Subquery que conta as linhas de `queryset` da escola da linha externa.

    Subquery em vez de Count() nas relações: com três Count() em joins
    diferentes (turmas × alunos × usuários) o banco multiplica as linhas
    antes de contar — lento em escola grande, mesmo com distinct=True.
    """
    contagem = (
        queryset.filter(escola=OuterRef('pk'))
        .order_by()
        .values('escola')
        .annotate(total=Count('pk'))
        .values('total')
    )
    return Coalesce(Subquery(contagem, output_field=IntegerField()), 0)


def _ultimo_por_escola(queryset):
    """Subquery com o `criado_em` mais recente de `queryset` na escola da linha externa."""
    ultimo = queryset.filter(escola=OuterRef('pk')).order_by('-criado_em').values('criado_em')[:1]
    return Subquery(ultimo, output_field=DateTimeField())


# Tudo o que conta como "registro pedagógico" da escola.
MODELOS_REGISTRO = (RegistroObservacao, RegistroEscrita, RegistroDesenho, RegistroLeitura)
DIAS_ATIVIDADE = 30


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resumo_escolas(request):
    """GET /api/admin/dashboard/ — cards do dashboard do admin (/admin/dashboard no front).

    Cada escola do escopo com os totais principais.

    Mesmo recorte de `listar_escolas` (admin → escolas da própria rede). Só
    gestão: professores e especialistas recebem 403.

    Contagens: turmas ativas, alunos com vínculo ativo, professores e
    coordenadores ativos, registros pedagógicos dos últimos 30 dias (observação,
    escrita, desenho e leitura) e a data do registro mais recente.
    Superadmin pode filtrar com ?instituicao_id=.
    """
    user = request.user
    if not pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escolas = _escolas_no_escopo(user)
    instituicao_id = request.query_params.get('instituicao_id')
    if instituicao_id and is_superadmin(user):
        escolas = escolas.filter(instituicao_id=instituicao_id)

    desde = timezone.now() - timedelta(days=DIAS_ATIVIDADE)
    registros_recentes = [
        _contagem_por_escola(modelo.objects.filter(criado_em__gte=desde)) for modelo in MODELOS_REGISTRO
    ]

    escolas = escolas.select_related('instituicao').annotate(
        registros_periodo=sum(registros_recentes[1:], registros_recentes[0]),
        # Greatest no PostgreSQL ignora nulos: só é nulo se a escola não tem registro nenhum.
        ultimo_registro=Greatest(*[_ultimo_por_escola(modelo.objects.all()) for modelo in MODELOS_REGISTRO]),
        total_turmas=_contagem_por_escola(Turma.objects.filter(ativa=True)),
        total_alunos=_contagem_por_escola(Aluno.objects.filter(status_vinculo='ativo')),
        total_professores=_contagem_por_escola(
            Usuario.objects.filter(is_active=True, nivel__in=NIVEIS_PROFESSOR)
        ),
        total_coordenadores=_contagem_por_escola(
            Usuario.objects.filter(is_active=True, nivel='coordenador')
        ),
    ).order_by('-ativa', 'nome')

    return Response([
        {
            'id': str(e.id),
            'nome': e.nome,
            'tipo_unidade': e.tipo_unidade,
            'cidade': e.cidade,
            'estado': e.estado,
            'ativa': e.ativa,
            'instituicao': str(e.instituicao_id),
            'instituicao_nome': e.instituicao.nome,
            'totais': {
                'turmas': e.total_turmas,
                'alunos': e.total_alunos,
                'professores': e.total_professores,
                'coordenadores': e.total_coordenadores,
                'registros_30d': e.registros_periodo,
            },
            'ultimo_registro': e.ultimo_registro.isoformat() if e.ultimo_registro else None,
        }
        for e in escolas
    ])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_escola(request):
    """Cria uma escola. Superadmin informa `instituicao` no body; admin usa sempre a própria."""
    user = request.user
    if not pode_administrar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    instituicao_id, erro = resolver_instituicao_cadastro(user, request.data)
    if erro:
        return erro

    serializer = EscolaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(instituicao_id=instituicao_id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_escola(request, escola_id):
    escola, erro = _escola_ou_erro(request.user, escola_id)
    if erro:
        return erro
    return Response(EscolaSerializer(escola).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_escola(request, escola_id):
    user = request.user
    if not pode_administrar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola, erro = _escola_ou_erro(user, escola_id)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = EscolaSerializer(escola, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)