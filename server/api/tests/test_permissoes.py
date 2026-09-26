"""Permissões de gestão: quem pode editar quem (usuários, instituição) e os
cadastros estruturais da rede (especialistas, disciplinas, contratos).

Critério de "bloqueado": a API recusa E o banco não muda.
"""
from api.models import Contrato, Disciplina, Especialista, TemplateDocumento

from .base import SENHA, CenarioMultiTenant

RECUSADO = (400, 403, 404)


class CoordenadorNaoAssumeContaTests(CenarioMultiTenant):
    """Falha crítica: o coordenador trocava e-mail e senha de outro
    coordenador (ou de um admin) da própria escola e assumia a conta."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.coord2_a1 = cls._usuario('coord2.a1@x.com', 'coordenador', cls.rede_a, cls.a1)

    def _patch(self, alvo, payload):
        return self.client.patch(f'/api/usuarios/{alvo.id}/atualizar/', payload, format='json')

    def test_coordenador_nao_troca_email_nem_senha_de_outro_coordenador(self):
        self.entrar(self.coord_a1)
        r = self._patch(self.coord2_a1, {'email': 'invasor@x.com', 'password': 'Invasao#2026'})
        self.assertEqual(r.status_code, 403, r.content)
        self.coord2_a1.refresh_from_db()
        self.assertEqual(self.coord2_a1.email, 'coord2.a1@x.com')
        self.assertTrue(self.coord2_a1.check_password(SENHA))

    def test_coordenador_continua_vendo_o_colega(self):
        """Ver e editar são regras diferentes: a restrição é só na edição."""
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(f'/api/usuarios/{self.coord2_a1.id}/').status_code, 200)

    def test_coordenador_edita_professor_da_propria_escola(self):
        self.entrar(self.coord_a1)
        r = self._patch(self.prof_a1, {'nome': 'Prof Renomeada'})
        self.assertEqual(r.status_code, 200, r.content)
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.nome, 'Prof Renomeada')

    def test_coordenador_precisa_informar_nivel_ao_criar(self):
        """Sem `nivel`, o usuário nasceria com o default do model — fora da
        lista que o coordenador pode criar."""
        self.entrar(self.coord_a1)
        r = self.client.post('/api/usuarios/criar/', {
            'email': 'sem.nivel@x.com', 'nome': 'Sem Nível', 'password': SENHA,
        }, format='json')
        self.assertEqual(r.status_code, 403, r.content)


class InstituicaoTests(CenarioMultiTenant):
    """Falha crítica: qualquer usuário da rede (professor, coordenador)
    conseguia editar a própria instituição, inclusive desativá-la."""

    def _patch(self, payload):
        return self.client.patch(f'/api/instituicoes/{self.rede_a.id}/atualizar/', payload, format='json')

    def test_professor_nao_edita_a_instituicao(self):
        self.entrar(self.prof_a1)
        r = self._patch({'nome': 'Hackeada', 'ativa': False})
        self.assertEqual(r.status_code, 403, r.content)
        self.rede_a.refresh_from_db()
        self.assertEqual((self.rede_a.nome, self.rede_a.ativa), ('Rede A', True))

    def test_coordenador_nao_edita_a_instituicao(self):
        self.entrar(self.coord_a1)
        self.assertEqual(self._patch({'nome': 'Hackeada'}).status_code, 403)

    def test_professor_ainda_ve_a_instituicao(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self.client.get(f'/api/instituicoes/{self.rede_a.id}/').status_code, 200)

    def test_admin_edita_mas_nao_desativa_a_propria_rede(self):
        self.entrar(self.admin_a)
        r = self._patch({'nome': 'Rede A Renomeada', 'ativa': False})
        self.assertEqual(r.status_code, 200, r.content)
        self.rede_a.refresh_from_db()
        self.assertEqual(self.rede_a.nome, 'Rede A Renomeada')
        self.assertTrue(self.rede_a.ativa)

    def test_superadmin_desativa_rede(self):
        self.entrar(self.superadmin)
        r = self._patch({'ativa': False})
        self.assertEqual(r.status_code, 200, r.content)
        self.rede_a.refresh_from_db()
        self.assertFalse(self.rede_a.ativa)


class EspecialistaDaRedeTests(CenarioMultiTenant):
    """Bug: o TenantManager escondia do coordenador os especialistas da rede
    (escola nula) — exatamente os que atendem todas as escolas."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.esp_rede_a = Especialista.objects.create(tipo_especialista='psicologo', instituicao=cls.rede_a)
        cls.esp_a2 = Especialista.objects.create(tipo_especialista='fonoaudiologo', instituicao=cls.rede_a, escola=cls.a2)
        cls.esp_rede_b = Especialista.objects.create(tipo_especialista='psicologo', instituicao=cls.rede_b)

    def test_coordenador_ve_os_da_rede_e_nao_os_de_outra_escola(self):
        self.entrar(self.coord_a1)
        ids = {e['id'] for e in self.client.get('/api/especialistas/').data}
        self.assertIn(str(self.esp_rede_a.id), ids)
        self.assertNotIn(str(self.esp_a2.id), ids)
        self.assertNotIn(str(self.esp_rede_b.id), ids)

    def test_coordenador_abre_o_detalhe_do_especialista_da_rede(self):
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(f'/api/especialistas/{self.esp_rede_a.id}/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/especialistas/{self.esp_rede_b.id}/').status_code, 404)


