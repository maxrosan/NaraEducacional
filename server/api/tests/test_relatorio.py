"""Relatórios: views (lista da coordenação, detalhe, PDF, geração, exclusão),
seções geradas por IA e templates (capa + ordem das seções) por escola.

Views:
  * lista da coordenação por escola (coordenador: a própria; admin: escolhe);
  * detalhe renova as URLs das imagens e respeita o tenant;
  * PDF para o superadmin, geração com IA (permissão e nome do cadastro);
  * exclusão apaga o PDF do storage.

Seções (services/relatorio.py, com a OpenAI mockada):
  * placeholder com None não derruba a seção (_preencher_prompt);
  * fallback em HTML escapado, sem texto cru com quebras de linha;
  * insumos "sem dado"/"erro" viram frase explícita (_insumo_ou_ausente);
  * Atividades exige JSON pelo response_format e não manda os dados duas vezes;
  * Conclusão sempre termina com a assinatura do backend, mesmo com erro ou
    resposta vazia, e não duplica o relato no contexto.

Templates (por escola):
  * no máximo UM ativo por escola — pela view e pelo índice do banco;
  * ativar um template não mexe nos de outras escolas;
  * escola do template: admin informa (ou usa a própria), coordenador sempre
    a dele, escola de outra rede é recusada;
  * modelo repetido na escola → 400 (antes 500 do banco);
  * items_sumario aceita só as seções do gerador;
  * listagem por escola/ativo, recorte de tenant e exclusão.
"""
import datetime
from unittest.mock import MagicMock, patch

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase
from django.urls import reverse

from api.models import Relatorio, RelatorioTemplate, Turma, Usuario
from api.services import relatorio
from api.services.relatorio import (
    _SCHEMA_ATIVIDADES,
    _SEM_BNCC,
    _gerar_secao_atividades,
    _gerar_secao_conclusao,
    _insumo_ou_ausente,
    _montar_assinatura_html,
    _preencher_prompt,
    _texto_para_html,
)

from .base import CenarioMultiTenant

CONTEUDO_FINALIZADO = 'x' * 60


# ======================================================================
# Views de relatório
# ======================================================================

