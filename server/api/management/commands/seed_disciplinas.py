import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Disciplina, Instituicao


DISCIPLINAS_BASICAS = [
    'Língua Portuguesa',
    'Matemática',
    'Ciências',
    'História',
    'Geografia',
    'Arte',
    'Língua Inglesa',
]

DISCIPLINAS_EXTRAS = [
    'Bilíngue',
    'Educação Física',
    'Socioemocional',
    'Música',
    'Educação Financeira',
    'Empreendedorismo',
]

TODAS_DISCIPLINAS = DISCIPLINAS_BASICAS + DISCIPLINAS_EXTRAS


class Command(BaseCommand):
    help = 'Cria o conjunto padrão de disciplinas para uma instituição (ou todas).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--instituicao-id',
            type=str,
            help='UUID da instituição. Se omitido, use --all.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Cria as disciplinas para TODAS as instituições cadastradas.',
        )

    def handle(self, *args, **options):
        instituicao_id = options.get('instituicao_id')
        aplicar_todas = options.get('all')

        if not instituicao_id and not aplicar_todas:
            raise CommandError('Informe --instituicao-id <uuid> ou --all.')

        if instituicao_id:
            try:
                uuid.UUID(instituicao_id)
            except ValueError:
                raise CommandError(f'"{instituicao_id}" não é um UUID válido.')
            instituicoes = Instituicao.objects.filter(id=instituicao_id)
            if not instituicoes.exists():
                raise CommandError(f'Instituição {instituicao_id} não encontrada.')
        else:
            instituicoes = Instituicao.objects.all()
            if not instituicoes.exists():
                raise CommandError('Nenhuma instituição cadastrada.')

        total_criadas = 0
        total_existentes = 0

        with transaction.atomic():
            for instituicao in instituicoes:
                self.stdout.write(f'\n>> {instituicao.nome} ({instituicao.id})')
                for nome in TODAS_DISCIPLINAS:
                    _, criada = Disciplina.objects.get_or_create(
                        instituicao=instituicao,
                        nome=nome,
                    )
                    if criada:
                        total_criadas += 1
                        self.stdout.write(self.style.SUCCESS(f'  + {nome}'))
                    else:
                        total_existentes += 1
                        self.stdout.write(f'  = {nome} (já existia)')

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído: {total_criadas} criadas, {total_existentes} já existentes.'
        ))