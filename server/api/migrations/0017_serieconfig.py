import uuid
from django.db import migrations, models


def seed_series(apps, schema_editor):
    SerieConfig = apps.get_model('api', 'SerieConfig')
    series = [
        # Educação Infantil
        {'nome': 'Adaptação', 'etapa': 'educacao_infantil', 'ordem': 0, 'idade_min': 0, 'idade_max': 2},
        {'nome': 'Nível 1', 'etapa': 'educacao_infantil', 'ordem': 1, 'idade_min': 2, 'idade_max': 3},
        {'nome': 'Nível 2', 'etapa': 'educacao_infantil', 'ordem': 2, 'idade_min': 3, 'idade_max': 4},
        {'nome': 'Nível 3', 'etapa': 'educacao_infantil', 'ordem': 3, 'idade_min': 4, 'idade_max': 5},
        {'nome': 'Nível 4', 'etapa': 'educacao_infantil', 'ordem': 4, 'idade_min': 5, 'idade_max': 6},
        {'nome': 'Nível 5', 'etapa': 'educacao_infantil', 'ordem': 5, 'idade_min': 6, 'idade_max': 7},
        # Ensino Fundamental
        {'nome': '1º ANO', 'etapa': 'ensino_fundamental', 'ordem': 6, 'idade_min': 6, 'idade_max': 7},
        {'nome': '2º ANO', 'etapa': 'ensino_fundamental', 'ordem': 7, 'idade_min': 7, 'idade_max': 8},
        {'nome': '3º ANO', 'etapa': 'ensino_fundamental', 'ordem': 8, 'idade_min': 8, 'idade_max': 9},
        {'nome': '4º ANO', 'etapa': 'ensino_fundamental', 'ordem': 9, 'idade_min': 9, 'idade_max': 10},
        {'nome': '5º ANO', 'etapa': 'ensino_fundamental', 'ordem': 10, 'idade_min': 10, 'idade_max': 11},
    ]
    for s in series:
        SerieConfig.objects.create(id=uuid.uuid4(), **s)


def reverse_seed(apps, schema_editor):
    SerieConfig = apps.get_model('api', 'SerieConfig')
    SerieConfig.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_seed_campos_experiencia_padrao'),
    ]

    operations = [
        migrations.CreateModel(
            name='SerieConfig',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=50, verbose_name='Nome da Série')),
                ('etapa', models.CharField(choices=[('educacao_infantil', 'Educação Infantil'), ('ensino_fundamental', 'Ensino Fundamental')], max_length=30, verbose_name='Etapa de Ensino')),
                ('ordem', models.IntegerField(verbose_name='Ordem de Exibição')),
                ('idade_min', models.IntegerField(blank=True, null=True, verbose_name='Idade Mínima (anos)')),
                ('idade_max', models.IntegerField(blank=True, null=True, verbose_name='Idade Máxima (anos)')),
                ('ativa', models.BooleanField(default=True, verbose_name='Ativa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Configuração de Série',
                'verbose_name_plural': 'Configurações de Séries',
                'db_table': 'series_config',
                'ordering': ['etapa', 'ordem'],
                'managed': True,
            },
        ),
        migrations.RunPython(seed_series, reverse_seed),
    ]
