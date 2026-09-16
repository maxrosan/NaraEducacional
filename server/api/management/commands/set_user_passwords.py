"""
Management command para definir senhas para usuários importados.

Uso:
    python manage.py set_user_passwords
    python manage.py set_user_passwords --password=senha123
"""

from django.core.management.base import BaseCommand
from api.models import Usuario


class Command(BaseCommand):
    help = 'Define senhas para todos os usuários que não têm senha configurada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='nara2025',
            help='Senha padrão para definir (padrão: nara2025)',
        )

    def handle(self, *args, **options):
        password = options['password']
        usuarios = Usuario.objects.all()
        count = 0

        self.stdout.write(self.style.MIGRATE_HEADING('Definindo senhas para usuários...'))

        for usuario in usuarios:
            # Verificar se o usuário já tem senha válida
            if not usuario.has_usable_password():
                usuario.set_password(password)
                usuario.save()
                count += 1
                self.stdout.write(f'  ✓ Senha definida para: {usuario.email}')

        if count == 0:
            self.stdout.write(self.style.WARNING('Nenhum usuário precisava de senha.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n{count} usuários atualizados com senha padrão: {password}'))

        # Listar todos os usuários para referência
        self.stdout.write('\n' + self.style.MIGRATE_LABEL('Usuários disponíveis:'))
        for usuario in usuarios[:10]:  # Limitar a 10 para não poluir
            status = '✓' if usuario.has_usable_password() else '✗'
            self.stdout.write(f'  {status} {usuario.email} ({usuario.perfil})')

        if usuarios.count() > 10:
            self.stdout.write(f'  ... e mais {usuarios.count() - 10} usuários')
