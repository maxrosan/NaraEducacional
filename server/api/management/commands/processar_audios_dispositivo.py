"""Worker que transforma os áudios do gravador físico em relatos individuais.

Uso:

    # uma passada (ideal para cron)
    python manage.py processar_audios_dispositivo

    # daemon: fica no ar checando a fila (ideal para dev e para container próprio)
    python manage.py processar_audios_dispositivo --loop --intervalo 15

    # reprocessar um áudio específico depois de corrigir o vínculo da turma
    python manage.py processar_audios_dispositivo --upload-id <uuid>
    python manage.py processar_audios_dispositivo --refazer-falhas
"""

import time

from django.core.management.base import BaseCommand, CommandError

from api.models import AudioDispositivo
from api.services import dispositivo_processamento


class Command(BaseCommand):
    help = 'Processa os áudios recebidos dos gravadores (transcrição → relato individual).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite', type=int, default=20,
            help='Quantos áudios processar por passada (default: 20).',
        )
        parser.add_argument(
            '--loop', action='store_true',
            help='Fica rodando em vez de sair após uma passada.',
        )
        parser.add_argument(
            '--intervalo', type=int, default=15,
            help='Segundos entre as passadas quando --loop (default: 15).',
        )
        parser.add_argument(
            '--upload-id', help='Processa apenas este upload_id (aceita status falhou).',
        )
        parser.add_argument(
            '--refazer-falhas', action='store_true',
            help='Devolve os áudios em "falhou" para a fila antes de processar '
                 '(use depois de corrigir turmas/vínculos).',
        )

    def handle(self, *args, **opcoes):
        if opcoes['upload_id']:
            return self._processar_um(opcoes['upload_id'])

        if opcoes['refazer_falhas']:
            devolvidos = AudioDispositivo.objects.filter(status='falhou').update(
                status='recebido', erro_processamento='', erro_codigo='',
            )
            self.stdout.write(f'{devolvidos} áudio(s) devolvido(s) à fila.')

        if not opcoes['loop']:
            return self._passada(opcoes['limite'])

        self.stdout.write(
            self.style.SUCCESS(
                f"Worker do gravador no ar (a cada {opcoes['intervalo']}s). Ctrl+C para sair."
            )
        )
        try:
            while True:
                self._passada(opcoes['limite'], silencioso_se_vazio=True)
                time.sleep(opcoes['intervalo'])
        except KeyboardInterrupt:
            self.stdout.write('\nEncerrado.')

    def _passada(self, limite, silencioso_se_vazio=False):
        resumo = dispositivo_processamento.processar_pendentes(limite=limite)
        if resumo['total'] == 0:
            if not silencioso_se_vazio:
                self.stdout.write('Nenhum áudio pendente.')
            return
        self.stdout.write(
            f"{resumo['total']} áudio(s): {resumo['processados']} processado(s), "
            f"{resumo['comandos']} comando(s) de sala, {resumo['falhas']} com falha, "
            f"{resumo['adiados']} adiado(s)."
        )

    def _processar_um(self, upload_id):
        audio = AudioDispositivo.objects.filter(upload_id=upload_id).first()
        if not audio:
            raise CommandError(f'Nenhum áudio com upload_id={upload_id}.')

        if audio.status in ('processado', 'comando'):
            self.stdout.write(
                self.style.WARNING(
                    'Áudio já processado — nada foi refeito (evita relato duplicado).'
                )
            )
            return

        resultado = dispositivo_processamento.processar_audio(audio)
        estilo = (
            self.style.SUCCESS
            if resultado.status in ('processado', 'comando')
            else self.style.ERROR
        )
        self.stdout.write(estilo(
            f"{resultado.status}: {resultado.feedback['mensagem']}"
        ))
