"""Conversores de rota: UUID na URL, id inteiro na view.

Regra do sistema: o banco só trabalha com `id` (int) — PK e todas as FKs. O
`uuid` é o identificador público e é o único que aparece nas URLs.

Cada conversor casa um UUID na URL, busca o `id` do registro e entrega o
INTEIRO para a view. Assim as views continuam recebendo `escola_id`,
`turma_id`... como id de verdade e fazem `Escola.objects.filter(id=escola_id)`
normalmente.

    path('escolas/<escola:escola_id>/', ...)   # /escolas/9f1c.../ → escola_id=12

* UUID que não existe → `ValueError` → o Django trata como rota sem match → 404.
* A busca usa `_base_manager` (sem filtro de tenant) de propósito: aqui só
  traduzimos uuid → id. Quem decide se o usuário pode ver o registro continua
  sendo a view, via `Model.objects` (TenantManager). Fora do escopo também
  vira 404 lá — não dá para descobrir se um uuid de outra escola existe.
* `reverse()` aceita instância, id (int) ou uuid e sempre gera a URL com uuid.
"""

import uuid as uuid_lib

from django.apps import apps
from django.db import models
from django.urls import register_converter


class _UUIDParaIdConverter:
    regex = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    modelo = None  # 'api.Escola'

    def _model(self):
        return apps.get_model(self.modelo)

    def to_python(self, value):
        pk = (
            self._model()._base_manager
            .filter(uuid=value)
            .values_list('pk', flat=True)
            .first()
        )
        if pk is None:
            raise ValueError(f'{self.modelo} com uuid {value} não existe.')
        return pk

    def to_url(self, value):
        if isinstance(value, models.Model):
            return str(value.uuid)
        if isinstance(value, uuid_lib.UUID):
            return str(value)
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            encontrado = (
                self._model()._base_manager
                .filter(pk=int(value))
                .values_list('uuid', flat=True)
                .first()
            )
            if encontrado is None:
                raise ValueError(f'{self.modelo} com id {value} não existe.')
            return str(encontrado)
        return str(value)


# nome usado na rota  →  model
CONVERSORES = {
    'instituicao': 'api.Instituicao',
    'escola': 'api.Escola',
    'especialista': 'api.Especialista',
    'usuario': 'api.Usuario',
    'turma': 'api.Turma',
    'disciplina': 'api.Disciplina',
    'aluno': 'api.Aluno',
    'projeto': 'api.Projeto',
    'producao': 'api.Producao',
    'producao_aluno': 'api.ProducaoAluno',
    'registro_escrita': 'api.RegistroEscrita',
    'registro_desenho': 'api.RegistroDesenho',
    'registro_leitura': 'api.RegistroLeitura',
    'campo_pedagogico': 'api.CampoPedagogico',
    'habilidade_bncc': 'api.HabilidadeBNCC',
    'pergunta': 'api.Pergunta',
    'pergunta_especialista': 'api.PerguntaEspecialista',
    'registro_observacao': 'api.RegistroObservacao',
    'observacao_transcricao': 'api.ObservacaoTranscricao',
    'planejamento_semanal': 'api.PlanejamentoSemanal',
    'periodo_avaliativo': 'api.PeriodoAvaliativo',
    'relatorio_template': 'api.RelatorioTemplate',
    'relatorio': 'api.Relatorio',
    'notificacao': 'api.Notificacao',
    'meta_paee': 'api.MetaPAEE',
    'sessao_especialista': 'api.SessaoEspecialista',
    'tarefa_paee': 'api.TarefaPAEE',
    'dispositivo': 'api.DispositivoGravador',
    'ticket': 'api.Ticket',
    'resposta_ticket': 'api.RespostaTicket',
    'log_auditoria': 'api.LogAuditoria',
    'permissao_usuario': 'api.PermissaoUsuario',
    'template_documento': 'api.TemplateDocumento',
    'contrato': 'api.Contrato',
    'prompt_categoria': 'api.PromptCategoria',
}


def registrar_conversores():
    for nome, modelo in CONVERSORES.items():
        classe = type(f'{nome.title().replace("_", "")}Converter', (_UUIDParaIdConverter,), {'modelo': modelo})
        register_converter(classe, nome)