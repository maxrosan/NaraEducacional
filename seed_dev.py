"""Dados de desenvolvimento para o Nara multi-tenant (versão ampliada).

Uso (a partir da pasta do projeto, no host):
    docker exec -i multi-nara-backend python manage.py shell < seed_dev.py

Idempotente: pode rodar várias vezes. Tudo é buscado por chave natural
(nome, e-mail, escola+nome...) e criado/atualizado. Nomes de alunos e de
funcionários são gerados com random "semeado", então saem SEMPRE iguais.
As senhas são redefinidas a cada execução.

Compatível com o seed antigo: Rede Alfa/Beta, Escola Alfa 1/Beta 1, Nível 3A e
os e-mails admin.alfa, coord.alfa, prof.alfa (idem beta) continuam existindo.

Estrutura criada
----------------
Global .......... superadmin, suporte, vendedor
Rede Alfa (RN) .. bimestral  | Alfa 1 (matriz, EI+EF) + Alfa 2 (filial, EI)
Rede Beta (PE) .. trimestral | Beta 1 (matriz, EI) + Beta 2 (filial, EF) + Beta 3 (filial INATIVA)
Rede Gama (CE) .. bimestral  | Gama Centro, Gama Norte, Gama Sul (professores gerados por turma)
Rede Delta (PB) . INSTITUIÇÃO INATIVA (para testar bloqueio)

Casos de borda propositais (para enxergar as regras de negócio)
---------------------------------------------------------------
* prof.alfa ................ professora com 2 turmas em turnos diferentes
* Nível 5A (Alfa 1) ........ turma SEM professor vinculado
* prof.alfa1.inativa ....... usuário inativo (is_active=False)
* aee.* .................... professor_especialista vinculado a turmas de etapas diferentes
* psicoped.alfa / fono.beta  Especialista da REDE (escola=None no cadastro)
* prof.semescola.gama ...... professor sem escola -> escopo 'nenhum' (não deve ver nada)
* admin2.gama .............. dois admins na mesma rede
* coord2.* ................. dois coordenadores na mesma escola
* "Nível 3A" ............... mesmo nome de turma em várias escolas/redes
* Nível 3A do ano anterior . turma inativa com alunos inativos (Alfa 1)
* Música (Alfa 1) .......... disciplina inativa
* Alunos transferidos/inativos nas turmas maiores; alguns com observações (AEE)
"""
import os
import random
import sys
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from api.models import (
    Aluno, Disciplina, Escola, Especialista, Instituicao, PeriodoAvaliativo,
    Projeto, Turma, Usuario, UsuarioDisciplina, UsuarioTurma,
)

SENHA = 'Nara@dev2026'
DOMINIO = 'nara.dev'
ANO = date.today().year

if not settings.DEBUG and os.getenv('SEED_FORCE') != '1':
    print('ABORTADO: DEBUG=False. Isto parece um ambiente real.')
    print('Se tiver certeza de que é desenvolvimento, rode com -e SEED_FORCE=1.')
    sys.exit(1)


# ---------------------------------------------------------------------------
# Pools de nomes (determinísticos via random.Random(semente))
# ---------------------------------------------------------------------------
NOMES_F = ['Alice', 'Helena', 'Laura', 'Manuela', 'Valentina', 'Sophia', 'Isabella',
           'Heloísa', 'Luiza', 'Júlia', 'Lorena', 'Lívia', 'Maria Clara', 'Cecília',
           'Eloá', 'Giovanna', 'Maria Eduarda', 'Mariana', 'Lara', 'Beatriz',
           'Antonella', 'Maria Júlia', 'Isadora', 'Ana Clara', 'Melissa', 'Esther',
           'Lavínia', 'Maitê', 'Aurora', 'Liz']
