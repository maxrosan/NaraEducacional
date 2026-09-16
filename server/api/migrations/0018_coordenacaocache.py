from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_serieconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoordenacaoCache',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('instituicao_id', models.UUIDField(db_index=True, verbose_name='ID da Instituição')),
                ('data_referencia', models.DateField(db_index=True, verbose_name='Data de Referência (D-1)')),
                ('janela_dias', models.PositiveIntegerField(default=30, verbose_name='Janela (dias)')),
                ('payload', models.JSONField(verbose_name='Payload agregado')),
                ('versao_schema', models.CharField(default='1', max_length=20, verbose_name='Versão do Schema')),
                ('gerado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Cache da Coordenação',
                'verbose_name_plural': 'Caches da Coordenação',
                'db_table': 'coordenacao_cache',
                'ordering': ['-data_referencia'],
                'managed': True,
                'unique_together': {('instituicao_id', 'data_referencia')},
                'indexes': [
                    models.Index(fields=['instituicao_id', '-data_referencia'], name='coordenacao_cac_instit_b3a1d2_idx'),
                ],
            },
        ),
    ]
