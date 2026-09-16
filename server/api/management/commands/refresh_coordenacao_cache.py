"""
Recomputa e persiste o snapshot da coordenação (`CoordenacaoCache`) localmente,
sem depender do scheduler/Celery nem do roundtrip HTTP do endpoint interno.

É o equivalente manual da task diária `tasks.refresh_coordenacao_cache`: útil
para rodar no servidor (ou no ambiente conda) e, principalmente, para
*diagnosticar* por que um payload sai vazio — imprime quantas crianças e
registros existem no banco da escola e qual a faixa de `data_observacao`.

O backend é single-tenant por escola, então a agregação cobre todo o banco; o
`instituicao_id` (env `NARA_INSTITUICAO_ID`) serve apenas de chave do snapshot.

Uso:
    python manage.py refresh_coordenacao_cache
    python manage.py refresh_coordenacao_cache --hoje
    python manage.py refresh_coordenacao_cache --instituicao-id <uuid> --data-referencia 2026-05-30
    python manage.py refresh_coordenacao_cache --dry-run   # só diagnostica, não grava
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.services.coordenacao_cache import (
    JANELA_DIAS,
    atualizar_cache_coordenacao,
    diagnosticar_cache,
    gerar_payload_coordenacao,
    resolver_recorte,
)


class Command(BaseCommand):
    help = (
        'Recomputa o cache da coordenação (CoordenacaoCache) e imprime um '
        'diagnóstico explicando por que o payload pode estar vazio.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--instituicao-id',
            dest='instituicao_id',
            default=None,
            help='UUID usado como chave do snapshot. Default: settings.NARA_INSTITUICAO_ID.',
        )
        parser.add_argument(
            '--data-referencia',
            dest='data_referencia',
            default=None,
            help='Data de referência YYYY-MM-DD. Default: ontem (D-1).',
        )
        parser.add_argument(
            '--hoje',
            action='store_true',
            help='Usa a data de hoje como referência (inclui registros de hoje).',
        )
        parser.add_argument(
            '--janela-dias',
            dest='janela_dias',
            type=int,
            default=JANELA_DIAS,
            help=f'Tamanho da janela em dias. Default: {JANELA_DIAS}.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas diagnostica e mostra o payload; não grava no banco.',
        )
        parser.add_argument(
            '--mostrar-payload',
            action='store_true',
            help='Imprime o payload computado (JSON).',
        )

    def handle(self, *args, **options):
        instituicao_id = options['instituicao_id'] or getattr(
            settings, 'NARA_INSTITUICAO_ID', ''
        )
        if not instituicao_id:
            raise CommandError(
                'instituicao_id não informado e NARA_INSTITUICAO_ID está vazio. '
                'Passe --instituicao-id <uuid> ou defina NARA_INSTITUICAO_ID no .env. '
                '(É só a chave do snapshot; a agregação cobre todo o banco.)'
            )

        janela_dias = options['janela_dias']

        if options['data_referencia']:
            try:
                data_referencia = date.fromisoformat(options['data_referencia'])
            except ValueError as exc:
                raise CommandError('--data-referencia inválida (use YYYY-MM-DD).') from exc
        elif options['hoje']:
            data_referencia = timezone.localdate()
        else:
            data_referencia = timezone.localdate() - timedelta(days=1)

        # ---- Diagnóstico (cobre todo o banco da escola) ----
        diag = diagnosticar_cache(data_referencia, janela_dias)
        self.stdout.write(self.style.MIGRATE_HEADING('Diagnóstico do cache da coordenação'))
        self.stdout.write(f"  instituicao_id (chave) .... {instituicao_id}")
        self.stdout.write(f"  data_referencia ........... {diag['data_referencia']}")
        self.stdout.write(
            f"  janela .................... {diag['data_inicio_janela']} → "
            f"{diag['data_referencia']} ({diag['janela_dias']} dias)"
        )
        self.stdout.write(f"  crianças no banco ......... {diag['total_criancas_banco']}")
        self.stdout.write(f"  registros (total) ......... {diag['total_registros_banco']}")
        self.stdout.write(
            f"  data_observacao (min/max) . {diag['data_observacao_min']} / "
            f"{diag['data_observacao_max']}"
        )
        self.stdout.write(
            self.style.SUCCESS(f"  registros NA JANELA ....... {diag['registros_na_janela']}")
            if diag['registros_na_janela']
            else self.style.ERROR(f"  registros NA JANELA ....... {diag['registros_na_janela']}")
        )

        # ---- Avisos acionáveis ----
        if diag['total_registros_banco'] == 0:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  Não há nenhum registro_observacao neste banco. '
                'Confirme que está conectado ao banco da escola correta.'
            ))
        elif diag['registros_na_janela'] == 0:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  Há {diag['total_registros_banco']} registro(s), mas nenhum "
                f"na janela. O mais recente é de {diag['data_observacao_max']}. "
                'Use --data-referencia/--hoje, ou aumente --janela-dias, ou crie '
                'observações recentes.'
            ))

        if options['mostrar_payload'] or options['dry_run']:
            recorte = resolver_recorte(data_referencia=data_referencia)
            payload = gerar_payload_coordenacao(instituicao_id, recorte)
            self.stdout.write('\nPayload computado:')
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))

        if options['dry_run']:
            self.stdout.write(self.style.NOTICE('\n--dry-run: nada foi gravado no banco.'))
            return

        obj = atualizar_cache_coordenacao(instituicao_id, data_referencia, janela_dias)
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Cache gravado: instituicao={obj.instituicao_id} "
            f"data_referencia={obj.data_referencia} gerado_em={obj.gerado_em.isoformat()}"
        ))
