from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_alter_perguntabncc_pergunta'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='relatorio',
            constraint=models.UniqueConstraint(
                fields=['id_crianca', 'periodo', 'instituicao_id'],
                name='unique_relatorio_crianca_periodo_instituicao',
            ),
        ),
    ]
