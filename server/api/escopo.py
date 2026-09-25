"""Regras de escopo multi-tenant usadas pelas views (escrita e painéis).

O `TenantManager` protege a LEITURA automaticamente. A escrita não tem essa
rede de proteção: quem decide `escola`/`instituicao` de um registro novo — ou
se um registro pode mudar de dono — é a view. Estas funções concentram essas
decisões num lugar só, para que todas as views apliquem a mesma regra.

Invariantes garantidos:
  * a instituição de um registro SEMPRE vem da escola (nunca do body);
  * admin só grava em escolas da própria rede;
  * coordenador só grava na própria escola;
  * registro "oficial" (escola E instituição nulas) só o superadmin cria/edita.

As funções devolvem `(valores..., erro)`, onde `erro` é um `Response` pronto no
formato `{'error': ...}` usado em toda a API, ou `None`.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from api.models import Aluno, Escola, UsuarioTurma
from api.tenancy import is_superadmin  # noqa: F401 — fonte única em tenancy; reexportado


def _erro(mensagem, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'error': mensagem}, status=codigo)


def _buscar_escola(escola_id):
    """Escola por id, sem filtro de tenant (a checagem de dono é feita por quem chama).
    UUID malformado vira None em vez de 500."""
    try:
        return Escola.objects.filter(id=escola_id).first()
    except (DjangoValidationError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------

SEM_ESCOLA_PROIBIDO = 'proibido'          # escola obrigatória para todos
SEM_ESCOLA_OFICIAL = 'oficial'            # superadmin pode omitir → registro oficial (ambos nulos)
SEM_ESCOLA_INSTITUICAO = 'instituicao'    # admin/superadmin podem omitir → registro da rede inteira


def resolver_escopo_criacao(user, data, sem_escola=SEM_ESCOLA_PROIBIDO):
    """Decide (escola_id, instituicao_id) de um registro novo.

    Retorna `(escola_id, instituicao_id, erro)`.
    """
    escola_id = data.get('escola') or None

    if is_superadmin(user):
        if escola_id:
            escola = _buscar_escola(escola_id)
            if escola is None:
                return None, None, _erro('Escola não encontrada.')
            instituicao_informada = data.get('instituicao')
            if instituicao_informada and str(instituicao_informada) != str(escola.instituicao_id):
                return None, None, _erro('A escola informada não pertence à instituição informada.')
            return escola.id, escola.instituicao_id, None
        if sem_escola == SEM_ESCOLA_OFICIAL:
            return None, None, None
        if sem_escola == SEM_ESCOLA_INSTITUICAO and data.get('instituicao'):
            return None, data.get('instituicao'), None
        return None, None, _erro('Campo escola é obrigatório.')

    if user.nivel == 'admin':
        if user.instituicao_id is None:
            return None, None, _erro('Usuário sem instituição vinculada.')
        if escola_id:
            escola = _buscar_escola(escola_id)
            if escola is None or escola.instituicao_id != user.instituicao_id:
                return None, None, _erro('A escola informada não pertence à sua instituição.')
            return escola.id, user.instituicao_id, None
        if sem_escola == SEM_ESCOLA_INSTITUICAO:
            return None, user.instituicao_id, None
        return None, None, _erro('Campo escola é obrigatório e precisa pertencer à sua instituição.')

    # coordenador e demais perfis de escola: sempre a própria escola (body ignorado)
    if user.escola_id is None:
        return None, None, _erro('Usuário sem escola vinculada.')
    return user.escola_id, user.instituicao_id, None


# ---------------------------------------------------------------------------
# Registros "oficial OU customizado" (CampoPedagogico, Pergunta)
# ---------------------------------------------------------------------------

def eh_oficial(obj) -> bool:
    """Oficial = escola E instituição nulas. Só escola nula NÃO basta: registros
    com instituição preenchida e escola nula pertencem a uma rede."""
    return obj.escola_id is None and obj.instituicao_id is None


OFICIAL = Q(escola__isnull=True, instituicao__isnull=True)


def filtro_oficiais_e_da_escola(escola_id) -> Q:
    """O que UMA ESCOLA enxerga de um cadastro "oficial OU customizado"
    (Pergunta, CampoPedagogico): os oficiais — comuns a todas as escolas, sem
    exceção — mais os customizados da própria escola.

    Fonte única desta regra: views e services (painel da coordenação,
    relatório, matriz de indicadores) usam esta função. Nunca usar só
    `escola__isnull=True`: isso também traz registros de escola nula com
    instituição preenchida, que pertencem a OUTRA rede.
    """
    if escola_id is None:
        # Registro oficial (sem escola) só pode referenciar outros oficiais.
        # Sem este caso, `Q(escola_id=None)` traria também os de escola nula
        # e instituição preenchida — de outra rede.
        return OFICIAL
    return OFICIAL | Q(escola_id=escola_id)


def buscar_visivel(model, pk, user):
    """Registro "oficial OU customizado" que o usuário pode ver (ver
    `filtro_visiveis`), ou None — inexistente, de outro escopo ou UUID
    malformado. Fora do escopo vira 404, sem revelar que o id existe."""
    try:
        return model._base_manager.filter(filtro_visiveis(user), pk=pk).first()
    except (DjangoValidationError, ValueError, TypeError):
        return None


def buscar_oficial_ou_da_escola(model, pk, escola_id):
    """Registro "oficial OU customizado" utilizável pela escola informada, ou
    None (inexistente, de outra escola/rede ou UUID malformado)."""
    try:
        return model._base_manager.filter(filtro_oficiais_e_da_escola(escola_id), pk=pk).first()
    except (DjangoValidationError, ValueError, TypeError):
        return None


def filtro_visiveis(user) -> Q:
    """Q para `Model.todos` (manager sem tenant): oficiais + os do escopo do usuário."""
    if is_superadmin(user):
        return Q()
    if user.nivel == 'admin':
        return OFICIAL | Q(instituicao_id=user.instituicao_id) if user.instituicao_id else OFICIAL
    return filtro_oficiais_e_da_escola(user.escola_id) if user.escola_id else OFICIAL


def pode_ver(user, obj) -> bool:
    if is_superadmin(user) or eh_oficial(obj):
        return True
    if user.nivel == 'admin':
        return obj.instituicao_id is not None and obj.instituicao_id == user.instituicao_id
    return obj.escola_id is not None and obj.escola_id == user.escola_id


def pode_editar(user, obj):
    """Retorna `erro` (Response) ou None. Oficial: só superadmin."""
    if is_superadmin(user):
        return None
    if eh_oficial(obj):
        return _erro('Só superadmin pode editar registros oficiais.', status.HTTP_403_FORBIDDEN)
    if not pode_ver(user, obj):
        return _erro('Sem permissão.', status.HTTP_403_FORBIDDEN)
    return None


# ---------------------------------------------------------------------------
# Usuário: escola/instituição/especialista na criação e na edição
# ---------------------------------------------------------------------------

def validar_vinculos_usuario(user, data, alvo=None):
    """Normaliza escola/instituicao/especialista do payload de Usuario conforme
    quem está editando. Muta `data` (dict) e retorna `erro` ou None.

    * superadmin: livre, mas escola e instituição precisam ser consistentes;
    * admin: instituição forçada para a dele; escola só da rede dele;
    * coordenador: não move ninguém (escola/instituição forçadas para as dele).
    """
    def diferente(campo, esperado):
        valor = data.get(campo)
        return campo in data and valor not in (None, '') and str(valor) != str(esperado)

    if is_superadmin(user):
        pass
    elif user.nivel == 'admin':
        # Pedido que tenta outra instituição é recusado INTEIRO — não aplicar
        # "o resto" (nível, senha) de uma requisição que tentava outra coisa.
        if diferente('instituicao', user.instituicao_id):
            return _erro('Você não pode vincular usuários a outra instituição.', status.HTTP_403_FORBIDDEN)
        data['instituicao'] = user.instituicao_id
        escola_id = data.get('escola')
        if escola_id:
            escola = _buscar_escola(escola_id)
            if escola is None or escola.instituicao_id != user.instituicao_id:
                return _erro('Escola informada não pertence à sua instituição.')
    else:
        if diferente('instituicao', user.instituicao_id) or diferente('escola', user.escola_id):
            return _erro('Você não pode vincular usuários a outra escola.', status.HTTP_403_FORBIDDEN)
        data['instituicao'] = user.instituicao_id
        data['escola'] = user.escola_id

    # Estado FINAL (payload sobre o registro atual) precisa ser consistente.
    def final(campo):
        if campo in data:
            return data[campo]
        return getattr(alvo, f'{campo}_id', None) if alvo else None

    escola_final, instituicao_final = final('escola'), final('instituicao')
    if escola_final:
        escola = _buscar_escola(escola_final)
        if escola is None:
            return _erro('Escola não encontrada.')
        if instituicao_final is None or str(escola.instituicao_id) != str(instituicao_final):
            return _erro('A escola informada não pertence à instituição do usuário.')

    especialista_id = data.get('especialista')
    if especialista_id:
        from api.models import Especialista
        try:
            esp = Especialista._base_manager.filter(id=especialista_id).first()
        except (DjangoValidationError, ValueError):
            esp = None
        if esp is None or str(esp.instituicao_id) != str(instituicao_final):
            return _erro('Especialista informado não pertence à instituição do usuário.')
    return None


# ---------------------------------------------------------------------------
# Gestão e busca no escopo (views de cadastro)
# ---------------------------------------------------------------------------

NIVEIS_GESTAO = ('admin', 'coordenador')
NIVEIS_ESPECIALISTA = ('especialista', 'professor_especialista')


def eh_especialista(user) -> bool:
    return user.nivel in NIVEIS_ESPECIALISTA


def pode_gerenciar(user) -> bool:
    """Quem pode criar/editar cadastros (turma, aluno, usuário...)."""
    return is_superadmin(user) or user.nivel in NIVEIS_GESTAO


def buscar_no_escopo(model, pk):
    """Objeto pelo id via `model.objects` (TenantManager): fora do escopo do
    usuário → None, igual a inexistente. UUID malformado → None em vez de 500."""
    try:
        return model.objects.filter(pk=pk).first()
    except (DjangoValidationError, ValueError, TypeError):
        return None


def filtrar_por(qs, request, parametro, model, campo):
    """Aplica `?<parametro>=<uuid>` como filtro por FK. Id inexistente, fora do
    escopo ou malformado → queryset vazio (em vez de 500)."""
    valor = request.query_params.get(parametro)
    if not valor:
        return qs
    obj = buscar_no_escopo(model, valor)
    return qs.filter(**{campo: obj}) if obj else qs.none()


def professor_vinculado_turma(usuario, turma_id) -> bool:
    """Usuário tem vínculo (UsuarioTurma) com a turma."""
    if turma_id is None:
        return False
    return UsuarioTurma.objects.filter(usuario=usuario, turma_id=turma_id).exists()


def dono_ou_gestao(user, obj, campo_dono='professor_id') -> bool:
    """Editar/apagar um registro: gestão pode qualquer um do escopo; os demais,
    só os próprios (`campo_dono` aponta o autor: professor_id, usuario_especialista_id...)."""
    return pode_gerenciar(user) or getattr(obj, campo_dono) == user.id


def aluno_do_body(request, campo='aluno', exigir_vinculo=True):
    """Aluno informado no body para criar um registro. Retorna `(aluno, erro)`.

    Com `exigir_vinculo`, quem não é gestão precisa estar vinculado
    (UsuarioTurma) à turma do aluno.
    """
    aluno_id = request.data.get(campo)
    if not aluno_id:
        return None, _erro(f'Campo {campo} é obrigatório.')
    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return None, _erro('Aluno não encontrado.', status.HTTP_404_NOT_FOUND)
    if exigir_vinculo and not pode_gerenciar(request.user) \
            and not professor_vinculado_turma(request.user, aluno.turma_id):
        return None, _erro('Você não está vinculado à turma desse aluno.', status.HTTP_403_FORBIDDEN)
    return aluno, None


# ---------------------------------------------------------------------------
# Leitura por escola (painéis da coordenação)
# ---------------------------------------------------------------------------

def pode_ver_escola(user, escola) -> bool:
    """Regra única de leitura por escola. `escola` é a instância, não o id."""
    if is_superadmin(user):
        return True
    if user.nivel == 'admin':
        return user.instituicao_id is not None and escola.instituicao_id == user.instituicao_id
    return user.escola_id is not None and escola.id == user.escola_id


def resolver_escola_painel(request):
    """Escola alvo dos painéis da coordenação. Retorna `(escola_id, erro)`.

    * coordenador: sempre a própria escola (query string ignorada);
    * admin/superadmin: `?escola_id=` obrigatório (podem gerenciar várias);
    * demais perfis: 403.
    """
    user = request.user
    if user.nivel == 'coordenador':
        if not user.escola_id:
            return None, _erro('Usuário sem escola vinculada.', status.HTTP_403_FORBIDDEN)
        return user.escola_id, None

    if not (is_superadmin(user) or user.nivel == 'admin'):
        return None, _erro('Sem permissão.', status.HTTP_403_FORBIDDEN)

    escola_id = request.GET.get('escola_id')
    if not escola_id:
        return None, _erro('Parâmetro escola_id é obrigatório para este nível.')

    escola = _buscar_escola(escola_id)  # UUID malformado → None, não 500
    if escola is None:
        return None, _erro('Escola não encontrada.', status.HTTP_404_NOT_FOUND)
    if not pode_ver_escola(user, escola):
        return None, _erro('Escola não pertence à sua instituição.', status.HTTP_403_FORBIDDEN)
    return escola.id, None