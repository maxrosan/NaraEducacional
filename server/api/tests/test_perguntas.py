"""Testes de perguntas: as duas telas do menu Configurações → Perguntas.

  * PerguntasBnccTests          — /api/perguntas/ (model Pergunta): perguntas
    oficiais (sem escola nem instituição, valem para todas as escolas) e as
    customizadas de cada escola. Oficial só o superadmin cria e edita.
  * PerguntasEspecialistasTests — /api/perguntas-especialistas/ (model
    PerguntaEspecialista): perguntas livres de cada escola, com referência
    BNCC obrigatória, paginação e abas ativas/inativas.

As duas classes usam o mesmo cenário (CenarioPerguntas).
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api.models import CampoPedagogico, Escola, HabilidadeBNCC, Pergunta, PerguntaEspecialista

from .base import CenarioMultiTenant


class CenarioPerguntas(CenarioMultiTenant):
    """Além do cenário do base.py:
    - habilidades EI03EO01 (ativa) e EI03EO99 (desativada);
    - campos de experiência: oficial "O eu, o outro e o nós", "Campo A1" (A1)
      e "Campo A2" (A2);
    - especialista em A1 (esp_a1)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.hab = HabilidadeBNCC._base_manager.create(codigo='EI03EO01', descricao='Demonstrar empatia.')
        cls.hab_inativa = HabilidadeBNCC._base_manager.create(codigo='EI03EO99', descricao='Antiga.', ativa=False)
        cls.campo_oficial = CampoPedagogico.todos.create(nome='O eu, o outro e o nós')
        cls.campo_a1 = CampoPedagogico.todos.create(nome='Campo A1', escola=cls.a1, instituicao=cls.rede_a)
        cls.campo_a2 = CampoPedagogico.todos.create(nome='Campo A2', escola=cls.a2, instituicao=cls.rede_a)
        cls.esp_a1 = cls._usuario('esp.a1@x.com', 'especialista', cls.rede_a, cls.a1)


# =============================================================================
# Perguntas BNCC (oficiais + customizadas da escola)
# =============================================================================

URL_BNCC_LISTAR = '/api/perguntas/'
URL_BNCC_CRIAR = '/api/perguntas/criar/'


def url_bncc_detalhe(p):
    return f'/api/perguntas/{p.id}/'


def url_bncc_atualizar(p):
    return f'/api/perguntas/{p.id}/atualizar/'


