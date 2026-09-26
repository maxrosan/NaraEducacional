"""Relatórios (lista da coordenação, PDF, geração com IA, exclusão) e
planejamento (autor, arquivo da turma, arquivo compartilhado entre semanas).
"""
from datetime import date
from unittest.mock import patch

from api.models import PlanejamentoDiario, PlanejamentoSemanal, Relatorio, Turma

from .base import CenarioMultiTenant

CONTEUDO_FINALIZADO = 'x' * 60


class ListaRelatoriosCoordenacaoTests(CenarioMultiTenant):
    """Bug: `resolver_recorte` era chamado sem `escola_id` → TypeError,
    engolido pelo `except Exception` → a tela recebia 404 SEMPRE."""

    URL = '/api/relatorios/coordenacao/'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rel_a1 = Relatorio.objects.create(aluno=cls.aluno_a1, escola=cls.a1, instituicao=cls.rede_a,
                                              conteudo=CONTEUDO_FINALIZADO)
        cls.rel_a2 = Relatorio.objects.create(aluno=cls.aluno_a2, escola=cls.a2, instituicao=cls.rede_a,
                                              conteudo=CONTEUDO_FINALIZADO)

    def _ids(self, resposta):
        return {r['id'] for r in resposta.data['results']}

    def test_coordenador_lista_os_relatorios_da_propria_escola(self):
        self.entrar(self.coord_a1)
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._ids(r), {str(self.rel_a1.id)})

    def test_admin_escolhe_a_escola(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(self.URL).status_code, 400)
        r = self.client.get(self.URL, {'escola_id': str(self.a2.id)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._ids(r), {str(self.rel_a2.id)})

    def test_admin_nao_lista_escola_de_outra_rede(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(self.URL, {'escola_id': str(self.b1.id)}).status_code, 403)

    def test_professor_nao_acessa_a_lista_da_coordenacao(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self.client.get(self.URL).status_code, 403)


class RelatorioPdfEGeracaoTests(CenarioMultiTenant):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.turma_a1_extra = Turma.objects.create(nome='Nível 4A', escola=cls.a1, instituicao=cls.rede_a)
        cls.aluno_turma_extra = cls._aluno('Duda A1 extra', cls.turma_a1_extra)
        cls.rel_a1 = Relatorio.objects.create(aluno=cls.aluno_a1, escola=cls.a1, instituicao=cls.rede_a,
                                              conteudo=CONTEUDO_FINALIZADO)

    @patch('api.views.relatorio.build_filename', return_value='relatorio.pdf')
    @patch('api.views.relatorio.ensure_pdf', return_value=(b'%PDF-1.4', True, None))
    def test_superadmin_baixa_o_pdf(self, _ensure, _nome):
        """Bug: a checagem manual comparava a instituição do usuário (nula no
        superadmin) com a do relatório → 403."""
        self.entrar(self.superadmin)
        r = self.client.get(f'/api/relatorios/{self.rel_a1.id}/pdf/download/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r.content))
        self.assertEqual(r['Content-Type'], 'application/pdf')

    @patch('api.views.relatorio.gerar_relatorio_com_ia')
    def test_professor_nao_gera_relatorio_de_aluno_de_turma_nao_vinculada(self, gerar):
        self.entrar(self.prof_a1)
        r = self.client.post('/api/gerar-relatorio/', {'crianca_id': str(self.aluno_turma_extra.id)}, format='json')
        self.assertEqual(r.status_code, 403, r.content)
        gerar.assert_not_called()

    @patch('api.views.relatorio.buscar_dados_estudante_para_relatorio', return_value={})
    @patch('api.views.relatorio.gerar_relatorio_com_ia', return_value={'content': 'ok'})
    def test_nome_enviado_para_a_ia_vem_do_cadastro(self, gerar, _dados):
        self.entrar(self.prof_a1)
        r = self.client.post('/api/gerar-relatorio/', {
            'crianca_id': str(self.aluno_a1.id), 'nome_crianca': 'Nome Inventado',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(gerar.call_args.args[0], 'Ana A1')

    @patch('api.signals.delete_from_storage')
    def test_excluir_relatorio_apaga_o_pdf_do_storage(self, apagar):
        """Bug: a exclusão em uso (views/avaliacao.py) deixava o PDF órfão."""
        # Um relatório por aluno/escola (unique_relatorio_aluno_escola): usa o
        # da fixture. `update` não dispara o pre_save que limparia o PDF.
        Relatorio.objects.filter(pk=self.rel_a1.pk).update(pdf_storage_key='relatorios/pdf/r.pdf')
        self.entrar(self.prof_a1)
        r = self.client.delete(f'/api/relatorios/{self.rel_a1.id}/deletar/')
        self.assertEqual(r.status_code, 204, getattr(r, 'data', r.content))
        apagar.assert_called_with('relatorios/pdf/r.pdf')


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