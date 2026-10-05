"""Registros pedagógicos: vínculo do professor com a turma, dono do registro,
campos que o cliente não pode trocar e a regra das perguntas oficiais.
"""
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

from api.models import (
    ObservacaoTranscricao, Pergunta, Producao, ProducaoAluno, RegistroEscrita,
    RegistroObservacao, Turma, UsuarioTurma,
)
from api.services.fases_producao import FASES_ESCRITA

from .base import CenarioMultiTenant

RECUSADO = (400, 403, 404)


class CenarioComTurmaExtra(CenarioMultiTenant):
    """Acrescenta, na escola A1, uma turma em que `prof_a1` NÃO está vinculada
    e um segundo professor (autor de registros que não são da `prof_a1`)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.turma_a1_extra = Turma.objects.create(nome='Nível 4A', escola=cls.a1, instituicao=cls.rede_a)
        cls.aluno_turma_extra = cls._aluno('Duda A1 extra', cls.turma_a1_extra)
        cls.prof2_a1 = cls._usuario('prof2.a1@x.com', 'professor_infantil', cls.rede_a, cls.a1)
        UsuarioTurma.objects.create(usuario=cls.prof2_a1, turma=cls.turma_a1)


# ---------------------------------------------------------------------------
# Produção (portfólio)
# ---------------------------------------------------------------------------

class VinculoProducaoTests(CenarioMultiTenant):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.aluno_b1_2 = cls._aluno('Davi B1', cls.turma_b1)
        cls.producao_b1 = Producao.objects.create(
            arquivo_hash='prod-b1', turma=cls.turma_b1, professor=cls.prof_b1,
            escola=cls.b1, instituicao=cls.rede_b,
        )
        cls.vinculo_b1 = ProducaoAluno.objects.create(producao=cls.producao_b1, aluno=cls.aluno_b1)

    def _url_vinculo(self):
        return f'/api/producoes/{self.producao_b1.id}/alunos/{self.vinculo_b1.id}/atualizar/'

    def test_admin_de_outra_rede_nao_edita_vinculo(self):
        """Falha crítica: ProducaoAluno não tem TenantManager e era buscado
        direto pelo id — admin da rede A editava vínculos da rede B."""
        self.entrar(self.admin_a)
        r = self.client.patch(self._url_vinculo(), {'legenda': 'invadido'}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        self.vinculo_b1.refresh_from_db()
        self.assertEqual(self.vinculo_b1.legenda, '')

    def test_edicao_do_vinculo_nao_troca_o_aluno(self):
        self.entrar(self.prof_b1)
        r = self.client.patch(self._url_vinculo(), {'aluno': str(self.aluno_b1_2.id), 'legenda': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.vinculo_b1.refresh_from_db()
        self.assertEqual((self.vinculo_b1.aluno_id, self.vinculo_b1.legenda), (self.aluno_b1.id, 'ok'))

    def test_destaque_false_em_multipart_nao_vira_true(self):
        """`request.data.get('destaque')` devolvia a string "false" (truthy)."""
        self.entrar(self.prof_b1)
        r = self.client.post(f'/api/producoes/{self.producao_b1.id}/alunos/vincular/', {
            'aluno': str(self.aluno_b1_2.id), 'destaque': 'false', 'incluir_relatorio': 'true',
        }, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        vinculo = ProducaoAluno.objects.get(producao=self.producao_b1, aluno=self.aluno_b1_2)
        self.assertFalse(vinculo.destaque)
        self.assertTrue(vinculo.incluir_relatorio)


# ---------------------------------------------------------------------------
# Observação e perguntas oficiais
# ---------------------------------------------------------------------------

class ObservacaoTests(CenarioComTurmaExtra):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pergunta_oficial = Pergunta.todos.create(pergunta='Reconhece o próprio nome?')
        cls.pergunta_a2 = Pergunta.todos.create(
            pergunta='Só da A2?', origem='escola', escola=cls.a2, instituicao=cls.rede_a,
        )
        cls.pergunta_rede_b = Pergunta.todos.create(
            pergunta='Vazada?', instituicao=cls.rede_b, escola=None,
        )

    def _criar(self, aluno, pergunta):
        return self.client.post('/api/registros-observacao/criar/', {
            'aluno': str(aluno.id), 'pergunta': str(pergunta.id),
            'resposta': 'Sim', 'data_observacao': '2026-03-10',
        }, format='json')

    def test_professor_registra_observacao_de_pergunta_oficial(self):
        """Bug: o serializer validava `pergunta` pelo TenantManager, que
        esconde as oficiais (escola nula) de quem tem escopo de escola."""
        self.entrar(self.prof_a1)
        r = self._criar(self.aluno_a1, self.pergunta_oficial)
        self.assertEqual(r.status_code, 201, r.content)

    def test_pergunta_customizada_de_outra_escola_e_recusada(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self._criar(self.aluno_a1, self.pergunta_a2).status_code, 400)
        self.assertFalse(RegistroObservacao.objects.filter(aluno=self.aluno_a1).exists())

    def test_pergunta_de_rede_escola_nula_nao_passa_por_oficial(self):
        """Escola nula + instituição preenchida é de UMA rede, não oficial."""
        self.entrar(self.prof_a1)
        self.assertEqual(self._criar(self.aluno_a1, self.pergunta_rede_b).status_code, 400)

    def test_professor_nao_registra_aluno_de_turma_nao_vinculada(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self._criar(self.aluno_turma_extra, self.pergunta_oficial).status_code, 403)

    def test_edicao_nao_move_a_observacao_para_outro_aluno(self):
        registro = RegistroObservacao.objects.create(
            aluno=self.aluno_a1, pergunta=self.pergunta_oficial, resposta='Sim',
            professor=self.prof_a1, escola=self.a1, instituicao=self.rede_a,
        )
        outro = self._aluno('Eva A1', self.turma_a1)
        self.entrar(self.prof_a1)
        self.client.patch(f'/api/registros-observacao/{registro.id}/atualizar/',
                          {'aluno': str(outro.id)}, format='json')
        registro.refresh_from_db()
        self.assertEqual(registro.aluno_id, self.aluno_a1.id)

    def test_transcricao_nao_aceita_aluno_de_outra_turma(self):
        self.entrar(self.prof_a1)
        r = self.client.post('/api/observacoes-transcricao/criar/', {
            'turma': str(self.turma_a1.id), 'aluno': str(self.aluno_turma_extra.id),
            'observacao_texto': 'x',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(ObservacaoTranscricao.objects.exists())


# ---------------------------------------------------------------------------
# Escrita / desenho (análise por IA) e leitura
# ---------------------------------------------------------------------------

class AnaliseProducaoTests(CenarioComTurmaExtra):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.registro_prof2 = RegistroEscrita.objects.create(
            arquivo_nome='x.jpg', arquivo_hash='hash-prof2', arquivo_path='escrita/x.jpg',
            arquivo_original='x.jpg', tamanho_arquivo=10, tipo_arquivo='image/jpeg',
            aluno=cls.aluno_a1, turma=cls.turma_a1, professor=cls.prof2_a1,
            escola=cls.a1, instituicao=cls.rede_a,
        )

    def _classificar(self):
        return self.client.post('/api/registros/classificacao/', {
            'tipo': 'escrita', 'arquivo_hash': 'hash-prof2', 'classificacao': FASES_ESCRITA[0],
        }, format='json')

    def test_professor_nao_reclassifica_registro_de_outra_professora(self):
        self.entrar(self.prof_a1)
        self.assertEqual(self._classificar().status_code, 403)

    def test_autora_reclassifica_o_proprio_registro(self):
        self.entrar(self.prof2_a1)
        self.assertEqual(self._classificar().status_code, 200)

    @patch('api.views.analise_producao.upload_bytes_to_storage')
    def test_upload_de_aluno_de_turma_nao_vinculada_e_recusado_antes_do_storage(self, upload):
        self.entrar(self.prof_a1)
        arquivo = SimpleUploadedFile('p.png', b'\x89PNG fake', content_type='image/png')
        r = self.client.post('/api/upload-escrita/', {
            'arquivo': arquivo, 'alunoId': str(self.aluno_turma_extra.id),
        }, format='multipart')
        self.assertEqual(r.status_code, 403, r.content)
        upload.assert_not_called()

    @patch('api.services.leitura.iniciar_analise')
    def test_leitura_de_aluno_de_turma_nao_vinculada_e_recusada(self, iniciar):
        self.entrar(self.prof_a1)
        audio = SimpleUploadedFile('a.webm', b'fake', content_type='audio/webm')
        r = self.client.post('/api/leitura/analisar/', {
            'audio': audio, 'aluno_id': str(self.aluno_turma_extra.id),
        }, format='multipart')
        self.assertEqual(r.status_code, 403, r.content)
        iniciar.assert_not_called()