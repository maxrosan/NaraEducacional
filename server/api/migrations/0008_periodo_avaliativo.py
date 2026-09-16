from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_relatorio_pdf_storage_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='PeriodoAvaliativo',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('descricao', models.CharField(max_length=200, verbose_name='Descrição do Período')),
                ('tipo_periodo', models.CharField(max_length=20, choices=[('bimestral', 'Bimestral'), ('trimestral', 'Trimestral'), ('semestral', 'Semestral'), ('anual', 'Anual')], verbose_name='Tipo do Período')),
                ('data_inicio', models.DateField(verbose_name='Data de Início')),
                ('data_fim', models.DateField(verbose_name='Data de Fim')),
                ('instituicao_id', models.UUIDField(db_index=True, verbose_name='ID da Instituição')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Período Avaliativo',
                'verbose_name_plural': 'Períodos Avaliativos',
                'db_table': 'periodos_avaliativos',
                'managed': True,
                'ordering': ['-data_inicio'],
                'indexes': [models.Index(fields=['instituicao_id', 'data_inicio', 'data_fim'], name='periodos_avaliativos_instituicao_data_idx')],
            },
        ),
    ]