class ListaRelatoriosCoordenacaoTests(CenarioMultiTenant):
    """Bug: `resolver_recorte` era chamado sem `escola_id` → TypeError,
    engolido pelo `except Exception` → a tela recebia 404 SEMPRE."""

    URL = '/api/relatorios/coordenacao/'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rel_a1 = Relatorio.objects.create(aluno=cls.aluno_a1, escola=cls.a1, instituicao=cls.rede_a,
                                              conteudo=CONTEUDO_FINALIZADO)
        cls.rel_a2 = Relatorio.objects.create(aluno=cls.aluno_a2, escola=cls.a2, instituicao=cls.rede_a,
                                              conteudo=CONTEUDO_FINALIZADO)

    def _ids(self, resposta):
        return {r['id'] for r in resposta.data['results']}

    def test_coordenador_lista_os_relatorios_da_propria_escola(self):
        self.entrar(self.coord_a1)
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._ids(r), {str(self.rel_a1.id)})

    def test_admin_escolhe_a_escola(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(self.URL).status_code, 400)
        r = self.client.get(self.URL, {'escola_id': str(self.a2.id)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._ids(r), {str(self.rel_a2.id)})

    def test_admin_nao_lista_escola_de_outra_rede(self):
        self.entrar(self.admin_a)
        self.assertEqual(self.client.get(self.URL, {'escola_id': str(self.b1.id)}).status_code, 403)

    def test_professor_nao_acessa_a_lista_da_coordenacao(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self.client.get(self.URL).status_code, 403)


class DetalheRelatorioTests(CenarioMultiTenant):
    """Regressões das views de relatório ativas (as de avaliacao.py)."""

    def test_detalhe_renova_urls_das_imagens(self):
        rel = Relatorio.objects.create(aluno=self.aluno_a1, escola=self.a1, instituicao=self.rede_a,
                                       conteudo='<img src="https://s3/velha.png?Expires=1">')
        self.entrar(self.prof_a1)
        with patch('api.views.avaliacao.refresh_img_urls_in_html',
                   return_value='<img src="https://s3/nova.png">') as refresh:
            r = self.client.get(f'/api/relatorios/{rel.id}/')
        self.assertEqual(r.status_code, 200)
        refresh.assert_called_once()
        self.assertIn('nova.png', r.data['conteudo'])

    def test_relatorio_de_outra_rede_nao_aparece(self):
        rel = Relatorio.objects.create(aluno=self.aluno_b1, escola=self.b1, instituicao=self.rede_b, conteudo='x')
        self.entrar(self.coord_a1)
        self.assertEqual(self.client.get(f'/api/relatorios/{rel.id}/').status_code, 404)


class RelatorioPdfEGeracaoTests(CenarioMultiTenant):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.turma_a1_extra = Turma.objects.create(nome='Nível 4A', escola=cls.a1, instituicao=cls.rede_a)
        cls.aluno_turma_extra = cls._aluno('Duda A1 extra', cls.turma_a1_extra)
        cls.rel_a1 = Relatorio.objects.create(aluno=cls.aluno_a1, escola=cls.a1, instituicao=cls.rede_a,
                                              conteudo=CONTEUDO_FINALIZADO)

    @patch('api.views.relatorio.build_filename', return_value='relatorio.pdf')
    @patch('api.views.relatorio.ensure_pdf', return_value=(b'%PDF-1.4', True, None))
    def test_superadmin_baixa_o_pdf(self, _ensure, _nome):
        """Bug: a checagem manual comparava a instituição do usuário (nula no
        superadmin) com a do relatório → 403."""
        self.entrar(self.superadmin)
        r = self.client.get(f'/api/relatorios/{self.rel_a1.id}/pdf/download/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r.content))
        self.assertEqual(r['Content-Type'], 'application/pdf')

    @patch('api.views.relatorio.gerar_relatorio_com_ia')
    def test_professor_nao_gera_relatorio_de_aluno_de_turma_nao_vinculada(self, gerar):
        self.entrar(self.prof_a1)
        r = self.client.post('/api/gerar-relatorio/', {'crianca_id': str(self.aluno_turma_extra.id)}, format='json')
        self.assertEqual(r.status_code, 403, r.content)
        gerar.assert_not_called()

    @patch('api.views.relatorio.buscar_dados_estudante_para_relatorio', return_value={})
    @patch('api.views.relatorio.gerar_relatorio_com_ia', return_value={'content': 'ok'})
    def test_nome_enviado_para_a_ia_vem_do_cadastro(self, gerar, _dados):
        self.entrar(self.prof_a1)
        r = self.client.post('/api/gerar-relatorio/', {
            'crianca_id': str(self.aluno_a1.id), 'nome_crianca': 'Nome Inventado',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(gerar.call_args.args[0], 'Ana A1')

    @patch('api.signals.delete_from_storage')
    def test_excluir_relatorio_apaga_o_pdf_do_storage(self, apagar):
        """Bug: a exclusão em uso (views/avaliacao.py) deixava o PDF órfão."""
        # Um relatório por aluno/escola (unique_relatorio_aluno_escola): usa o
        # da fixture. `update` não dispara o pre_save que limparia o PDF.
        Relatorio.objects.filter(pk=self.rel_a1.pk).update(pdf_storage_key='relatorios/pdf/r.pdf')
        self.entrar(self.prof_a1)
        r = self.client.delete(f'/api/relatorios/{self.rel_a1.id}/deletar/')
        self.assertEqual(r.status_code, 204, getattr(r, 'data', r.content))
        apagar.assert_called_with('relatorios/pdf/r.pdf')


# ======================================================================
# Seções geradas por IA
# ======================================================================

PERIODO = {'type': 'personalizado', 'startDate': '2026-08-01', 'endDate': '2026-09-30'}


class SecoesHelpersTests(SimpleTestCase):
    def test_preencher_prompt_aceita_none_e_numero(self):
        self.assertEqual(
            _preencher_prompt('Idade: {idade} | Turma: {turma} | Ano: {ano}', idade=None, turma='', ano=2026),
            'Idade: Não informado | Turma: Não informado | Ano: 2026',
        )

    def test_preencher_prompt_mantem_placeholder_nao_informado(self):
        # Quem não foi passado continua no texto (a guarda troca depois).
        self.assertEqual(_preencher_prompt('{a} {b}', a='x'), 'x {b}')

    def test_texto_para_html_escapa_e_quebra_em_paragrafos(self):
        html = _texto_para_html('Linha <b>1</b>\nLinha 2\n\nOutro bloco')
        self.assertEqual(html, '<p>Linha &lt;b&gt;1&lt;/b&gt;<br>Linha 2</p><p>Outro bloco</p>')
        self.assertNotIn('\n', html)

    def test_texto_para_html_vazio(self):
        self.assertEqual(_texto_para_html(''), '')
        self.assertEqual(_texto_para_html(None), '')

    def test_insumo_ou_ausente(self):
        ausente = 'NADA'
        for texto in [
            '', None, '<p>Sem registros de observação BNCC para o período especificado.</p>',
            '<p>Erro ao recuperar dados de observação BNCC.</p>',
            '<p>Não foi possível gerar o relato individual automaticamente neste momento.</p>',
            '<p>A análise automática dos relatos está indisponível.</p>',
        ]:
            with self.subTest(texto=texto):
                self.assertEqual(_insumo_ou_ausente(texto, ausente), ausente)
        self.assertEqual(_insumo_ou_ausente('<p>Ana gosta de <b>pintar</b>.</p>', ausente), 'Ana gosta de pintar.')


def _planejamento_falso():
    dia = MagicMock(atividades_propostas='Pintura com <b>guache</b>', dia_semana='segunda_feira')
    dia.planejamentos_habilidades.select_related.return_value = []
    plano = MagicMock(semana_inicio=datetime.date(2026, 9, 7), semana_fim=datetime.date(2026, 9, 11))
    plano.planejamentos_diarios.all.return_value.order_by.return_value = [dia]
    return plano


@patch.object(relatorio, 'get_openai_client', return_value=object())
@patch.object(relatorio, 'PlanejamentoSemanal')
class SecaoAtividadesTests(SimpleTestCase):
    INFO = {'turma_id': 'turma-1', 'turma_nome': 'Infantil 4', 'idade': None}

    def _configurar(self, mock_planejamento):
        mock_planejamento.objects.filter.return_value.order_by.return_value = [_planejamento_falso()]

    def test_exige_json_e_preenche_idade_none(self, mock_planejamento, _cliente):
        self._configurar(mock_planejamento)
        with patch.object(relatorio, 'resolver_prompt', return_value='Turma {turma}, idade {idade}:\n{planejamentos}'), \
             patch.object(relatorio, '_gerar_com_guarda_idioma', return_value='{"texto": "<p>Narrativa</p>"}') as ia:
            resultado = _gerar_secao_atividades(self.INFO, PERIODO, 'Ana')

        self.assertEqual(resultado, '<p>Narrativa</p>')
        kwargs = ia.call_args.kwargs
        self.assertIs(kwargs['response_format'], _SCHEMA_ATIVIDADES)
        sistema, usuario = kwargs['messages'][0]['content'], kwargs['messages'][1]['content']
        self.assertIn('idade Não informado', sistema)
        # Planejamentos já embutidos no prompt: não vão de novo na mensagem do usuário.
        self.assertIn('Pintura com', sistema)
        self.assertNotIn('Pintura com', usuario)

    def test_sem_placeholder_os_dados_vao_na_mensagem_do_usuario(self, mock_planejamento, _cliente):
        self._configurar(mock_planejamento)
        with patch.object(relatorio, 'resolver_prompt', return_value='Escreva a seção.'), \
             patch.object(relatorio, '_gerar_com_guarda_idioma', return_value='{"texto": "<p>ok</p>"}') as ia:
            _gerar_secao_atividades(self.INFO, PERIODO, 'Ana')
        self.assertIn('Pintura com', ia.call_args.kwargs['messages'][1]['content'])

    def test_resposta_fora_do_json_cai_no_fallback_escapado(self, mock_planejamento, _cliente):
        self._configurar(mock_planejamento)
        with patch.object(relatorio, 'resolver_prompt', return_value='{planejamentos}'), \
             patch.object(relatorio, '_gerar_com_guarda_idioma', return_value='texto livre, não JSON'):
            resultado = _gerar_secao_atividades(self.INFO, PERIODO, 'Ana')
        self.assertTrue(resultado.startswith('<p>'))
        self.assertIn('&lt;b&gt;guache&lt;/b&gt;', resultado)
        self.assertNotIn('<b>', resultado)
        self.assertNotIn('\n', resultado)

    def test_sem_turma_nao_chama_a_ia(self, mock_planejamento, _cliente):
        with patch.object(relatorio, '_gerar_com_guarda_idioma') as ia:
            resultado = _gerar_secao_atividades({'turma_id': None}, PERIODO, 'Ana')
        ia.assert_not_called()
        self.assertTrue(resultado.startswith('<p>'))


@patch.object(relatorio, 'get_openai_client', return_value=object())
class SecaoConclusaoTests(SimpleTestCase):
    ARGS = dict(
        nome_crianca='Ana', secao_relatos='<p>Ana brinca muito.</p>', secao_producoes='',
        secao_registros_observacao='<p>Sem registros de observação BNCC para o período especificado.</p>',
        analise_completa='<p>Pintura.</p>', turma_nome='Infantil 4', nome_professora='Leticia', idade=None,
    )
    ASSINATURA = _montar_assinatura_html('Leticia')

    def _gerar(self, template, resposta=None, erro=None):
        ia = MagicMock(return_value=resposta, side_effect=erro)
        with patch.object(relatorio, 'resolver_prompt', return_value=template), \
             patch.object(relatorio, '_gerar_com_guarda_idioma', ia):
            return _gerar_secao_conclusao(**self.ARGS), ia

    def test_remove_assinatura_da_ia_e_anexa_a_oficial(self, _cliente):
        resultado, _ = self._gerar('Carta para {nome_aluno}.', '<p>Querida família.</p><p>Com carinho,</p>')
        self.assertTrue(resultado.endswith(self.ASSINATURA))
        self.assertIn('Querida família', resultado)
        self.assertEqual(resultado.count('Com carinho'), 1)  # só a do backend

    def test_erro_na_ia_ainda_tem_mensagem_e_assinatura(self, _cliente):
        """Antes devolvia "" — o relatório saía sem conclusão e sem assinatura."""
        resultado, _ = self._gerar('Carta.', erro=Exception('timeout'))
        self.assertIn('Não foi possível', resultado)
        self.assertTrue(resultado.endswith(self.ASSINATURA))

    def test_resposta_vazia_vira_mensagem(self, _cliente):
        resultado, _ = self._gerar('Carta.', '   ')
        self.assertIn('Não foi possível', resultado)
        self.assertTrue(resultado.endswith(self.ASSINATURA))

    def test_relato_embutido_no_prompt_nao_se_repete_no_contexto(self, _cliente):
        _, ia = self._gerar('Relato: {relato_individual}', '<p>ok</p>')
        sistema = ia.call_args.kwargs['messages'][0]['content']
        contexto = ia.call_args.kwargs['messages'][1]['content']
        self.assertIn('Ana brinca muito.', sistema)
        self.assertNotIn('RELATO INDIVIDUAL', contexto)
        self.assertIn('O QUE VIVEMOS JUNTOS', contexto)

    def test_bncc_sem_dado_vira_frase_explicita(self, _cliente):
        _, ia = self._gerar('Carta.', '<p>ok</p>')
        contexto = ia.call_args.kwargs['messages'][1]['content']
        self.assertIn(_SEM_BNCC, contexto)
        self.assertNotIn('<p>Sem registros', contexto)


# ======================================================================
# Templates de relatório (capa + ordem das seções)
# ======================================================================

SECOES_VALIDAS = [
    {'chave': 'conclusao', 'titulo': 'Para a família', 'visivel': True},
    {'chave': 'atividades', 'titulo': '', 'visivel': True},
    {'chave': 'portfolio', 'titulo': 'Portfólio', 'visivel': False},
]


class TemplatesBase(CenarioMultiTenant):
    """Helpers comuns. Sem testes próprios."""

    def criar(self, usuario, **dados):
        self.entrar(usuario)
        payload = {'nome': 'Template', 'modelo': 'classico', 'ativo': True, **dados}
        return self.client.post(reverse('criar_relatorio_template'), payload, format='json')

    def template(self, escola, modelo='classico', ativo=False, **extra):
        return RelatorioTemplate._base_manager.create(
            nome=f'{modelo} {escola.nome}', modelo=modelo, ativo=ativo,
            escola=escola, instituicao=escola.instituicao, **extra,
        )

    def ativos(self, escola):
        return list(RelatorioTemplate._base_manager.filter(escola=escola, ativo=True).values_list('modelo', flat=True))

    def admin(self, email, rede, escola=None):
        return Usuario._base_manager.create(email=email, nome='Admin extra', nivel='admin',
                                            instituicao=rede, escola=escola)


class UmTemplateAtivoPorEscolaTests(TemplatesBase):
    def test_criar_ativo_desativa_o_anterior_da_mesma_escola(self):
        self.template(self.a1, 'classico', ativo=True)
        r = self.criar(self.admin_a, escola=str(self.a1.id), modelo='mascote')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.ativos(self.a1), ['mascote'])

    def test_ativar_por_patch_desativa_os_outros(self):
        self.template(self.a1, 'classico', ativo=True)
        outro = self.template(self.a1, 'natureza')
        self.entrar(self.coord_a1)
        r = self.client.patch(reverse('atualizar_relatorio_template', args=[outro.id]), {'ativo': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.ativos(self.a1), ['natureza'])

    def test_nao_mexe_em_outra_escola(self):
        self.template(self.a2, 'classico', ativo=True)
        self.criar(self.admin_a, escola=str(self.a1.id))
        self.assertEqual(self.ativos(self.a2), ['classico'])
        self.assertEqual(self.ativos(self.a1), ['classico'])

    def test_banco_recusa_dois_ativos_na_mesma_escola(self):
        self.template(self.a1, 'classico', ativo=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.template(self.a1, 'mascote', ativo=True)

    def test_varios_inativos_na_mesma_escola_sao_permitidos(self):
        self.template(self.a1, 'classico')
        self.template(self.a1, 'mascote')
        self.assertEqual(RelatorioTemplate._base_manager.filter(escola=self.a1).count(), 2)


class EscolaDoTemplateTests(TemplatesBase):
    def test_admin_informa_a_escola(self):
        r = self.criar(self.admin_a, escola=str(self.a1.id))
        self.assertEqual(r.status_code, 201, r.content)
        tpl = RelatorioTemplate._base_manager.get(id=r.json()['id'])
        self.assertEqual((tpl.escola_id, tpl.instituicao_id), (self.a1.id, self.rede_a.id))

    def test_admin_com_escola_propria_nao_precisa_informar(self):
        admin = self.admin('admin.com.escola@x.com', self.rede_a, escola=self.a2)
        r = self.criar(admin)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(str(r.json()['escola']), str(self.a2.id))

    def test_admin_sem_escola_e_sem_informar_e_recusado(self):
        self.assertEqual(self.criar(self.admin_a).status_code, 400)

    def test_admin_nao_cria_em_escola_de_outra_rede(self):
        r = self.criar(self.admin_a, escola=str(self.b1.id))
        self.assertIn(r.status_code, (400, 403, 404), r.content)
        self.assertFalse(RelatorioTemplate._base_manager.filter(escola=self.b1).exists())

    def test_coordenador_sempre_grava_na_propria_escola(self):
        r = self.criar(self.coord_a1, escola=str(self.a2.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(str(r.json()['escola']), str(self.a1.id))

    def test_professor_nao_cria(self):
        self.assertEqual(self.criar(self.prof_a1).status_code, 403)

    def test_modelo_repetido_na_escola_e_400(self):
        self.template(self.a1, 'classico')
        r = self.criar(self.coord_a1, modelo='classico')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('classico', r.json()['error'])


class ItemsSumarioTests(TemplatesBase):
    def test_normaliza_titulo_vazio_e_mantem_visibilidade(self):
        r = self.criar(self.coord_a1, items_sumario=SECOES_VALIDAS)
        self.assertEqual(r.status_code, 201, r.content)
        itens = r.json()['items_sumario']
        self.assertEqual([i['chave'] for i in itens], ['conclusao', 'atividades', 'portfolio'])
        self.assertEqual(itens[1]['titulo'], 'O que vivemos juntos neste período')
        self.assertFalse(itens[2]['visivel'])

    def test_recusa_secao_desconhecida(self):
        r = self.criar(self.coord_a1, items_sumario=[{'chave': 'analise_leitura', 'titulo': 'x'}])
        self.assertEqual(r.status_code, 400)
        self.assertIn('items_sumario', r.json())

    def test_recusa_secao_repetida(self):
        self.assertEqual(self.criar(self.coord_a1, items_sumario=[{'chave': 'bncc'}, {'chave': 'bncc'}]).status_code, 400)

    def test_recusa_formato_que_nao_e_lista(self):
        self.assertEqual(self.criar(self.coord_a1, items_sumario={'chave': 'bncc'}).status_code, 400)


class ListagemEExclusaoDeTemplatesTests(TemplatesBase):
    def setUp(self):
        super().setUp()
        self.ativo_a1 = self.template(self.a1, 'classico', ativo=True)
        self.inativo_a1 = self.template(self.a1, 'mascote')
        self.ativo_a2 = self.template(self.a2, 'classico', ativo=True)
        self.ativo_b1 = self.template(self.b1, 'classico', ativo=True)

    def _ids(self, usuario, **params):
        self.entrar(usuario)
        r = self.client.get(reverse('listar_relatorio_templates'), params)
        self.assertEqual(r.status_code, 200, r.content)
        return [t['id'] for t in r.json()]

    def _excluir(self, usuario, template):
        self.entrar(usuario)
        return self.client.delete(reverse('deletar_relatorio_template', args=[template.id]))

    def test_admin_ve_so_a_propria_rede(self):
        ids = self._ids(self.admin_a)
        self.assertNotIn(str(self.ativo_b1.id), ids)
        self.assertEqual(len(ids), 3)

    def test_filtro_por_escola_e_ativo(self):
        self.assertEqual(self._ids(self.admin_a, escola=str(self.a1.id), ativo='1'), [str(self.ativo_a1.id)])

    def test_ativo_vem_primeiro(self):
        self.assertEqual(self._ids(self.admin_a, escola=str(self.a1.id))[0], str(self.ativo_a1.id))

    def test_coordenador_ve_so_a_propria_escola(self):
        self.assertEqual(set(self._ids(self.coord_a1)), {str(self.ativo_a1.id), str(self.inativo_a1.id)})

    def test_excluir(self):
        self.assertEqual(self._excluir(self.coord_a1, self.inativo_a1).status_code, 204)
        self.assertFalse(RelatorioTemplate._base_manager.filter(id=self.inativo_a1.id).exists())

    def test_professor_nao_exclui(self):
        self.assertEqual(self._excluir(self.prof_a1, self.inativo_a1).status_code, 403)

    def test_admin_de_outra_rede_nao_ve_para_excluir(self):
        admin_b = self.admin('admin.b@x.com', self.rede_b)
        self.assertEqual(self._excluir(admin_b, self.ativo_a1).status_code, 404)
        self.assertTrue(RelatorioTemplate._base_manager.filter(id=self.ativo_a1.id).exists())