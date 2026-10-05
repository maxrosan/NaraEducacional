"""Testes de Disciplina: todos os endpoints de /api/disciplinas/.

Seções:
  * listagem     — paginação, abas ativas/inativas, filtros, escopo, custo de queries
  * detalhe      — escopo do GET de uma disciplina
  * permissões   — quem pode criar e editar, e em qual escola
  * professores  — gravados junto com a disciplina (transação), só professor_fundamental
  * nome único   — por escola, sem diferenciar maiúsculas
  * vínculos     — endpoints avulsos de listar/vincular/desvincular
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api.models import Disciplina, Escola, UsuarioDisciplina

from .base import CenarioMultiTenant

URL_LISTAR = '/api/disciplinas/'
URL_CRIAR = '/api/disciplinas/criar/'


def url_detalhe(d):
    return f'/api/disciplinas/{d.id}/'


def url_atualizar(d):
    return f'/api/disciplinas/{d.id}/atualizar/'


def url_professores(d):
    return f'/api/disciplinas/{d.id}/professores/'


def url_vincular(d):
    return f'/api/disciplinas/{d.id}/professores/vincular/'


def url_desvincular(d, usuario):
    return f'/api/disciplinas/{d.id}/professores/{usuario.id}/desvincular/'


class DisciplinasTests(CenarioMultiTenant):
    """Além do cenário do base.py: disciplinas Matemática (A1), Português (A2)
    e Matemática (B1, outra rede); professores de fundamental em A1, A2 e B1,
    com pf_a1 vinculado à Matemática de A1."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pf_a1 = cls._usuario('pf.a1@x.com', 'professor_fundamental', cls.rede_a, cls.a1)
        cls.pf2_a1 = cls._usuario('pf2.a1@x.com', 'professor_fundamental', cls.rede_a, cls.a1)
        cls.pf_a2 = cls._usuario('pf.a2@x.com', 'professor_fundamental', cls.rede_a, cls.a2)
        cls.pf_b1 = cls._usuario('pf.b1@x.com', 'professor_fundamental', cls.rede_b, cls.b1)

        cls.mat_a1 = cls._disciplina('Matemática', cls.a1)
        cls.port_a2 = cls._disciplina('Português', cls.a2)
        cls.mat_b1 = cls._disciplina('Matemática', cls.b1)
        UsuarioDisciplina.objects.create(
            usuario=cls.pf_a1, disciplina=cls.mat_a1, escola=cls.a1, instituicao=cls.rede_a,
        )

    @staticmethod
    def _disciplina(nome, escola, ativo=True):
        return Disciplina.objects.create(nome=nome, escola=escola, instituicao=escola.instituicao, ativo=ativo)

    # --- helpers ----------------------------------------------------------

    def _listar(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_LISTAR, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _post_criar(self, usuario=None, **extra):
        dados = {'escola': str(self.a1.id), 'nome': 'Ciências'}
        dados.update(extra)
        self.entrar(usuario or self.admin_a)
        return self.client.post(URL_CRIAR, dados, format='json')

    def _patch(self, disciplina, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(url_atualizar(disciplina), dados, format='json')

    def _professores(self, disciplina_id):
        return set(UsuarioDisciplina.objects.filter(disciplina_id=disciplina_id).values_list('usuario_id', flat=True))

    # =====================================================================
    # Listagem
    # =====================================================================

    def test_listagem_sem_page_continua_devolvendo_array(self):
        dados = self._listar(self.admin_a)
        self.assertIsInstance(dados, list)
        self.assertEqual({d['id'] for d in dados}, {str(self.mat_a1.id), str(self.port_a2.id)})

    def test_listagem_pagina_de_10(self):
        for i in range(14):
            self._disciplina(f'Disciplina {i:02d}', self.a1)
        p1 = self._listar(self.admin_a, page=1, ativo='true')
        self.assertEqual((p1['count'], p1['total_paginas'], len(p1['results'])), (16, 2, 10))
        p2 = self._listar(self.admin_a, page=2, ativo='true')
        ids = {d['id'] for d in p1['results']} | {d['id'] for d in p2['results']}
        self.assertEqual(len(ids), 16, 'páginas não podem repetir nem pular disciplinas')

    def test_listagem_pagina_fora_do_intervalo_vai_para_a_ultima(self):
        dados = self._listar(self.admin_a, page=99)
        self.assertEqual((dados['pagina'], len(dados['results'])), (1, 2))

    def test_listagem_page_size_tem_teto(self):
        self.assertEqual(self._listar(self.admin_a, page=1, page_size=1000)['page_size'], 50)

    def test_listagem_abas_e_totais(self):
        self._disciplina('Artes', self.a1, ativo=False)
        ativas = self._listar(self.admin_a, page=1, ativo='true')
        inativas = self._listar(self.admin_a, page=1, ativo='false')
        self.assertTrue(all(d['ativo'] for d in ativas['results']))
        self.assertEqual([d['nome'] for d in inativas['results']], ['Artes'])
        self.assertEqual(ativas['totais'], {'ativas': 2, 'inativas': 1})
        self.assertEqual(inativas['totais'], {'ativas': 2, 'inativas': 1})

    def test_listagem_filtro_por_escola_e_busca(self):
        dados = self._listar(self.admin_a, page=1, escola=str(self.a2.id))
        self.assertEqual([d['id'] for d in dados['results']], [str(self.port_a2.id)])
        dados = self._listar(self.admin_a, page=1, busca='MATEM')
        self.assertEqual([d['id'] for d in dados['results']], [str(self.mat_a1.id)])
        self.assertEqual(dados['totais'], {'ativas': 1, 'inativas': 0})

    def test_listagem_escola_de_outra_rede_ou_invalida_devolve_vazio(self):
        for escola in (str(self.b1.id), 'nao-e-uuid'):
            dados = self._listar(self.admin_a, page=1, escola=escola)
            self.assertEqual(dados['count'], 0, escola)
            self.assertEqual(dados['totais'], {'ativas': 0, 'inativas': 0}, escola)

    def test_listagem_escopo(self):
        ids = {d['id'] for d in self._listar(self.admin_a, page=1)['results']}
        self.assertNotIn(str(self.mat_b1.id), ids)
        ids = {d['id'] for d in self._listar(self.coord_a1, page=1)['results']}
        self.assertEqual(ids, {str(self.mat_a1.id)})

    def test_listagem_traz_professores_embutidos(self):
        d = next(d for d in self._listar(self.admin_a, page=1)['results'] if d['id'] == str(self.mat_a1.id))
        self.assertEqual(d['escola_nome'], 'A1')
        self.assertEqual(d['professores'], [{
            'usuario': str(self.pf_a1.id), 'usuario_nome': self.pf_a1.nome,
            'usuario_nivel': 'professor_fundamental',
        }])

    def test_listagem_numero_de_queries_nao_cresce(self):
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_LISTAR, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for i in range(6):
            d = self._disciplina(f'Extra {i}', self.a2)
            UsuarioDisciplina.objects.create(usuario=self.pf_a2, disciplina=d, escola=self.a2, instituicao=self.rede_a)
        self.assertEqual(contar(), antes)

    # =====================================================================
    # Detalhe
    # =====================================================================

    def test_detalhe_fora_do_escopo_e_404(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(url_detalhe(self.mat_a1)).status_code, 200)
        self.assertEqual(self.client.get(url_detalhe(self.mat_b1)).status_code, 404)
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(url_detalhe(self.port_a2)).status_code, 404)

    # =====================================================================
    # Permissões
    # =====================================================================

    def test_admin_cria_na_escola_informada(self):
        r = self._post_criar()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))

    def test_coordenador_cria_sempre_na_propria_escola(self):
        r = self._post_criar(self.coord_a1, escola=str(self.a2.id))  # body ignorado
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))

    def test_professor_nao_cria_nem_edita(self):
        self.assertEqual(self._post_criar(self.pf_a1).status_code, 403)
        self.assertEqual(self._patch(self.mat_a1, self.pf_a1, nome='X').status_code, 403)

    def test_admin_nao_cria_em_escola_de_outra_rede(self):
        self.assertIn(self._post_criar(escola=str(self.b1.id)).status_code, (400, 403, 404))
        self.assertFalse(Disciplina.objects.filter(nome='Ciências').exists())

    def test_admin_nao_edita_disciplina_de_outra_rede(self):
        self.assertEqual(self._patch(self.mat_b1, nome='X').status_code, 404)

    def test_nao_cria_em_escola_desativada(self):
        Escola.objects.filter(pk=self.a2.pk).update(ativa=False)
        self.assertEqual(self._post_criar(escola=str(self.a2.id)).status_code, 400)

    def test_desativar_e_reativar(self):
        for ativo in (False, True):
            self.assertEqual(self._patch(self.mat_a1, ativo=ativo).status_code, 200)
            self.mat_a1.refresh_from_db()
            self.assertEqual(self.mat_a1.ativo, ativo)

    def test_edicao_nao_muda_a_escola(self):
        self.assertEqual(self._patch(self.mat_a1, escola=str(self.a2.id), nome='Matemática I').status_code, 200)
        self.mat_a1.refresh_from_db()
        self.assertEqual(self.mat_a1.escola_id, self.a1.id)

    # =====================================================================
    # Professores gravados junto com a disciplina
    # =====================================================================

    def test_cria_com_professores_numa_requisicao(self):
        r = self._post_criar(professores=[str(self.pf_a1.id), str(self.pf2_a1.id)])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._professores(r.json()['id']), {self.pf_a1.id, self.pf2_a1.id})
        vinculo = UsuarioDisciplina.objects.filter(disciplina_id=r.json()['id']).first()
        self.assertEqual((vinculo.escola_id, vinculo.instituicao_id), (self.a1.id, self.rede_a.id))

    def test_atualizar_sincroniza_professores(self):
        self.assertEqual(self._patch(self.mat_a1, professores=[str(self.pf2_a1.id)]).status_code, 200)
        self.assertEqual(self._professores(self.mat_a1.id), {self.pf2_a1.id})
        self.assertEqual(self._patch(self.mat_a1, professores=[]).status_code, 200)
        self.assertEqual(self._professores(self.mat_a1.id), set())

    def test_atualizar_sem_professores_nao_mexe_nos_vinculos(self):
        self.assertEqual(self._patch(self.mat_a1, nome='Matemática I').status_code, 200)
        self.assertEqual(self._professores(self.mat_a1.id), {self.pf_a1.id})

    def test_so_professor_fundamental(self):
        """prof_a1 (base.py) é professor_infantil."""
        r = self._post_criar(professores=[str(self.prof_a1.id)])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('professores', r.json())
        self.assertFalse(Disciplina.objects.filter(nome='Ciências').exists())

    def test_professor_de_outra_escola_barra_tudo(self):
        r = self._patch(self.mat_a1, nome='Matemática I', professores=[str(self.pf_a2.id)])
        self.assertEqual(r.status_code, 400, r.content)
        self.mat_a1.refresh_from_db()
        self.assertEqual(self.mat_a1.nome, 'Matemática')
        self.assertEqual(self._professores(self.mat_a1.id), {self.pf_a1.id})

    def test_mantem_vinculo_existente_de_usuario_inativo(self):
        self.pf_a1.is_active = False
        self.pf_a1.save()
        r = self._patch(self.mat_a1, professores=[str(self.pf_a1.id)])
        self.assertEqual(r.status_code, 200, r.content)

    # =====================================================================
    # Nome único por escola
    # =====================================================================

    def test_nome_duplicado_sem_diferenciar_maiusculas(self):
        r = self._post_criar(nome='MATEMÁTICA')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('nome', r.json())

    def test_nome_exatamente_igual_nao_vira_500(self):
        self.assertEqual(self._post_criar(nome='Matemática').status_code, 400)

    def test_mesmo_nome_em_outra_escola_pode(self):
        self.assertEqual(self._post_criar(nome='Matemática', escola=str(self.a2.id)).status_code, 201)

    def test_duplicada_inativa_orienta_a_reativar(self):
        Disciplina.objects.filter(pk=self.mat_a1.pk).update(ativo=False)
        r = self._post_criar(nome='matemática')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Inativas', r.json()['nome'][0])

    def test_renomear_para_nome_existente(self):
        outra = self._disciplina('Geografia', self.a1)
        self.assertEqual(self._patch(outra, nome='matemática').status_code, 400)

    def test_editar_mudando_so_maiusculas_do_proprio_nome(self):
        self.assertEqual(self._patch(self.mat_a1, nome='MATEMÁTICA').status_code, 200)

    def test_duplicada_antiga_continua_editavel(self):
        """O banco aceita 'matemática' ao lado de 'Matemática' (constraint diferencia
        maiúsculas); duplicatas de antes da regra não podem travar a edição."""
        antiga = self._disciplina('matemática', self.a1)
        self.assertEqual(self._patch(antiga, nome='matemática', ativo=False).status_code, 200)

    def test_nome_em_branco(self):
        self.assertEqual(self._post_criar(nome='   ').status_code, 400)

    # =====================================================================
    # Endpoints avulsos de vínculo
    # =====================================================================

    def test_listar_professores(self):
        self.entrar(self.admin_a)
        r = self.client.get(url_professores(self.mat_a1))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([v['usuario'] for v in r.json()], [str(self.pf_a1.id)])
        self.assertEqual(self.client.get(url_professores(self.mat_b1)).status_code, 404)

    def test_vincular_novo_e_repetido(self):
        self.entrar(self.admin_a)
        r = self.client.post(url_vincular(self.mat_a1), {'usuario': str(self.pf2_a1.id)}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post(url_vincular(self.mat_a1), {'usuario': str(self.pf2_a1.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_vincular_aplica_as_mesmas_regras(self):
        self.entrar(self.admin_a)
        for usuario in (self.prof_a1, self.pf_a2):  # nível errado; outra escola
            r = self.client.post(url_vincular(self.mat_a1), {'usuario': str(usuario.id)}, format='json')
            self.assertEqual(r.status_code, 400, usuario.email)

    def test_desvincular(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.delete(url_desvincular(self.mat_a1, self.pf_a1)).status_code, 204)
        self.assertEqual(self.client.delete(url_desvincular(self.mat_a1, self.pf_a1)).status_code, 404)

    def test_professor_nao_mexe_em_vinculos(self):
        self.entrar(self.pf_a1)
        r = self.client.post(url_vincular(self.mat_a1), {'usuario': str(self.pf2_a1.id)}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.delete(url_desvincular(self.mat_a1, self.pf_a1)).status_code, 403)