"""GET /api/turmas/: listagem paginada, abas ativas/inativas e custo fixo de queries."""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api.models import Turma, UsuarioTurma

from .base import CenarioMultiTenant

URL = '/api/turmas/'


class ListagemTurmasTests(CenarioMultiTenant):

    def _get(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _criar(self, qtd, escola=None, ativa=True, prefixo='T'):
        escola = escola or self.a1
        return [
            Turma.objects.create(nome=f'{prefixo} {i:02d}', escola=escola,
                                 instituicao=escola.instituicao, ativa=ativa)
            for i in range(qtd)
        ]

    # --- compatibilidade --------------------------------------------------

    def test_sem_page_continua_devolvendo_array(self):
        dados = self._get(self.admin_a)
        self.assertIsInstance(dados, list)
        self.assertEqual({t['id'] for t in dados}, {str(self.turma_a1.id), str(self.turma_a2.id)})

    # --- paginação --------------------------------------------------------

    def test_pagina_de_10(self):
        self._criar(14)  # + turma_a1 e turma_a2 = 16 ativas na rede A
        p1 = self._get(self.admin_a, page=1, ativa='true')
        self.assertEqual((p1['count'], p1['total_paginas'], len(p1['results'])), (16, 2, 10))

        p2 = self._get(self.admin_a, page=2, ativa='true')
        self.assertEqual(len(p2['results']), 6)
        ids = {t['id'] for t in p1['results']} | {t['id'] for t in p2['results']}
        self.assertEqual(len(ids), 16, 'páginas não podem repetir nem pular turmas')

    def test_pagina_fora_do_intervalo_vai_para_a_ultima(self):
        dados = self._get(self.admin_a, page=99)
        self.assertEqual(dados['pagina'], 1)
        self.assertEqual(len(dados['results']), 2)

    def test_page_size_tem_teto(self):
        self.assertEqual(self._get(self.admin_a, page=1, page_size=1000)['page_size'], 50)

    # --- abas -------------------------------------------------------------

    def test_filtro_ativa_e_totais_das_abas(self):
        self._criar(3, ativa=False, prefixo='Antiga')
        ativas = self._get(self.admin_a, page=1, ativa='true')
        inativas = self._get(self.admin_a, page=1, ativa='false')

        self.assertTrue(all(t['ativa'] for t in ativas['results']))
        self.assertTrue(all(not t['ativa'] for t in inativas['results']))
        self.assertEqual(inativas['count'], 3)
        # Totais iguais nas duas abas: não dependem do filtro `ativa`.
        self.assertEqual(ativas['totais'], {'ativas': 2, 'inativas': 3})
        self.assertEqual(inativas['totais'], {'ativas': 2, 'inativas': 3})

    def test_filtro_por_escola(self):
        dados = self._get(self.admin_a, page=1, escola=str(self.a2.id))
        self.assertEqual([t['id'] for t in dados['results']], [str(self.turma_a2.id)])
        self.assertEqual(dados['totais'], {'ativas': 1, 'inativas': 0})

    def test_escola_de_outra_rede_ou_invalida_devolve_vazio(self):
        for escola in (str(self.b1.id), 'nao-e-uuid'):
            dados = self._get(self.admin_a, page=1, escola=escola)
            self.assertEqual(dados['count'], 0, escola)

    # --- escopo -----------------------------------------------------------

    def test_admin_nao_ve_turmas_de_outra_rede(self):
        ids = {t['id'] for t in self._get(self.admin_a, page=1)['results']}
        self.assertNotIn(str(self.turma_b1.id), ids)

    def test_coordenador_ve_so_a_propria_escola(self):
        ids = {t['id'] for t in self._get(self.coord_a1, page=1)['results']}
        self.assertEqual(ids, {str(self.turma_a1.id)})

    # --- relacionamentos --------------------------------------------------

    def test_professores_vem_embutidos(self):
        turma = next(t for t in self._get(self.admin_a, page=1)['results']
                     if t['id'] == str(self.turma_a1.id))
        self.assertEqual(turma['escola_nome'], 'A1')
        self.assertEqual(turma['professores'], [{
            'usuario': str(self.prof_a1.id),
            'usuario_nome': self.prof_a1.nome,
            'usuario_nivel': 'professor_infantil',
        }])

    def test_numero_de_queries_nao_cresce_com_as_turmas(self):
        """Sem select_related/prefetch, cada turma a mais custaria 2+ queries."""
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for turma in self._criar(8, escola=self.a2):
            UsuarioTurma.objects.create(usuario=self.coord_a2, turma=turma)
        self.assertEqual(contar(), antes)