class DisciplinaDuplicadaTests(CenarioMultiTenant):
    """Bug: nome repetido na mesma escola estourava a UniqueConstraint (500)."""

    def test_nome_repetido_na_escola_responde_400(self):
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.post('/api/disciplinas/criar/', {'nome': 'Matemática'}, format='json').status_code, 201)
        r = self.client.post('/api/disciplinas/criar/', {'nome': 'Matemática'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(Disciplina.objects.filter(escola=self.a1, nome='Matemática').count(), 1)

    def test_mesmo_nome_em_outra_escola_e_permitido(self):
        Disciplina.objects.create(nome='Matemática', escola=self.a2, instituicao=self.rede_a)
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.post('/api/disciplinas/criar/', {'nome': 'Matemática'}, format='json').status_code, 201)


class ContratoTests(CenarioMultiTenant):
    """Contrato aceitava escola de uma rede com instituição de outra, e
    template de outra escola."""

    def test_superadmin_nao_cria_contrato_com_escola_e_instituicao_de_redes_diferentes(self):
        self.entrar(self.superadmin)
        r = self.client.post('/api/contratos/criar/', {
            'documento': 'x', 'escola': str(self.b1.id), 'instituicao': str(self.rede_a.id),
            'responsavel': str(self.superadmin.id),
        }, format='json')
        self.assertIn(r.status_code, RECUSADO, r.content)
        self.assertFalse(Contrato.objects.exists())

    def test_contrato_deriva_a_instituicao_da_escola(self):
        self.entrar(self.superadmin)
        r = self.client.post('/api/contratos/criar/', {
            'documento': 'x', 'escola': str(self.b1.id), 'responsavel': str(self.superadmin.id),
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Contrato.objects.get(id=r.data['id']).instituicao_id, self.rede_b.id)

    def test_admin_nao_usa_template_exclusivo_de_outra_escola(self):
        template_a2 = TemplateDocumento.objects.create(
            titulo='Só A2', documento='d', escola=self.a2, instituicao=self.rede_a,
            responsavel=self.admin_a, criado_por=self.admin_a,
        )
        self.entrar(self.admin_a)
        r = self.client.post('/api/contratos/criar/', {
            'documento': 'x', 'escola': str(self.a1.id), 'template': str(template_a2.id),
            'responsavel': str(self.admin_a.id),
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(Contrato.objects.exists())