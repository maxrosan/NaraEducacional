# Generated manually for A2: Adicionar campo pergunta_norma nas Perguntas BNCC

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_alertas_lidos'),
    ]

    operations = [
        migrations.AddField(
            model_name='perguntabncc',
            name='pergunta_norma',
            field=models.TextField(blank=True, null=True, verbose_name='Pergunta Original da Norma BNCC'),
        ),
    ]
