"""Cenário multi-tenant compartilhado pelos testes.

Duas redes (tenants) independentes:
    Rede A: escolas A1 e A2        Rede B: escola B1
Cada escola tem coordenador, professor, turma e aluno; cada rede tem um admin.

Autenticação SEMPRE por JWT real (não force_authenticate): é o
`TenantJWTAuthentication` que define o escopo do TenantManager. Com
force_authenticate o escopo nunca é definido e o teste não prova isolamento.
"""
from datetime import date

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Aluno, Escola, Instituicao, Turma, Usuario, UsuarioTurma

SENHA = 'Senha#Forte2026'


class CenarioMultiTenant(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.rede_a = Instituicao.objects.create(nome='Rede A')
        cls.rede_b = Instituicao.objects.create(nome='Rede B')
        cls.a1 = Escola.objects.create(instituicao=cls.rede_a, nome='A1')
        cls.a2 = Escola.objects.create(instituicao=cls.rede_a, nome='A2')
        cls.b1 = Escola.objects.create(instituicao=cls.rede_b, nome='B1')

        cls.superadmin = cls._usuario('super@x.com', 'superadmin', None, None, is_superuser=True)
        cls.admin_a = cls._usuario('admin.a@x.com', 'admin', cls.rede_a, None)
        cls.admin_b = cls._usuario('admin.b@x.com', 'admin', cls.rede_b, None)
        cls.coord_a1 = cls._usuario('coord.a1@x.com', 'coordenador', cls.rede_a, cls.a1)
        cls.coord_a2 = cls._usuario('coord.a2@x.com', 'coordenador', cls.rede_a, cls.a2)
        cls.coord_b1 = cls._usuario('coord.b1@x.com', 'coordenador', cls.rede_b, cls.b1)
        cls.prof_a1 = cls._usuario('prof.a1@x.com', 'professor_infantil', cls.rede_a, cls.a1)
        cls.prof_b1 = cls._usuario('prof.b1@x.com', 'professor_infantil', cls.rede_b, cls.b1)

        cls.turma_a1 = Turma.objects.create(nome='Nível 3A', escola=cls.a1, instituicao=cls.rede_a)
        cls.turma_a2 = Turma.objects.create(nome='Nível 3B', escola=cls.a2, instituicao=cls.rede_a)
        cls.turma_b1 = Turma.objects.create(nome='Nível 3A', escola=cls.b1, instituicao=cls.rede_b)
        UsuarioTurma.objects.create(usuario=cls.prof_a1, turma=cls.turma_a1)
        UsuarioTurma.objects.create(usuario=cls.prof_b1, turma=cls.turma_b1)

        cls.aluno_a1 = cls._aluno('Ana A1', cls.turma_a1)
        cls.aluno_a2 = cls._aluno('Bia A2', cls.turma_a2)
        cls.aluno_b1 = cls._aluno('Caio B1', cls.turma_b1)

    @staticmethod
    def _usuario(email, nivel, instituicao, escola, **extra):
        return Usuario.objects.create_user(
            email=email, password=SENHA, nome=email.split('@')[0], nivel=nivel,
            instituicao=instituicao, escola=escola, **extra,
        )

    @staticmethod
    def _aluno(nome, turma):
        return Aluno.objects.create(
            nome_completo=nome, data_nascimento=date(2020, 1, 1), turma=turma,
            escola=turma.escola, instituicao=turma.instituicao,
        )

    def entrar(self, usuario):
        """Autentica o client com um access token JWT real."""
        token = RefreshToken.for_user(usuario).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return self.client