class PerguntasBnccTests(CenarioPerguntas):
    """Perguntas: 'Oficial' (sem escola/instituição), 'Da A1', 'Da A2' e
    'Da B1' (outra rede)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.oficial = cls._pergunta_bncc('Oficial', None, campo=cls.campo_oficial, faixa='Nível 3')
        cls.da_a1 = cls._pergunta_bncc('Da A1', cls.a1, campo=cls.campo_a1, faixa='Nível 4')
        cls.da_a2 = cls._pergunta_bncc('Da A2', cls.a2)
        cls.da_b1 = cls._pergunta_bncc('Da B1', cls.b1)

    @classmethod
    def _pergunta_bncc(cls, texto, escola, campo=None, faixa='Nível 3'):
        return Pergunta.todos.create(
            pergunta=texto, faixa_etaria=faixa, campo_experiencia=campo, habilidade_bncc=cls.hab,
            origem='bncc' if escola is None else 'escola',
            escola=escola, instituicao=escola.instituicao if escola else None,
        )

    # --- helpers ----------------------------------------------------------

    def _textos(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_BNCC_LISTAR, params)
        self.assertEqual(r.status_code, 200, r.content)
        return {p['pergunta'] for p in r.json()}

    def _post_criar(self, usuario=None, **extra):
        dados = {'escola': str(self.a1.id), 'pergunta': 'Nova BNCC?', 'faixa_etaria': 'Nível 3',
                 'referencia_bncc': 'EI03EO01'}
        dados.update(extra)
        self.entrar(usuario or self.admin_a)
        return self.client.post(URL_BNCC_CRIAR, {k: v for k, v in dados.items() if v is not None}, format='json')

    # `alvo` (e não `pergunta`): `pergunta` é também um campo enviado em **dados.
    def _patch(self, alvo, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(url_bncc_atualizar(alvo), dados, format='json')

    # --- listagem ---------------------------------------------------------

    def test_admin_ve_oficiais_e_as_da_rede(self):
        self.assertEqual(self._textos(self.admin_a), {'Oficial', 'Da A1', 'Da A2'})

    def test_coordenador_e_professor_veem_oficiais_e_as_da_escola(self):
        self.assertEqual(self._textos(self.coord_a1), {'Oficial', 'Da A1'})
        self.assertEqual(self._textos(self.prof_a1), {'Oficial', 'Da A1'})

    def test_superadmin_ve_todas(self):
        self.assertEqual(self._textos(self.superadmin), {'Oficial', 'Da A1', 'Da A2', 'Da B1'})

    def test_filtro_por_faixa_etaria(self):
        self.assertEqual(self._textos(self.admin_a, faixa_etaria='Nível 4'), {'Da A1'})

    # --- detalhe ----------------------------------------------------------

    def test_oficial_e_visivel_para_todos(self):
        for usuario in (self.admin_b, self.coord_a1, self.prof_b1):
            self.entrar(usuario)
            self.assertEqual(self.client.get(url_bncc_detalhe(self.oficial)).status_code, 200, usuario.email)

    def test_detalhe_fora_do_escopo_e_404(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(url_bncc_detalhe(self.da_b1)).status_code, 404)
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(url_bncc_detalhe(self.da_a2)).status_code, 404)

    # --- criação ----------------------------------------------------------

    def test_superadmin_sem_escola_cria_oficial(self):
        r = self._post_criar(self.superadmin, escola=None)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['escola'], r.json()['instituicao']), (None, None))

    def test_superadmin_cria_na_escola_informada(self):
        r = self._post_criar(self.superadmin, escola=str(self.b1.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.b1.id))

    def test_admin_cria_na_escola_da_rede(self):
        r = self._post_criar(escola=str(self.a2.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['escola'], r.json()['instituicao']), (str(self.a2.id), str(self.rede_a.id)))

    def test_admin_nao_cria_oficial_nem_em_outra_rede(self):
        # A recusa vem do resolver_escopo_criacao (400/403/404 conforme o caso);
        # o que importa é que nada seja criado.
        self.assertIn(self._post_criar(escola=None).status_code, (400, 403))
        self.assertIn(self._post_criar(escola=str(self.b1.id)).status_code, (400, 403, 404))
        self.assertFalse(Pergunta.todos.filter(pergunta='Nova BNCC?').exists())

    def test_coordenador_cria_sempre_na_propria_escola(self):
        r = self._post_criar(self.coord_a1, escola=str(self.a2.id))  # body ignorado
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))

    def test_professor_e_especialista_nao_criam(self):
        self.assertEqual(self._post_criar(self.prof_a1).status_code, 403)
        self.assertEqual(self._post_criar(self.esp_a1).status_code, 403)

    # --- campo de experiência ---------------------------------------------

    def test_campo_oficial_ou_da_propria_escola(self):
        self.assertEqual(self._post_criar(campo_experiencia=str(self.campo_oficial.id)).status_code, 201)
        self.assertEqual(
            self._post_criar(pergunta='Outra?', campo_experiencia=str(self.campo_a1.id)).status_code, 201,
        )

    def test_campo_de_outra_escola(self):
        self.assertEqual(self._post_criar(campo_experiencia=str(self.campo_a2.id)).status_code, 400)

    def test_pergunta_oficial_so_aceita_campo_oficial(self):
        r = self._post_criar(self.superadmin, escola=None, campo_experiencia=str(self.campo_a1.id))
        self.assertEqual(r.status_code, 400, r.content)

    def test_edicao_tambem_valida_o_campo(self):
        self.assertEqual(self._patch(self.da_a1, campo_experiencia=str(self.campo_a2.id)).status_code, 400)

    # --- edição -----------------------------------------------------------

    def test_admin_edita_as_da_rede(self):
        r = self._patch(self.da_a2, pergunta='Da A2 (revisada)')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['pergunta'], 'Da A2 (revisada)')

    def test_so_superadmin_edita_oficial(self):
        self.assertEqual(self._patch(self.oficial, self.admin_a, pergunta='X').status_code, 403)
        self.assertEqual(self._patch(self.oficial, self.coord_a1, pergunta='X').status_code, 403)
        self.assertEqual(self._patch(self.oficial, self.superadmin, pergunta='Oficial (revisada)').status_code, 200)

    def test_desativar_e_reativar(self):
        for ativa in (False, True):
            self.assertEqual(self._patch(self.da_a1, ativa=ativa).status_code, 200)
            self.da_a1.refresh_from_db()
            self.assertEqual(self.da_a1.ativa, ativa)

    def test_edicao_fora_do_escopo(self):
        self.assertEqual(self._patch(self.da_b1, pergunta='X').status_code, 404)
        self.assertEqual(self._patch(self.da_a2, self.coord_a1, pergunta='X').status_code, 404)

    def test_professor_nao_edita(self):
        self.assertEqual(self._patch(self.da_a1, self.prof_a1, pergunta='X').status_code, 403)

    def test_edicao_nao_muda_a_escola(self):
        self.assertEqual(self._patch(self.da_a1, escola=str(self.a2.id), pergunta='Da A1').status_code, 200)
        self.da_a1.refresh_from_db()
        self.assertEqual(self.da_a1.escola_id, self.a1.id)

    # --- listagem paginada (tela BNCC do admin) ---------------------------

    def _pagina(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_BNCC_LISTAR, {'page': 1, **params})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_paginada_com_totais_e_permissao_de_editar_oficiais(self):
        Pergunta.todos.filter(pk=self.da_a2.pk).update(ativa=False)
        dados = self._pagina(self.admin_a, ativa='true')
        self.assertEqual({p['pergunta'] for p in dados['results']}, {'Oficial', 'Da A1'})
        self.assertEqual(dados['totais'], {'ativas': 2, 'inativas': 1})
        self.assertFalse(dados['pode_editar_oficiais'])
        self.assertTrue(self._pagina(self.superadmin)['pode_editar_oficiais'])

    def test_paginada_filtros(self):
        self.assertEqual({p['pergunta'] for p in self._pagina(self.admin_a, origem='oficial')['results']}, {'Oficial'})
        self.assertEqual({p['pergunta'] for p in self._pagina(self.admin_a, origem='escola')['results']}, {'Da A1', 'Da A2'})
        self.assertEqual({p['pergunta'] for p in self._pagina(self.admin_a, escola=str(self.a2.id))['results']}, {'Da A2'})
        self.assertEqual(
            {p['pergunta'] for p in self._pagina(self.admin_a, campo=str(self.campo_oficial.id))['results']}, {'Oficial'},
        )
        self.assertEqual(self._pagina(self.admin_a, campo='nao-e-uuid')['count'], 0)
        self.assertEqual(self._pagina(self.admin_a, escola=str(self.b1.id))['count'], 0)  # fora do escopo
        self.assertEqual(self._pagina(self.admin_a, busca='ei03eo')['count'], 3)

    def test_paginada_traz_nomes_e_referencia(self):
        p = next(p for p in self._pagina(self.admin_a)['results'] if p['pergunta'] == 'Da A1')
        self.assertEqual(
            (p['campo_experiencia_nome'], p['habilidade_bncc_codigo'], p['escola_nome']), ('Campo A1', 'EI03EO01', 'A1'),
        )

    def test_paginada_numero_de_queries_nao_cresce(self):
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_BNCC_LISTAR, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for i in range(5):
            self._pergunta_bncc(f'Extra {i}', self.a1 if i % 2 else self.a2, campo=self.campo_oficial)
        self.assertEqual(contar(), antes)

    # --- referência BNCC ---------------------------------------------------

    def test_referencia_obrigatoria(self):
        r = self._post_criar(referencia_bncc='')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('referencia_bncc', r.json())
        self.assertEqual(self._post_criar(referencia_bncc='XX99').status_code, 400)
        self.assertEqual(self._post_criar(referencia_bncc='EI03EO99').status_code, 400)  # desativada

    def test_referencia_pelo_codigo(self):
        r = self._post_criar(referencia_bncc=' ei03eo01 ')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['habilidade_bncc_codigo'], 'EI03EO01')

    def test_referencia_nao_pode_ser_removida(self):
        self.assertEqual(self._patch(self.da_a1, referencia_bncc='').status_code, 400)

    def test_pergunta_antiga_sem_referencia_continua_editavel(self):
        antiga = Pergunta.todos.create(pergunta='Antiga', escola=self.a1, instituicao=self.rede_a, origem='escola')
        self.assertEqual(self._patch(antiga, ativa=False).status_code, 200)


# =============================================================================
# Perguntas dos especialistas
# =============================================================================

URL_LISTAR = '/api/perguntas-especialistas/'
URL_CRIAR = '/api/perguntas-especialistas/criar/'


def url_atualizar(p):
    return f'/api/perguntas-especialistas/{p.id}/atualizar/'


class PerguntasEspecialistasTests(CenarioPerguntas):
    """Perguntas: 'Como a criança se relaciona?' (A1, de esp_a1),
    'Pergunta A2' (A2, de admin_a) e 'Pergunta B1' (outra rede)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.p_a1 = cls._pergunta('Como a criança se relaciona?', cls.a1, cls.esp_a1, campo=cls.campo_oficial, nivel='Nível 3')
        cls.p_a2 = cls._pergunta('Pergunta A2', cls.a2, cls.admin_a, campo=cls.campo_a2, nivel='1º ANO')
        cls.p_b1 = cls._pergunta('Pergunta B1', cls.b1, cls.admin_b)

    @classmethod
    def _pergunta(cls, texto, escola, autor, campo=None, nivel='Nível 3', status='ativa', habilidade='padrao'):
        return PerguntaEspecialista._base_manager.create(
            pergunta=texto, pergunta_facilitadora=texto, nivel=nivel, status=status,
            campo_experiencia=campo, habilidade_bncc=cls.hab if habilidade == 'padrao' else habilidade,
            escola=escola, instituicao=escola.instituicao, usuario_especialista=autor,
        )

    # --- helpers ----------------------------------------------------------

    def _listar(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_LISTAR, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _post_criar(self, usuario=None, **extra):
        dados = {
            'escola': str(self.a1.id), 'pergunta': 'Nova pergunta?', 'pergunta_facilitadora': 'Nova pergunta?',
            'nivel': 'Nível 4', 'campo_experiencia': str(self.campo_oficial.id), 'referencia_bncc': 'EI03EO01',
        }
        dados.update(extra)
        self.entrar(usuario or self.admin_a)
        return self.client.post(URL_CRIAR, dados, format='json')

    # `alvo` (e não `pergunta`): `pergunta` é também um campo enviado em **dados.
    def _patch(self, alvo, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(url_atualizar(alvo), dados, format='json')

    def _textos(self, dados):
        return [p['pergunta'] for p in dados['results']]

    # =====================================================================
    # Listagem
    # =====================================================================

    def test_listagem_sem_page_continua_devolvendo_array(self):
        dados = self._listar(self.admin_a)
        self.assertIsInstance(dados, list)
        self.assertEqual({p['pergunta'] for p in dados}, {'Como a criança se relaciona?', 'Pergunta A2'})

    def test_listagem_pagina_de_10(self):
        for i in range(12):
            self._pergunta(f'Extra {i:02d}', self.a1, self.admin_a)
        p1 = self._listar(self.admin_a, page=1, status='ativa')
        self.assertEqual((p1['count'], p1['total_paginas'], len(p1['results'])), (14, 2, 10))

    def test_listagem_abas_e_totais(self):
        self._pergunta('Desativada', self.a1, self.admin_a, status='inativa')
        inativas = self._listar(self.admin_a, page=1, status='inativa')
        self.assertEqual(self._textos(inativas), ['Desativada'])
        self.assertEqual(inativas['totais'], {'ativas': 2, 'inativas': 1})

    def test_listagem_filtros(self):
        self.assertEqual(self._textos(self._listar(self.admin_a, page=1, escola=str(self.a2.id))), ['Pergunta A2'])
        self.assertEqual(self._textos(self._listar(self.admin_a, page=1, nivel='1º ANO')), ['Pergunta A2'])
        self.assertEqual(
            self._textos(self._listar(self.admin_a, page=1, campo=str(self.campo_oficial.id))),
            ['Como a criança se relaciona?'],
        )
        self.assertEqual(self._listar(self.admin_a, page=1, campo='nao-e-uuid')['count'], 0)

    def test_listagem_busca_por_texto_ou_codigo(self):
        self.assertEqual(self._textos(self._listar(self.admin_a, page=1, busca='RELACIONA')), ['Como a criança se relaciona?'])
        self.assertEqual(self._listar(self.admin_a, page=1, busca='ei03eo')['count'], 2)

    def test_listagem_escopo(self):
        self.assertNotIn('Pergunta B1', self._textos(self._listar(self.admin_a, page=1)))
        self.assertEqual(self._textos(self._listar(self.coord_a1, page=1)), ['Como a criança se relaciona?'])

    def test_listagem_traz_nomes_e_referencia(self):
        p = next(p for p in self._listar(self.admin_a, page=1)['results'] if p['pergunta'] == 'Pergunta A2')
        self.assertEqual(
            (p['escola_nome'], p['campo_experiencia_nome'], p['habilidade_bncc_codigo'], p['usuario_especialista_nome']),
            ('A2', 'Campo A2', 'EI03EO01', self.admin_a.nome),
        )

    def test_listagem_numero_de_queries_nao_cresce(self):
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_LISTAR, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for i in range(5):
            self._pergunta(f'Q{i}', self.a1 if i % 2 else self.a2, self.esp_a1, campo=self.campo_a1)
        self.assertEqual(contar(), antes)

    # =====================================================================
    # Referência BNCC
    # =====================================================================

    def test_referencia_obrigatoria_na_criacao(self):
        self.assertEqual(self._post_criar(referencia_bncc='   ').status_code, 400)
        dados = {'escola': str(self.a1.id), 'pergunta': 'Sem referência'}
        self.entrar(self.admin_a)
        r = self.client.post(URL_CRIAR, dados, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('referencia_bncc', r.json())

    def test_codigo_sem_diferenciar_maiusculas_e_espacos(self):
        r = self._post_criar(referencia_bncc='  ei03eo01 ')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['habilidade_bncc_codigo'], 'EI03EO01')

    def test_codigo_inexistente(self):
        r = self._post_criar(referencia_bncc='XX99')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('XX99', r.json()['referencia_bncc'][0])

    def test_habilidade_desativada_nao_pode_ser_escolhida(self):
        self.assertEqual(self._post_criar(referencia_bncc='EI03EO99').status_code, 400)

    def test_quem_ja_usa_habilidade_desativada_continua_editavel(self):
        p = self._pergunta('Antiga', self.a1, self.admin_a, habilidade=self.hab_inativa)
        self.assertEqual(self._patch(p, nivel='Nível 5').status_code, 200)

    def test_referencia_nao_pode_ser_removida(self):
        self.assertEqual(self._patch(self.p_a1, referencia_bncc='').status_code, 400)
        self.assertEqual(self._patch(self.p_a1, habilidade_bncc=None).status_code, 400)

    def test_pergunta_antiga_sem_referencia_ainda_pode_ser_desativada(self):
        p = self._pergunta('Sem ref', self.a1, self.admin_a, habilidade=None)
        self.assertEqual(self._patch(p, status='inativa').status_code, 200)

    # =====================================================================
    # Criação
    # =====================================================================

    def test_admin_cria_na_escola_escolhida(self):
        r = self._post_criar(escola=str(self.a2.id), campo_experiencia=str(self.campo_a2.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['escola'], r.json()['usuario_especialista']), (str(self.a2.id), str(self.admin_a.id)))

    def test_admin_precisa_escolher_a_escola(self):
        r = self._post_criar(escola='')
        self.assertEqual(r.status_code, 400, r.content)

    def test_admin_nao_cria_em_escola_de_outra_rede(self):
        self.assertIn(self._post_criar(escola=str(self.b1.id)).status_code, (400, 403, 404))
        self.assertFalse(PerguntaEspecialista._base_manager.filter(pergunta='Nova pergunta?').exists())

    def test_coordenador_cria_sempre_na_propria_escola(self):
        r = self._post_criar(self.coord_a1, escola=str(self.a2.id))  # body ignorado
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))

    def test_especialista_cria_na_propria_escola(self):
        r = self._post_criar(self.esp_a1, escola=str(self.a2.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))

    def test_professor_nao_cria(self):
        self.assertEqual(self._post_criar(self.prof_a1).status_code, 403)

    def test_campo_de_outra_escola(self):
        self.assertEqual(self._post_criar(campo_experiencia=str(self.campo_a2.id)).status_code, 400)

    def test_campo_da_propria_escola(self):
        self.assertEqual(self._post_criar(campo_experiencia=str(self.campo_a1.id)).status_code, 201)

    def test_nao_cria_em_escola_desativada(self):
        Escola.objects.filter(pk=self.a2.pk).update(ativa=False)
        self.assertEqual(self._post_criar(escola=str(self.a2.id)).status_code, 400)

    # =====================================================================
    # Edição
    # =====================================================================

    def test_trocar_referencia(self):
        HabilidadeBNCC._base_manager.create(codigo='EF01LP01', descricao='Outra.')
        r = self._patch(self.p_a1, referencia_bncc='ef01lp01')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['habilidade_bncc_codigo'], 'EF01LP01')

    def test_desativar_e_reativar(self):
        for status_pergunta in ('inativa', 'ativa'):
            self.assertEqual(self._patch(self.p_a1, status=status_pergunta).status_code, 200)
            self.p_a1.refresh_from_db()
            self.assertEqual(self.p_a1.status, status_pergunta)

    def test_especialista_edita_a_propria_mas_nao_a_do_colega(self):
        self.assertEqual(self._patch(self.p_a1, self.esp_a1, nivel='Nível 4').status_code, 200)
        da_gestao = self._pergunta('Da coordenação', self.a1, self.coord_a1)
        self.assertEqual(self._patch(da_gestao, self.esp_a1, nivel='Nível 4').status_code, 403)

    def test_admin_nao_edita_de_outra_rede(self):
        self.assertEqual(self._patch(self.p_b1, status='inativa').status_code, 404)


