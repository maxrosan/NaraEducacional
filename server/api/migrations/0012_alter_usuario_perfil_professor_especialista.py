from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_configuracaoregistro'),
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
                    ('professor_especialista', 'Professor Especialista'),
                    ('especialista', 'Especialista'),
                ],
                default='professor',
                max_length=30,
            ),
        ),
    ]
