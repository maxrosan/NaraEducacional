"""Prompts de IA (global × personalizado por rede), tickets de suporte e
notificações — recursos em que usuários SEM escola (superadmin, suporte)
convivem com o recorte por tenant.
"""
from api.models import Notificacao, PromptCategoria, PromptTemplate, Ticket
from api.services.prompt_resolver import resolver_prompt
from api.tenancy import clear_current_tenant, set_current_tenant

from .base import CenarioMultiTenant


class PromptTests(CenarioMultiTenant):
    """Prompt global (superadmin) + personalizado POR ESCOLA."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.categoria = PromptCategoria.objects.create(titulo='Escrita')
        cls.tpl_global = PromptTemplate._base_manager.create(
            categoria=cls.categoria, prompt_global='GLOBAL', personalizado='',
        )

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

    def test_tela_do_coordenador_mostra_o_que_vale_para_a_escola(self):
        self.entrar(self.coord_a1)

        def origem():
            r = self.client.get('/api/prompts/categorias/')
            self.assertEqual(r.status_code, 200, r.content)
            return next(c for c in r.data if c['id'] == str(self.categoria.id))['template_resolvido']['origem']

        self.assertEqual(origem(), 'global')
        self._salvar(personalizado='Da A1')
        self.assertEqual(origem(), 'personalizado')


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