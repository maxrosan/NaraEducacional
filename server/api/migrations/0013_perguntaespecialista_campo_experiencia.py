# Generated manually for adding campo_experiencia field

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adiciona o campo 'campo_experiencia' à tabela perguntas_especialistas.
    Este campo define como a pergunta será agrupada no formulário de observação do professor.
    O campo 'especialidade' é mantido para compatibilidade com dados existentes.
    """

    dependencies = [
        ('api', '0012_alter_usuario_perfil_professor_especialista'),
    ]

    operations = [
        migrations.AddField(
            model_name='perguntaespecialista',
            name='campo_experiencia',
            field=models.CharField(
                db_index=True,
                default='',
                max_length=200,
                verbose_name='Campo de Experiência'
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='perguntaespecialista',
            name='especialidade',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                verbose_name='Especialidade (Legado)'
            ),
        ),
        # Migração de dados: copiar especialidade para campo_experiencia se estiver vazio
        migrations.RunSQL(
            sql="""
                UPDATE perguntas_especialistas
                SET campo_experiencia = COALESCE(especialidade, 'Outros')
                WHERE campo_experiencia = '' OR campo_experiencia IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
