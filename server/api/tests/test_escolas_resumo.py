"""GET /api/admin/dashboard/: cards de escolas do dashboard do admin."""
from datetime import timedelta

from django.utils import timezone

from api.models import Aluno, RegistroObservacao, Turma

from .base import CenarioMultiTenant

URL = '/api/admin/dashboard/'


class ResumoEscolasTests(CenarioMultiTenant):

    def _resumo(self, usuario):
        self.entrar(usuario)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        return {e['id']: e for e in r.json()}

    def test_admin_ve_so_as_escolas_da_propria_rede(self):
        escolas = self._resumo(self.admin_a)
        self.assertEqual(set(escolas), {str(self.a1.id), str(self.a2.id)})

    def test_contagens_da_escola(self):
        a1 = self._resumo(self.admin_a)[str(self.a1.id)]['totais']
        # Cenário base da A1: 1 turma, 1 aluno, prof_a1 e coord_a1.
        self.assertEqual(a1, {'turmas': 1, 'alunos': 1, 'professores': 1, 'coordenadores': 1, 'registros_30d': 0})

        a2 = self._resumo(self.admin_a)[str(self.a2.id)]['totais']
        # A2 tem coordenador, turma e aluno, mas nenhum professor.
        self.assertEqual(a2, {'turmas': 1, 'alunos': 1, 'professores': 0, 'coordenadores': 1, 'registros_30d': 0})

    def test_nao_conta_inativos(self):
        Turma.objects.create(nome='Antiga', escola=self.a1, instituicao=self.rede_a, ativa=False)
        Aluno.objects.filter(pk=self.aluno_a1.pk).update(status_vinculo='transferido')
        self.prof_a1.is_active = False
        self.prof_a1.save()

        a1 = self._resumo(self.admin_a)[str(self.a1.id)]['totais']
        self.assertEqual(a1, {'turmas': 1, 'alunos': 0, 'professores': 0, 'coordenadores': 1, 'registros_30d': 0})

    def test_contagem_nao_multiplica_com_varios_registros(self):
        """Várias turmas e alunos na mesma escola não inflam os outros totais."""
        for i in range(3):
            t = Turma.objects.create(nome=f'Extra {i}', escola=self.a1, instituicao=self.rede_a)
            self._aluno(f'Extra {i}', t)
        a1 = self._resumo(self.admin_a)[str(self.a1.id)]['totais']
        self.assertEqual(a1, {'turmas': 4, 'alunos': 4, 'professores': 1, 'coordenadores': 1, 'registros_30d': 0})

    def test_coordenador_ve_so_a_propria_escola(self):
        self.assertEqual(set(self._resumo(self.coord_a1)), {str(self.a1.id)})

    def test_professor_nao_acessa(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_superadmin_ve_todas_e_filtra_por_rede(self):
        self.assertEqual(
            set(self._resumo(self.superadmin)),
            {str(self.a1.id), str(self.a2.id), str(self.b1.id)},
        )
        self.entrar(self.superadmin)
        r = self.client.get(URL, {'instituicao_id': str(self.rede_b.id)})
        self.assertEqual({e['id'] for e in r.json()}, {str(self.b1.id)})

    def _observacao(self, criado_em):
        r = RegistroObservacao.objects.create(
            aluno=self.aluno_a1, professor=self.prof_a1, escola=self.a1, instituicao=self.rede_a,
        )
        # criado_em é auto_now_add: ajusta depois de criar.
        RegistroObservacao.objects.filter(pk=r.pk).update(criado_em=criado_em)

    def test_atividade_recente(self):
        agora = timezone.now()
        self._observacao(agora - timedelta(days=2))
        self._observacao(agora - timedelta(days=5))
        self._observacao(agora - timedelta(days=45))  # fora da janela de 30 dias

        escolas = self._resumo(self.admin_a)
        a1 = escolas[str(self.a1.id)]
        self.assertEqual(a1['totais']['registros_30d'], 2)
        self.assertTrue(a1['ultimo_registro'].startswith((agora - timedelta(days=2)).date().isoformat()))

        a2 = escolas[str(self.a2.id)]
        self.assertEqual(a2['totais']['registros_30d'], 0)
        self.assertIsNone(a2['ultimo_registro'])

    def test_listagem_de_escolas_continua_funcionando(self):
        """Regressão: `_escolas_no_escopo` é função auxiliar, não view."""
        self.entrar(self.admin_a)
        r = self.client.get('/api/escolas/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual({e['id'] for e in r.json()}, {str(self.a1.id), str(self.a2.id)})

    def test_resumo_traz_nome_da_rede(self):
        escolas = self._resumo(self.admin_a)
        self.assertEqual(escolas[str(self.a1.id)]['instituicao_nome'], 'Rede A')