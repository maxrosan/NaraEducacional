"""Testes de Usuario: listagem paginada e cadastro com vínculos.

Seções:
  * listagem        — paginação, abas ativos/inativos, filtros, busca, escopo, queries
  * vínculos        — turmas, disciplinas e tipo de especialista gravados junto (transação)
  * autoedição      — o próprio usuário não mexe em nível, escola, vínculos nem status
  * permissões      — regras que já existiam (coordenador x admin), para não regredir

As regras de escopo entre redes já são cobertas por test_seguranca_tenant.
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api.models import Disciplina, Especialista, Turma, Usuario, UsuarioDisciplina, UsuarioTurma

from .base import CenarioMultiTenant

URL_LISTAR = '/api/usuarios/'
URL_CRIAR = '/api/usuarios/criar/'


def url_atualizar(u):
    return f'/api/usuarios/{u.id}/atualizar/'


class UsuariosTests(CenarioMultiTenant):
    """Cenário do base.py: rede A tem admin_a (sem escola), coord_a1, coord_a2
    e prof_a1 (professor_infantil em A1). Aqui: turma_a1 (A1, com prof_a1),
    turma_a2 (A2) e disciplinas Matemática (A1) e Português (A2)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.mat_a1 = Disciplina.objects.create(nome='Matemática', escola=cls.a1, instituicao=cls.rede_a)
        cls.port_a2 = Disciplina.objects.create(nome='Português', escola=cls.a2, instituicao=cls.rede_a)

    # --- helpers ----------------------------------------------------------

    def _listar(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_LISTAR, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _post_criar(self, usuario=None, **extra):
        dados = {
            'nome': 'Rita Nova', 'email': 'rita@x.com', 'password': 'senha-forte-1',
            'nivel': 'professor_fundamental', 'escola': str(self.a1.id),
        }
        dados.update(extra)
        self.entrar(usuario or self.admin_a)
        return self.client.post(URL_CRIAR, dados, format='json')

    def _patch(self, alvo, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(url_atualizar(alvo), dados, format='json')

    def _turmas(self, u):
        return set(UsuarioTurma.objects.filter(usuario=u).values_list('turma_id', flat=True))

    def _disciplinas(self, u):
        return set(UsuarioDisciplina.objects.filter(usuario=u).values_list('disciplina_id', flat=True))

    def _novo(self, email, nivel, escola, ativo=True):
        u = self._usuario(email, nivel, escola.instituicao, escola)
        if not ativo:
            Usuario.objects.filter(pk=u.pk).update(is_active=False)
        return u

    # =====================================================================
    # Listagem
    # =====================================================================

    def test_listagem_sem_page_continua_devolvendo_array(self):
        dados = self._listar(self.admin_a)
        self.assertIsInstance(dados, list)
        self.assertEqual(
            {u['email'] for u in dados},
            {'admin.a@x.com', 'coord.a1@x.com', 'coord.a2@x.com', 'prof.a1@x.com'},
        )

    def test_listagem_sem_page_aceita_filtros(self):
        """Os formulários de turma/disciplina pedem só professores ativos."""
        self._novo('inativo@x.com', 'professor_infantil', self.a1, ativo=False)
        dados = self._listar(self.admin_a, nivel='professor_infantil', ativo='true')
        self.assertEqual([u['email'] for u in dados], ['prof.a1@x.com'])

    def test_listagem_pagina_de_10(self):
        for i in range(12):
            self._novo(f'p{i:02d}@x.com', 'professor_infantil', self.a1)
        p1 = self._listar(self.admin_a, page=1, ativo='true')
        self.assertEqual((p1['count'], p1['total_paginas'], len(p1['results'])), (16, 2, 10))
        p2 = self._listar(self.admin_a, page=2, ativo='true')
        ids = {u['id'] for u in p1['results']} | {u['id'] for u in p2['results']}
        self.assertEqual(len(ids), 16, 'páginas não podem repetir nem pular usuários')

    def test_listagem_abas_e_totais(self):
        self._novo('inativo@x.com', 'professor_infantil', self.a1, ativo=False)
        ativos = self._listar(self.admin_a, page=1, ativo='true')
        inativos = self._listar(self.admin_a, page=1, ativo='false')
        self.assertEqual([u['email'] for u in inativos['results']], ['inativo@x.com'])
        self.assertEqual(ativos['totais'], {'ativos': 4, 'inativos': 1})
        self.assertEqual(inativos['totais'], {'ativos': 4, 'inativos': 1})

    def test_listagem_filtros_escola_nivel_e_busca(self):
        self.assertEqual(
            {u['email'] for u in self._listar(self.admin_a, page=1, escola=str(self.a1.id))['results']},
            {'coord.a1@x.com', 'prof.a1@x.com'},
        )
        self.assertEqual(
            {u['email'] for u in self._listar(self.admin_a, page=1, nivel='coordenador')['results']},
            {'coord.a1@x.com', 'coord.a2@x.com'},
        )
        dados = self._listar(self.admin_a, page=1, busca='PROF.A1')
        self.assertEqual([u['email'] for u in dados['results']], ['prof.a1@x.com'])
        self.assertEqual(dados['totais'], {'ativos': 1, 'inativos': 0})

    def test_listagem_escola_de_outra_rede_devolve_vazio(self):
        dados = self._listar(self.admin_a, page=1, escola=str(self.b1.id))
        self.assertEqual((dados['count'], dados['totais']), (0, {'ativos': 0, 'inativos': 0}))

    def test_listagem_escopo(self):
        emails = {u['email'] for u in self._listar(self.admin_a, page=1)['results']}
        self.assertNotIn('admin.b@x.com', emails)
        self.assertNotIn('super@x.com', emails)
        emails = {u['email'] for u in self._listar(self.coord_a1, page=1)['results']}
        self.assertEqual(emails, {'coord.a1@x.com', 'prof.a1@x.com'})

    def test_professor_nao_lista(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self.client.get(URL_LISTAR, {'page': 1}).status_code, 403)

    def test_listagem_traz_vinculos_e_metadados(self):
        UsuarioTurma.objects.create(usuario=self.prof_a1, turma=self.turma_a1)
        dados = self._listar(self.admin_a, page=1, busca='prof.a1')
        prof = dados['results'][0]
        self.assertEqual(prof['turmas'], [{'turma': str(self.turma_a1.id), 'turma_nome': 'Nível 3A'}])
        self.assertEqual(prof['disciplinas'], [])
        self.assertEqual(prof['escola_nome'], 'A1')
        self.assertEqual(dados['usuario_atual'], str(self.admin_a.id))
        self.assertIn('admin', dados['niveis_permitidos'])
        self.assertNotIn('superadmin', dados['niveis_permitidos'])

    def test_coordenador_recebe_so_os_niveis_que_pode_atribuir(self):
        dados = self._listar(self.coord_a1, page=1)
        self.assertEqual(set(dados['niveis_permitidos']), {
            'professor_infantil', 'professor_fundamental', 'professor_especialista', 'especialista',
        })

    def test_listagem_numero_de_queries_nao_cresce(self):
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_LISTAR, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for i in range(5):
            u = self._novo(f'q{i}@x.com', 'professor_fundamental', self.a1)
            UsuarioTurma.objects.create(usuario=u, turma=self.turma_a1)
            UsuarioDisciplina.objects.create(usuario=u, disciplina=self.mat_a1, escola=self.a1, instituicao=self.rede_a)
        self.assertEqual(contar(), antes)

    # =====================================================================
    # Vínculos gravados junto com o usuário
    # =====================================================================

    def test_cria_com_turmas_e_disciplinas(self):
        r = self._post_criar(turmas=[str(self.turma_a1.id)], disciplinas=[str(self.mat_a1.id)])
        self.assertEqual(r.status_code, 201, r.content)
        u = Usuario.objects.get(email='rita@x.com')
        self.assertEqual(self._turmas(u), {self.turma_a1.id})
        self.assertEqual(self._disciplinas(u), {self.mat_a1.id})

    def test_turma_de_outra_escola_barra_tudo(self):
        r = self._post_criar(turmas=[str(self.turma_a2.id)])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('turmas', r.json())
        self.assertFalse(Usuario.objects.filter(email='rita@x.com').exists())

    def test_disciplina_so_para_professor_fundamental(self):
        r = self._post_criar(nivel='professor_infantil', disciplinas=[str(self.mat_a1.id)])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('disciplinas', r.json())

    def test_disciplina_de_outra_escola(self):
        self.assertEqual(self._post_criar(disciplinas=[str(self.port_a2.id)]).status_code, 400)

    def test_perfil_sem_turma_nao_recebe_turmas(self):
        r = self._post_criar(nivel='admin', escola=None, turmas=[str(self.turma_a1.id)])
        self.assertEqual(r.status_code, 400, r.content)

    def test_editar_sincroniza_turmas(self):
        UsuarioTurma.objects.create(usuario=self.prof_a1, turma=self.turma_a1)
        outra = Turma.objects.create(nome='Nível 4A', escola=self.a1, instituicao=self.rede_a)
        self.assertEqual(self._patch(self.prof_a1, turmas=[str(outra.id)]).status_code, 200)
        self.assertEqual(self._turmas(self.prof_a1), {outra.id})
        self.assertEqual(self._patch(self.prof_a1, turmas=[]).status_code, 200)
        self.assertEqual(self._turmas(self.prof_a1), set())

    def test_editar_sem_listas_nao_mexe_nos_vinculos(self):
        UsuarioTurma.objects.create(usuario=self.prof_a1, turma=self.turma_a1)
        self.assertEqual(self._patch(self.prof_a1, nome='Outro Nome').status_code, 200)
        self.assertEqual(self._turmas(self.prof_a1), {self.turma_a1.id})

    def test_mudar_de_escola_remove_vinculos_antigos(self):
        UsuarioTurma.objects.create(usuario=self.prof_a1, turma=self.turma_a1)
        self.assertEqual(self._patch(self.prof_a1, escola=str(self.a2.id)).status_code, 200)
        self.assertEqual(self._turmas(self.prof_a1), set())

    def test_tipo_especialista_cria_e_reaproveita_o_registro(self):
        r = self._post_criar(nivel='especialista', tipo_especialista='psicologo')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['tipo_especialista'], 'psicologo')
        r = self._post_criar(email='outra@x.com', nivel='especialista', tipo_especialista='psicologo')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            Especialista._base_manager.filter(escola=self.a1, tipo_especialista='psicologo').count(), 1,
        )

    def test_tipo_especialista_invalido(self):
        self.assertEqual(self._post_criar(nivel='especialista', tipo_especialista='astrologo').status_code, 400)

    def test_deixar_de_ser_especialista_desfaz_a_ligacao(self):
        r = self._post_criar(nivel='especialista', tipo_especialista='fonoaudiologo')
        u = Usuario.objects.get(pk=r.json()['id'])
        r = self._patch(u, nivel='professor_infantil')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()['tipo_especialista'])

    # =====================================================================
    # Autoedição
    # =====================================================================

    def test_professor_nao_se_vincula_sozinho_a_turmas(self):
        r = self._patch(self.prof_a1, self.prof_a1, nome='Novo Nome', turmas=[str(self.turma_a1.id)])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._turmas(self.prof_a1), set())
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.nome, 'Novo Nome')

    def test_ninguem_se_desativa_nem_se_promove(self):
        r = self._patch(self.coord_a1, self.coord_a1, is_active=False, nivel='admin')
        self.assertEqual(r.status_code, 200, r.content)
        self.coord_a1.refresh_from_db()
        self.assertTrue(self.coord_a1.is_active)
        self.assertEqual(self.coord_a1.nivel, 'coordenador')

    # =====================================================================
    # Permissões que já existiam
    # =====================================================================

    def test_desativar_e_reativar(self):
        for ativo in (False, True):
            self.assertEqual(self._patch(self.prof_a1, is_active=ativo).status_code, 200)
            self.prof_a1.refresh_from_db()
            self.assertEqual(self.prof_a1.is_active, ativo)

    def test_coordenador_nao_edita_outro_coordenador(self):
        self.assertEqual(self._patch(self.coord_a2, self.coord_a1, is_active=False).status_code, 403)

    def test_coordenador_nao_cria_admin(self):
        self.assertEqual(self._post_criar(self.coord_a1, nivel='admin').status_code, 403)

    def test_coordenador_cria_na_propria_escola_com_turma(self):
        r = self._post_criar(self.coord_a1, nivel='professor_infantil', turmas=[str(self.turma_a1.id)])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))