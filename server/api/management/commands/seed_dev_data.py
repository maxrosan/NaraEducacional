"""
Management command para popular banco de dados com dados de desenvolvimento

Uso:
    python manage.py seed_dev_data
    python manage.py seed_dev_data --flush  # Limpa dados antes de popular
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Instituicao, Usuario, Turma, UsuarioTurma, HabilidadeBNCC


class Command(BaseCommand):
    help = 'Popula o banco de dados com dados iniciais para desenvolvimento'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Limpa dados existentes antes de popular',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write(self.style.WARNING('Limpando dados existentes...'))
            self._flush_data()

        self.stdout.write(self.style.MIGRATE_HEADING('Iniciando seed de dados de desenvolvimento...'))

        with transaction.atomic():
            # 1. Criar Instituições
            instituicoes = self._create_instituicoes()
            self.stdout.write(self.style.SUCCESS(f'✓ {len(instituicoes)} instituições criadas'))

            # 2. Criar Usuários
            usuarios = self._create_usuarios(instituicoes)
            self.stdout.write(self.style.SUCCESS(f'✓ {len(usuarios)} usuários criados'))

            # 3. Criar Turmas
            turmas = self._create_turmas(instituicoes)
            self.stdout.write(self.style.SUCCESS(f'✓ {len(turmas)} turmas criadas'))

            # 4. Vincular Professores às Turmas
            vinculos = self._create_vinculos(usuarios, turmas)
            self.stdout.write(self.style.SUCCESS(f'✓ {len(vinculos)} vínculos professor-turma criados'))

            # 5. Criar algumas Habilidades BNCC de exemplo
            habilidades = self._create_habilidades_bncc()
            self.stdout.write(self.style.SUCCESS(f'✓ {len(habilidades)} habilidades BNCC criadas'))

        self.stdout.write('\n' + self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('SEED CONCLUÍDO COM SUCESSO! 🎉'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self._print_credentials()

    def _flush_data(self):
        """Remove dados existentes (exceto superusers)"""
        UsuarioTurma.objects.all().delete()
        Turma.objects.all().delete()
        Usuario.objects.filter(is_superuser=False).delete()
        Instituicao.objects.all().delete()
        HabilidadeBNCC.objects.all().delete()

    def _create_instituicoes(self):
        """Cria instituições de exemplo"""
        instituicoes = []

        escola_demo, _ = Instituicao.objects.update_or_create(
            cnpj='12.345.678/0001-90',
            defaults={
                'nome': 'Escola Municipal Demo NARA',
                'email_institucional': 'contato@demo.nara.dev',
                'endereco': 'Rua das Flores, 123',
                'cidade': 'São Paulo',
                'estado': 'SP',
                'telefone': '(11) 3456-7890',
                'ativa': True
            }
        )
        instituicoes.append(escola_demo)

        escola_teste, _ = Instituicao.objects.update_or_create(
            cnpj='98.765.432/0001-10',
            defaults={
                'nome': 'Centro Educacional Teste',
                'email_institucional': 'contato@teste.nara.dev',
                'endereco': 'Av. Principal, 456',
                'cidade': 'Rio de Janeiro',
                'estado': 'RJ',
                'telefone': '(21) 9876-5432',
                'ativa': True
            }
        )
        instituicoes.append(escola_teste)

        return instituicoes

    def _create_usuarios(self, instituicoes):
        """Cria usuários de exemplo para cada perfil"""
        usuarios = []
        escola_demo = instituicoes[0]

        def criar_ou_atualizar_usuario(email, senha, nome, perfil, instituicao, tipo_especialista=None, is_admin=False):
            usuario, criado = Usuario.objects.get_or_create(
                email=email,
                defaults={
                    'nome': nome,
                    'perfil': perfil,
                    'instituicao': instituicao,
                    'tipo_especialista': tipo_especialista,
                    'ativo': True,
                    'is_staff': is_admin,
                    'is_superuser': is_admin,
                }
            )

            if not criado:
                usuario.nome = nome
                usuario.perfil = perfil
                usuario.instituicao = instituicao
                usuario.tipo_especialista = tipo_especialista
                usuario.ativo = True
                usuario.is_staff = is_admin
                usuario.is_superuser = is_admin

            usuario.set_password(senha)
            usuario.save()
            return usuario

        # 1. ADMIN
        usuarios.append(
            criar_ou_atualizar_usuario(
                email='admin@nara.dev',
                senha='admin123',
                nome='Administrador do Sistema',
                perfil='admin',
                instituicao=escola_demo,
                is_admin=True
            )
        )

        # 2. COORDENADOR PEDAGÓGICO
        usuarios.append(
            criar_ou_atualizar_usuario(
                email='coordenador@nara.dev',
                senha='coord123',
                nome='Maria Silva Coordenadora',
                perfil='coordenador',
                instituicao=escola_demo
            )
        )

        # 3. PROFESSORES
        usuarios.append(
            criar_ou_atualizar_usuario(
                email='professor1@nara.dev',
                senha='prof123',
                nome='Ana Paula Santos',
                perfil='professor',
                instituicao=escola_demo
            )
        )

        usuarios.append(
            criar_ou_atualizar_usuario(
                email='professor2@nara.dev',
                senha='prof123',
                nome='Carlos Eduardo Oliveira',
                perfil='professor',
                instituicao=escola_demo
            )
        )

        usuarios.append(
            criar_ou_atualizar_usuario(
                email='professor3@nara.dev',
                senha='prof123',
                nome='Juliana Ferreira Costa',
                perfil='professor',
                instituicao=escola_demo
            )
        )

        # 4. ESPECIALISTAS
        usuarios.append(
            criar_ou_atualizar_usuario(
                email='psicologo@nara.dev',
                senha='esp123',
                nome='Dr. Roberto Mendes',
                perfil='especialista',
                tipo_especialista='psicologo',
                instituicao=escola_demo
            )
        )

        usuarios.append(
            criar_ou_atualizar_usuario(
                email='psicopedagoga@nara.dev',
                senha='esp123',
                nome='Dra. Fernanda Lima',
                perfil='especialista',
                tipo_especialista='psicopedagogo',
                instituicao=escola_demo
            )
        )

        usuarios.append(
            criar_ou_atualizar_usuario(
                email='fonoaudiologo@nara.dev',
                senha='esp123',
                nome='Dra. Patrícia Alves',
                perfil='especialista',
                tipo_especialista='fonoaudiologo',
                instituicao=escola_demo
            )
        )

        return usuarios

    def _create_turmas(self, instituicoes):
        """Cria turmas de exemplo"""
        turmas = []
        escola_demo = instituicoes[0]

        # Educação Infantil
        turmas.append(Turma.objects.update_or_create(
            nome='Infantil 4 - Turma A',
            instituicao_id=escola_demo.id,
            defaults={
                'faixa_etaria': 'Infantil 4',
                'turno': 'matutino',
                'ano_letivo': '2025',
                'ativa': True
            }
        )[0])

        turmas.append(Turma.objects.update_or_create(
            nome='Infantil 5 - Turma A',
            instituicao_id=escola_demo.id,
            defaults={
                'faixa_etaria': 'Infantil 5',
                'turno': 'vespertino',
                'ano_letivo': '2025',
                'ativa': True
            }
        )[0])

        # 1º Ano Fundamental
        turmas.append(Turma.objects.update_or_create(
            nome='1º Ano A',
            instituicao_id=escola_demo.id,
            defaults={
                'faixa_etaria': '1º Ano',
                'turno': 'matutino',
                'ano_letivo': '2025',
                'ativa': True
            }
        )[0])

        turmas.append(Turma.objects.update_or_create(
            nome='1º Ano B',
            instituicao_id=escola_demo.id,
            defaults={
                'faixa_etaria': '1º Ano',
                'turno': 'vespertino',
                'ano_letivo': '2025',
                'ativa': True
            }
        )[0])

        # 2º Ano Fundamental
        turmas.append(Turma.objects.update_or_create(
            nome='2º Ano A',
            instituicao_id=escola_demo.id,
            defaults={
                'faixa_etaria': '2º Ano',
                'turno': 'matutino',
                'ano_letivo': '2025',
                'ativa': True
            }
        )[0])

        return turmas

    def _create_vinculos(self, usuarios, turmas):
        """Vincula professores às turmas"""
        vinculos = []

        # Buscar professores
        professores = [u for u in usuarios if u.perfil in ['professor', 'professor_especialista']]

        # Ana Paula → Infantil 4 - Turma A e 1º Ano A
        if len(professores) > 0 and len(turmas) > 0:
            vinculos.append(UsuarioTurma.objects.create(
                usuario=professores[0],
                turma=turmas[0]  # Infantil 4 - Turma A
            ))
            vinculos.append(UsuarioTurma.objects.create(
                usuario=professores[0],
                turma=turmas[2]  # 1º Ano A
            ))

        # Carlos Eduardo → Infantil 5 - Turma A e 1º Ano B
        if len(professores) > 1 and len(turmas) > 1:
            vinculos.append(UsuarioTurma.objects.create(
                usuario=professores[1],
                turma=turmas[1]  # Infantil 5 - Turma A
            ))
            vinculos.append(UsuarioTurma.objects.create(
                usuario=professores[1],
                turma=turmas[3]  # 1º Ano B
            ))

        # Juliana Ferreira → 2º Ano A
        if len(professores) > 2 and len(turmas) > 4:
            vinculos.append(UsuarioTurma.objects.create(
                usuario=professores[2],
                turma=turmas[4]  # 2º Ano A
            ))

        return vinculos

    def _create_habilidades_bncc(self):
        """Cria habilidades BNCC de exemplo"""
        habilidades = []

        habilidades_data = [
            {
                'codigo': 'EF01LP01',
                'descricao': 'Reconhecer que textos são lidos e escritos da esquerda para a direita e de cima para baixo da página.',
                'componente_curricular': 'Língua Portuguesa',
                'ano_serie': '1º ano',
                'campo_atuacao': 'Todos os campos de atuação'
            },
            {
                'codigo': 'EF01LP02',
                'descricao': 'Escrever, espontaneamente ou por ditado, palavras e frases de forma alfabética – usando letras/grafemas que representem fonemas.',
                'componente_curricular': 'Língua Portuguesa',
                'ano_serie': '1º ano',
                'campo_atuacao': 'Todos os campos de atuação'
            },
            {
                'codigo': 'EF15LP09',
                'descricao': 'Expressar-se em situações de intercâmbio oral com clareza, preocupando-se em ser compreendido pelo interlocutor e usando a palavra com tom de voz audível, boa articulação e ritmo adequado.',
                'componente_curricular': 'Língua Portuguesa',
                'ano_serie': '1º ao 5º ano',
                'campo_atuacao': 'Todos os campos de atuação'
            },
            {
                'codigo': 'EF15LP10',
                'descricao': 'Escutar, com atenção, falas de professores e colegas, formulando perguntas pertinentes ao tema e solicitando esclarecimentos sempre que necessário.',
                'componente_curricular': 'Língua Portuguesa',
                'ano_serie': '1º ao 5º ano',
                'campo_atuacao': 'Todos os campos de atuação'
            },
            {
                'codigo': 'EI03CG02',
                'descricao': 'Demonstrar controle e adequação do uso de seu corpo em brincadeiras e jogos, escuta e reconto de histórias, atividades artísticas, entre outras possibilidades.',
                'componente_curricular': 'Educação Infantil',
                'ano_serie': 'Infantil 4 e 5 anos',
                'campo_atuacao': 'Corpo, gestos e movimentos'
            },
            {
                'codigo': 'EI03EO06',
                'descricao': 'Manifestar interesse e respeito por diferentes culturas e modos de vida.',
                'componente_curricular': 'Educação Infantil',
                'ano_serie': 'Infantil 4 e 5 anos',
                'campo_atuacao': 'O eu, o outro e o nós'
            },
        ]

        for data in habilidades_data:
            hab, _ = HabilidadeBNCC.objects.update_or_create(
                codigo=data['codigo'],
                defaults=data
            )
            habilidades.append(hab)

        return habilidades

    def _print_credentials(self):
        """Imprime credenciais de acesso"""
        self.stdout.write('\n' + self.style.MIGRATE_LABEL('CREDENCIAIS DE ACESSO:'))
        self.stdout.write(self.style.MIGRATE_LABEL('='*70))

        credenciais = [
            ('ADMIN', 'admin@nara.dev', 'admin123', 'Acesso total ao sistema'),
            ('COORDENADOR', 'coordenador@nara.dev', 'coord123', 'Dashboard coordenação, relatórios gerais'),
            ('PROFESSOR 1', 'professor1@nara.dev', 'prof123', 'Ana Paula - Infantil 4-A e 1º Ano A'),
            ('PROFESSOR 2', 'professor2@nara.dev', 'prof123', 'Carlos Eduardo - Infantil 5-A e 1º Ano B'),
            ('PROFESSOR 3', 'professor3@nara.dev', 'prof123', 'Juliana Ferreira - 2º Ano A'),
            ('PSICÓLOGO', 'psicologo@nara.dev', 'esp123', 'Dr. Roberto Mendes'),
            ('PSICOPEDAGOGA', 'psicopedagoga@nara.dev', 'esp123', 'Dra. Fernanda Lima'),
            ('FONOAUDIÓLOGO', 'fonoaudiologo@nara.dev', 'esp123', 'Dra. Patrícia Alves'),
        ]

        for perfil, email, senha, descricao in credenciais:
            self.stdout.write(f'\n{self.style.SUCCESS("●")} {self.style.WARNING(perfil.ljust(15))}')
            self.stdout.write(f'  Email:    {self.style.HTTP_INFO(email)}')
            self.stdout.write(f'  Senha:    {self.style.HTTP_INFO(senha)}')
            self.stdout.write(f'  Detalhes: {descricao}')

        self.stdout.write('\n' + self.style.MIGRATE_LABEL('='*70))
        self.stdout.write(self.style.WARNING('\n⚠️  ATENÇÃO: Estas credenciais são APENAS para desenvolvimento!'))
        self.stdout.write(self.style.WARNING('   NUNCA use estas senhas em produção.\n'))
