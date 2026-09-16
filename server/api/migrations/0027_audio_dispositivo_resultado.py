"""Resultado do processamento do áudio do gravador (base do feedback ao firmware).

O aparelho não tem tela: a professora só sabe se a turma foi reconhecida e se a
criança foi registrada consultando o servidor depois do upload. Estes campos são
o que o endpoint de feedback devolve.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_dispositivo_multiplas_turmas'),
    ]

    operations = [
        migrations.AddField(
            model_name='audiodispositivo',
            name='erro_codigo',
            field=models.CharField(
                blank=True, default='', max_length=40,
                verbose_name='Código do erro (legível por máquina, para o firmware)',
            ),
        ),
        migrations.AddField(
            model_name='audiodispositivo',
            name='transcricao',
            field=models.TextField(
                blank=True, default='', verbose_name='Transcrição completa do áudio',
            ),
        ),
        migrations.AddField(
            model_name='audiodispositivo',
            name='turma_resultado',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[
                    ('', 'Ainda não processado'),
                    ('anunciada', 'Anunciada na fala e autorizada'),
                    ('nao_autorizada', 'Anunciada na fala, mas fora do escopo do dispositivo'),
                    ('ativa', 'Turma ativa corrente (nada foi anunciado)'),
                    ('unica', 'Única turma do dispositivo'),
                    ('indefinida', 'Não foi possível determinar a turma'),
                ],
                verbose_name='Como a turma foi decidida',
            ),
        ),
        migrations.AddField(
            model_name='audiodispositivo',
            name='turma_anunciada_texto',
            field=models.CharField(
                blank=True, default='', max_length=200,
                verbose_name='Nome de turma reconhecido na fala',
            ),
        ),
        migrations.AddField(
            model_name='audiodispositivo',
            name='total_observacoes',
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name='Quantas observações o áudio gerou',
            ),
        ),
        migrations.AddField(
            model_name='audiodispositivo',
            name='alunos_identificados',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Nomes pareados com crianças da turma',
            ),
        ),
        migrations.AddField(
            model_name='audiodispositivo',
            name='nomes_nao_identificados',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Nomes citados que não bateram com nenhuma criança',
            ),
        ),
        migrations.AlterField(
            model_name='audiodispositivo',
            name='status',
            field=models.CharField(
                default='recebido', max_length=20,
                choices=[
                    ('recebido', 'Recebido (aguardando processamento)'),
                    ('processando', 'Processando'),
                    ('processado', 'Processado (observações geradas)'),
                    ('comando', 'Comando de sala (só anunciou a turma)'),
                    ('falhou', 'Falha no processamento'),
                ],
            ),
        ),
        migrations.AlterField(
            model_name='audiodispositivo',
            name='observacao',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.SET_NULL,
                related_name='audios_dispositivo', to='api.observacaotranscricao',
                verbose_name='Primeira observação gerada (atalho para o relato)',
            ),
        ),
    ]
