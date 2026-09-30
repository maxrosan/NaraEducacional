"""Testes de Aluno: todos os endpoints de /api/alunos/.

Seções:
  * listagem    — paginação, abas por status, filtros, busca, escopo, custo de queries
  * detalhe     — escopo do GET de um aluno
  * permissões  — quem pode criar e editar
  * turma       — turma obrigatória, ativa, da mesma escola ao mover
  * duplicidade — mesmo nome + nascimento na mesma escola (sem constraint no banco)
  * validações  — nascimento, telefone, escola desativada
"""
from datetime import date, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext

from api.models import Aluno, Escola, Turma

from .base import CenarioMultiTenant

URL_LISTAR = '/api/alunos/'
URL_CRIAR = '/api/alunos/criar/'


def url_detalhe(aluno):
    return f'/api/alunos/{aluno.id}/'


def url_atualizar(aluno):
    return f'/api/alunos/{aluno.id}/atualizar/'


class AlunosTests(CenarioMultiTenant):
    """Cenário (base.py): aluno_a1 ('Ana A1', turma_a1/escola A1), aluno_a2
    ('Bia A2', turma_a2/A2) e aluno_b1 ('Caio B1', outra rede). Todos ativos,
    nascidos em 01/01/2020."""

    # --- helpers ----------------------------------------------------------

    def _listar(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_LISTAR, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _criar_alunos(self, qtd, turma=None, status_vinculo='ativo', prefixo='Aluno'):
        """Cria alunos direto no banco (massa de dados para a listagem)."""
        turma = turma or self.turma_a1
        return [
            Aluno.objects.create(
                nome_completo=f'{prefixo} {i:02d}', data_nascimento=date(2019, 1, 1) + timedelta(days=i),
                turma=turma, escola=turma.escola, instituicao=turma.instituicao,
                status_vinculo=status_vinculo,
            )
            for i in range(qtd)
        ]

    def _payload(self, **extra):
        dados = {
            'turma': str(self.turma_a1.id), 'nome_completo': 'Davi Novo',
            'data_nascimento': '2019-05-10',
        }
        dados.update(extra)
        return dados

    def _post_criar(self, usuario=None, **extra):
        self.entrar(usuario or self.admin_a)
        return self.client.post(URL_CRIAR, self._payload(**extra), format='json')

    def _patch(self, aluno, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(url_atualizar(aluno), dados, format='json')

    def _turma(self, nome, escola=None, **extra):
        escola = escola or self.a1
        return Turma.objects.create(nome=nome, escola=escola, instituicao=escola.instituicao, **extra)

    # =====================================================================
    # Listagem
    # =====================================================================

    def test_listagem_sem_page_continua_devolvendo_array(self):
        dados = self._listar(self.admin_a)
        self.assertIsInstance(dados, list)
        self.assertEqual({a['id'] for a in dados}, {str(self.aluno_a1.id), str(self.aluno_a2.id)})

    def test_listagem_pagina_de_10(self):
        self._criar_alunos(14)  # + aluno_a1 e aluno_a2 = 16 ativos na rede A
        p1 = self._listar(self.admin_a, page=1, status='ativo')
        self.assertEqual((p1['count'], p1['total_paginas'], len(p1['results'])), (16, 2, 10))

        p2 = self._listar(self.admin_a, page=2, status='ativo')
        self.assertEqual(len(p2['results']), 6)
        ids = {a['id'] for a in p1['results']} | {a['id'] for a in p2['results']}
        self.assertEqual(len(ids), 16, 'páginas não podem repetir nem pular alunos')

    def test_listagem_pagina_fora_do_intervalo_vai_para_a_ultima(self):
        dados = self._listar(self.admin_a, page=99)
        self.assertEqual((dados['pagina'], len(dados['results'])), (1, 2))

    def test_listagem_page_size_tem_teto(self):
        self.assertEqual(self._listar(self.admin_a, page=1, page_size=1000)['page_size'], 50)

    def test_listagem_abas_por_status_e_totais(self):
        self._criar_alunos(2, status_vinculo='inativo', prefixo='Inativo')
        self._criar_alunos(1, status_vinculo='transferido', prefixo='Transferido')
        esperado = {'ativo': 2, 'inativo': 2, 'transferido': 1}

        for status_vinculo, qtd in esperado.items():
            dados = self._listar(self.admin_a, page=1, status=status_vinculo)
            self.assertEqual(dados['count'], qtd, status_vinculo)
            self.assertTrue(all(a['status_vinculo'] == status_vinculo for a in dados['results']))
            # Totais iguais em todas as abas: não dependem do filtro de status.
            self.assertEqual(dados['totais'], esperado, status_vinculo)

    def test_listagem_varios_status_de_uma_vez(self):
        """A aba Inativos da tela pede inativo e transferido juntos."""
        self._criar_alunos(2, status_vinculo='inativo', prefixo='Inativo')
        self._criar_alunos(1, status_vinculo='transferido', prefixo='Transferido')
        dados = self._listar(self.admin_a, page=1, status='inativo,transferido')
        self.assertEqual(dados['count'], 3)
        self.assertTrue(all(a['status_vinculo'] != 'ativo' for a in dados['results']))

    def test_listagem_status_invalido_nao_filtra(self):
        self._criar_alunos(1, status_vinculo='inativo')
        self.assertEqual(self._listar(self.admin_a, page=1, status='all')['count'], 3)

    def test_listagem_filtro_por_escola(self):
        dados = self._listar(self.admin_a, page=1, escola=str(self.a2.id))
        self.assertEqual([a['id'] for a in dados['results']], [str(self.aluno_a2.id)])

    def test_listagem_filtro_por_turma_e_totais(self):
        self._criar_alunos(2, status_vinculo='inativo')  # na turma_a1
        dados = self._listar(self.admin_a, page=1, turma=str(self.turma_a1.id), status='ativo')
        self.assertEqual([a['id'] for a in dados['results']], [str(self.aluno_a1.id)])
        self.assertEqual(dados['totais'], {'ativo': 1, 'inativo': 2, 'transferido': 0})

    def test_listagem_busca_por_nome_sem_diferenciar_maiusculas(self):
        dados = self._listar(self.admin_a, page=1, busca='  ana ')
        self.assertEqual([a['id'] for a in dados['results']], [str(self.aluno_a1.id)])
        self.assertEqual(dados['totais']['ativo'], 1)

    def test_listagem_escola_ou_turma_fora_do_escopo_devolve_vazio(self):
        for params in ({'escola': str(self.b1.id)}, {'turma': str(self.turma_b1.id)}, {'turma': 'nao-e-uuid'}):
            dados = self._listar(self.admin_a, page=1, **params)
            self.assertEqual(dados['count'], 0, params)
            self.assertEqual(dados['totais'], {'ativo': 0, 'inativo': 0, 'transferido': 0}, params)

    def test_listagem_admin_nao_ve_alunos_de_outra_rede(self):
        ids = {a['id'] for a in self._listar(self.admin_a, page=1)['results']}
        self.assertNotIn(str(self.aluno_b1.id), ids)

    def test_listagem_coordenador_ve_so_a_propria_escola(self):
        ids = {a['id'] for a in self._listar(self.coord_a1, page=1)['results']}
        self.assertEqual(ids, {str(self.aluno_a1.id)})

    def test_listagem_traz_nomes_de_turma_e_escola(self):
        aluno = self._listar(self.admin_a, page=1, busca='Ana')['results'][0]
        self.assertEqual((aluno['turma_nome'], aluno['escola_nome']), ('Nível 3A', 'A1'))

    def test_listagem_numero_de_queries_nao_cresce_com_os_alunos(self):
        """Sem select_related, cada aluno a mais custaria 2 queries (turma e escola)."""
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_LISTAR, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        self._criar_alunos(4, turma=self._turma('Nível 4A'))
        self._criar_alunos(4, turma=self.turma_a2, prefixo='Outro')
        self.assertEqual(contar(), antes)

    # =====================================================================
    # Detalhe
    # =====================================================================

    def test_detalhe_da_propria_rede(self):
        self.entrar(self.admin_a)
        r = self.client.get(url_detalhe(self.aluno_a2))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['nome_completo'], 'Bia A2')

    def test_detalhe_fora_do_escopo_e_404(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(url_detalhe(self.aluno_b1)).status_code, 404)
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(url_detalhe(self.aluno_a2)).status_code, 404)

    # =====================================================================
    # Permissões
    # =====================================================================

    def test_admin_cria_aluno_na_escola_da_turma(self):
        r = self._post_criar()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['escola'], r.json()['instituicao']), (str(self.a1.id), str(self.rede_a.id)))

    def test_coordenador_cria_na_propria_escola(self):
        self.assertEqual(self._post_criar(self.coord_a1).status_code, 201)

    def test_coordenador_nao_cria_em_turma_de_outra_escola(self):
        r = self._post_criar(self.coord_a1, turma=str(self.turma_a2.id))
        self.assertIn(r.status_code, (403, 404), r.content)
        self.assertFalse(Aluno.objects.filter(nome_completo='Davi Novo').exists())

    def test_professor_nao_cria_nem_edita(self):
        self.assertEqual(self._post_criar(self.prof_a1).status_code, 403)
        self.assertEqual(self._patch(self.aluno_a1, self.prof_a1, nome_responsavel='X').status_code, 403)

    def test_admin_nao_edita_aluno_de_outra_rede(self):
        self.assertEqual(self._patch(self.aluno_b1, nome_responsavel='X').status_code, 404)

    def test_edicao_nao_muda_a_escola_direto(self):
        r = self._patch(self.aluno_a1, escola=str(self.a2.id), nome_responsavel='Maria')
        self.assertEqual(r.status_code, 200, r.content)
        self.aluno_a1.refresh_from_db()
        self.assertEqual(self.aluno_a1.escola_id, self.a1.id)

    def test_inativar_transferir_e_reativar(self):
        for status_vinculo in ('inativo', 'transferido', 'ativo'):
            self.assertEqual(self._patch(self.aluno_a1, status_vinculo=status_vinculo).status_code, 200)
            self.aluno_a1.refresh_from_db()
            self.assertEqual(self.aluno_a1.status_vinculo, status_vinculo)

    # =====================================================================
    # Turma
    # =====================================================================

    def test_turma_obrigatoria(self):
        self.entrar(self.admin_a)
        payload = self._payload()
        del payload['turma']
        self.assertEqual(self.client.post(URL_CRIAR, payload, format='json').status_code, 400)

    def test_turma_de_outra_rede_e_404(self):
        self.assertEqual(self._post_criar(turma=str(self.turma_b1.id)).status_code, 404)

    def test_nao_cria_em_turma_desativada(self):
        turma = self._turma('Nível 9Z', ativa=False)
        r = self._post_criar(turma=str(turma.id))
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('turma', r.json())

    def test_mover_para_turma_da_mesma_escola(self):
        nova = self._turma('Nível 4A')
        r = self._patch(self.aluno_a1, turma=str(nova.id))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['turma_nome'], 'Nível 4A')

    def test_nao_move_para_turma_de_outra_escola(self):
        r = self._patch(self.aluno_a1, turma=str(self.turma_a2.id))
        self.assertEqual(r.status_code, 400, r.content)
        self.aluno_a1.refresh_from_db()
        self.assertEqual(self.aluno_a1.turma_id, self.turma_a1.id)

    def test_nao_move_para_turma_desativada(self):
        turma = self._turma('Nível 9Z', ativa=False)
        self.assertEqual(self._patch(self.aluno_a1, turma=str(turma.id)).status_code, 400)

    def test_aluno_em_turma_desativada_continua_editavel(self):
        """Desativar a turma não pode travar a edição dos alunos que já estão nela."""
        Turma.objects.filter(pk=self.turma_a1.pk).update(ativa=False)
        r = self._patch(self.aluno_a1, turma=str(self.turma_a1.id), nome_responsavel='Maria')
        self.assertEqual(r.status_code, 200, r.content)

    def test_mover_para_turma_fora_do_escopo_e_404(self):
        self.assertEqual(self._patch(self.aluno_a1, turma=str(self.turma_b1.id)).status_code, 404)

    # =====================================================================
    # Duplicidade (nome + nascimento na mesma escola)
    # =====================================================================

    def test_duplicado_na_mesma_escola(self):
        r = self._post_criar(nome_completo='ANA A1', data_nascimento='2020-01-01')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('nome_completo', r.json())

    def test_duplicado_com_acento_em_maiuscula(self):
        Aluno.objects.create(
            nome_completo='João Álvares', data_nascimento=date(2019, 3, 3), turma=self.turma_a1,
            escola=self.a1, instituicao=self.rede_a,
        )
        r = self._post_criar(nome_completo='JOÃO ÁLVARES', data_nascimento='2019-03-03')
        self.assertEqual(r.status_code, 400, r.content)

    def test_duplicado_em_outra_turma_da_mesma_escola(self):
        turma = self._turma('Nível 4A')
        r = self._post_criar(turma=str(turma.id), nome_completo='Ana A1', data_nascimento='2020-01-01')
        self.assertEqual(r.status_code, 400, r.content)

    def test_homonimo_com_outra_data_ou_em_outra_escola_pode(self):
        self.assertEqual(self._post_criar(nome_completo='Ana A1', data_nascimento='2020-02-02').status_code, 201)
        r = self._post_criar(turma=str(self.turma_a2.id), nome_completo='Ana A1', data_nascimento='2020-01-01')
        self.assertEqual(r.status_code, 201, r.content)

    def test_sem_data_de_nascimento_nao_bloqueia(self):
        self.assertEqual(self._post_criar(nome_completo='Ana A1', data_nascimento=None).status_code, 201)

    def test_duplicado_inativo_orienta_a_reativar(self):
        Aluno.objects.filter(pk=self.aluno_a1.pk).update(status_vinculo='transferido')
        r = self._post_criar(nome_completo='Ana A1', data_nascimento='2020-01-01')
        self.assertEqual(r.status_code, 400)
        self.assertIn('reative', r.json()['nome_completo'][0])

    def test_editar_para_dados_de_outro_aluno(self):
        outro = self._criar_alunos(1)[0]
        r = self._patch(outro, nome_completo='Ana A1', data_nascimento='2020-01-01')
        self.assertEqual(r.status_code, 400, r.content)

    def test_editar_mantendo_os_proprios_dados(self):
        r = self._patch(self.aluno_a1, nome_completo='Ana A1', data_nascimento='2020-01-01', nome_responsavel='Maria')
        self.assertEqual(r.status_code, 200, r.content)

    def test_duplicado_antigo_continua_editavel(self):
        """Sem constraint no banco, podem existir duplicatas de antes da regra."""
        antigo = Aluno.objects.create(
            nome_completo='Ana A1', data_nascimento=date(2020, 1, 1), turma=self.turma_a1,
            escola=self.a1, instituicao=self.rede_a,
        )
        r = self._patch(antigo, nome_completo='Ana A1', nome_responsavel='Maria')
        self.assertEqual(r.status_code, 200, r.content)

    # =====================================================================
    # Validações
    # =====================================================================

    def test_nascimento_no_futuro(self):
        amanha = (date.today() + timedelta(days=2)).isoformat()
        self.assertEqual(self._post_criar(data_nascimento=amanha).status_code, 400)

    def test_telefone_do_responsavel(self):
        self.assertEqual(self._post_criar(telefone_responsavel='1234').status_code, 400)
        r = self._post_criar(telefone_responsavel='(84) 99999-8888')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['telefone_responsavel'], '(84) 99999-8888')

    def test_nome_em_branco(self):
        self.assertEqual(self._post_criar(nome_completo='   ').status_code, 400)

    def test_status_invalido(self):
        self.assertEqual(self._patch(self.aluno_a1, status_vinculo='excluido').status_code, 400)

    def test_nao_cria_em_escola_desativada(self):
        Escola.objects.filter(pk=self.a1.pk).update(ativa=False)
        r = self._post_criar()
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(Aluno.objects.filter(nome_completo='Davi Novo').exists())