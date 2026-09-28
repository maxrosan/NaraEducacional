"""Dados de desenvolvimento para o Nara multi-tenant.

Uso (a partir da pasta do projeto):
    docker exec -i multi-nara-backend python manage.py shell < seed_dev.py

Idempotente: pode rodar várias vezes. Registros são buscados pelo nome/e-mail
e só criados se não existirem; as senhas são redefinidas a cada execução.

Cria duas redes para testar o isolamento entre tenants:
    Rede Alfa: Escola Alfa 1 (coordenador + professor + turma + alunos)
    Rede Beta: Escola Beta 1 (coordenador + professor + turma + alunos)
"""
import os
import sys
from datetime import date

from django.conf import settings
from django.db import transaction

from api.models import Aluno, Escola, Instituicao, Turma, Usuario, UsuarioTurma

SENHA = 'Nara@dev2026'

if not settings.DEBUG and os.getenv('SEED_FORCE') != '1':
    print('ABORTADO: DEBUG=False. Isto parece um ambiente real.')
    print('Se tiver certeza de que é desenvolvimento, rode com -e SEED_FORCE=1.')
    sys.exit(1)


def usuario(email, nome, nivel, instituicao=None, escola=None, superuser=False):
    u, criado = Usuario.objects.get_or_create(
        email=email,
        defaults={
            'nome': nome, 'nivel': nivel, 'instituicao': instituicao, 'escola': escola,
            'is_superuser': superuser, 'is_staff': superuser,
        },
    )
    u.set_password(SENHA)
    u.is_active = True
    u.save()
    print(f"  {'+' if criado else '='} {nivel:<20} {email}")
    return u


def rede(nome_rede, nome_escola, nome_turma, alunos, prefixo):
    inst, _ = Instituicao.objects.get_or_create(nome=nome_rede)
    esc, _ = Escola.objects.get_or_create(nome=nome_escola, instituicao=inst)
    turma, _ = Turma.objects.get_or_create(
        nome=nome_turma, escola=esc, instituicao=inst,
        defaults={'turno': 'manha', 'ano_letivo': str(date.today().year)},
    )
    print(f'\n{nome_rede} / {nome_escola} / {nome_turma}')

    usuario(f'admin.{prefixo}@nara.dev', f'Admin {nome_rede}', 'admin', inst)
    usuario(f'coord.{prefixo}@nara.dev', f'Coordenação {nome_escola}', 'coordenador', inst, esc)
    prof = usuario(f'prof.{prefixo}@nara.dev', f'Professora {nome_escola}', 'professor_infantil', inst, esc)
    UsuarioTurma.objects.get_or_create(usuario=prof, turma=turma)

    for nome in alunos:
        Aluno.objects.get_or_create(
            nome_completo=nome, turma=turma,
            defaults={'data_nascimento': date(2021, 3, 15), 'escola': esc, 'instituicao': inst},
        )
    print(f'  alunos: {", ".join(alunos)}')


with transaction.atomic():
    print('Global')
    usuario('super@nara.dev', 'Super Admin', 'superadmin', superuser=True)
    rede('Rede Alfa', 'Escola Alfa 1', 'Nível 3A', ['Ana Alfa', 'Bruno Alfa'], 'alfa')
    rede('Rede Beta', 'Escola Beta 1', 'Nível 3A', ['Carla Beta', 'Diego Beta'], 'beta')

print(f'\nSenha de todos os usuários: {SENHA}')