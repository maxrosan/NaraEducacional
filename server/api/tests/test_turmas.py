"""Testes de Turma: todos os endpoints de /api/turmas/.

Seções:
  * listagem   — paginação, abas ativas/inativas, filtros, escopo, custo de queries
  * detalhe    — escopo do GET de uma turma
  * permissões — quem pode criar e editar, e em qual escola
  * professores — gravados junto com a turma (transação), regras de vínculo
  * nome único — mesmo nome + escola + ano letivo (sem constraint no banco)
  * validações — idades, ano letivo, nome, escola desativada
  * vínculos   — endpoints avulsos de listar/vincular/desvincular professores
  * frequência de registro — tela Registros: listagem enxuta e alteração
    individual/em lote (substitui a tabela antiga `configuracoes_registro`)
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api.models import Escola, Turma, UsuarioTurma

from .base import CenarioMultiTenant

URL_LISTAR = '/api/turmas/'
URL_CRIAR = '/api/turmas/criar/'
URL_FREQUENCIAS = '/api/turmas/frequencia-registro/'
URL_ATUALIZAR_FREQUENCIA = '/api/turmas/frequencia-registro/atualizar/'


def url_detalhe(turma):
    return f'/api/turmas/{turma.id}/'


def url_atualizar(turma):
    return f'/api/turmas/{turma.id}/atualizar/'


def url_professores(turma):
    return f'/api/turmas/{turma.id}/professores/'


def url_vincular(turma):
    return f'/api/turmas/{turma.id}/professores/vincular/'


def url_desvincular(turma, usuario):
    return f'/api/turmas/{turma.id}/professores/{usuario.id}/desvincular/'


class TurmasTests(CenarioMultiTenant):
    """Cenário (base.py): turma_a1 ('Nível 3A', escola A1, com prof_a1),
    turma_a2 ('Nível 3B', A2) e turma_b1 ('Nível 3A', B1, outra rede)."""

    # --- helpers ----------------------------------------------------------

    def _listar(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(URL_LISTAR, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _criar_turmas(self, qtd, escola=None, ativa=True, prefixo='T'):
        """Cria turmas direto no banco (massa de dados para a listagem)."""
        escola = escola or self.a1
        return [
            Turma.objects.create(nome=f'{prefixo} {i:02d}', escola=escola,
                                 instituicao=escola.instituicao, ativa=ativa)
            for i in range(qtd)
        ]

    def _payload(self, **extra):
        dados = {
            'escola': str(self.a1.id), 'nome': 'Nível 4A', 'etapa': 'educacao_infantil',
            'turno': 'manha', 'ano_letivo': '2026',
        }
        dados.update(extra)
        return dados

    def _post_criar(self, usuario=None, **extra):
        self.entrar(usuario or self.admin_a)
        return self.client.post(URL_CRIAR, self._payload(**extra), format='json')

    def _patch(self, turma, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(url_atualizar(turma), dados, format='json')

    def _professores(self, turma_id):
        return set(UsuarioTurma.objects.filter(turma_id=turma_id).values_list('usuario_id', flat=True))

    # =====================================================================
    # Listagem
    # =====================================================================

    def test_listagem_sem_page_continua_devolvendo_array(self):
        dados = self._listar(self.admin_a)
        self.assertIsInstance(dados, list)
        self.assertEqual({t['id'] for t in dados}, {str(self.turma_a1.id), str(self.turma_a2.id)})

    def test_listagem_pagina_de_10(self):
        self._criar_turmas(14)  # + turma_a1 e turma_a2 = 16 ativas na rede A
        p1 = self._listar(self.admin_a, page=1, ativa='true')
        self.assertEqual((p1['count'], p1['total_paginas'], len(p1['results'])), (16, 2, 10))

        p2 = self._listar(self.admin_a, page=2, ativa='true')
        self.assertEqual(len(p2['results']), 6)
        ids = {t['id'] for t in p1['results']} | {t['id'] for t in p2['results']}
        self.assertEqual(len(ids), 16, 'páginas não podem repetir nem pular turmas')

    def test_listagem_pagina_fora_do_intervalo_vai_para_a_ultima(self):
        dados = self._listar(self.admin_a, page=99)
        self.assertEqual(dados['pagina'], 1)
        self.assertEqual(len(dados['results']), 2)

    def test_listagem_page_size_tem_teto(self):
        self.assertEqual(self._listar(self.admin_a, page=1, page_size=1000)['page_size'], 50)

    def test_listagem_filtro_ativa_e_totais_das_abas(self):
        self._criar_turmas(3, ativa=False, prefixo='Antiga')
        ativas = self._listar(self.admin_a, page=1, ativa='true')
        inativas = self._listar(self.admin_a, page=1, ativa='false')

        self.assertTrue(all(t['ativa'] for t in ativas['results']))
        self.assertTrue(all(not t['ativa'] for t in inativas['results']))
        self.assertEqual(inativas['count'], 3)
        # Totais iguais nas duas abas: não dependem do filtro `ativa`.
        self.assertEqual(ativas['totais'], {'ativas': 2, 'inativas': 3})
        self.assertEqual(inativas['totais'], {'ativas': 2, 'inativas': 3})

    def test_listagem_filtro_por_escola(self):
        dados = self._listar(self.admin_a, page=1, escola=str(self.a2.id))
        self.assertEqual([t['id'] for t in dados['results']], [str(self.turma_a2.id)])
        self.assertEqual(dados['totais'], {'ativas': 1, 'inativas': 0})

    def test_listagem_escola_de_outra_rede_ou_invalida_devolve_vazio(self):
        for escola in (str(self.b1.id), 'nao-e-uuid'):
            dados = self._listar(self.admin_a, page=1, escola=escola)
            self.assertEqual(dados['count'], 0, escola)
            self.assertEqual(dados['totais'], {'ativas': 0, 'inativas': 0}, escola)

    def test_listagem_admin_nao_ve_turmas_de_outra_rede(self):
        ids = {t['id'] for t in self._listar(self.admin_a, page=1)['results']}
        self.assertNotIn(str(self.turma_b1.id), ids)

    def test_listagem_coordenador_ve_so_a_propria_escola(self):
        ids = {t['id'] for t in self._listar(self.coord_a1, page=1)['results']}
        self.assertEqual(ids, {str(self.turma_a1.id)})

    def test_listagem_traz_professores_embutidos(self):
        turma = next(t for t in self._listar(self.admin_a, page=1)['results']
                     if t['id'] == str(self.turma_a1.id))
        self.assertEqual(turma['escola_nome'], 'A1')
        self.assertEqual(turma['professores'], [{
            'usuario': str(self.prof_a1.id),
            'usuario_nome': self.prof_a1.nome,
            'usuario_nivel': 'professor_infantil',
        }])

    def test_listagem_numero_de_queries_nao_cresce_com_as_turmas(self):
        """Sem select_related/prefetch, cada turma a mais custaria 2+ queries."""
        def contar():
            self.entrar(self.admin_a)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_LISTAR, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for turma in self._criar_turmas(8, escola=self.a2):
            UsuarioTurma.objects.create(usuario=self.coord_a2, turma=turma)
        self.assertEqual(contar(), antes)

    # =====================================================================
    # Detalhe
    # =====================================================================

    def test_detalhe_da_propria_rede(self):
        self.entrar(self.admin_a)
        r = self.client.get(url_detalhe(self.turma_a2))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['nome'], 'Nível 3B')

    def test_detalhe_fora_do_escopo_e_404(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(url_detalhe(self.turma_b1)).status_code, 404)
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(url_detalhe(self.turma_a2)).status_code, 404)

    # =====================================================================
    # Permissões de escrita
    # =====================================================================

    def test_professor_nao_cria_nem_edita(self):
        self.assertEqual(self._post_criar(self.prof_a1).status_code, 403)
        self.assertEqual(self._patch(self.turma_a1, self.prof_a1, turno='tarde').status_code, 403)

    def test_coordenador_cria_sempre_na_propria_escola(self):
        r = self._post_criar(self.coord_a1, escola=str(self.a2.id))  # body ignorado
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['escola'], str(self.a1.id))

    def test_admin_nao_cria_em_escola_de_outra_rede(self):
        r = self._post_criar(escola=str(self.b1.id))
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(Turma.objects.filter(nome='Nível 4A').exists())

    def test_admin_nao_edita_turma_de_outra_rede(self):
        self.assertEqual(self._patch(self.turma_b1, turno='tarde').status_code, 404)

    def test_edicao_nao_muda_a_escola_da_turma(self):
        r = self._patch(self.turma_a1, escola=str(self.a2.id), turno='tarde')
        self.assertEqual(r.status_code, 200, r.content)
        self.turma_a1.refresh_from_db()
        self.assertEqual(self.turma_a1.escola_id, self.a1.id)

    def test_desativar_e_reativar(self):
        self.assertEqual(self._patch(self.turma_a1, ativa=False).status_code, 200)
        self.turma_a1.refresh_from_db()
        self.assertFalse(self.turma_a1.ativa)
        self.assertEqual(self._patch(self.turma_a1, ativa=True).status_code, 200)
        self.turma_a1.refresh_from_db()
        self.assertTrue(self.turma_a1.ativa)

    # =====================================================================
    # Professores gravados junto com a turma
    # =====================================================================

    def test_cria_com_professores_numa_requisicao(self):
        r = self._post_criar(professores=[str(self.prof_a1.id), str(self.coord_a1.id)])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._professores(r.json()['id']), {self.prof_a1.id, self.coord_a1.id})

    def test_atualizar_sincroniza_professores(self):
        r = self._patch(self.turma_a1, professores=[str(self.coord_a1.id)])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._professores(self.turma_a1.id), {self.coord_a1.id})

    def test_atualizar_com_lista_vazia_remove_todos(self):
        r = self._patch(self.turma_a1, professores=[])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._professores(self.turma_a1.id), set())

    def test_atualizar_sem_professores_nao_mexe_nos_vinculos(self):
        r = self._patch(self.turma_a1, turno='tarde')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._professores(self.turma_a1.id), {self.prof_a1.id})

    def test_professor_de_outra_escola_barra_tudo(self):
        """Transação: se um professor é inválido, nem a turma é criada."""
        r = self._post_criar(professores=[str(self.prof_a1.id), str(self.prof_b1.id)])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('professores', r.json())
        self.assertFalse(Turma.objects.filter(nome='Nível 4A').exists())

    def test_edicao_com_professor_invalido_nao_grava_nada(self):
        r = self._patch(self.turma_a1, turno='tarde', professores=[str(self.prof_b1.id)])
        self.assertEqual(r.status_code, 400, r.content)
        self.turma_a1.refresh_from_db()
        self.assertEqual(self.turma_a1.turno, 'manha')
        self.assertEqual(self._professores(self.turma_a1.id), {self.prof_a1.id})

    def test_nao_vincula_usuario_inativo_novo(self):
        self.prof_a1.is_active = False
        self.prof_a1.save()
        self.assertEqual(self._post_criar(professores=[str(self.prof_a1.id)]).status_code, 400)

    def test_mantem_vinculo_existente_de_usuario_inativo(self):
        """Salvar a turma não pode desfazer um vínculo antigo sem o usuário pedir."""
        self.prof_a1.is_active = False
        self.prof_a1.save()
        r = self._patch(self.turma_a1, professores=[str(self.prof_a1.id)], turno='tarde')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._professores(self.turma_a1.id), {self.prof_a1.id})

    def test_nao_vincula_nivel_nao_permitido(self):
        especialista = self._usuario('esp.a1@x.com', 'especialista', self.rede_a, self.a1)
        self.assertEqual(self._post_criar(professores=[str(especialista.id)]).status_code, 400)

    # =====================================================================
    # Nome único por escola + ano letivo
    # =====================================================================

    def test_nome_duplicado_na_mesma_escola_e_ano(self):
        r = self._post_criar(nome='nível 3a', ano_letivo=self.turma_a1.ano_letivo)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('nome', r.json())

    def test_mesmo_nome_em_outro_ano_ou_outra_escola_pode(self):
        self.assertEqual(self._post_criar(nome='Nível 3A', ano_letivo='2030').status_code, 201)
        r = self._post_criar(nome='Nível 3A', escola=str(self.a2.id), ano_letivo=self.turma_a1.ano_letivo)
        self.assertEqual(r.status_code, 201, r.content)

    def test_duplicada_inativa_orienta_a_reativar(self):
        Turma.objects.filter(pk=self.turma_a1.pk).update(ativa=False)
        r = self._post_criar(nome='Nível 3A', ano_letivo=self.turma_a1.ano_letivo)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Inativas', r.json()['nome'][0])

    def test_renomear_para_nome_existente(self):
        outra = Turma.objects.create(nome='Nível 5A', escola=self.a1, instituicao=self.rede_a,
                                     ano_letivo=self.turma_a1.ano_letivo)
        self.assertEqual(self._patch(outra, nome='NÍVEL 3A').status_code, 400)

    def test_editar_mantendo_o_proprio_nome(self):
        r = self._patch(self.turma_a1, nome=self.turma_a1.nome, turno='tarde')
        self.assertEqual(r.status_code, 200, r.content)

    def test_duplicada_antiga_continua_editavel_sem_mudar_o_nome(self):
        """Sem constraint no banco, podem existir duplicatas de antes da regra:
        editar outros campos delas não pode ser bloqueado."""
        antiga = Turma.objects.create(nome='Nível 3A', escola=self.a1, instituicao=self.rede_a,
                                      ano_letivo=self.turma_a1.ano_letivo)
        r = self._patch(antiga, nome='Nível 3A', turno='tarde')
        self.assertEqual(r.status_code, 200, r.content)

    # =====================================================================
    # Validações
    # =====================================================================

    def test_idade_minima_maior_que_maxima(self):
        self.assertEqual(self._post_criar(idade_min=5, idade_max=3).status_code, 400)

    def test_patch_de_uma_idade_compara_com_a_salva(self):
        Turma.objects.filter(pk=self.turma_a1.pk).update(idade_min=4)
        self.assertEqual(self._patch(self.turma_a1, idade_max=3).status_code, 400)

    def test_idade_fora_da_faixa(self):
        self.assertEqual(self._post_criar(idade_max=40).status_code, 400)

    def test_ano_letivo_invalido(self):
        for ano in ('abc', '26', '1999'):
            self.assertEqual(self._post_criar(ano_letivo=ano).status_code, 400, ano)

    def test_nome_em_branco(self):
        self.assertEqual(self._post_criar(nome='   ').status_code, 400)

    def test_nao_cria_em_escola_desativada(self):
        Escola.objects.filter(pk=self.a2.pk).update(ativa=False)
        r = self._post_criar(escola=str(self.a2.id))
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(Turma.objects.filter(nome='Nível 4A').exists())

    # =====================================================================
    # Endpoints avulsos de vínculo
    # =====================================================================

    def test_listar_professores_da_turma(self):
        self.entrar(self.admin_a)
        r = self.client.get(url_professores(self.turma_a1))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([v['usuario'] for v in r.json()], [str(self.prof_a1.id)])

    def test_listar_professores_fora_do_escopo_e_404(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(url_professores(self.turma_b1)).status_code, 404)

    def test_vincular_novo_e_repetido(self):
        self.entrar(self.admin_a)
        r = self.client.post(url_vincular(self.turma_a1), {'usuario': str(self.coord_a1.id)}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post(url_vincular(self.turma_a1), {'usuario': str(self.coord_a1.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._professores(self.turma_a1.id), {self.prof_a1.id, self.coord_a1.id})

    def test_vincular_aplica_a_mesma_regra_de_nivel(self):
        especialista = self._usuario('esp2.a1@x.com', 'especialista', self.rede_a, self.a1)
        self.entrar(self.admin_a)
        r = self.client.post(url_vincular(self.turma_a1), {'usuario': str(especialista.id)}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_vincular_usuario_de_outra_escola(self):
        self.entrar(self.admin_a)
        r = self.client.post(url_vincular(self.turma_a1), {'usuario': str(self.coord_a2.id)}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_desvincular(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.delete(url_desvincular(self.turma_a1, self.prof_a1)).status_code, 204)
        self.assertEqual(self._professores(self.turma_a1.id), set())
        # Segunda vez: vínculo já não existe.
        self.assertEqual(self.client.delete(url_desvincular(self.turma_a1, self.prof_a1)).status_code, 404)

    def test_professor_nao_mexe_em_vinculos(self):
        self.entrar(self.prof_a1)
        r = self.client.post(url_vincular(self.turma_a1), {'usuario': str(self.coord_a1.id)}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.delete(url_desvincular(self.turma_a1, self.prof_a1)).status_code, 403)

    # =====================================================================
    # Frequência de registro
    # =====================================================================

    def _listar_frequencias(self, usuario=None, **params):
        self.entrar(usuario or self.admin_a)
        r = self.client.get(URL_FREQUENCIAS, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _patch_frequencia(self, usuario=None, **dados):
        self.entrar(usuario or self.admin_a)
        return self.client.patch(URL_ATUALIZAR_FREQUENCIA, dados, format='json')

    def _criar_com_frequencia(self, qtd, frequencia, **kwargs):
        turmas = self._criar_turmas(qtd, **kwargs)
        Turma.objects.filter(pk__in=[t.pk for t in turmas]).update(frequencia_registro=frequencia)
        return turmas

    def _frequencia(self, turma):
        turma.refresh_from_db()
        return turma.frequencia_registro

    @staticmethod
    def _ids_resultado(dados):
        return {t['id'] for t in dados['results']}

    def test_frequencia_turma_nova_comeca_semanal(self):
        self.assertEqual(self.turma_a1.frequencia_registro, 'semanal')
        self.assertEqual(self._post_criar().json()['frequencia_registro'], 'semanal')

    def test_frequencia_pode_ser_definida_no_cadastro_e_na_edicao(self):
        r = self._post_criar(frequencia_registro='quinzenal')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['frequencia_registro'], 'quinzenal')

        r = self._patch(self.turma_a1, frequencia_registro='mensal')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._frequencia(self.turma_a1), 'mensal')

        self.assertEqual(self._patch(self.turma_a1, frequencia_registro='anual').status_code, 400)

    def test_frequencia_vem_na_listagem_de_turmas(self):
        linha = self._listar(self.admin_a, page=1)['results'][0]
        self.assertIn('frequencia_registro', linha)

    def test_frequencias_escopo_admin_e_coordenador(self):
        ids_admin = self._ids_resultado(self._listar_frequencias())
        self.assertEqual(ids_admin, {str(self.turma_a1.id), str(self.turma_a2.id)})

        ids_coord = self._ids_resultado(self._listar_frequencias(self.coord_a1))
        self.assertEqual(ids_coord, {str(self.turma_a1.id)})

    def test_frequencias_paginacao_de_10(self):
        self._criar_turmas(15)
        dados = self._listar_frequencias()
        self.assertEqual(len(dados['results']), 10)
        self.assertEqual(dados['count'], 17)  # 15 + turma_a1 + turma_a2
        self.assertEqual(dados['total_paginas'], 2)
        self.assertEqual(self._listar_frequencias(page=99)['pagina'], 2)

    def test_frequencias_linha_e_enxuta(self):
        linha = self._listar_frequencias()['results'][0]
        self.assertEqual(
            set(linha),
            {'id', 'nome', 'turno', 'ano_letivo', 'etapa', 'ativa',
             'escola', 'escola_nome', 'frequencia_registro'},
        )

    def test_frequencias_so_ativas_por_padrao(self):
        inativa, = self._criar_turmas(1, ativa=False)
        self.assertNotIn(str(inativa.id), self._ids_resultado(self._listar_frequencias()))
        self.assertIn(str(inativa.id), self._ids_resultado(self._listar_frequencias(ativa='false')))

    def test_frequencias_filtro_por_escola(self):
        dados = self._listar_frequencias(escola=str(self.a2.id))
        self.assertEqual(self._ids_resultado(dados), {str(self.turma_a2.id)})
        self.assertEqual(self._listar_frequencias(escola=str(self.b1.id))['count'], 0)
        self.assertEqual(self._listar_frequencias(escola='nao-e-uuid')['count'], 0)

    def test_frequencias_filtro_e_totais(self):
        self._criar_com_frequencia(3, 'quinzenal', prefixo='Q')
        self._criar_com_frequencia(1, 'mensal', prefixo='M')
        dados = self._listar_frequencias(frequencia='quinzenal')
        self.assertEqual(dados['count'], 3)
        # Os totais ignoram o filtro de frequência (são o resumo da tela).
        self.assertEqual(dados['totais'], {'semanal': 2, 'quinzenal': 3, 'mensal': 1})
        self.assertEqual(self._listar_frequencias(frequencia='anual')['count'], 0)

    def test_frequencias_busca_por_nome(self):
        self._criar_turmas(3, prefixo='Busca')
        dados = self._listar_frequencias(busca='busca 01')
        self.assertEqual([t['nome'] for t in dados['results']], ['Busca 01'])

    def test_frequencias_numero_de_queries_nao_cresce_com_as_turmas(self):
        self.entrar(self.admin_a)

        def contar():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL_FREQUENCIAS, {'page': 1}).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        self._criar_turmas(8, escola=self.a2)
        self.assertEqual(contar(), antes)

    def test_atualizar_frequencia_de_uma_e_de_varias_turmas(self):
        r = self._patch_frequencia(turmas=[str(self.turma_a1.id)], frequencia_registro='quinzenal')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), {'atualizadas': 1, 'frequencia_registro': 'quinzenal'})
        self.assertEqual(self._frequencia(self.turma_a1), 'quinzenal')
        self.assertEqual(self._frequencia(self.turma_a2), 'semanal')

        ids = [str(self.turma_a1.id), str(self.turma_a2.id)]
        r = self._patch_frequencia(turmas=ids, frequencia_registro='mensal')
        self.assertEqual(r.json()['atualizadas'], 2)
        self.assertEqual(self._frequencia(self.turma_a2), 'mensal')

    def test_atualizar_frequencia_muda_atualizado_em(self):
        antes = self.turma_a1.atualizado_em
        self._patch_frequencia(turmas=[str(self.turma_a1.id)], frequencia_registro='mensal')
        self.turma_a1.refresh_from_db()
        self.assertGreater(self.turma_a1.atualizado_em, antes)

    def test_atualizar_frequencia_de_toda_a_escola_so_ativas(self):
        inativa, = self._criar_turmas(1, ativa=False, prefixo='I')
        ativas = self._criar_turmas(2, prefixo='A')
        r = self._patch_frequencia(escola=str(self.a1.id), frequencia_registro='quinzenal')
        self.assertEqual(r.json()['atualizadas'], 3)  # 2 novas + turma_a1
        self.assertEqual(self._frequencia(ativas[0]), 'quinzenal')
        self.assertEqual(self._frequencia(inativa), 'semanal')
        self.assertEqual(self._frequencia(self.turma_a2), 'semanal')

    def test_atualizar_frequencia_fora_do_escopo_nao_altera_nada(self):
        ids = [str(self.turma_a1.id), str(self.turma_b1.id)]
        self.assertEqual(self._patch_frequencia(turmas=ids, frequencia_registro='mensal').status_code, 404)
        self.assertEqual(self._frequencia(self.turma_a1), 'semanal')
        self.assertEqual(self._frequencia(self.turma_b1), 'semanal')

        r = self._patch_frequencia(escola=str(self.b1.id), frequencia_registro='mensal')
        self.assertEqual(r.status_code, 404)

        r = self._patch_frequencia(self.coord_a1, turmas=[str(self.turma_a2.id)], frequencia_registro='mensal')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self._frequencia(self.turma_a2), 'semanal')

    def test_professor_nao_altera_frequencia(self):
        r = self._patch_frequencia(self.prof_a1, turmas=[str(self.turma_a1.id)], frequencia_registro='mensal')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._frequencia(self.turma_a1), 'semanal')

    def test_atualizar_frequencia_validacoes(self):
        alvo = [str(self.turma_a1.id)]
        casos = [
            {'turmas': alvo, 'frequencia_registro': 'anual'},
            {'turmas': alvo},
            {'frequencia_registro': 'mensal'},
            {'turmas': alvo, 'escola': str(self.a1.id), 'frequencia_registro': 'mensal'},
            {'turmas': [], 'frequencia_registro': 'mensal'},
            {'turmas': ['x'], 'frequencia_registro': 'mensal'},
        ]
        for dados in casos:
            with self.subTest(dados=dados):
                self.assertEqual(self._patch_frequencia(**dados).status_code, 400)