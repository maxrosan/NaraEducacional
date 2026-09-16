from django.core.management.base import BaseCommand
from api.models import Usuario


class Command(BaseCommand):
    help = 'Cria o usuário master se não existir'

    def handle(self, *args, **options):
        email = 'beatriz@naraeducacional.com'

        if Usuario.objects.filter(email=email).exists():
            self.stdout.write(f'Usuário {email} já existe — pulando.')
            return

        Usuario.objects.create_superuser(
            email=email,
            password='NaraEad@2026',
            nome='Beatriz',
        )
        self.stdout.write(self.style.SUCCESS(f'Usuário master {email} criado com sucesso.'))
