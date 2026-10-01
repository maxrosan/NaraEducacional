"""Escrita entre tenants: nenhum usuário pode criar, mover ou promover
registros para fora do próprio escopo (rede do admin, escola do coordenador).

Critério de "bloqueado": a API recusa (400/403/404) E o banco não muda.
"""
from api.models import (
    CampoPedagogico, HabilidadeBNCC, PeriodoAvaliativo, Pergunta, RelatorioTemplate,
    TemplateDocumento,
)

from .base import CenarioMultiTenant

RECUSADO = (400, 403, 404)


class UsuarioEntreTenantsTests(CenarioMultiTenant):
    """Falha crítica: admin movia um usuário da própria rede para outra rede
    como admin, com senha nova → controle total do outro cliente."""

    def _atualizar(self, alvo, payload):
        return self.client.patch(f'/api/usuarios/{alvo.id}/atualizar/', payload, format='json')

    def test_admin_nao_move_usuario_para_outra_rede_como_admin(self):
        self.entrar(self.admin_a)
        r = self._atualizar(self.prof_a1, {
            'instituicao': str(self.rede_b.id), 'escola': None,
            'nivel': 'admin', 'password': 'Invasao#2026',
        })
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.instituicao_id, self.rede_a.id, r.content)
        self.assertEqual(self.prof_a1.nivel, 'professor_infantil')

    def test_admin_nao_coloca_usuario_em_escola_de_outra_rede(self):
        self.entrar(self.admin_a)
        r = self._atualizar(self.prof_a1, {'escola': str(self.b1.id)})
        self.assertIn(r.status_code, RECUSADO, r.content)
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.escola_id, self.a1.id)

    def test_admin_move_usuario_entre_escolas_da_propria_rede(self):
        self.entrar(self.admin_a)
        r = self._atualizar(self.prof_a1, {'escola': str(self.a2.id)})
        self.assertEqual(r.status_code, 200, r.content)
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.escola_id, self.a2.id)
        self.assertEqual(self.prof_a1.instituicao_id, self.rede_a.id)

    def test_coordenador_nao_tira_usuario_da_propria_escola(self):
        self.entrar(self.coord_a1)
        for escola in (self.a2, self.b1):
            r = self._atualizar(self.prof_a1, {'escola': str(escola.id)})
            self.prof_a1.refresh_from_db()
            self.assertEqual(self.prof_a1.escola_id, self.a1.id, (escola.nome, r.content))

    def test_superadmin_pode_mover_entre_redes(self):
        self.entrar(self.superadmin)
        r = self._atualizar(self.prof_a1, {'instituicao': str(self.rede_b.id), 'escola': str(self.b1.id)})
        self.assertEqual(r.status_code, 200, r.content)
        self.prof_a1.refresh_from_db()
        self.assertEqual((self.prof_a1.instituicao_id, self.prof_a1.escola_id), (self.rede_b.id, self.b1.id))

    def test_superadmin_nao_cria_inconsistencia_escola_de_uma_rede_instituicao_de_outra(self):
        self.entrar(self.superadmin)
        r = self._atualizar(self.prof_a1, {'instituicao': str(self.rede_a.id), 'escola': str(self.b1.id)})
        self.assertIn(r.status_code, RECUSADO, r.content)


class CriacaoComEscolaDeOutraRedeTests(CenarioMultiTenant):
    """Admin informava `escola` de outra rede e o registro nascia com
    escola de um cliente e instituicao de outro."""

    CASOS = [
        ('/api/periodos-avaliativos/criar/', PeriodoAvaliativo,
         {'descricao': '1º Bim', 'tipo_periodo': 'bimestral', 'data_inicio': '2026-02-01', 'data_fim': '2026-04-30'}),
        ('/api/relatorio-templates/criar/', RelatorioTemplate, {'nome': 'Capa', 'modelo': 'classico'}),
        ('/api/campos-pedagogicos/criar/', CampoPedagogico, {'nome': 'Corpo, gestos e movimentos'}),
        # Toda pergunta tem referência BNCC (habilidade criada em setUpTestData).
        ('/api/perguntas/criar/', Pergunta, {'pergunta': 'Reconhece o próprio nome?', 'referencia_bncc': 'EI03EO01'}),
    ]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        HabilidadeBNCC._base_manager.create(codigo='EI03EO01', descricao='Demonstrar empatia.')

    def _manager(self, model):
        return getattr(model, 'todos', model._base_manager)

    def test_admin_nao_cria_em_escola_de_outra_rede(self):
        self.entrar(self.admin_a)
        for url, model, payload in self.CASOS:
            with self.subTest(url=url):
                r = self.client.post(url, {**payload, 'escola': str(self.b1.id)}, format='json')
                self.assertIn(r.status_code, RECUSADO, r.content)
                self.assertFalse(self._manager(model).filter(escola=self.b1).exists())

    def test_admin_cria_em_escola_da_propria_rede(self):
        self.entrar(self.admin_a)
        for url, model, payload in self.CASOS:
            with self.subTest(url=url):
                r = self.client.post(url, {**payload, 'escola': str(self.a2.id)}, format='json')
                self.assertEqual(r.status_code, 201, r.content)
                obj = self._manager(model).get(id=r.data['id'])
                self.assertEqual((obj.escola_id, obj.instituicao_id), (self.a2.id, self.rede_a.id))

    def test_superadmin_nao_cria_escola_de_uma_rede_com_instituicao_de_outra(self):
        self.entrar(self.superadmin)
        for url, model, payload in self.CASOS:
            with self.subTest(url=url):
                r = self.client.post(url, {**payload, 'escola': str(self.b1.id),
                                           'instituicao': str(self.rede_a.id)}, format='json')
                if r.status_code == 201:
                    obj = self._manager(model).get(id=r.data['id'])
                    self.assertEqual(obj.instituicao_id, self.rede_b.id, 'instituição deve vir da escola')
                else:
                    self.assertIn(r.status_code, RECUSADO, r.content)


