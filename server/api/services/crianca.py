"""Regras de negócio relacionadas a crianças (alunos)."""

from typing import Optional
from uuid import UUID

from api.models import Crianca, Turma


def _split_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item for item in value.split(',') if item]


def listar_criancas_filtradas(
    *,
    crianca_id: Optional[str] = None,
    crianca_id_in: Optional[str] = None,
    turma_id: Optional[str] = None,
    turma_id_in: Optional[str] = None,
    instituicao_id: Optional[str] = None,
    status_vinculo: Optional[str] = None,
    nome: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> tuple[list[Crianca], dict[UUID, str], Optional[int]]:
    """Retorna crianças filtradas, um mapa {turma_id: nome}, e o total de
    registros (só quando paginado; None caso contrário).

    Paginação é opt-in: se `page` não for informado, devolve todos os
    registros como antes — comportamento usado pelo drill-down do
    coordenador via id__in/turma_id__in, que não deve ser paginado.

    `nome` filtra por busca parcial (case-insensitive) em nome_completo,
    necessário para a busca da tela de gestão de alunos continuar
    funcionando corretamente quando combinada com paginação (sem isso,
    buscar um nome que está fora da página atual não encontraria nada).
    """
    queryset = Crianca.objects.all()

    if crianca_id:
        queryset = queryset.filter(id=crianca_id)
    if crianca_id_in:
        queryset = queryset.filter(id__in=_split_csv(crianca_id_in))
    if turma_id:
        queryset = queryset.filter(turma_id=turma_id)
    if turma_id_in:
        queryset = queryset.filter(turma_id__in=_split_csv(turma_id_in))
    if instituicao_id:
        queryset = queryset.filter(instituicao_id=instituicao_id)
    if nome:
        queryset = queryset.filter(nome_completo__icontains=nome)

    # Filtro por status_vinculo:
    # - valor explícito ('ativo', 'inativo', ...) => filtra por ele;
    # - 'all'/'todos' => sem filtro (gestão de alunos do admin, que precisa ver inativos);
    # - ausente => oculta inativos por padrão, exceto em busca por id único, para que
    #   relatórios/portfólios de um aluno já desativado ainda possam ser abertos diretamente.
    if status_vinculo and status_vinculo not in ('all', 'todos'):
        queryset = queryset.filter(status_vinculo=status_vinculo)
    elif not status_vinculo and not crianca_id:
        queryset = queryset.filter(status_vinculo='ativo')

    queryset = queryset.order_by('nome_completo')

    total = None
    if page:
        total = queryset.count()
        page_size = page_size or 20
        start = (page - 1) * page_size
        queryset = queryset[start:start + page_size]

    criancas = list(queryset)
    turma_ids = {c.turma_id for c in criancas if c.turma_id}
    turma_names = dict(
        Turma.objects.filter(id__in=turma_ids).values_list('id', 'nome')
    )
    return criancas, turma_names, total