NOMES_M = ['Miguel', 'Arthur', 'Gael', 'Théo', 'Heitor', 'Ravi', 'Davi', 'Bernardo',
           'Noah', 'Gabriel', 'Samuel', 'Pedro', 'Isaac', 'Benício', 'Benjamin',
           'Matheus', 'Lucas', 'Joaquim', 'Nicolas', 'Lorenzo', 'Henrique',
           'João Miguel', 'Rafael', 'Enzo', 'Guilherme', 'Bento', 'Emanuel', 'Levi',
           'Caio', 'Otávio']
ADULTOS_F = ['Ana Paula', 'Fernanda', 'Patrícia', 'Juliana', 'Aline', 'Camila', 'Renata',
             'Simone', 'Priscila', 'Vanessa', 'Adriana', 'Luciana', 'Tatiane', 'Kátia',
             'Cristiane', 'Michele', 'Daniela', 'Roberta', 'Jéssica', 'Larissa']
ADULTOS_M = ['Carlos', 'Marcelo', 'Rodrigo', 'André', 'Fábio', 'Leandro', 'Ricardo',
             'Eduardo', 'Alexandre', 'Thiago', 'Rogério', 'Sérgio', 'Diego', 'Paulo']
SOBRENOMES = ['Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Alves',
              'Pereira', 'Lima', 'Gomes', 'Costa', 'Ribeiro', 'Martins', 'Carvalho',
              'Almeida', 'Lopes', 'Soares', 'Fernandes', 'Vieira', 'Barbosa', 'Rocha',
              'Dias', 'Nascimento', 'Andrade', 'Moreira', 'Nunes', 'Marques', 'Machado',
              'Mendes', 'Freitas', 'Cardoso', 'Ramos', 'Gonçalves', 'Santana', 'Teixeira',
              'Medeiros', 'Dantas', 'Cavalcanti', 'Bezerra', 'Araújo']
OBSERVACOES = [
    'Laudo de TEA. Acompanhamento com professora do AEE.',
    'Em avaliação fonoaudiológica (trocas na fala).',
    'Alergia a lactose. Lanche diferenciado.',
    'TDAH em investigação. Família orientada a procurar neuropediatra.',
    'Baixa visão: sentar próximo ao quadro.',
]
PROJETOS = [
    ('Horta na Escola', 'Cultivo de hortaliças e observação do ciclo das plantas.'),
    ('Leitura em Família', 'Sacola literária semanal levada para casa.'),
    ('Brincadeiras de Antigamente', 'Resgate de brincadeiras com os avós.'),
    ('Reciclar é Legal', 'Separação de resíduos e brinquedos com sucata.'),
    ('Cultura Nordestina', 'Cordel, xilogravura e ritmos regionais.'),
    ('Pequenos Cientistas', 'Experimentos simples e registro de hipóteses.'),
]
PERIODOS = {  # (mês, dia) de início e fim de cada período
    'bimestral': [((2, 2), (4, 17)), ((4, 22), (7, 3)), ((7, 27), (9, 30)), ((10, 1), (12, 11))],
    'trimestral': [((2, 2), (5, 8)), ((5, 11), (8, 28)), ((8, 31), (12, 11))],
    'semestral': [((2, 2), (7, 3)), ((7, 27), (12, 11))],
}
NOME_PERIODO = {'bimestral': 'Bimestre', 'trimestral': 'Trimestre', 'semestral': 'Semestre'}

DISC_EF = ['Língua Portuguesa', 'Matemática', 'Ciências', 'História', 'Geografia',
           'Arte', 'Educação Física', 'Língua Inglesa']
DISC_EI = ['Música', 'Educação Física', 'Língua Inglesa']
POLIVALENTE = ['Língua Portuguesa', 'Matemática', 'Ciências', 'História', 'Geografia']
AUTO = 'auto'  # gera um professor por turma + um de Educação Física para o EF


# ---------------------------------------------------------------------------
# Helpers de configuração
# ---------------------------------------------------------------------------
def slug(txt):
    return slugify(txt.replace('º', '').replace('Escola', '')).replace('-', '')


