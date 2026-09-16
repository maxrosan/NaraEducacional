# Generated manually for seeding default Campos de Experiência

from django.db import migrations
import uuid


STANDARD_CAMPOS = [
    ("O eu, o outro e o nós", "Users"),
    ("Escuta, fala, pensamento e imaginação", "MessageCircle"),
    ("Espaços, tempos, quantidades, relações e transformações", "Shapes"),
    ("Corpo, gestos e movimentos", "ToyBrick"),
    ("Traços, sons, cores e formas", "Palette"),
]


def seed_standard_campos(apps, schema_editor):
    CampoExperienciaCustomizado = apps.get_model("api", "CampoExperienciaCustomizado")
    for nome, icone in STANDARD_CAMPOS:
        exists = CampoExperienciaCustomizado.objects.filter(
            instituicao_id__isnull=True,
            nome=nome,
        ).exists()
        if exists:
            continue
        CampoExperienciaCustomizado.objects.create(
            id=uuid.uuid4(),
            instituicao_id=None,
            nome=nome,
            icone=icone,
            ativo=True,
        )


def unseed_standard_campos(apps, schema_editor):
    CampoExperienciaCustomizado = apps.get_model("api", "CampoExperienciaCustomizado")
    nomes = [nome for nome, _ in STANDARD_CAMPOS]
    CampoExperienciaCustomizado.objects.filter(
        instituicao_id__isnull=True,
        nome__in=nomes,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0015_rename_campos_expe_institu_idx_campos_expe_institu_629a7d_idx"),
    ]

    operations = [
        migrations.RunPython(seed_standard_campos, unseed_standard_campos),
    ]
