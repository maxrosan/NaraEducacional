"""
Management command para criar usuários de teste de permissões.

Cria exatamente os usuários que test_permissoes_acesso.py espera,
com as credenciais definidas em tests/.env (ou os defaults abaixo).

Uso:
    python manage.py seed_test_permissoes
    python manage.py seed_test_permissoes --flush  # remove os usuários antes de recriar
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Instituicao, Usuario


USUARIOS_TESTE = [
    {
        'email': 'admin@nara.dev',
        'senha': 'admin123',
        'nome': 'Admin Teste Permissões',
        'perfil': 'admin',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'email': 'coordenador@nara.dev',
        'senha': 'coordenador123',
        'nome': 'Coordenador Teste Permissões',
        'perfil': 'coordenador',
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'email': 'professor@nara.dev',
        'senha': 'professor123',
        'nome': 'Professor Teste Permissões',
        'perfil': 'professor',
        'is_staff': False,
        'is_superuser': False,
    },
]


class Command(BaseCommand):
    help = 'Cria usuários de teste para test_permissoes_acesso.py'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Remove os usuários de teste antes de recriar',
        )

    def handle(self, *args, **options):
        if options['flush']:
            emails = [u['email'] for u in USUARIOS_TESTE]
            deleted, _ = Usuario.objects.filter(email__in=emails).delete()
            self.stdout.write(self.style.WARNING(f'Removidos {deleted} usuários de teste anteriores.'))

        # Garante que existe pelo menos uma instituição
        instituicao, criada = Instituicao.objects.get_or_create(
            cnpj='00.000.000/0001-00',
            defaults={
                'nome': 'Instituição Teste Permissões',
                'email_institucional': 'teste@permissoes.dev',
                'ativa': True,
            }
        )
        if criada:
            self.stdout.write(self.style.SUCCESS('✓ Instituição de teste criada'))

        with transaction.atomic():
            for dados in USUARIOS_TESTE:
                usuario, criado = Usuario.objects.get_or_create(
                    email=dados['email'],
                    defaults={
                        'nome': dados['nome'],
                        'perfil': dados['perfil'],
                        'instituicao': instituicao,
                        'ativo': True,
                        'is_staff': dados['is_staff'],
                        'is_superuser': dados['is_superuser'],
                    }
                )

                if not criado:
                    usuario.nome = dados['nome']
                    usuario.perfil = dados['perfil']
                    usuario.instituicao = instituicao
                    usuario.ativo = True
                    usuario.is_staff = dados['is_staff']
                    usuario.is_superuser = dados['is_superuser']

                usuario.set_password(dados['senha'])
                usuario.save()

                acao = 'criado' if criado else 'atualizado'
                self.stdout.write(self.style.SUCCESS(
                    f'✓ {dados["perfil"].upper().ljust(12)} {acao}: {dados["email"]}'
                ))

        self.stdout.write('\n' + self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('USUÁRIOS DE TESTE PRONTOS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.MIGRATE_LABEL('\nCredenciais para tests/.env:\n'))

        env_lines = [
            f'NARA_ADMIN_EMAIL=admin@nara.dev',
            f'NARA_ADMIN_PASSWORD=admin123',
            f'NARA_COORDENADOR_EMAIL=coordenador@nara.dev',
            f'NARA_COORDENADOR_PASSWORD=coordenador123',
            f'NARA_PROFESSOR_EMAIL=professor@nara.dev',
            f'NARA_PROFESSOR_PASSWORD=professor123',
        ]
        for line in env_lines:
            self.stdout.write(f'  {self.style.HTTP_INFO(line)}')

        self.stdout.write(self.style.WARNING('\n⚠️  Apenas para testes. Nunca use em produção.\n'))
