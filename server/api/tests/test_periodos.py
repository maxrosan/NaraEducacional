"""Testes de PeriodoAvaliativo: todos os endpoints de /api/periodos-avaliativos/.

Seções:
  * listagem     — paginação, abas vigentes/encerrados, filtro por escola, escopo, queries
  * detalhe      — escopo do GET de um período
  * permissões   — quem pode criar, editar e excluir, e em qual escola
  * validações   — datas, ano automático, sobreposição do mesmo tipo na escola
  * exclusão     — endpoint novo de exclusão
"""
from datetime import date, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from api.models import Escola, PeriodoAvaliativo

from .base import CenarioMultiTenant

URL_LISTAR = '/api/periodos-avaliativos/'
URL_CRIAR = '/api/periodos-avaliativos/criar/'


def url_detalhe(p):
    return f'/api/periodos-avaliativos/{p.id}/'


def url_atualizar(p):
    return f'/api/periodos-avaliativos/{p.id}/atualizar/'


def url_excluir(p):
    return f'/api/periodos-avaliativos/{p.id}/excluir/'


def _manager():
    return getattr(PeriodoAvaliativo, 'todos', PeriodoAvaliativo._base_manager)


class PeriodosTests(CenarioMultiTenant):
    """Além do cenário do base.py (relativo a hoje):
    A1: 'Encerrado A1' (terminou há 30 dias) e 'Vigente A1' (em andamento);
    A2: 'Futuro A2' (começa daqui a 30 dias); B1: 'Vigente B1' (outra rede).
    Todos bimestrais."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        hoje = timezone.localdate()
        cls.hoje = hoje
        cls.encerrado_a1 = cls._periodo('Encerrado A1', cls.a1, hoje - timedelta(days=90), hoje - timedelta(days=30))
        cls.vigente_a1 = cls._periodo('Vigente A1', cls.a1, hoje - timedelta(days=10), hoje + timedelta(days=50))
        cls.futuro_a2 = cls._periodo('Futuro A2', cls.a2, hoje + timedelta(days=30), hoje + timedelta(days=90))
        cls.vigente_b1 = cls._periodo('Vigente B1', cls.b1, hoje - timedelta(days=10), hoje + timedelta(days=50))

    @staticmethod
    def _periodo(descricao, escola, inicio, fim, tipo='bimestral'):
        return _manager().create(
            descricao=descricao, tipo_periodo=tipo, data_inicio=inicio, data_fim=fim,
            ano=inicio.year, escola=escola, instituicao=escola.instituicao,
        )

    # --- helpers ----------------------------------------------------------

    def _listar(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_LISTAR, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _post_criar(self, usuario=None, **extra):
        # Por padrão, um período anual num ano distante: não cruza com os do cenário.
        dados = {
            'escola': str(self.a1.id), 'descricao': 'Ano 2090', 'tipo_periodo': 'anual',
            'data_inicio': '2090-02-01', 'data_fim': '2090-12-15',
        }
        dados.update(extra)
        self.entrar(usuario or self.admin_a)
        return self.client.post(URL_CRIAR, dados, format='json')

    def _patch(self, periodo, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(url_atualizar(periodo), dados, format='json')

    def _descricoes(self, dados):
        return [p['descricao'] for p in dados['results']]

    # =====================================================================
    # Listagem
    # =====================================================================

    def test_listagem_sem_page_continua_devolvendo_array(self):
        dados = self._listar(self.admin_a)
        self.assertIsInstance(dados, list)
        self.assertEqual({p['descricao'] for p in dados}, {'Encerrado A1', 'Vigente A1', 'Futuro A2'})

    def test_listagem_abas_vigentes_e_encerrados(self):
        vigentes = self._listar(self.admin_a, page=1, situacao='vigentes')
        encerrados = self._listar(self.admin_a, page=1, situacao='encerrados')
        # Vigentes: o que está em andamento primeiro, depois os futuros.
        self.assertEqual(self._descricoes(vigentes), ['Vigente A1', 'Futuro A2'])
        self.assertEqual(self._descricoes(encerrados), ['Encerrado A1'])
        self.assertEqual(vigentes['totais'], {'vigentes': 2, 'encerrados': 1})
        self.assertEqual(encerrados['totais'], {'vigentes': 2, 'encerrados': 1})

    def test_listagem_periodo_que_termina_hoje_ainda_e_vigente(self):
        self._periodo('Termina hoje', self.a1, self.hoje - timedelta(days=5), self.hoje, tipo='semestral')
        self.assertIn('Termina hoje', self._descricoes(self._listar(self.admin_a, page=1, situacao='vigentes')))

    def test_listagem_pagina_de_10(self):
        for i in range(12):
            inicio = date(2000 + i, 2, 1)
            self._periodo(f'Antigo {i:02d}', self.a1, inicio, inicio + timedelta(days=60))
        p1 = self._listar(self.admin_a, page=1, situacao='encerrados')
        self.assertEqual((p1['count'], p1['total_paginas'], len(p1['results'])), (13, 2, 10))
        # Encerrados: do mais recente ao mais antigo.
        self.assertEqual(p1['results'][0]['descricao'], 'Encerrado A1')

    def test_listagem_pagina_fora_do_intervalo_vai_para_a_ultima(self):
        dados = self._listar(self.admin_a, page=99, situacao='vigentes')
        self.assertEqual((dados['pagina'], len(dados['results'])), (1, 2))

    def test_listagem_page_size_tem_teto(self):
        self.assertEqual(self._listar(self.admin_a, page=1, page_size=1000)['page_size'], 50)

    def test_listagem_filtro_por_escola(self):
        dados = self._listar(self.admin_a, page=1, escola=str(self.a2.id))
        self.assertEqual(self._descricoes(dados), ['Futuro A2'])
        self.assertEqual(dados['totais'], {'vigentes': 1, 'encerrados': 0})

    def test_listagem_escola_de_outra_rede_ou_invalida_devolve_vazio(self):
        for escola in (str(self.b1.id), 'nao-e-uuid'):
            dados = self._listar(self.admin_a, page=1, escola=escola)
            self.assertEqual(dados['count'], 0, escola)
            self.assertEqual(dados['totais'], {'vigentes': 0, 'encerrados': 0}, escola)

    def test_listagem_escopo(self):
        self.assertNotIn('Vigente B1', self._descricoes(self._listar(self.admin_a, page=1)))
        self.assertEqual(
            set(self._descricoes(self._listar(self.coord_a1, page=1))), {'Encerrado A1', 'Vigente A1'},
        )

    def test_listagem_mostra_a_escola_do_periodo(self):
        dados = self._listar(self.admin_a, page=1, situacao='vigentes')
        self.assertEqual(
            {(p['descricao'], p['escola_nome']) for p in dados['results']},
            {('Vigente A1', 'A1'), ('Futuro A2', 'A2')},
        )

    def test_listagem_numero_de_queries_nao_cresce(self):
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_LISTAR, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for i in range(5):
            inicio = date(2001 + i, 2, 1)
            self._periodo(f'Extra {i}', self.a2 if i % 2 else self.a1, inicio, inicio + timedelta(days=30))
        self.assertEqual(contar(), antes)

    # =====================================================================
    # Detalhe
    # =====================================================================

    def test_detalhe_fora_do_escopo_e_404(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(url_detalhe(self.futuro_a2)).status_code, 200)
        self.assertEqual(self.client.get(url_detalhe(self.vigente_b1)).status_code, 404)
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(url_detalhe(self.futuro_a2)).status_code, 404)

    # =====================================================================
    # Permissões
    # =====================================================================

    def test_admin_cria_na_escola_informada(self):
        r = self._post_criar(escola=str(self.a2.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['escola'], r.json()['escola_nome']), (str(self.a2.id), 'A2'))

    def test_coordenador_cria_sempre_na_propria_escola(self):
        r = self._post_criar(self.coord_a1, escola=str(self.a2.id))  # body ignorado
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))

    def test_professor_nao_cria_edita_nem_exclui(self):
        self.assertEqual(self._post_criar(self.prof_a1).status_code, 403)
        self.assertEqual(self._patch(self.vigente_a1, self.prof_a1, descricao='X').status_code, 403)
        self.entrar(self.prof_a1)
        self.assertEqual(self.client.delete(url_excluir(self.vigente_a1)).status_code, 403)

    def test_admin_nao_edita_periodo_de_outra_rede(self):
        self.assertEqual(self._patch(self.vigente_b1, descricao='X').status_code, 404)

    def test_nao_cria_em_escola_desativada(self):
        Escola.objects.filter(pk=self.a2.pk).update(ativa=False)
        self.assertEqual(self._post_criar(escola=str(self.a2.id)).status_code, 400)

    def test_edicao_nao_muda_a_escola(self):
        self.assertEqual(self._patch(self.vigente_a1, escola=str(self.a2.id), descricao='Novo nome').status_code, 200)
        self.vigente_a1.refresh_from_db()
        self.assertEqual(self.vigente_a1.escola_id, self.a1.id)

    # =====================================================================
    # Validações
    # =====================================================================

    def test_fim_antes_do_inicio(self):
        r = self._post_criar(data_inicio='2090-05-01', data_fim='2090-04-30')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('data_fim', r.json())

    def test_patch_de_uma_data_compara_com_a_salva(self):
        antes_do_inicio = (self.vigente_a1.data_inicio - timedelta(days=1)).isoformat()
        self.assertEqual(self._patch(self.vigente_a1, data_fim=antes_do_inicio).status_code, 400)

    def test_ano_vem_da_data_de_inicio_quando_nao_informado(self):
        self.assertEqual(self._post_criar().json()['ano'], 2090)

    def test_ano_e_numero_fora_da_faixa(self):
        self.assertEqual(self._post_criar(ano=1500).status_code, 400)
        self.assertEqual(self._post_criar(numero=0).status_code, 400)

    def test_sobreposicao_do_mesmo_tipo_na_mesma_escola(self):
        inicio = (self.vigente_a1.data_fim - timedelta(days=5)).isoformat()
        fim = (self.vigente_a1.data_fim + timedelta(days=40)).isoformat()
        r = self._post_criar(descricao='Cruzado', tipo_periodo='bimestral', data_inicio=inicio, data_fim=fim)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('Vigente A1', r.json()['data_inicio'][0])

    def test_tipo_diferente_pode_sobrepor(self):
        """Um período anual convive com os bimestres dentro dele."""
        r = self._post_criar(
            tipo_periodo='anual',
            data_inicio=(self.hoje - timedelta(days=100)).isoformat(),
            data_fim=(self.hoje + timedelta(days=200)).isoformat(),
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_mesmas_datas_em_outra_escola_pode(self):
        r = self._post_criar(
            escola=str(self.a2.id), tipo_periodo='bimestral',
            data_inicio=self.encerrado_a1.data_inicio.isoformat(), data_fim=self.encerrado_a1.data_fim.isoformat(),
        )
        self.assertEqual(r.status_code, 201, r.content)

    def test_periodos_encostados_podem(self):
        """Um termina num dia e o próximo começa no dia seguinte."""
        inicio = (self.vigente_a1.data_fim + timedelta(days=1)).isoformat()
        fim = (self.vigente_a1.data_fim + timedelta(days=60)).isoformat()
        r = self._post_criar(tipo_periodo='bimestral', data_inicio=inicio, data_fim=fim)
        self.assertEqual(r.status_code, 201, r.content)

    def test_editar_sem_mudar_datas_nao_conflita_consigo(self):
        r = self._patch(self.vigente_a1, descricao='2º Bimestre', data_inicio=self.vigente_a1.data_inicio.isoformat())
        self.assertEqual(r.status_code, 200, r.content)

    def test_editar_para_cruzar_com_outro(self):
        r = self._patch(self.vigente_a1, data_inicio=(self.encerrado_a1.data_fim - timedelta(days=1)).isoformat())
        self.assertEqual(r.status_code, 400, r.content)

    def test_tipo_invalido(self):
        self.assertEqual(self._post_criar(tipo_periodo='mensal').status_code, 400)

    # =====================================================================
    # Exclusão
    # =====================================================================

    def test_excluir(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.delete(url_excluir(self.futuro_a2)).status_code, 204)
        self.assertFalse(_manager().filter(pk=self.futuro_a2.pk).exists())
        self.assertEqual(self.client.delete(url_excluir(self.futuro_a2)).status_code, 404)

    def test_nao_exclui_periodo_fora_do_escopo(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.delete(url_excluir(self.vigente_b1)).status_code, 404)
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.delete(url_excluir(self.futuro_a2)).status_code, 404)
        self.assertEqual(_manager().filter(pk__in=[self.vigente_b1.pk, self.futuro_a2.pk]).count(), 2)