class RegistroOficialFalsoTests(CenarioMultiTenant):
    """`escola` nula = registro OFICIAL (BNCC), visível para todas as redes.
    Admin conseguia criar "oficial" com a própria instituição → vazava para
    as outras redes e ele mesmo não conseguia mais editar."""

    def test_admin_nao_cria_campo_ou_pergunta_sem_escola(self):
        self.entrar(self.admin_a)
        for url, model, payload in [
            ('/api/campos-pedagogicos/criar/', CampoPedagogico, {'nome': 'Campo sem escola'}),
            ('/api/perguntas/criar/', Pergunta, {'pergunta': 'Pergunta sem escola'}),
        ]:
            with self.subTest(url=url):
                r = self.client.post(url, payload, format='json')
                self.assertIn(r.status_code, RECUSADO, r.content)
                self.assertFalse(model.todos.filter(escola__isnull=True, instituicao=self.rede_a).exists())

    def test_dado_legado_falso_oficial_nao_vaza_para_outra_rede(self):
        """Mesmo que o banco já tenha registros criados pela falha."""
        campo = CampoPedagogico.todos.create(nome='Vazado', instituicao=self.rede_a, escola=None)
        pergunta = Pergunta.todos.create(pergunta='Vazada?', instituicao=self.rede_a, escola=None)
        oficial = CampoPedagogico.todos.create(nome='Oficial BNCC')
        self.entrar(self.coord_b1)
        ids = {c['id'] for c in self.client.get('/api/campos-pedagogicos/').data}
        self.assertNotIn(str(campo.id), ids)
        self.assertIn(str(oficial.id), ids)
        self.assertNotIn(str(pergunta.id), {p['id'] for p in self.client.get('/api/perguntas/').data})
        self.assertIn(self.client.get(f'/api/campos-pedagogicos/{campo.id}/').status_code, RECUSADO)
        self.assertIn(self.client.get(f'/api/perguntas/{pergunta.id}/').status_code, RECUSADO)

    def test_superadmin_cria_oficial(self):
        self.entrar(self.superadmin)
        r = self.client.post('/api/campos-pedagogicos/criar/', {'nome': 'Novo oficial'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        obj = CampoPedagogico.todos.get(id=r.data['id'])
        self.assertEqual((obj.escola_id, obj.instituicao_id), (None, None))


class MoverRegistroPorPatchTests(CenarioMultiTenant):
    """Serializers com escola/instituicao graváveis permitiam mover um
    registro para outra rede num simples PATCH."""

    def test_patch_nao_move_pergunta_nem_campo(self):
        pergunta = Pergunta.todos.create(pergunta='P?', escola=self.a1, instituicao=self.rede_a)
        campo = CampoPedagogico.todos.create(nome='C', escola=self.a1, instituicao=self.rede_a)
        self.entrar(self.admin_a)
        for url, obj in [(f'/api/perguntas/{pergunta.id}/atualizar/', pergunta),
                         (f'/api/campos-pedagogicos/{campo.id}/atualizar/', campo)]:
            with self.subTest(url=url):
                self.client.patch(url, {'escola': str(self.b1.id), 'instituicao': str(self.rede_b.id)}, format='json')
                obj.refresh_from_db()
                self.assertEqual((obj.escola_id, obj.instituicao_id), (self.a1.id, self.rede_a.id))


class TemplateDocumentoTests(CenarioMultiTenant):
    """criar/atualizar não validavam escola/instituicao: dava para criar ou
    mover um template para outra rede, ou deixá-lo sem dono."""

    def _payload(self, **extra):
        return {'titulo': 'Contrato', 'documento': '<p>x</p>', 'tipo': 'contrato',
                'responsavel': str(self.admin_a.id), **extra}

    def test_admin_nao_cria_template_em_outra_rede(self):
        self.entrar(self.admin_a)
        r = self.client.post('/api/templates-documento/criar/',
                             self._payload(instituicao=str(self.rede_b.id), escola=str(self.b1.id)), format='json')
        self.assertFalse(TemplateDocumento.objects.filter(instituicao=self.rede_b).exists(), r.content)

    def test_template_criado_por_admin_pertence_a_rede_dele(self):
        self.entrar(self.admin_a)
        r = self.client.post('/api/templates-documento/criar/', self._payload(), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(TemplateDocumento.objects.get(id=r.data['id']).instituicao_id, self.rede_a.id)

    def test_admin_nao_move_template_por_patch(self):
        t = TemplateDocumento.objects.create(titulo='T', documento='d', instituicao=self.rede_a,
                                             responsavel=self.admin_a, criado_por=self.admin_a)
        self.entrar(self.admin_a)
        self.client.patch(f'/api/templates-documento/{t.id}/atualizar/',
                          {'instituicao': str(self.rede_b.id)}, format='json')
        t.refresh_from_db()
        self.assertEqual(t.instituicao_id, self.rede_a.id)