# =============================================================================
# Campos de experiência (gerenciador da tela BNCC)
# =============================================================================

URL_CAMPOS = '/api/campos-pedagogicos/'


def url_campo_desativar(c):
    return f'/api/campos-pedagogicos/{c.id}/desativar/'


class CamposPedagogicosTests(CenarioPerguntas):
    """Perguntas usando os campos: BNCC 'Da A1' (Campo A1), 'Oficial' (campo
    oficial), 'Da B1' (campo oficial, outra rede); de especialista 'Esp A1'
    (Campo A1)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.campo_a1_extra = CampoPedagogico.todos.create(nome='Campo A1 Extra', escola=cls.a1, instituicao=cls.rede_a)
        cls.campo_oficial_2 = CampoPedagogico.todos.create(nome='Corpo, gestos e movimentos')
        cls.p_da_a1 = Pergunta.todos.create(
            pergunta='Da A1', escola=cls.a1, instituicao=cls.rede_a, origem='escola',
            campo_experiencia=cls.campo_a1, habilidade_bncc=cls.hab,
        )
        cls.p_oficial = Pergunta.todos.create(pergunta='Oficial', origem='bncc', campo_experiencia=cls.campo_oficial)
        cls.p_da_b1 = Pergunta.todos.create(
            pergunta='Da B1', escola=cls.b1, instituicao=cls.rede_b, origem='escola',
            campo_experiencia=cls.campo_oficial,
        )
        cls.p_esp_a1 = PerguntaEspecialista._base_manager.create(
            pergunta='Esp A1', escola=cls.a1, instituicao=cls.rede_a, usuario_especialista=cls.esp_a1,
            campo_experiencia=cls.campo_a1, habilidade_bncc=cls.hab,
        )

    def _desativar(self, campo, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.post(url_campo_desativar(campo), dados, format='json')

    # --- listagem -----------------------------------------------------------

    def test_listar_com_uso_conta_so_o_que_o_usuario_ve(self):
        self.entrar(self.admin_a)
        dados = {c['nome']: c for c in self.client.get(URL_CAMPOS, {'com_uso': 1}).json()}
        self.assertEqual(dados['Campo A1']['total_perguntas'], 2)            # BNCC + especialista
        self.assertEqual(dados['O eu, o outro e o nós']['total_perguntas'], 1)  # 'Da B1' é de outra rede
        self.assertNotIn('total_perguntas', self.client.get(URL_CAMPOS).json()[0])

    def test_listar_filtra_por_ativo(self):
        CampoPedagogico.todos.filter(pk=self.campo_a1_extra.pk).update(ativo=False)
        self.entrar(self.admin_a)
        nomes = {c['nome'] for c in self.client.get(URL_CAMPOS, {'ativo': 'false'}).json()}
        self.assertEqual(nomes, {'Campo A1 Extra'})

    # --- desativar ------------------------------------------------------------

    def test_desativar_campo_sem_perguntas(self):
        r = self._desativar(self.campo_a1_extra)
        self.assertEqual(r.status_code, 200, r.content)
        self.campo_a1_extra.refresh_from_db()
        self.assertFalse(self.campo_a1_extra.ativo)

    def test_campo_com_perguntas_exige_destino(self):
        r = self._desativar(self.campo_a1)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.json()['total_vinculos'], 2)
        self.campo_a1.refresh_from_db()
        self.assertTrue(self.campo_a1.ativo)

    def test_remaneja_os_dois_tipos_de_pergunta_e_desativa(self):
        r = self._desativar(self.campo_a1, remanejar_para=str(self.campo_a1_extra.id))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['perguntas_remanejadas'], 2)
        self.p_da_a1.refresh_from_db()
        self.p_esp_a1.refresh_from_db()
        self.assertEqual(self.p_da_a1.campo_experiencia_id, self.campo_a1_extra.id)
        self.assertEqual(self.p_esp_a1.campo_experiencia_id, self.campo_a1_extra.id)

    def test_destino_oficial_serve_para_campo_da_escola(self):
        r = self._desativar(self.campo_a1, remanejar_para=str(self.campo_oficial.id))
        self.assertEqual(r.status_code, 200, r.content)

    def test_destino_invalido(self):
        CampoPedagogico.todos.filter(pk=self.campo_oficial_2.pk).update(ativo=False)
        for destino in (self.campo_a2, self.campo_a1, self.campo_oficial_2):  # outra escola; o mesmo; desativado
            r = self._desativar(self.campo_a1, remanejar_para=str(destino.id))
            self.assertEqual(r.status_code, 400, (destino.nome, r.content))
        self.assertEqual(self._desativar(self.campo_a1, remanejar_para='nao-e-uuid').status_code, 404)
        self.campo_a1.refresh_from_db()
        self.assertTrue(self.campo_a1.ativo)

    def test_campo_oficial_so_superadmin(self):
        self.assertEqual(self._desativar(self.campo_oficial, remanejar_para=str(self.campo_oficial_2.id)).status_code, 403)
        # Oficial só remaneja para outro oficial (as perguntas são de várias redes).
        r = self._desativar(self.campo_oficial, self.superadmin, remanejar_para=str(self.campo_a1.id))
        self.assertEqual(r.status_code, 400, r.content)
        r = self._desativar(self.campo_oficial, self.superadmin, remanejar_para=str(self.campo_oficial_2.id))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['perguntas_remanejadas'], 2)  # 'Oficial' e 'Da B1'

    def test_permissoes(self):
        self.assertEqual(self._desativar(self.campo_a1_extra, self.prof_a1).status_code, 403)
        self.assertEqual(self._desativar(self.campo_a2, self.coord_a1).status_code, 404)

    def test_reativar_pelo_atualizar(self):
        CampoPedagogico.todos.filter(pk=self.campo_a1_extra.pk).update(ativo=False)
        self.entrar(self.admin_a)
        r = self.client.patch(f'/api/campos-pedagogicos/{self.campo_a1_extra.id}/atualizar/', {'ativo': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.campo_a1_extra.refresh_from_db()
        self.assertTrue(self.campo_a1_extra.ativo)