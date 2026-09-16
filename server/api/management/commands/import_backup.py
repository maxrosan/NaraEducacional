"""
Management command para importar dados do backup JSON para o PostgreSQL local

Uso:
    python manage.py import_backup
    python manage.py import_backup --flush  # Limpa dados antes de importar
    python manage.py import_backup --path /caminho/para/backups
"""

import json
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import (
    Instituicao,
    Usuario,
    Turma,
    Crianca,
    Relatorio,
    PerguntaBNCC,
    CalendarioBimestre,
)


class Command(BaseCommand):
    help = 'Importa dados do backup JSON para o banco de dados PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Limpa dados existentes antes de importar',
        )
        parser.add_argument(
            '--path',
            type=str,
            default='backups/20251129',
            help='Caminho para a pasta de backups (padrão: backups/20251129)',
        )

    def handle(self, *args, **options):
        backup_path = Path(options['path'])

        if not backup_path.exists():
            self.stderr.write(self.style.ERROR(f'Pasta de backup não encontrada: {backup_path}'))
            return

        if options['flush']:
            self.stdout.write(self.style.WARNING('Limpando dados existentes...'))
            self._flush_data()

        self.stdout.write(self.style.MIGRATE_HEADING('Iniciando importação do backup...'))
        self.stdout.write(f'Pasta: {backup_path.absolute()}')

        with transaction.atomic():
            # 1. Importar Instituições
            count = self._import_instituicoes(backup_path / 'instituicoes.json')
            self.stdout.write(self.style.SUCCESS(f'✓ {count} instituições importadas'))

            # 2. Importar Turmas
            count = self._import_turmas(backup_path / 'turmas.json')
            self.stdout.write(self.style.SUCCESS(f'✓ {count} turmas importadas'))

            # 3. Importar Usuários
            count = self._import_usuarios(backup_path / 'usuarios.json')
            self.stdout.write(self.style.SUCCESS(f'✓ {count} usuários importados'))

            # 4. Importar Crianças
            count = self._import_criancas(backup_path / 'criancas.json')
            self.stdout.write(self.style.SUCCESS(f'✓ {count} crianças importadas'))

            # 5. Importar Perguntas BNCC
            count = self._import_perguntas_bncc(backup_path / 'perguntas_bncc.json')
            self.stdout.write(self.style.SUCCESS(f'✓ {count} perguntas BNCC importadas'))

            # 6. Importar Calendário de Bimestres
            count = self._import_calendario(backup_path / 'calendario_bimestres.json')
            self.stdout.write(self.style.SUCCESS(f'✓ {count} bimestres importados'))

            # 7. Importar Relatórios
            count = self._import_relatorios(backup_path / 'relatorios.json')
            self.stdout.write(self.style.SUCCESS(f'✓ {count} relatórios importados'))

        self.stdout.write('\n' + self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('IMPORTAÇÃO CONCLUÍDA COM SUCESSO! 🎉'))
        self.stdout.write(self.style.SUCCESS('='*70))

    def _flush_data(self):
        """Remove dados existentes"""
        Relatorio.objects.all().delete()
        Crianca.objects.all().delete()
        PerguntaBNCC.objects.all().delete()
        CalendarioBimestre.objects.all().delete()
        Usuario.objects.filter(is_superuser=False).delete()
        Turma.objects.all().delete()
        Instituicao.objects.all().delete()
        self.stdout.write(self.style.WARNING('Dados limpos com sucesso.'))

    def _load_json(self, filepath):
        """Carrega arquivo JSON"""
        if not filepath.exists():
            self.stdout.write(self.style.WARNING(f'Arquivo não encontrado: {filepath}'))
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _parse_datetime(self, dt_str):
        """Converte string datetime para objeto datetime"""
        if not dt_str:
            return timezone.now()
        try:
            # Tenta formato ISO com timezone
            if '+' in dt_str or 'Z' in dt_str:
                dt_str = dt_str.replace('Z', '+00:00')
                return datetime.fromisoformat(dt_str)
            # Tenta formato sem timezone
            return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return timezone.now()

    def _parse_date(self, date_str):
        """Converte string date para objeto date"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    def _import_instituicoes(self, filepath):
        """Importa instituições do backup"""
        data = self._load_json(filepath)
        count = 0

        for item in data:
            try:
                Instituicao.objects.update_or_create(
                    id=UUID(item['id']),
                    defaults={
                        'nome': item.get('nome', ''),
                        'cnpj': item.get('cnpj', '').strip() if item.get('cnpj') else None,
                        'email_institucional': item.get('email_institucional', ''),
                        'cidade': item.get('cidade', ''),
                        'estado': item.get('uf', ''),
                        'telefone': item.get('telefone', ''),
                        'logo_url': item.get('logo_url', ''),
                        'tipo_relatorio': item.get('tipo_relatorio', 'texto_e_evidencia'),
                        'report_settings': item.get('report_settings', {}),
                        'ordem_relatorio': item.get('ordem_relatorio', []),
                        'ativa': True,
                    }
                )
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Erro ao importar instituição {item.get("id")}: {e}'))

        return count

    def _import_turmas(self, filepath):
        """Importa turmas do backup"""
        data = self._load_json(filepath)
        count = 0

        for item in data:
            try:
                Turma.objects.update_or_create(
                    id=UUID(item['id']),
                    defaults={
                        'nome': item.get('nome', ''),
                        'faixa_etaria': item.get('faixa_etaria', ''),
                        'turno': item.get('turno', 'manha'),
                        'ano_letivo': str(item.get('ano_letivo', '2025')),
                        'instituicao_id': UUID(item['instituicao_id']) if item.get('instituicao_id') else None,
                        'ativa': True,
                    }
                )
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Erro ao importar turma {item.get("id")}: {e}'))

        return count

    def _import_usuarios(self, filepath):
        """Importa usuários do backup"""
        data = self._load_json(filepath)
        count = 0

        # Mapeamento de perfis legados para Django
        perfil_map = {
            'admin': 'admin',
            'coordenador': 'coordenador',
            'professor': 'professor',
            'professor_especialista': 'professor_especialista',
            'especialista': 'especialista',
        }

        for item in data:
            try:
                perfil = perfil_map.get(item.get('perfil', 'professor'), 'professor')

                # Buscar instituição se existir
                instituicao = None
                if item.get('instituicao_id'):
                    try:
                        instituicao = Instituicao.objects.get(id=UUID(item['instituicao_id']))
                    except Instituicao.DoesNotExist:
                        pass

                Usuario.objects.update_or_create(
                    id=UUID(item['id']),
                    defaults={
                        'email': item.get('email', ''),
                        'nome': item.get('nome', ''),
                        'perfil': perfil,
                        'tipo_especialista': item.get('tipo_especialista'),
                        'instituicao': instituicao,
                        'ativo': item.get('ativo', True),
                        'is_staff': perfil in ['admin', 'coordenador'],
                        'is_superuser': perfil == 'admin',
                    }
                )
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Erro ao importar usuário {item.get("id")}: {e}'))

        return count

    def _import_criancas(self, filepath):
        """Importa crianças do backup"""
        data = self._load_json(filepath)
        count = 0

        for item in data:
            try:
                Crianca.objects.update_or_create(
                    id=UUID(item['id']),
                    defaults={
                        'nome_completo': item.get('nome_completo', ''),
                        'data_nascimento': self._parse_date(item.get('data_nascimento')),
                        'genero': item.get('genero'),
                        'turma_id': UUID(item['turma_id']) if item.get('turma_id') else None,
                        'instituicao_id': UUID(item['instituicao_id']) if item.get('instituicao_id') else None,
                        'nome_responsavel': item.get('nome_responsavel', ''),
                        'telefone_responsavel': item.get('telefone_responsavel', ''),
                        'status_vinculo': item.get('status_vinculo', 'ativo'),
                        'observacoes': item.get('observacoes'),
                    }
                )
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Erro ao importar criança {item.get("id")}: {e}'))

        return count

    def _import_perguntas_bncc(self, filepath):
        """Importa perguntas BNCC do backup"""
        data = self._load_json(filepath)
        count = 0

        for item in data:
            try:
                PerguntaBNCC.objects.update_or_create(
                    id=UUID(item['id']) if isinstance(item.get('id'), str) else item.get('id'),
                    defaults={
                        'faixa_etaria': item.get('faixa_etaria', ''),
                        'campo_experiencia': item.get('campo_experiencia', ''),
                        'pergunta': item.get('pergunta', ''),
                        'habilidade_bncc': item.get('habilidade_bncc', ''),
                        'area_conhecimento': item.get('area_conhecimento', ''),
                    }
                )
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Erro ao importar pergunta BNCC {item.get("id")}: {e}'))

        return count

    def _import_calendario(self, filepath):
        """Importa calendário de bimestres do backup"""
        data = self._load_json(filepath)
        count = 0

        for item in data:
            try:
                # O backup usa 'inicio' e 'fim' em vez de 'data_inicio' e 'data_fim'
                # Usa ano + bimestre como chave única em vez do id original
                CalendarioBimestre.objects.update_or_create(
                    ano=item.get('ano_letivo', 2025),
                    bimestre=item.get('numero_bimestre', 1),
                    defaults={
                        'data_inicio': self._parse_date(item.get('inicio')),
                        'data_fim': self._parse_date(item.get('fim')),
                        'instituicao_id': UUID(item['instituicao_id']) if item.get('instituicao_id') else None,
                    }
                )
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Erro ao importar bimestre {item.get("id")}: {e}'))

        return count

    def _import_relatorios(self, filepath):
        """Importa relatórios do backup"""
        data = self._load_json(filepath)
        count = 0

        for item in data:
            try:
                Relatorio.objects.update_or_create(
                    id=UUID(item['id']),
                    defaults={
                        'id_crianca': UUID(item['id_crianca']) if item.get('id_crianca') else None,
                        'periodo': item.get('periodo', ''),
                        'conteudo': item.get('conteudo', ''),
                        'revisado_por': UUID(item['revisado_por']) if item.get('revisado_por') else None,
                        'pdf_url': item.get('pdf_url', ''),
                        'instituicao_id': UUID(item['instituicao_id']) if item.get('instituicao_id') else None,
                    }
                )
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Erro ao importar relatório {item.get("id")}: {e}'))

        return count
