import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0028_relatorio_template'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='perfil',
            field=models.CharField(
                choices=[
                    ('admin', 'Administrador'),
                    ('coordenador', 'Coordenador Pedagógico'),
                    ('professor', 'Professor'),
                    ('professor_infantil', 'Professor Educação Infantil'),
                    ('professor_fundamental', 'Professor Ensino Fundamental'),
                    ('professor_especialista', 'Professor Especialista'),
                    ('especialista', 'Especialista'),
                ],
                default='professor',
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name='Disciplina',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100, verbose_name='Nome da Disciplina')),
                ('ativo', models.BooleanField(default=True, verbose_name='Disciplina Ativa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('instituicao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disciplinas', to='api.instituicao', verbose_name='Instituição')),
            ],
            options={
                'db_table': 'disciplinas',
                'verbose_name': 'Disciplina',
                'verbose_name_plural': 'Disciplinas',
                'ordering': ['nome'],
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='UsuarioDisciplina',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('disciplina', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usuario_disciplinas', to='api.disciplina', verbose_name='Disciplina')),
                ('instituicao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usuario_disciplinas', to='api.instituicao', verbose_name='Instituição')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usuario_disciplinas', to='api.usuario', verbose_name='Usuário')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'usuario_disciplinas',
                'verbose_name': 'Vínculo Usuário-Disciplina',
                'verbose_name_plural': 'Vínculos Usuário-Disciplina',
                'managed': True,
            },
        ),
        migrations.AddConstraint(
            model_name='disciplina',
            constraint=models.UniqueConstraint(fields=('instituicao', 'nome'), name='unique_disciplina_por_instituicao'),
        ),
        migrations.AddConstraint(
            model_name='usuariodisciplina',
            constraint=models.UniqueConstraint(fields=('usuario', 'disciplina'), name='unique_usuario_disciplina'),
        ),
        migrations.AddIndex(
            model_name='usuariodisciplina',
            index=models.Index(fields=['usuario'], name='usuario_disc_usuario_idx'),
        ),
        migrations.AddIndex(
            model_name='usuariodisciplina',
            index=models.Index(fields=['instituicao'], name='usuario_disc_instit_idx'),
        ),
        migrations.AddField(
            model_name='usuario',
            name='disciplinas',
            field=models.ManyToManyField(related_name='professores', through='api.UsuarioDisciplina', to='api.disciplina', verbose_name='Disciplinas'),
        ),
    ]