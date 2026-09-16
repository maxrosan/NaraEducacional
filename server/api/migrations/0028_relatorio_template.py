import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0027_audio_dispositivo_resultado'),
    ]

    operations = [
        migrations.CreateModel(
            name='RelatorioTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('instituicao_id', models.UUIDField(db_index=True, verbose_name='ID da Instituição')),
                ('nome', models.CharField(max_length=100, verbose_name='Nome dado pela escola a este template')),
                ('modelo', models.CharField(
                    choices=[
                        ('classico', 'Clássico NARA'),
                        ('memorias', 'Memórias da Infância'),
                        ('mascote', 'Com a Nara'),
                        ('natureza', 'Pequenas Descobertas'),
                        ('essencial', 'Essencial'),
                    ],
                    max_length=20,
                    verbose_name='Modelo base',
                )),
                ('usa_foto_crianca', models.BooleanField(blank=True, default=None, null=True, verbose_name='Usa foto da criança na capa')),
                ('config', models.JSONField(default=dict, verbose_name='Configuração de personalização')),
                ('items_sumario', models.JSONField(default=list, verbose_name='Itens do sumário (ordem e visibilidade)')),
                ('ativo', models.BooleanField(default=False, verbose_name='Ativa (vale para os próximos relatórios)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Template de Relatório',
                'verbose_name_plural': 'Templates de Relatório',
                'db_table': 'relatorio_templates',
                'ordering': ['-updated_at'],
                'managed': True,
            },
        ),
        migrations.AddField(
            model_name='relatorio',
            name='template',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='relatorios',
                to='api.relatoriotemplate',
                verbose_name='Template de PDF utilizado',
            ),
        ),
        migrations.AddIndex(
            model_name='relatoriotemplate',
            index=models.Index(fields=['instituicao_id', 'ativo'], name='rel_tpl_inst_ativo_idx'),
        ),
        migrations.AddConstraint(
            model_name='relatoriotemplate',
            constraint=models.UniqueConstraint(
                fields=['instituicao_id', 'modelo'],
                name='unique_template_por_modelo_instituicao',
            ),
        ),
        migrations.AddConstraint(
            model_name='relatoriotemplate',
            constraint=models.UniqueConstraint(
                fields=['instituicao_id'],
                condition=models.Q(ativo=True),
                name='unique_template_ativo_por_instituicao',
            ),
        ),
    ]