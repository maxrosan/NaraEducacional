"""Planejamento: autor, arquivos da turma e IA (sugestões de atividades e BNCC).

Views:
  * professor não cria em nome de outro; coordenador cria pela professora;
  * arquivo de outra turma é recusado;
  * arquivo compartilhado entre semanas só sai do storage quando ninguém usa.

IA (services/planejamento_ia.py, com a OpenAI mockada) — cada tarefa usa a
sua categoria de prompt:
  * sugestão de atividades → "Planejamento" (global = texto do legado);
  * sugestão de habilidades BNCC → "Planejamento - Habilidades BNCC", com o
    formato JSON SEMPRE anexado pelo código — mesmo se o texto do banco (ou o
    personalizado da escola) não falar em JSON. Sem isso a OpenAI recusa o
    response_format=json_object e a tela caía no fallback por palavras-chave.
"""
from datetime import date
from unittest.mock import MagicMock, patch

from api.models import PlanejamentoDiario, PlanejamentoSemanal, PromptCategoria, PromptTemplate
from api.services import planejamento_ia
from api.services.planejamento_ia import (
    CATEGORIA_PLANEJAMENTO_ATIVIDADES,
    CATEGORIA_PLANEJAMENTO_BNCC,
    _FORMATO_RESPOSTA_BNCC,
    sugerir_atividades_a_partir_de_prompt,
    sugerir_habilidades_bncc,
)

from .base import CenarioMultiTenant


# ======================================================================
# Views de planejamento
# ======================================================================

class PlanejamentoTests(CenarioMultiTenant):

    SEGUNDA = date(2026, 3, 2)

    def _criar(self, **extra):
        return self.client.post('/api/planejamento/criar/', {
            'turma_id': str(self.turma_a1.id), 'semana_inicio': self.SEGUNDA.isoformat(), **extra,
        }, format='json')

    def test_professor_nao_cria_planejamento_em_nome_de_outro(self):
        self.entrar(self.prof_a1)
        r = self._criar(professor_id=str(self.coord_a1.id))
        self.assertEqual(r.status_code, 403, r.content)
        self.assertFalse(PlanejamentoSemanal.objects.exists())

    def test_coordenador_cria_em_nome_da_professora(self):
        self.entrar(self.coord_a1)
        r = self._criar(professor_id=str(self.prof_a1.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(PlanejamentoSemanal.objects.get().professor_id, self.prof_a1.id)

    def test_arquivo_de_outra_turma_e_recusado(self):
        chave_b1 = f'planejamentos/{self.turma_b1.id}/segunda/alheio.pdf'
        self.entrar(self.prof_a1)
        r = self._criar(dias={'segunda': {'arquivo_storage_key': chave_b1}})
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(PlanejamentoSemanal.objects.exists())

    @patch('api.views.planejamento.remover_arquivo_planejamento')
    def test_arquivo_compartilhado_so_e_apagado_quando_ninguem_mais_usa(self, remover):
        """Bug: `aplicar_em_semanas` grava o mesmo arquivo em várias semanas;
        trocar o arquivo de UMA apagava do storage o arquivo de todas."""
        chave = f'planejamentos/{self.turma_a1.id}/segunda/compartilhado.pdf'
        semanas = []
        for i in range(2):
            inicio = date(2026, 3, 2 + 7 * i)
            semana = PlanejamentoSemanal.objects.create(
                turma=self.turma_a1, semana_inicio=inicio, semana_fim=date(2026, 3, 6 + 7 * i),
                professor=self.prof_a1, escola=self.a1, instituicao=self.rede_a,
            )
            PlanejamentoDiario.objects.create(
                planejamento_semanal=semana, dia_semana='segunda', data=inicio,
                arquivo_storage_key=chave, escola=self.a1, instituicao=self.rede_a,
            )
            semanas.append(semana)

        self.entrar(self.prof_a1)
        sem_arquivo = {'dias': {'segunda': {'arquivo_storage_key': None}}}

        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.put(f'/api/planejamento/{semanas[0].id}/atualizar/', sem_arquivo, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        remover.assert_not_called()  # a outra semana ainda usa o arquivo

        with self.captureOnCommitCallbacks(execute=True):
            self.client.put(f'/api/planejamento/{semanas[1].id}/atualizar/', sem_arquivo, format='json')
        remover.assert_called_once_with(chave)


# ======================================================================
# Sugestões com IA
# ======================================================================

CANDIDATAS = [{
    'id': 'h1', 'codigo': 'EI03EF01', 'descricao': 'Expressar ideias por meio da linguagem oral',
    'componente_curricular': '', 'ano_serie': '', 'campo_atuacao': '',
}]
RESPOSTA_IA = '{"habilidades": [{"id": "h1", "codigo": "EI03EF01", "justificativa": "Roda de conversa."}]}'


def _cliente_openai(conteudo=RESPOSTA_IA):
    cliente = MagicMock()
    cliente.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content=conteudo))]
    return cliente


