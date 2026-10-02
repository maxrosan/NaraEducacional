"""Consumo da API OpenAI: registro com tenant e consulta pelo superadmin.

Cobre:
  * registrar_uso_openai preenche escola/instituição (antes ficavam NULL):
    escola do contexto > escola do usuário; instituição sempre derivada da
    escola; admin sem escola fica só com a instituição;
  * registrar nunca levanta exceção;
  * transcrição (whisper) também leva a escola;
  * endpoints de consulta: só superadmin, filtros, ranking de escolas,
    paginação e parâmetros malformados sem 500.
"""
import datetime
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from api.models import OpenAIUsage
from api.services.openai_usage import registrar_uso_openai, registrar_uso_whisper

from .base import CenarioMultiTenant


def _ultimo():
    return OpenAIUsage._base_manager.order_by('-id').first()


class RegistroComTenantTests(CenarioMultiTenant):
    """coord_a1 é da escola A1; admin_a é da rede A, sem escola."""

    def test_escola_do_contexto_tem_prioridade_e_define_a_instituicao(self):
        registrar_uso_openai(input_tokens=10, output_tokens=5, model='gpt-4o-mini',
                             usuario=self.coord_a1, escola_id=self.a2.id)
        reg = _ultimo()
        self.assertEqual(reg.escola_id, self.a2.id)
        self.assertEqual(reg.instituicao_id, self.rede_a.id)
        self.assertEqual(reg.usuario_id, self.coord_a1.id)

    def test_sem_contexto_usa_a_escola_do_usuario(self):
        registrar_uso_openai(input_tokens=10, output_tokens=5, model='gpt-4o-mini', usuario=self.coord_a1)
        reg = _ultimo()
        self.assertEqual((reg.escola_id, reg.instituicao_id), (self.a1.id, self.rede_a.id))

    def test_admin_sem_escola_fica_so_com_a_instituicao(self):
        registrar_uso_openai(input_tokens=10, output_tokens=5, model='gpt-4o-mini', usuario=self.admin_a)
        reg = _ultimo()
        self.assertIsNone(reg.escola_id)
        self.assertEqual(reg.instituicao_id, self.rede_a.id)

    def test_chamada_de_sistema_sem_nada_fica_sem_tenant(self):
        registrar_uso_openai(input_tokens=10, output_tokens=5, model='gpt-4o-mini')
        reg = _ultimo()
        self.assertIsNone(reg.escola_id)
        self.assertIsNone(reg.instituicao_id)

    def test_nunca_levanta_excecao(self):
        antes = OpenAIUsage._base_manager.count()
        registrar_uso_openai(input_tokens=10, output_tokens=5, escola_id='nao-e-uuid')  # não pode estourar
        registrar_uso_openai()  # sem tokens: só loga
        self.assertEqual(OpenAIUsage._base_manager.count(), antes)

    def test_transcricao_leva_a_escola(self):
        registrar_uso_whisper(duracao_segundos=90.5, modelo='whisper-1', escola_id=self.a1.id)
        reg = _ultimo()
        self.assertEqual(reg.input_tokens, 91)  # segundos, arredondado para cima
        self.assertEqual((reg.escola_id, reg.instituicao_id), (self.a1.id, self.rede_a.id))
        self.assertGreater(reg.total_cost, 0)


class ConsultaUsoTests(CenarioMultiTenant):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.suporte = cls._usuario('suporte@x.com', 'suporte', None, None)

    def setUp(self):
        super().setUp()

        def criar(escola, custo, model='gpt-4o-mini', dias_atras=0, usuario=None):
            reg = OpenAIUsage._base_manager.create(
                input_tokens=100, output_tokens=50, image_tokens=0,
                input_cost=Decimal(custo), output_cost=Decimal('0'), total_cost=Decimal(custo),
                model=model, usuario=usuario, escola=escola, instituicao=escola.instituicao if escola else None,
            )
            if dias_atras:
                OpenAIUsage._base_manager.filter(pk=reg.pk).update(
                    criado_em=timezone.now() - datetime.timedelta(days=dias_atras),
                )
            return reg

        criar(self.a1, '0.30', usuario=self.coord_a1)
        criar(self.a1, '0.20', model='whisper-1')
        criar(self.b1, '1.00')
        criar(self.b1, '0.50', dias_atras=40)
        criar(None, '0.05')

    def _get(self, usuario, nome, **params):
        self.entrar(usuario)
        return self.client.get(reverse(nome), params)

    def test_so_superadmin_acessa(self):
        for usuario in (self.admin_a, self.suporte, self.coord_a1):
            with self.subTest(nivel=usuario.nivel):
                self.assertEqual(self._get(usuario, 'resumo_uso_openai').status_code, 403)
                self.assertEqual(self._get(usuario, 'listar_uso_openai').status_code, 403)

    def test_resumo_sem_filtro(self):
        dados = self._get(self.superadmin, 'resumo_uso_openai').json()
        self.assertEqual(dados['totais']['registros'], 5)
        self.assertAlmostEqual(dados['totais']['total_cost'], 2.05)
        self.assertEqual([e['nome'] for e in dados['top_escolas']], [self.b1.nome, self.a1.nome])
        self.assertEqual(str(dados['top_usuarios'][0]['usuario_id']), str(self.coord_a1.id))
        self.assertEqual(dados['modelos_disponiveis'], ['gpt-4o-mini', 'whisper-1'])
        self.assertTrue(all(isinstance(d['custo'], float) for d in dados['por_dia']))

    def test_filtro_por_escola_e_por_rede(self):
        por_escola = self._get(self.superadmin, 'resumo_uso_openai', escola=str(self.a1.id)).json()
        self.assertEqual(por_escola['totais']['registros'], 2)
        por_rede = self._get(self.superadmin, 'resumo_uso_openai', instituicao=str(self.rede_b.id)).json()
        self.assertAlmostEqual(por_rede['totais']['total_cost'], 1.50)

    def test_filtro_por_modelo_e_periodo(self):
        hoje = timezone.localdate()
        dados = self._get(
            self.superadmin, 'resumo_uso_openai',
            model='gpt-4o-mini', data_inicio=(hoje - datetime.timedelta(days=7)).isoformat(),
            data_fim=hoje.isoformat(),
        ).json()
        self.assertEqual(dados['totais']['registros'], 3)  # o de 40 dias e o whisper ficam fora

    def test_parametros_malformados_sao_ignorados(self):
        r = self._get(self.superadmin, 'resumo_uso_openai', escola='abc', data_inicio='2026-02-31', data_fim='ontem')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['totais']['registros'], 5)

    def test_registros_paginados_com_escola(self):
        r = self._get(self.superadmin, 'listar_uso_openai', page_size=2)
        self.assertEqual(r.status_code, 200)
        dados = r.json()
        self.assertEqual(dados['paginacao'], {'page': 1, 'page_size': 2, 'total': 5, 'total_pages': 3})
        self.assertEqual(len(dados['registros']), 2)
        com_escola = [x for x in dados['registros'] if x['escola']]
        for registro in com_escola:
            self.assertIn('nome', registro['escola'])
            self.assertIn('nome', registro['instituicao'])

    def test_page_size_tem_teto(self):
        dados = self._get(self.superadmin, 'listar_uso_openai', page_size=5000).json()
        self.assertEqual(dados['paginacao']['page_size'], 100)