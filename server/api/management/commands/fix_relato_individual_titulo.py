"""
Corrige títulos de seção já salvos em RelatorioTemplate.items_sumario que
ainda carregam o sufixo antigo "da Criança".

Motivo: os títulos padrão dessas seções no código (server/api/services/
relatorio.py :: _SECOES_PADRAO, e o espelho
client/src/lib/templateRelatorioShared.js) já foram corrigidos para:
    - chave "relato"     -> "Relato Individual"
    - chave "portfolio"  -> "Portfólio"
Porém, templates de relatório criados/salvos antes dessa correção ainda têm
"Relato Individual da Criança" / "Portfólio da Criança" persistidos no JSON
de `items_sumario`, e esse valor salvo tem prioridade sobre o default do
código (ver `_normalizar_items_sumario`), fazendo o título antigo continuar
aparecendo — inclusive em relatórios gerados a partir de agora, já que o
título é lido do template a cada geração, não é fixo por relatório.

Onde colocar este arquivo no projeto:
    server/api/management/commands/fix_relato_individual_titulo.py

Uso:
    python manage.py fix_relato_individual_titulo --dry-run   # só mostra o que mudaria
    python manage.py fix_relato_individual_titulo             # aplica de fato
"""
from django.core.management.base import BaseCommand

from api.models import RelatorioTemplate

# chave da seção -> (texto correto, marcador que identifica o título antigo)
_CORRECOES = {
    'relato': ('Relato Individual', 'relato individual'),
    'portfolio': ('Portfólio', 'portfólio'),
}
_SUFIXO_ANTIGO = 'criança'


def _eh_titulo_antigo(chave: str, titulo: str) -> bool:
    """Detecta variações do título antigo (maiúsculas/espaços não importam),
    sem mexer em títulos diferentes que o coordenador tenha escolhido de
    propósito para a seção."""
    if not titulo or chave not in _CORRECOES:
        return False
    normalizado = titulo.strip().lower()
    _, marcador = _CORRECOES[chave]
    return marcador in normalizado and _SUFIXO_ANTIGO in normalizado


class Command(BaseCommand):
    help = (
        'Corrige os títulos das seções "relato" e "portfolio" salvos em '
        'RelatorioTemplate.items_sumario, removendo o sufixo "da Criança".'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas lista os templates que seriam alterados, sem salvar.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        alterados = 0

        for template in RelatorioTemplate.objects.all():
            items = template.items_sumario
            if not isinstance(items, list):
                continue

            mudou = False
            for item in items:
                if not isinstance(item, dict):
                    continue
                chave = item.get('chave')
                if chave not in _CORRECOES:
                    continue

                titulo_atual = (item.get('titulo') or '').strip()
                if _eh_titulo_antigo(chave, titulo_atual):
                    titulo_correto, _ = _CORRECOES[chave]
                    self.stdout.write(
                        f'  template={template.id} instituicao={template.instituicao_id} '
                        f'chave={chave} "{titulo_atual}" -> "{titulo_correto}"'
                    )
                    item['titulo'] = titulo_correto
                    mudou = True

            if mudou:
                alterados += 1
                if not dry_run:
                    template.save(update_fields=['items_sumario'])

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[dry-run] {alterados} template(s) seriam corrigidos. Nenhuma alteração foi salva.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{alterados} template(s) corrigido(s) com sucesso.'
            ))  