def T(nome, idade, turno='manha', alunos=None, ano=ANO, ativa=True):
    """Turma. idade = idade das crianças em 31/03 do ano letivo."""
    return dict(nome=nome, idade=idade, turno=turno, alunos=alunos, ano=ano, ativa=ativa,
                etapa='educacao_infantil' if idade <= 5 else 'ensino_fundamental')


def P(email, nivel, turmas=(), disciplinas=(), ativo=True, sem_escola=False):
    """Professor(a). turmas/disciplinas por nome (turmas do ano corrente)."""
    return dict(email=email, nivel=nivel, turmas=list(turmas), disciplinas=list(disciplinas),
                ativo=ativo, sem_escola=sem_escola)


def E(email, tipo, escola=None, base=None):
    """Especialista. escola=None -> atende a rede toda; `base` é a escola do
    USUÁRIO (sem ela o usuário cairia no escopo 'nenhum')."""
    return dict(email=email, tipo=tipo, escola=escola, base=base or escola)


# ---------------------------------------------------------------------------
# Configuração das redes
# ---------------------------------------------------------------------------
REDES = [
    dict(
        nome='Rede Alfa', cidade='Natal', uf='RN', ddd='84', periodo='bimestral', ativa=True,
        admins=['admin.alfa'],
        especialistas=[
            E('psicoped.alfa', 'psicopedagogo', escola=None, base='Escola Alfa 1'),
            E('fono.alfa2', 'fonoaudiologo', escola='Escola Alfa 2'),
        ],
        escolas=[
            dict(
                nome='Escola Alfa 1', tipo='matriz', ativa=True,
                coordenadores=['coord.alfa', 'coord2.alfa1'],
                disciplinas=DISC_EF, disciplinas_inativas=['Música'],
                turmas=[
                    T('Nível 2A', 2, 'integral'), T('Nível 3A', 3, 'manha'),
                    T('Nível 3B', 3, 'tarde'), T('Nível 4A', 4), T('Nível 5A', 5, 'tarde'),
                    T('1º Ano A', 6), T('2º Ano A', 7), T('3º Ano A', 8, 'tarde'),
                    T('Nível 3A', 3, ano=ANO - 1, ativa=False, alunos=5),
                ],
                professores=[
                    P('prof.alfa', 'professor_infantil', ['Nível 3A', 'Nível 3B']),
                    P('prof.alfa1.nivel2a', 'professor_infantil', ['Nível 2A']),
                    P('prof.alfa1.nivel4a', 'professor_infantil', ['Nível 4A']),
                    P('prof.alfa1.inativa', 'professor_infantil', ['Nível 4A'], ativo=False),
                    P('prof.alfa1.1ano', 'professor_fundamental', ['1º Ano A'],
                      ['Língua Portuguesa', 'Matemática']),
                    P('prof.alfa1.fund', 'professor_fundamental', ['2º Ano A', '3º Ano A'], POLIVALENTE),
                    P('prof.alfa1.edfisica', 'professor_fundamental',
                      ['1º Ano A', '2º Ano A', '3º Ano A'], ['Educação Física']),
                    P('prof.alfa1.ingles', 'professor_fundamental',
                      ['1º Ano A', '2º Ano A', '3º Ano A'], ['Língua Inglesa', 'Arte']),
                    P('aee.alfa1', 'professor_especialista', ['Nível 4A', '1º Ano A']),
                    # Nível 5A fica sem professor de propósito.
                ],
            ),
            dict(
                nome='Escola Alfa 2', tipo='filial', ativa=True,
                coordenadores=['coord.alfa2'], disciplinas=DISC_EI,
                turmas=[T('Nível 1A', 1, 'integral'), T('Nível 2A', 2, 'integral'), T('Nível 3A', 3)],
                professores=[
                    P('prof.alfa2.bercario', 'professor_infantil', ['Nível 1A', 'Nível 2A']),
                    P('prof.alfa2.nivel3a', 'professor_infantil', ['Nível 3A']),
                ],
            ),
        ],
    ),
    dict(
        nome='Rede Beta', cidade='Recife', uf='PE', ddd='81', periodo='trimestral', ativa=True,
        admins=['admin.beta'],
        especialistas=[
            E('psicologa.beta', 'psicologo', escola='Escola Beta 1'),
            E('fono.beta', 'fonoaudiologo', escola=None, base='Escola Beta 2'),
        ],
        escolas=[
            dict(
                nome='Escola Beta 1', tipo='matriz', ativa=True,
                coordenadores=['coord.beta'], disciplinas=DISC_EI,
                turmas=[T('Nível 3A', 3), T('Nível 4A', 4, 'tarde'), T('Nível 5A', 5, 'integral')],
                professores=[
                    P('prof.beta', 'professor_infantil', ['Nível 3A']),
                    P('prof.beta1.b', 'professor_infantil', ['Nível 4A', 'Nível 5A']),
                ],
            ),
            dict(
                nome='Escola Beta 2', tipo='filial', ativa=True,
                coordenadores=['coord.beta2'], disciplinas=DISC_EF,
                turmas=[T('1º Ano A', 6), T('1º Ano B', 6, 'tarde'), T('2º Ano A', 7),
                        T('4º Ano A', 9), T('5º Ano A', 10, 'tarde', alunos=12)],
                professores=[
                    P('prof.beta2.alfab', 'professor_fundamental', ['1º Ano A', '1º Ano B'],
                      ['Língua Portuguesa', 'Matemática']),
                    P('prof.beta2.fund', 'professor_fundamental',
                      ['2º Ano A', '4º Ano A', '5º Ano A'], POLIVALENTE),
                    P('prof.beta2.arte', 'professor_fundamental',
                      ['1º Ano A', '1º Ano B', '2º Ano A', '4º Ano A', '5º Ano A'], ['Arte']),
                    P('prof.beta2.edfisica', 'professor_fundamental',
                      ['1º Ano A', '1º Ano B', '2º Ano A', '4º Ano A', '5º Ano A'], ['Educação Física']),
                    P('aee.beta2', 'professor_especialista', ['1º Ano B', '4º Ano A']),
                ],
            ),
            dict(
                nome='Escola Beta 3', tipo='filial', ativa=False,
                coordenadores=['coord.beta3'], disciplinas=[],
                turmas=[T('Nível 3A', 3, ativa=False, alunos=4)],
                professores=[],
            ),
        ],
    ),
    dict(
        nome='Rede Gama', cidade='Fortaleza', uf='CE', ddd='85', periodo='bimestral', ativa=True,
        admins=['admin.gama', 'admin2.gama'],
        especialistas=[
            E('to.gama', 'terapeuta_ocupacional', escola='Escola Gama Centro'),
            E('psicoped.gama', 'psicopedagogo', escola='Escola Gama Norte'),
        ],
        extras=[P('prof.semescola.gama', 'professor_infantil', sem_escola=True)],
        escolas=[
            dict(
                nome='Escola Gama Centro', tipo='matriz', ativa=True,
                coordenadores=['coord.gamacentro', 'coord2.gamacentro'], disciplinas=DISC_EF,
                turmas=[T('Nível 2A', 2, 'integral'), T('Nível 3A', 3), T('Nível 4A', 4),
                        T('Nível 5A', 5, 'tarde'), T('1º Ano A', 6), T('2º Ano A', 7),
                        T('3º Ano A', 8), T('4º Ano A', 9, 'tarde'), T('5º Ano A', 10, 'tarde')],
                professores=AUTO,
            ),
            dict(
                nome='Escola Gama Norte', tipo='filial', ativa=True,
                coordenadores=['coord.gamanorte'], disciplinas=DISC_EF,
                turmas=[T('Nível 3A', 3), T('Nível 4A', 4, 'tarde'),
                        T('1º Ano A', 6), T('2º Ano A', 7, 'tarde')],
                professores=AUTO,
            ),
            dict(
                nome='Escola Gama Sul', tipo='filial', ativa=True,
                coordenadores=['coord.gamasul'], disciplinas=DISC_EI,
                turmas=[T('Nível 1A', 1, 'integral'), T('Nível 2A', 2, 'integral'), T('Nível 3A', 3)],
                professores=AUTO,
            ),
        ],
    ),
    dict(
        nome='Rede Delta', cidade='João Pessoa', uf='PB', ddd='83', periodo='semestral', ativa=False,
        admins=['admin.delta'], especialistas=[],
        escolas=[
            dict(
                nome='Escola Delta 1', tipo='matriz', ativa=True,
                coordenadores=['coord.delta'], disciplinas=DISC_EF,
                turmas=[T('Nível 3A', 3), T('1º Ano A', 6)],
                professores=AUTO,
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------
CONTAS = []  # (rede, escola, nivel, email, ativo) para o resumo final


def email(local):
    return f'{local}@{DOMINIO}'


def nome_adulto(semente):
    rng = random.Random(semente)
    primeiro = rng.choice(ADULTOS_F if rng.random() < 0.75 else ADULTOS_M)
    return f'{primeiro} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}'


def telefone(rng, ddd):
    return f'({ddd}) 9{rng.randint(8000, 9999)}-{rng.randint(1000, 9999)}'


def usuario(local, nivel, inst=None, esc=None, esp=None, ativo=True, superuser=False, nome=None):
    u, _ = Usuario.objects.update_or_create(
        email=email(local),
        defaults=dict(
            nome=nome or nome_adulto(local), nivel=nivel, instituicao=inst, escola=esc,
            especialista=esp, is_active=ativo, is_superuser=superuser, is_staff=superuser,
        ),
    )
    u.set_password(SENHA)
    u.save(update_fields=['password'])
    CONTAS.append((inst.nome if inst else 'Global', esc.nome if esc else '—', nivel, u.email, ativo))
    return u


def professores_auto(esc_cfg):
    esc_slug = slug(esc_cfg['nome'])
    atuais = [t for t in esc_cfg['turmas'] if t['ativa'] and t['ano'] == ANO]
    profs = []
    for t in atuais:
        if t['etapa'] == 'educacao_infantil':
            profs.append(P(f"prof.{esc_slug}.{slug(t['nome'])}", 'professor_infantil', [t['nome']]))
        else:
            profs.append(P(f"prof.{esc_slug}.{slug(t['nome'])}", 'professor_fundamental',
                           [t['nome']], POLIVALENTE))
    ef = [t['nome'] for t in atuais if t['etapa'] == 'ensino_fundamental']
    if ef:
        profs.append(P(f'prof.{esc_slug}.edfisica', 'professor_fundamental', ef, ['Educação Física']))
    return profs


def criar_alunos(turma, t, esc, inst, usados, ddd):
    rng = random.Random(f"{esc.nome}|{t['nome']}|{t['ano']}")
    n = t['alunos'] or rng.randint(6, 10)
    inicio_janela = date(t['ano'] - t['idade'] - 1, 4, 1)
    for i in range(n):
        while True:
            genero = rng.choice('FM')
            primeiro = rng.choice(NOMES_F if genero == 'F' else NOMES_M)
            nome = f'{primeiro} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}'
            if nome not in usados:
                break
        usados.add(nome)

        if not t['ativa']:
            status = 'inativo'
        elif n >= 8 and i == n - 1:
            status = 'transferido'
        elif n >= 9 and i == n - 2:
            status = 'inativo'
        else:
            status = 'ativo'

        responsavel = f"{rng.choice(ADULTOS_F if rng.random() < 0.7 else ADULTOS_M)} {nome.split()[-1]}"
        Aluno.objects.update_or_create(
            nome_completo=nome, escola=esc,
            defaults=dict(
                turma=turma, instituicao=inst, genero=genero, status_vinculo=status,
                data_nascimento=inicio_janela + timedelta(days=rng.randint(0, 364)),
                nome_responsavel=responsavel, telefone_responsavel=telefone(rng, ddd),
                observacoes=rng.choice(OBSERVACOES) if i == 0 and rng.random() < 0.5 else None,
            ),
        )
    return n


def criar_escola(inst, rede, idx_rede, idx_esc, cfg):
    raiz = f'{10 + idx_rede}.{100 + idx_rede}.{200 + idx_rede}'
    esc, _ = Escola.objects.update_or_create(
        nome=cfg['nome'], instituicao=inst,
        defaults=dict(
            tipo_unidade=cfg['tipo'], ativa=cfg['ativa'], cidade=rede['cidade'], estado=rede['uf'],
            cnpj=f'{raiz}/{idx_esc + 1:04d}-{idx_esc:02d}',
            endereco=f'Rua da Educação, {100 + idx_esc * 50}', telefone=f"({rede['ddd']}) 3{idx_rede}{idx_esc}00-0000",
        ),
    )
    status = '' if cfg['ativa'] else '  [ESCOLA INATIVA]'
    print(f"\n  {cfg['nome']} ({cfg['tipo']}){status}")

    # Disciplinas
    disciplinas = {}
    for nome in cfg['disciplinas'] + cfg.get('disciplinas_inativas', []):
        d, _ = Disciplina.objects.update_or_create(
            escola=esc, nome=nome,
            defaults=dict(instituicao=inst, ativo=nome not in cfg.get('disciplinas_inativas', [])),
        )
        disciplinas[nome] = d

    # Turmas + alunos
    turmas, usados, total_alunos = {}, set(), 0
    for ordem, t in enumerate(cfg['turmas']):
        faixa = f"{t['idade']} ano" if t['idade'] == 1 else f"{t['idade']} anos"
        turma, _ = Turma.objects.update_or_create(
            nome=t['nome'], escola=esc, ano_letivo=str(t['ano']),
            defaults=dict(
                instituicao=inst, turno=t['turno'], ativa=t['ativa'], etapa=t['etapa'],
                faixa_etaria=faixa, ordem=ordem, idade_min=t['idade'], idade_max=t['idade'],
            ),
        )
        if t['ano'] == ANO:
            turmas[t['nome']] = turma
        total_alunos += criar_alunos(turma, t, esc, inst, usados, rede['ddd'])
    print(f"    turmas: {len(cfg['turmas'])} | alunos: {total_alunos} | disciplinas: {len(disciplinas)}")

    # Pessoas
    for local in cfg['coordenadores']:
        usuario(local, 'coordenador', inst, esc)

    profs = professores_auto(cfg) if cfg['professores'] == AUTO else cfg['professores']
    for p in profs:
        prof = usuario(p['email'], p['nivel'], inst, esc, ativo=p['ativo'])
        for nome_turma in p['turmas']:
            UsuarioTurma.objects.get_or_create(usuario=prof, turma=turmas[nome_turma])
        for nome_disc in p['disciplinas']:
            UsuarioDisciplina.objects.get_or_create(
                usuario=prof, disciplina=disciplinas[nome_disc],
                defaults=dict(escola=esc, instituicao=inst),
            )

    # Períodos avaliativos
    for numero, ((mi, di), (mf, df)) in enumerate(PERIODOS[rede['periodo']], start=1):
        PeriodoAvaliativo.objects.update_or_create(
            escola=esc, tipo_periodo=rede['periodo'], ano=ANO, numero=numero,
            defaults=dict(
                instituicao=inst, descricao=f"{numero}º {NOME_PERIODO[rede['periodo']]} {ANO}",
                data_inicio=date(ANO, mi, di), data_fim=date(ANO, mf, df),
            ),
        )

    # Projetos (um em andamento, um concluído e, às vezes, um cancelado)
    rng = random.Random(f"projetos|{esc.nome}")
    escolhidos = rng.sample(PROJETOS, 3 if rng.random() < 0.5 else 2)
    situacoes = [
        ('em_andamento', date(ANO, 8, 3), date(ANO, 11, 27)),
        ('concluido', date(ANO, 3, 2), date(ANO, 6, 26)),
        ('cancelado', date(ANO, 5, 4), None),
    ]
    for (nome, desc), (status_proj, ini, fim) in zip(escolhidos, situacoes):
        Projeto.objects.update_or_create(
            escola=esc, nome=nome,
            defaults=dict(instituicao=inst, descricao=desc, status=status_proj,
                          data_inicio=ini, data_fim=fim),
        )
    return esc


def criar_rede(idx, rede):
    raiz = f'{10 + idx}.{100 + idx}.{200 + idx}'
    inst, _ = Instituicao.objects.update_or_create(
        nome=rede['nome'],
        defaults=dict(
            ativa=rede['ativa'], cidade=rede['cidade'], estado=rede['uf'],
            cnpj=f'{raiz}/0001-{idx:02d}', email_institucional=f"contato.{slug(rede['nome'])}@{DOMINIO}",
            endereco='Av. Central, 1000', telefone=f"({rede['ddd']}) 3000-000{idx}",
        ),
    )
    status = '' if rede['ativa'] else '  [INSTITUIÇÃO INATIVA]'
    print(f"\n{'=' * 70}\n{rede['nome']} - {rede['cidade']}/{rede['uf']} - períodos {rede['periodo']}{status}")

    for local in rede['admins']:
        usuario(local, 'admin', inst)

    escolas = {cfg['nome']: criar_escola(inst, rede, idx, j, cfg) for j, cfg in enumerate(rede['escolas'])}

    for e in rede['especialistas']:
        esc_cadastro = escolas[e['escola']] if e['escola'] else None
        esp = (Especialista.objects.filter(instituicao=inst, escola=esc_cadastro,
                                           tipo_especialista=e['tipo']).first()
               or Especialista.objects.create(instituicao=inst, escola=esc_cadastro,
                                              tipo_especialista=e['tipo']))
        usuario(e['email'], 'especialista', inst, escolas[e['base']], esp=esp)

    for p in rede.get('extras', []):
        usuario(p['email'], p['nivel'], inst, esc=None, ativo=p['ativo'])  # sem escola


with transaction.atomic():
    print('Global')
    usuario('super', 'superadmin', superuser=True, nome='Super Admin')
    usuario('suporte', 'suporte', nome='Equipe de Suporte')
    usuario('vendedor', 'vendedor', nome='Equipe Comercial')
    for i, rede in enumerate(REDES, start=1):
        criar_rede(i, rede)


# ---------------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------------
print(f"\n{'=' * 70}\nRESUMO POR INSTITUIÇÃO")
for inst in Instituicao.objects.filter(nome__in=[r['nome'] for r in REDES]).order_by('nome'):
    print(f'  {inst.nome:<11} escolas={inst.escolas.count():<3} turmas={inst.turmas.count():<3} '
          f'alunos={inst.alunos.count():<4} usuarios={inst.usuarios.count():<3} '
          f'disciplinas={inst.disciplinas.count()}')

print(f"\n{'=' * 70}\nCONTAS (senha de todas: {SENHA})")
ordem_rede = {nome: i for i, nome in enumerate(dict.fromkeys(c[0] for c in CONTAS))}
CONTAS.sort(key=lambda c: (ordem_rede[c[0]], c[1] != '—', c[1]))  # sort estável: mantém a ordem de criação
rede_atual = escola_atual = None
for rede_nome, esc_nome, nivel, mail, ativo in CONTAS:
    if rede_nome != rede_atual:
        print(f'\n[{rede_nome}]')
        rede_atual, escola_atual = rede_nome, None
    if esc_nome != escola_atual:
        print(f"  {esc_nome if esc_nome != '—' else '(sem escola)'}")
        escola_atual = esc_nome
    print(f"    {nivel:<23} {mail}{'' if ativo else '  (INATIVO)'}")