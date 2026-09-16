# Generated manually for CampoExperienciaCustomizado model

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    """
    Cria a tabela para armazenar Campos de Experiência customizados.
    Permite que administradores criem novos campos além dos padrão da BNCC.
    """

    dependencies = [
        ('api', '0013_perguntaespecialista_campo_experiencia'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampoExperienciaCustomizado',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('instituicao_id', models.UUIDField(blank=True, db_index=True, null=True, verbose_name='ID da Instituição')),
                ('nome', models.CharField(max_length=200, verbose_name='Nome do Campo de Experiência')),
                ('icone', models.CharField(default='BookOpen', max_length=50, verbose_name='Nome do Ícone (Lucide)')),
                ('cor', models.CharField(blank=True, max_length=20, null=True, verbose_name='Cor (hex)')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Campo de Experiência Customizado',
                'verbose_name_plural': 'Campos de Experiência Customizados',
                'db_table': 'campos_experiencia_customizados',
                'managed': True,
            },
        ),
        migrations.AddIndex(
            model_name='campoexperienciacustomizado',
            index=models.Index(fields=['instituicao_id', 'ativo'], name='campos_expe_institu_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='campoexperienciacustomizado',
            unique_together={('instituicao_id', 'nome')},
        ),
    ]