@patch.object(planejamento_ia, '_candidatos_bncc', return_value=CANDIDATAS)
class SugestaoBnccTests(CenarioMultiTenant):
    def _sistema(self, cliente):
        return cliente.chat.completions.create.call_args.kwargs['messages'][0]['content']

    def test_usa_a_categoria_propria_e_anexa_o_formato_json(self, _candidatas):
        cliente = _cliente_openai()
        with patch.object(planejamento_ia, 'get_openai_client', return_value=cliente):
            resultado = sugerir_habilidades_bncc('Roda de conversa sobre a família.', escola_id=self.a1.id)

        self.assertEqual(resultado['origem'], 'ia')
        self.assertEqual([h['codigo'] for h in resultado['habilidades']], ['EI03EF01'])
        sistema = self._sistema(cliente)
        self.assertTrue(sistema.startswith('Você é uma especialista pedagógica'))
        self.assertTrue(sistema.endswith(_FORMATO_RESPOSTA_BNCC))
        self.assertIn('JSON', sistema)

    def test_personalizado_sem_json_continua_valido(self, _candidatas):
        categoria = PromptCategoria.objects.get(titulo=CATEGORIA_PLANEJAMENTO_BNCC)
        PromptTemplate._base_manager.create(
            categoria=categoria, escola=self.a1, instituicao=self.rede_a,
            personalizado='Escolha as habilidades mais ligadas ao brincar.',
        )
        cliente = _cliente_openai()
        with patch.object(planejamento_ia, 'get_openai_client', return_value=cliente):
            sugerir_habilidades_bncc('Roda de conversa sobre a família.', escola_id=self.a1.id)

        sistema = self._sistema(cliente)
        self.assertTrue(sistema.startswith('Escolha as habilidades mais ligadas ao brincar.'))
        self.assertIn('JSON', sistema)

    def test_global_de_atividades_nao_vaza_para_bncc(self, _candidatas):
        cliente = _cliente_openai()
        with patch.object(planejamento_ia, 'get_openai_client', return_value=cliente):
            sugerir_habilidades_bncc('Roda de conversa sobre a família.')
        self.assertNotIn('sugira atividades', self._sistema(cliente))

    def test_codigo_fora_da_lista_cai_no_fallback(self, _candidatas):
        cliente = _cliente_openai('{"habilidades": [{"id": "x", "codigo": "INVENTADO"}]}')
        with patch.object(planejamento_ia, 'get_openai_client', return_value=cliente):
            resultado = sugerir_habilidades_bncc('Roda de conversa sobre a família.')
        self.assertEqual(resultado['origem'], 'fallback')


class SugestaoAtividadesTests(CenarioMultiTenant):
    def test_usa_o_global_de_planejamento(self):
        with patch.object(planejamento_ia, '_chamar_openai_text', return_value='- Atividade') as chamar:
            sugerir_atividades_a_partir_de_prompt('Trabalhar cores primárias com tinta.')
        sistema = chamar.call_args.args[0]
        self.assertEqual(
            sistema,
            'Com base nas habilidades BNCC informadas e no histórico da turma, sugira atividades.',
        )
        self.assertEqual(CATEGORIA_PLANEJAMENTO_ATIVIDADES, 'Planejamento')

    def test_personalizado_de_bncc_nao_afeta_atividades(self):
        PromptTemplate._base_manager.create(
            categoria=PromptCategoria.objects.get(titulo=CATEGORIA_PLANEJAMENTO_BNCC),
            escola=self.a1, instituicao=self.rede_a, personalizado='SÓ BNCC',
        )
        with patch.object(planejamento_ia, '_chamar_openai_text', return_value='- Atividade') as chamar:
            sugerir_atividades_a_partir_de_prompt('Trabalhar cores primárias com tinta.', escola_id=self.a1.id)
        self.assertNotIn('SÓ BNCC', chamar.call_args.args[0])