"""GET /api/instituicoes/: superadmin vê todas; os demais, só a própria rede."""
from .base import CenarioMultiTenant

URL = '/api/instituicoes/'


class ListarInstituicoesTests(CenarioMultiTenant):

    def _ids(self, usuario):
        self.entrar(usuario)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        return {i['id'] for i in r.json()}

    def test_superadmin_ve_todas(self):
        ids = self._ids(self.superadmin)
        self.assertIn(str(self.rede_a.id), ids)
        self.assertIn(str(self.rede_b.id), ids)

    def test_admin_ve_so_a_propria_rede(self):
        self.assertEqual(self._ids(self.admin_a), {str(self.rede_a.id)})
        self.assertEqual(self._ids(self.admin_b), {str(self.rede_b.id)})

    def test_coordenador_e_professor_veem_so_a_propria_rede(self):
        self.assertEqual(self._ids(self.coord_a1), {str(self.rede_a.id)})
        self.assertEqual(self._ids(self.prof_b1), {str(self.rede_b.id)})

    def test_criar_continua_so_superadmin(self):
        self.entrar(self.admin_a)
        r = self.client.post('/api/instituicoes/criar/', {'nome': 'Rede Nova'}, format='json')
        self.assertEqual(r.status_code, 403, r.content)