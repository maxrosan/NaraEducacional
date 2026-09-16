from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0006_relatorio_unique_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='relatorio',
            name='pdf_storage_key',
            field=models.CharField(
                blank=True,
                max_length=500,
                null=True,
                verbose_name='Chave do PDF no Storage',
            ),
        ),
    ]
