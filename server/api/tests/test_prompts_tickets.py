"""Prompts de IA (global × personalizado por rede), tickets de suporte e
notificações — recursos em que usuários SEM escola (superadmin, suporte)
convivem com o recorte por tenant.
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from api.models import Escola, Notificacao, PromptCategoria, PromptTemplate, Ticket
from api.services.prompt_resolver import resolver_prompt
from api.tenancy import clear_current_tenant, set_current_tenant

from .base import CenarioMultiTenant

# Texto global de "Planejamento" trazido do sistema legado (migration 0003).
TEXTO_PLANEJAMENTO_LEGADO = (
    'Com base nas habilidades BNCC informadas e no histórico da turma, sugira atividades.'
)


class PromptTests(CenarioMultiTenant):
    """Prompt global (superadmin) + personalizado POR ESCOLA."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # 'Escrita' já vem da migration 0003 (categorias e prompts padrão).
        cls.categoria, _ = PromptCategoria.objects.get_or_create(titulo='Escrita')
        cls.tpl_global = PromptTemplate._base_manager.create(
            categoria=cls.categoria, prompt_global='GLOBAL', personalizado='',
        )

    @staticmethod
    def _global_da_migration(titulo):
        return (
            PromptTemplate._base_manager
            .filter(categoria__titulo=titulo, escola__isnull=True, instituicao__isnull=True)
            .order_by('criado_em').first()
        )

    def test_categorias_padrao_criadas_pela_migration(self):
        titulos = set(PromptCategoria.objects.filter(ativo=True).values_list('titulo', flat=True))
        self.assertTrue({
            'Relatórios - Atividades', 'Voz', 'Desenho', 'Planejamento',
            'Planejamento - Habilidades BNCC', 'Escrita',
            'Relatórios - Relato Individual', 'Relatórios - Produções', 'Relatórios - Conclusão',
        } <= titulos)
        self.assertEqual(PromptCategoria.objects.filter(titulo='Escrita').count(), 1)

    def test_prompts_globais_carregados_pela_migration(self):
        # Todas as categorias do sistema têm global — inclusive as duas de
        # Planejamento, agora separadas (antes Planejamento ficava sem global
        # porque uma categoria servia a duas tarefas).
        com_global = [
            'Escrita', 'Desenho', 'Voz', 'Relatórios - Atividades', 'Relatórios - Relato Individual',
            'Relatórios - Produções', 'Relatórios - Conclusão',
            'Planejamento', 'Planejamento - Habilidades BNCC',
        ]
        for titulo in com_global:
            with self.subTest(categoria=titulo):
                self.assertTrue(
                    PromptTemplate._base_manager.filter(
                        categoria__titulo=titulo, escola__isnull=True, instituicao__isnull=True,
                    ).exclude(prompt_global='').exists()
                )
        self.assertTrue(resolver_prompt('Voz').startswith('Você é um assistente'))
        self.assertNotIn('{{', resolver_prompt('Voz'))

    def test_planejamento_usa_o_texto_do_legado_e_bncc_tem_o_proprio(self):
        self.assertEqual(
            self._global_da_migration('Planejamento').prompt_global.strip(), TEXTO_PLANEJAMENTO_LEGADO,
        )
        bncc = self._global_da_migration('Planejamento - Habilidades BNCC').prompt_global
        self.assertNotEqual(bncc.strip(), TEXTO_PLANEJAMENTO_LEGADO)
        # O formato JSON é anexado pelo código; o texto editável não precisa dele.
        self.assertTrue(bncc.startswith('Você é uma especialista pedagógica'))

    def _salvar(self, **campos):
        return self.client.post('/api/prompts/salvar/', {'categoria': str(self.categoria.id), **campos}, format='json')

    def _personalizado_da(self, escola):
        return PromptTemplate._base_manager.filter(categoria=self.categoria, escola=escola).first()

    def test_coordenador_nao_altera_o_prompt_global(self):
        """Falha crítica: salvar sobrescrevia o registro mais recente da
        categoria — qualquer rede mudava o prompt de todas."""
        self.entrar(self.coord_a1)
        r = self._salvar(prompt_global='HACK', personalizado='Da A1')
        self.assertEqual(r.status_code, 200, r.content)
        self.tpl_global.refresh_from_db()
        self.assertEqual(self.tpl_global.prompt_global, 'GLOBAL')
        self.assertEqual(self._personalizado_da(self.a1).personalizado, 'Da A1')

    def test_personalizado_vale_so_para_a_propria_escola(self):
        """Regra de negócio: o prompt é por ESCOLA, não por rede — A2, da
        mesma rede, continua usando o global."""
        self.entrar(self.coord_a1)
        self._salvar(personalizado='Da A1')
        self.assertEqual(resolver_prompt('Escrita', escola_id=self.a1.id), 'Da A1')
        self.assertEqual(resolver_prompt('Escrita', escola_id=self.a2.id), 'GLOBAL')
        self.assertEqual(resolver_prompt('Escrita', escola_id=self.b1.id), 'GLOBAL')

    def test_personalizado_grava_escola_e_instituicao_da_escola(self):
        """O `cliente_id` do legado equivale à escola; a instituição acompanha
        a da escola (é ela que o TenantManager usa no recorte do admin)."""
        self.entrar(self.admin_a)
        self._salvar(personalizado='Da A2', escola=str(self.a2.id))
        tpl = self._personalizado_da(self.a2)
        self.assertEqual(tpl.instituicao_id, self.a2.instituicao_id)

    def test_coordenador_so_personaliza_a_propria_escola(self):
        self.entrar(self.coord_a1)
        self.assertEqual(self._salvar(personalizado='Tentando A2', escola=str(self.a2.id)).status_code, 200)
        self.assertIsNone(self._personalizado_da(self.a2))
        self.assertEqual(self._personalizado_da(self.a1).personalizado, 'Tentando A2')

    def test_admin_personaliza_escola_da_rede_informando_a_escola(self):
        self.entrar(self.admin_a)
        self.assertEqual(self._salvar(personalizado='Sem escola').status_code, 400)
        r = self._salvar(personalizado='Da A2', escola=str(self.a2.id))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._personalizado_da(self.a2).personalizado, 'Da A2')

    def test_admin_nao_personaliza_escola_de_outra_rede(self):
        self.entrar(self.admin_a)
        self.assertEqual(self._salvar(personalizado='Invasão', escola=str(self.b1.id)).status_code, 404)
        self.assertIsNone(self._personalizado_da(self.b1))

    def test_superadmin_altera_o_prompt_global(self):
        self.entrar(self.superadmin)
        self.assertEqual(self._salvar(prompt_global='NOVO GLOBAL').status_code, 200)
        self.tpl_global.refresh_from_db()
        self.assertEqual(self.tpl_global.prompt_global, 'NOVO GLOBAL')

    def test_resolver_enxerga_o_global_dentro_de_request_de_professor(self):
        """Bug: com o escopo de escola ativo (request de professor), o
        TenantManager escondia o template global e tudo caía no .txt."""
        set_current_tenant(('escola', self.a1.id))
        try:
            self.assertEqual(resolver_prompt('Escrita', escola_id=self.a1.id), 'GLOBAL')
        finally:
            clear_current_tenant()

    # --- resolver: título e categoria ------------------------------------

    def test_resolver_nao_diferencia_maiusculas_no_titulo(self):
        """Mesmo critério da migration 0003: renomear só a caixa da categoria
        não pode desligar o banco em silêncio e cair no .txt."""
        PromptCategoria.objects.filter(pk=self.categoria.pk).update(titulo='escrita')
        self.assertEqual(resolver_prompt('Escrita', escola_id=self.a1.id), 'GLOBAL')

    def test_resolver_ignora_categoria_inativa(self):
        PromptCategoria.objects.filter(pk=self.categoria.pk).update(ativo=False)
        self.assertEqual(resolver_prompt('Escrita', escola_id=self.a1.id, fallback_arquivo=None), '')

    def test_tela_do_coordenador_mostra_o_que_vale_para_a_escola(self):
        self.entrar(self.coord_a1)

        def origem():
            r = self.client.get('/api/prompts/categorias/')
            self.assertEqual(r.status_code, 200, r.content)
            return next(c for c in r.data if c['id'] == str(self.categoria.id))['template_resolvido']['origem']

        self.assertEqual(origem(), 'global')
        self._salvar(personalizado='Da A1')
        self.assertEqual(origem(), 'personalizado')

    # --- categorias: taxonomia só do superadmin --------------------------

    def test_so_superadmin_cria_categoria(self):
        url = reverse('criar_prompt_categoria')
        for usuario in (self.admin_a, self.coord_a1):
            with self.subTest(usuario=usuario.email):
                self.entrar(usuario)
                self.assertEqual(self.client.post(url, {'titulo': 'Nova'}, format='json').status_code, 403)
        self.entrar(self.superadmin)
        self.assertEqual(self.client.post(url, {'titulo': 'Nova'}, format='json').status_code, 201)

    # --- visão da rede (GET /prompts/rede/) -------------------------------

    def _rede(self, usuario):
        self.entrar(usuario)
        r = self.client.get('/api/prompts/rede/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _categoria_na_rede(self, dados, categoria=None):
        categoria = categoria or self.categoria
        return next(c for c in dados['categorias'] if c['id'] == str(categoria.id))

    @staticmethod
    def _escolas_personalizadas(categoria_dados):
        return {p['escola'] for p in categoria_dados['personalizadas']}

    def test_rede_admin_ve_as_escolas_da_propria_rede(self):
        dados = self._rede(self.admin_a)
        ids = {e['id'] for e in dados['escolas']}
        self.assertIn(str(self.a1.id), ids)
        self.assertIn(str(self.a2.id), ids)
        self.assertNotIn(str(self.b1.id), ids)
        self.assertFalse(dados['pode_editar_global'])

    def test_rede_traz_o_global_e_comeca_sem_personalizacao(self):
        cat = self._categoria_na_rede(self._rede(self.admin_a))
        self.assertEqual(cat['global']['texto'], 'GLOBAL')
        self.assertEqual(cat['personalizadas'], [])

    def test_rede_marca_so_as_escolas_que_personalizaram(self):
        self.entrar(self.admin_a)
        self._salvar(personalizado='Da A2', escola=str(self.a2.id))
        cat = self._categoria_na_rede(self._rede(self.admin_a))
        self.assertEqual(self._escolas_personalizadas(cat), {str(self.a2.id)})
        self.assertNotIn('personalizado', cat['personalizadas'][0])

    def test_rede_personalizado_em_branco_conta_como_global(self):
        self.entrar(self.admin_a)
        self._salvar(personalizado='Da A1', escola=str(self.a1.id))
        self._salvar(personalizado='   ', escola=str(self.a1.id))
        cat = self._categoria_na_rede(self._rede(self.admin_a))
        self.assertEqual(cat['personalizadas'], [])
        self.assertEqual(resolver_prompt('Escrita', escola_id=self.a1.id), 'GLOBAL')

    def test_rede_nao_mostra_personalizacao_de_outra_rede(self):
        PromptTemplate._base_manager.create(
            categoria=self.categoria, escola=self.b1, instituicao=self.rede_b,
            prompt_global='', personalizado='Da B1',
        )
        cat = self._categoria_na_rede(self._rede(self.admin_a))
        self.assertNotIn(str(self.b1.id), self._escolas_personalizadas(cat))

    def test_rede_coordenador_ve_so_a_propria_escola(self):
        dados = self._rede(self.coord_a1)
        self.assertEqual([e['id'] for e in dados['escolas']], [str(self.a1.id)])

    def test_rede_superadmin_ve_todas_e_pode_editar_o_global(self):
        dados = self._rede(self.superadmin)
        ids = {e['id'] for e in dados['escolas']}
        self.assertTrue({str(self.a1.id), str(self.b1.id)} <= ids)
        self.assertTrue(dados['pode_editar_global'])

    def test_rede_ignora_categoria_e_escola_inativas(self):
        inativa = PromptCategoria.objects.create(titulo='Antiga', ativo=False)
        Escola.objects.filter(pk=self.a2.pk).update(ativa=False)
        dados = self._rede(self.admin_a)
        self.assertNotIn(str(inativa.id), {c['id'] for c in dados['categorias']})
        self.assertNotIn(str(self.a2.id), {e['id'] for e in dados['escolas']})

    def test_rede_professor_nao_acessa(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self.client.get('/api/prompts/rede/').status_code, 403)

    def test_rede_numero_de_queries_nao_cresce(self):
        self.entrar(self.admin_a)

        def contar():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get('/api/prompts/rede/').status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for i in range(3):
            categoria = PromptCategoria.objects.create(titulo=f'Extra {i}')
            PromptTemplate._base_manager.create(categoria=categoria, prompt_global=f'G{i}', personalizado='')
            for escola in (self.a1, self.a2):
                PromptTemplate._base_manager.create(
                    categoria=categoria, escola=escola, instituicao_id=escola.instituicao_id,
                    prompt_global='', personalizado=f'P{i}',
                )
        self.assertEqual(contar(), antes)


class TicketTests(CenarioMultiTenant):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.suporte = cls._usuario('suporte@x.com', 'suporte', None, None)

    def _abrir(self):
        return self.client.post('/api/tickets/criar/', {
            'titulo': 'Ajuda', 'descricao': 'Não consigo gerar o relatório', 'categoria': 'duvida',
        }, format='json')

    def test_protocolo_nao_colide_com_ticket_de_outra_rede(self):
        """Bug: a sequência era calculada só com os tickets da própria rede
        (TenantManager) e repetia números já usados por outra → 500."""
        Ticket._base_manager.create(
            protocolo='NARA-0001', titulo='t', descricao='d', categoria='duvida',
            usuario_solicitante=self.prof_b1, escola=self.b1, instituicao=self.rede_b,
        )
        self.entrar(self.prof_a1)
        r = self._abrir()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotEqual(r.data['protocolo'], 'NARA-0001')

    def test_resposta_do_suporte_aparece_para_quem_abriu(self):
        """Bug: a resposta herdava a escola de quem respondia (o suporte não
        tem) e o TenantManager a escondia da escola que abriu o chamado."""
        self.entrar(self.prof_a1)
        ticket_id = self._abrir().data['id']

        self.entrar(self.suporte)
        r = self.client.post(f'/api/tickets/{ticket_id}/responder/', {'descricao': 'Estamos verificando'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)

        self.entrar(self.prof_a1)
        respostas = self.client.get(f'/api/tickets/{ticket_id}/respostas/').data
        self.assertIn('Estamos verificando', [x['descricao'] for x in respostas])

    def test_professor_de_outra_rede_nao_ve_o_ticket(self):
        self.entrar(self.prof_a1)
        ticket_id = self._abrir().data['id']
        self.entrar(self.prof_b1)
        self.assertEqual(self.client.get(f'/api/tickets/{ticket_id}/').status_code, 404)


class NotificacaoTests(CenarioMultiTenant):

    def test_notificar_usuario_de_sistema_responde_400(self):
        """Bug: Notificacao.instituicao é obrigatória; usuário sem instituição
        (suporte, superadmin) estourava no banco (500)."""
        suporte = self._usuario('suporte@x.com', 'suporte', None, None)
        self.entrar(self.superadmin)
        r = self.client.post('/api/notificacoes/criar/', {
            'usuario': str(suporte.id), 'titulo': 'Oi', 'conteudo': 'x', 'tipo': 'aviso',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(Notificacao.objects.exists())