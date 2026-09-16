"""
Management command para criar o calendário de bimestres de 2025.

Uso:
    python manage.py seed_bimestres_2025
"""

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import CalendarioBimestre, Instituicao


class Command(BaseCommand):
    help = 'Cria o calendário de bimestres de 2025 para todas as instituições.'

    def handle(self, *args, **options):
        bimestres_2025 = [
            (1, datetime.date(2025, 2, 1), datetime.date(2025, 4, 30)),
            (2, datetime.date(2025, 5, 1), datetime.date(2025, 7, 31)),
            (3, datetime.date(2025, 8, 1), datetime.date(2025, 10, 31)),
            (4, datetime.date(2025, 11, 1), datetime.date(2026, 1, 31)),
        ]

        instituicoes = list(Instituicao.objects.values_list('id', flat=True))
        if not instituicoes:
            instituicoes = [None]

        self.stdout.write(self.style.MIGRATE_HEADING('Iniciando seed de bimestres 2025...'))
        total_criados = 0
        total_existentes = 0

        with transaction.atomic():
            for instituicao_id in instituicoes:
                for numero, data_inicio, data_fim in bimestres_2025:
                    calendario, created = CalendarioBimestre.objects.get_or_create(
                        ano=2025,
                        bimestre=numero,
                        instituicao_id=instituicao_id,
                        defaults={
                            'data_inicio': data_inicio,
                            'data_fim': data_fim,
                        }
                    )

                    if created:
                        total_criados += 1
                    else:
                        total_existentes += 1

        self.stdout.write(self.style.SUCCESS(f'✓ {total_criados} bimestres criados'))
        if total_existentes:
            self.stdout.write(self.style.WARNING(f'• {total_existentes} bimestres já existiam'))
        self.stdout.write(self.style.SUCCESS('Seed concluído.'))
