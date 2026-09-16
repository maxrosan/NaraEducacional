from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0029_perfil_disciplinas'),  
    ]

    operations = [
        migrations.AddField(
            model_name='instituicao',
            name='logo_storage_key',
            field=models.CharField(max_length=500, null=True, blank=True, verbose_name='Chave do Logo no Storage'),
        ),
    ]