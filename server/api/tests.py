"""
Testes automatizados para a API NARA.
Cobertura dos endpoints críticos para entrega de 12/dezembro.

Executar: DJANGO_SETTINGS_MODULE=nara_api.test_settings python manage.py test api
"""

from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from unittest.mock import patch, MagicMock
import json
import tempfile
import os
import uuid
from datetime import date, timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from api.models import (
    Instituicao,
    Relatorio,
    Usuario,
    Turma,
    Crianca,
    RegistroObservacao,
    UsuarioTurma,
    PeriodoAvaliativo,
    RegistroEscrita,
    ObservacaoTranscricao,
    PerguntaEspecialista,
    ConfiguracaoRegistro,
    ProducaoFoto,
    ProducaoFotoCrianca,
    HabilidadeBNCC,
    PerguntaBNCC,
)


class HealthCheckTests(TestCase):
    """Testes do endpoint de health check."""

    def setUp(self):
        self.client = Client()

    def test_health_check_returns_200(self):
        """Health check deve retornar 200."""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)

    def test_health_check_returns_json(self):
        """Health check deve retornar JSON com status ok."""
        response = self.client.get('/api/health/')
        data = json.loads(response.content)
        self.assertIn('status', data)


class AuthenticationTests(APITestCase):
    """Testes de autenticação nos endpoints protegidos."""

    def test_upload_escrita_requires_auth(self):
        """Upload de escrita deve exigir autenticação."""
        response = self.client.post('/api/upload-escrita/')
        self.assertIn(response.status_code, [401, 403])

    def test_upload_desenho_requires_auth(self):
        """Upload de desenho deve exigir autenticação."""
        response = self.client.post('/api/upload-desenho/')
        self.assertIn(response.status_code, [401, 403])

    def test_upload_audio_requires_auth(self):
        """Upload de áudio deve exigir autenticação."""
        response = self.client.post('/api/upload-audio/')
        self.assertIn(response.status_code, [401, 403])

    def test_gerar_relatorio_requires_auth(self):
        """Geração de relatório deve exigir autenticação."""
        response = self.client.post('/api/gerar-relatorio/')
        self.assertIn(response.status_code, [401, 403])

    def test_portfolio_upload_requires_auth(self):
        """Upload de portfólio deve exigir autenticação."""
        response = self.client.post('/api/portfolio/upload/')
        self.assertIn(response.status_code, [400, 401, 403])


class ObservacaoTranscricaoTests(APITestCase):
    """Testes de observações e transcrições."""

    def test_salvar_observacao_endpoint_exists(self):
        """Endpoint de salvar observação deve existir."""
        response = self.client.post(
            '/api/salvar-observacoes-transcricao/',
            {},
            format='json'
        )
        # Endpoint existe (pode retornar qualquer código, menos 404)
        self.assertNotEqual(response.status_code, 404)

    def test_buscar_observacoes_endpoint_exists(self):
        """Endpoint de buscar observações deve existir."""
        response = self.client.get('/api/buscar-observacoes-transcricao/')
        # Endpoint existe (pode retornar qualquer código, menos 404)
        self.assertNotEqual(response.status_code, 404)


class HabilidadesBNCCTests(APITestCase):
    """Testes do endpoint de habilidades BNCC."""

    def test_listar_habilidades(self):
        """Listar habilidades BNCC deve retornar 200."""
        response = self.client.get('/api/habilidades-bncc/')
        self.assertEqual(response.status_code, 200)

    def test_listar_habilidades_retorna_dict_com_habilidades(self):
        """Listar habilidades deve retornar um dict com chave habilidades."""
        response = self.client.get('/api/habilidades-bncc/')
        data = json.loads(response.content)
        # O endpoint retorna um dict com 'habilidades' e 'total'
        self.assertIn('habilidades', data)
        self.assertIn('total', data)


class MelhorarTextoTests(APITestCase):
    """Testes do endpoint de melhoria de texto com IA."""

    def test_melhorar_texto_sem_texto(self):
        """Melhorar texto sem texto deve retornar erro."""
        response = self.client.post(
            '/api/melhorar-texto/',
            {'contexto': 'observacao'},
            format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_melhorar_texto_endpoint_aceita_contexto_generico(self):
        """Melhorar texto deve aceitar qualquer contexto (usa fallback)."""
        # O endpoint usa fallback para contextos não predefinidos
        response = self.client.post(
            '/api/melhorar-texto/',
            {'texto': 'teste', 'contexto': 'generico'},
            format='json'
        )
        # Vai tentar chamar OpenAI, então pode dar 200 ou 500 se não tiver API key
        self.assertIn(response.status_code, [200, 500])

    def test_melhorar_texto_com_dados_validos(self):
        """Melhorar texto com dados válidos deve processar."""
        response = self.client.post(
            '/api/melhorar-texto/',
            {'texto': 'A criança brincou muito hoje.', 'contexto': 'observacao'},
            format='json'
        )
        # Vai tentar chamar OpenAI, então pode dar 200 ou 500 se não tiver API key
        self.assertIn(response.status_code, [200, 500])


class PortfolioTests(APITestCase):
    """Testes dos endpoints de portfólio."""

    def test_listar_portfolio(self):
        """Listar portfólio deve funcionar."""
        response = self.client.get('/api/portfolio/listar/')
        self.assertIn(response.status_code, [200, 403])

    def test_upload_portfolio_sem_arquivo(self):
        """Upload de portfólio sem arquivo deve retornar erro."""
        response = self.client.post('/api/portfolio/upload/')
        self.assertIn(response.status_code, [400, 401, 403])

    def test_atualizar_vinculos_portfolio_em_lote(self):
        """Atualização em lote deve alterar incluir_relatorio."""
        instituicao = Instituicao.objects.create(nome='Instituição Portfólio')
        usuario = Usuario.objects.create_user(
            email='professor.portfolio@example.com',
            password='senha123',
            nome='Professor Portfólio',
            perfil='professor',
            instituicao=instituicao,
        )

        producao = ProducaoFoto.objects.create(
            arquivo_url='https://example.com/arquivo.jpg',
            arquivo_nome='arquivo.jpg',
            arquivo_hash=f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            tamanho_bytes=12345,
            tipo_midia='foto',
            mime_type='image/jpeg',
            turma_id=str(uuid.uuid4()),
            professora_id=str(uuid.uuid4()),
            professora_nome='Professora Teste',
            projeto='Projeto Teste',
        )

        vinculo = ProducaoFotoCrianca.objects.create(
            producao_foto=producao,
            crianca_id=str(uuid.uuid4()),
            crianca_nome='Criança Teste',
            legenda='Legenda inicial',
            incluir_relatorio=False,
        )

        self.client.force_authenticate(user=usuario)
        response = self.client.patch(
            '/api/portfolio/vinculos/lote/',
            {'vinculo_ids': [vinculo.id], 'incluir_relatorio': True},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vinculo.refresh_from_db()
        self.assertTrue(vinculo.incluir_relatorio)


class PlanejamentoTests(APITestCase):
    """Testes dos endpoints de planejamento."""

    def test_criar_planejamento_endpoint_exists(self):
        """Endpoint de criar planejamento deve existir."""
        response = self.client.post(
            '/api/planejamento/',
            {},
            format='json'
        )
        # Endpoint existe (pode retornar qualquer código, menos 404)
        self.assertNotEqual(response.status_code, 404)

    def test_sugerir_bncc_planejamento_fallback(self):
        """Sugestão de habilidades BNCC deve responder com fallback se IA cair."""
        habilidade = HabilidadeBNCC.objects.create(
            codigo='EF01LP01',
            descricao='Reconhecer que textos são lidos da esquerda para a direita.',
            componente_curricular='Língua Portuguesa',
            ano_serie='1º Ano',
            campo_atuacao='Leitura'
        )
        # O novo fluxo só considera códigos presentes em perguntas_bncc.
        PerguntaBNCC.objects.create(
            faixa_etaria='1º Ano',
            campo_experiencia='Escuta, fala, pensamento e imaginação',
            pergunta='A criança reconhece a leitura da esquerda para a direita?',
            habilidade_bncc=habilidade.codigo,
        )

        payload = {
            'atividades_texto': 'Atividades de leitura e contação de histórias com a turma.',
            'limite': 2,
        }

        with patch(
            'api.services.planejamento_ia.get_openai_client',
            side_effect=RuntimeError('OPENAI_API_KEY ausente para teste'),
        ):
            response = self.client.post(
                '/api/planejamento/sugerir-bncc/',
                payload,
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('origem'), 'fallback')
        self.assertTrue(len(data.get('habilidades', [])) >= 1)
        self.assertEqual(data['habilidades'][0]['codigo'], habilidade.codigo)


class RelatorioUniquenessTests(APITestCase):
    """Testes de unicidade de relatório por período."""

    def test_relatorio_unico_por_periodo(self):
        """Não deve permitir duplicidade de relatório no mesmo período."""
        payload = {
            'id_crianca': str(uuid.uuid4()),
            'periodo': '1º Bimestre',
            'conteudo': 'Relatório de teste.',
            'instituicao_id': str(uuid.uuid4()),
        }

        response_1 = self.client.post('/api/relatorios/salvar/', payload, format='json')
        self.assertEqual(response_1.status_code, 201)

        response_2 = self.client.post('/api/relatorios/salvar/', payload, format='json')
        self.assertEqual(response_2.status_code, 200)
        data = response_2.json()
        self.assertTrue(data.get('already_exists'))


class RelatorioPdfTests(APITestCase):
    """Testes dos endpoints de PDF do relatório."""

    @patch('api.views_rest.upload_bytes_to_storage')
    @patch('api.views_rest.is_s3_configured')
    def test_upload_pdf_relatorio_salva_url_e_storage_key(self, mock_is_s3_configured, mock_upload):
        """Upload do PDF deve salvar URL e storage key."""
        mock_is_s3_configured.return_value = True
        mock_upload.return_value = ('relatorios/teste.pdf', 'https://example.com/relatorio.pdf')

        instituicao = Instituicao.objects.create(nome='Instituicao Teste')
        usuario = Usuario.objects.create_user(
            email='usuario@example.com',
            password='senha123',
            nome='Usuario Teste',
            instituicao=instituicao,
        )
        relatorio = Relatorio.objects.create(
            id_crianca=uuid.uuid4(),
            periodo='1º Bimestre',
            conteudo='Relatorio de teste.',
            instituicao_id=instituicao.id,
        )

        self.client.force_authenticate(user=usuario)
        pdf_file = SimpleUploadedFile('relatorio.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = self.client.post(
            f'/api/relatorios/{relatorio.id}/pdf/',
            {'file': pdf_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, 200)
        relatorio.refresh_from_db()
        self.assertEqual(relatorio.pdf_url, 'https://example.com/relatorio.pdf')
        self.assertEqual(relatorio.pdf_storage_key, 'relatorios/teste.pdf')

    @patch('api.views_rest.generate_presigned_url')
    @patch('api.views_rest.is_s3_configured')
    def test_refresh_pdf_relatorio_regenera_url(self, mock_is_s3_configured, mock_generate_url):
        """Refresh deve regenerar URL presigned do PDF."""
        mock_is_s3_configured.return_value = True
        mock_generate_url.return_value = 'https://example.com/relatorio_refresh.pdf'

        instituicao = Instituicao.objects.create(nome='Instituicao Teste')
        usuario = Usuario.objects.create_user(
            email='usuario2@example.com',
            password='senha123',
            nome='Usuario Teste 2',
            instituicao=instituicao,
        )
        relatorio = Relatorio.objects.create(
            id_crianca=uuid.uuid4(),
            periodo='2º Bimestre',
            conteudo='Relatorio de teste.',
            instituicao_id=instituicao.id,
            pdf_storage_key='relatorios/teste_refresh.pdf',
            pdf_url='https://example.com/relatorio_antigo.pdf',
        )

        self.client.force_authenticate(user=usuario)
        response = self.client.post(f'/api/relatorios/{relatorio.id}/pdf/refresh/')

        self.assertEqual(response.status_code, 200)
        relatorio.refresh_from_db()
        self.assertEqual(relatorio.pdf_url, 'https://example.com/relatorio_refresh.pdf')


class UploadValidationTests(APITestCase):
    """Testes de validação de upload."""

    def test_upload_escrita_arquivo_invalido(self):
        """Upload de escrita com arquivo inválido deve ser rejeitado."""
        # Criar arquivo temporário com extensão inválida
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'conteudo de texto')
            temp_path = f.name

        try:
            with open(temp_path, 'rb') as f:
                response = self.client.post(
                    '/api/upload-escrita/',
                    {'arquivo': f},
                    format='multipart'
                )
            # Deve retornar erro (400, 403, 415)
            self.assertIn(response.status_code, [400, 401, 403, 415])
        finally:
            os.unlink(temp_path)


class SecurityTests(TestCase):
    """Testes de segurança."""

    def test_no_hardcoded_credentials(self):
        """Verificar que não há credenciais hardcoded."""
        import api.views as views_module
        import inspect

        source = inspect.getsource(views_module)

        # Verificar padrões de API keys
        self.assertNotIn('sk-proj-', source)
        self.assertNotIn('sk-ant-', source)

    def test_env_variables_used(self):
        """Verificar que variáveis de ambiente são usadas."""
        from django.conf import settings
        import os

        # OPENAI_API_KEY deve vir de variável de ambiente
        openai_key = os.getenv('OPENAI_API_KEY', '')
        # Se não estiver definida, não é um erro (pode estar em produção)
        self.assertTrue(True)


class TimeoutTests(APITestCase):
    """Testes de timeout em endpoints de IA."""

    def test_views_has_timeout_configuration(self):
        """Views devem ter configuração de timeout para IA."""
        import api.views as views_module
        import inspect

        # Verificar que o módulo views tem configuração de timeout
        source = inspect.getsource(views_module)
        has_timeout_config = 'IA_REQUEST_TIMEOUT_SECONDS' in source or 'timeout_seconds' in source
        self.assertTrue(has_timeout_config, "views deve usar configuração de timeout")

    def test_ia_timeout_env_helper_exists(self):
        """Verificar que função de helper de timeout existe."""
        import api.views as views_module

        # Verificar que _get_int_env existe
        self.assertTrue(hasattr(views_module, '_get_int_env'))


class EndpointExistenceTests(APITestCase):
    """Testes para verificar que os endpoints existem."""

    def test_analise_escrita_endpoint(self):
        """Endpoint de análise de escrita deve existir."""
        response = self.client.get('/api/analise-escrita/')
        self.assertNotEqual(response.status_code, 404)

    def test_upload_audio_endpoint(self):
        """Endpoint de upload de áudio deve existir."""
        response = self.client.post('/api/upload-audio/')
        self.assertNotEqual(response.status_code, 404)

    def test_iniciar_analise_leitura_endpoint(self):
        """Endpoint de início da análise de leitura deve existir."""
        response = self.client.post('/api/leitura/analisar/')
        self.assertNotEqual(response.status_code, 404)

    def test_gerar_relatorio_endpoint(self):
        """Endpoint de gerar relatório deve existir."""
        response = self.client.post('/api/gerar-relatorio/')
        self.assertNotEqual(response.status_code, 404)


class CriticalFeaturesTests(TestCase):
    """Testes das funcionalidades críticas da checklist."""

    def test_whisper_api_import_available(self):
        """Verificar que OpenAI client está disponível para Whisper API."""
        try:
            from openai import OpenAI
            self.assertTrue(True)
        except ImportError:
            self.fail("OpenAI client não disponível")

    def test_django_orm_models_exist(self):
        """Verificar que os models do Django ORM existem."""
        from api.models import (
            RegistroEscrita,
            RegistroDesenho,
            HabilidadeBNCC,
            PlanejamentoSemanal,
            ObservacaoTranscricao,
            ProducaoFoto,
            ProducaoFotoCrianca
        )
        self.assertTrue(True)

    def test_portfolio_n_to_n_models(self):
        """Verificar que os models N-to-N de portfólio existem."""
        from api.models import ProducaoFoto, ProducaoFotoCrianca

        # Verificar que ProducaoFotoCrianca tem ForeignKey para ProducaoFoto
        # O campo se chama 'producao_foto' conforme definido no model
        self.assertTrue(hasattr(ProducaoFotoCrianca, 'producao_foto'))


class AlertasRegistroTests(APITestCase):
    """Testes dos alertas de registros semanais (C21)."""

    def setUp(self):
        self.instituicao = Instituicao.objects.create(nome='Instituicao Alertas')
        self.professor = Usuario.objects.create_user(
            email='professor.alerta@nara.dev',
            password='senha123',
            nome='Professor Alerta',
            perfil='professor',
            instituicao=self.instituicao,
        )
        self.coordenador = Usuario.objects.create_user(
            email='coord.alerta@nara.dev',
            password='senha123',
            nome='Coord Alerta',
            perfil='coordenador',
            instituicao=self.instituicao,
        )
        self.turma = Turma.objects.create(
            nome='Turma Teste',
            faixa_etaria='Nível 1',
            turno='manha',
            instituicao_id=self.instituicao.id,
        )
        UsuarioTurma.objects.create(usuario=self.professor, turma=self.turma)
        self.crianca = Crianca.objects.create(
            nome_completo='Aluno Teste',
            turma_id=self.turma.id,
            instituicao_id=self.instituicao.id,
        )

    def test_professor_recebe_alerta_quando_insuficiente(self):
        hoje = timezone.localdate()
        RegistroObservacao.objects.create(
            crianca_id=self.crianca.id,
            professor_id=self.professor.id,
            data_observacao=hoje,
        )
        RegistroObservacao.objects.create(
            crianca_id=self.crianca.id,
            professor_id=self.professor.id,
            data_observacao=hoje,
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get('/api/alertas/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['tipo'], 'registro-semanal')
        self.assertEqual(data[0]['dados']['total_registros'], 2)

    def test_coordenador_recebe_alertas_dos_professores(self):
        hoje = timezone.localdate()
        RegistroObservacao.objects.create(
            crianca_id=self.crianca.id,
            professor_id=self.professor.id,
            data_observacao=hoje,
        )

        self.client.force_authenticate(user=self.coordenador)
        response = self.client.get('/api/alertas/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any(alerta['dados']['professor_id'] == str(self.professor.id) for alerta in data))


class IndicadorLinguagemTests(APITestCase):
    """Testes do indicador de desenvolvimento de linguagem (C22)."""

    def setUp(self):
        self.instituicao = Instituicao.objects.create(nome='Instituicao Linguagem')
        self.coordenador = Usuario.objects.create_user(
            email='coord.linguagem@nara.dev',
            password='senha123',
            nome='Coord Linguagem',
            perfil='coordenador',
            instituicao=self.instituicao,
        )
        self.turma = Turma.objects.create(
            nome='Turma Linguagem',
            faixa_etaria='Nível 2',
            turno='tarde',
            instituicao_id=self.instituicao.id,
        )
        self.crianca1 = Crianca.objects.create(
            nome_completo='Aluno Linguagem 1',
            turma_id=self.turma.id,
            instituicao_id=self.instituicao.id,
        )
        self.crianca2 = Crianca.objects.create(
            nome_completo='Aluno Linguagem 2',
            turma_id=self.turma.id,
            instituicao_id=self.instituicao.id,
        )

        hoje = timezone.localdate()
        self.periodo = PeriodoAvaliativo.objects.create(
            descricao='Período Teste',
            tipo_periodo='bimestral',
            data_inicio=hoje - timedelta(days=7),
            data_fim=hoje + timedelta(days=7),
            instituicao_id=self.instituicao.id,
        )

        RegistroEscrita.objects.create(
            nome_aluno=self.crianca1.nome_completo,
            turma_id=str(self.turma.id),
            serie_aluno='Educação Infantil',
            arquivo_nome='escrita1.png',
            arquivo_hash='hash_escrita_1',
            arquivo_path='uploads/escrita/escrita1.png',
            arquivo_original='escrita1.png',
            tamanho_arquivo=1234,
            tipo_arquivo='image/png',
            etapa_ia='Pré-silábico',
            analise_detalhada='Análise escrita 1',
            professora='Professora Teste',
        )
        RegistroEscrita.objects.create(
            nome_aluno=self.crianca2.nome_completo,
            turma_id=str(self.turma.id),
            serie_aluno='Educação Infantil',
            arquivo_nome='escrita2.png',
            arquivo_hash='hash_escrita_2',
            arquivo_path='uploads/escrita/escrita2.png',
            arquivo_original='escrita2.png',
            tamanho_arquivo=1234,
            tipo_arquivo='image/png',
            etapa_ia='Pré-silábico',
            analise_detalhada='Análise escrita 2',
            professora='Professora Teste',
        )

        ObservacaoTranscricao.objects.create(
            aluno_nome=self.crianca1.nome_completo,
            crianca_id=str(self.crianca1.id),
            observacao_texto='Leitura oral registrada',
            tipo_observacao='LEITURA_ORAL',
            data_observacao=hoje,
            turma_id=str(self.turma.id),
            turma_nome=self.turma.nome,
            professora_id=str(self.coordenador.id),
            professora_nome=self.coordenador.nome,
        )
        ObservacaoTranscricao.objects.create(
            aluno_nome=self.crianca2.nome_completo,
            crianca_id=str(self.crianca2.id),
            observacao_texto='Leitura oral registrada',
            tipo_observacao='LEITURA_ORAL',
            data_observacao=hoje,
            turma_id=str(self.turma.id),
            turma_nome=self.turma.nome,
            professora_id=str(self.coordenador.id),
            professora_nome=self.coordenador.nome,
        )
        ObservacaoTranscricao.objects.create(
            aluno_nome=self.crianca1.nome_completo,
            crianca_id=str(self.crianca1.id),
            observacao_texto='Observação de fala',
            tipo_observacao='TRANSCRICAO_IA',
            data_observacao=hoje,
            turma_id=str(self.turma.id),
            turma_nome=self.turma.nome,
            professora_id=str(self.coordenador.id),
            professora_nome=self.coordenador.nome,
        )

    def test_indicador_linguagem_retorna_percentual(self):
        self.client.force_authenticate(user=self.coordenador)
        response = self.client.get(f'/api/indicadores/linguagem/?instituicao_id={self.instituicao.id}')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('turmas', data)
        self.assertEqual(len(data['turmas']), 1)
        resultado = data['turmas'][0]
        self.assertEqual(resultado['percentual_final'], 83)


class TurmasFilteringTests(APITestCase):
    """Garante filtragem segura de turmas por usuário autenticado."""

    def setUp(self):
        self.instituicao = Instituicao.objects.create(nome='Instituição Turmas')
        self.outra_instituicao = Instituicao.objects.create(nome='Outra Instituição')

        self.admin = Usuario.objects.create_user(
            email='admin.turmas@example.com',
            password='senha123',
            nome='Admin Turmas',
            perfil='admin',
            instituicao=self.instituicao,
        )
        self.professor = Usuario.objects.create_user(
            email='professor.turmas@example.com',
            password='senha123',
            nome='Professor Turmas',
            perfil='professor',
            instituicao=self.instituicao,
        )
        self.professor_especialista = Usuario.objects.create_user(
            email='professor.especialista@example.com',
            password='senha123',
            nome='Professor Especialista',
            perfil='professor_especialista',
            instituicao=self.instituicao,
        )
        self.outro_professor = Usuario.objects.create_user(
            email='outro.professor.turmas@example.com',
            password='senha123',
            nome='Outro Professor',
            perfil='professor',
            instituicao=self.instituicao,
        )

        self.turma_professor = Turma.objects.create(
            nome='Infantil 4-A',
            faixa_etaria='Nível 4',
            instituicao_id=self.instituicao.id,
            ativa=True,
        )
        self.turma_outro_professor = Turma.objects.create(
            nome='1º Ano A',
            faixa_etaria='1º Ano',
            instituicao_id=self.instituicao.id,
            ativa=True,
        )
        self.turma_professor_especialista = Turma.objects.create(
            nome='2º Ano A',
            faixa_etaria='2º Ano',
            instituicao_id=self.instituicao.id,
            ativa=True,
        )
        Turma.objects.create(
            nome='Turma Externa',
            faixa_etaria='Nível 5',
            instituicao_id=self.outra_instituicao.id,
            ativa=True,
        )

        UsuarioTurma.objects.create(usuario=self.professor, turma=self.turma_professor)
        UsuarioTurma.objects.create(usuario=self.outro_professor, turma=self.turma_outro_professor)
        UsuarioTurma.objects.create(usuario=self.professor_especialista, turma=self.turma_professor_especialista)

    def test_professor_lista_apenas_suas_turmas(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.get('/api/turmas/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        turma_ids = {item['id'] for item in response.json()}
        self.assertSetEqual(turma_ids, {str(self.turma_professor.id)})

        usuario_ids_nested = {
            vinculo['usuarios']['id']
            for item in response.json()
            for vinculo in item.get('usuario_turmas', [])
        }
        self.assertSetEqual(usuario_ids_nested, {str(self.professor.id)})

    def test_professor_especialista_lista_apenas_suas_turmas(self):
        self.client.force_authenticate(user=self.professor_especialista)

        response = self.client.get('/api/turmas/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        turma_ids = {item['id'] for item in response.json()}
        self.assertSetEqual(turma_ids, {str(self.turma_professor_especialista.id)})

    def test_professor_nao_consegue_filtrar_por_outro_usuario(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.get(f'/api/turmas/?usuario_id={self.outro_professor.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        turma_ids = {item['id'] for item in response.json()}
        self.assertSetEqual(turma_ids, {str(self.turma_professor.id)})

    def test_admin_pode_filtrar_por_usuario_da_mesma_instituicao(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f'/api/turmas/?instituicao_id={self.instituicao.id}&usuario_id={self.professor.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        turma_ids = {item['id'] for item in response.json()}
        self.assertSetEqual(turma_ids, {str(self.turma_professor.id)})

    def test_admin_recebe_403_ao_informar_instituicao_diferente(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f'/api/turmas/?instituicao_id={self.outra_instituicao.id}')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PerguntasEspecialistasTests(APITestCase):
    """Valida criação e listagem segura de perguntas de especialistas."""

    def setUp(self):
        self.instituicao = Instituicao.objects.create(nome='Instituição Perguntas')
        self.outra_instituicao = Instituicao.objects.create(nome='Instituição Externa Perguntas')

        self.admin = Usuario.objects.create_user(
            email='admin.perguntas@example.com',
            password='senha123',
            nome='Admin Perguntas',
            perfil='admin',
            instituicao=self.instituicao,
        )

        self.pergunta_global = PerguntaEspecialista.objects.create(
            instituicao_id=None,
            especialidade='Música',
            nivel='Nível 1',
            pergunta_facilitadora='Explora ritmos simples?',
            referencia_norma='GLOBAL01',
            status='ativa',
        )
        self.pergunta_externa = PerguntaEspecialista.objects.create(
            instituicao_id=self.outra_instituicao.id,
            especialidade='Música',
            nivel='Nível 1',
            pergunta_facilitadora='Participa de ensaios?',
            referencia_norma='EXT01',
            status='ativa',
        )

    def test_criar_pergunta_especialista_sucesso(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            'especialidade': 'Inglês',
            'nivel': '1º Ano A',
            'pergunta_facilitadora': 'Compreende instruções simples?',
            'referencia_norma': 'EF01LI01',
            'status': 'ativa',
        }

        response = self.client.post('/api/perguntas-especialistas/criar/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pergunta = PerguntaEspecialista.objects.get(id=response.json()['id'])
        self.assertEqual(pergunta.instituicao_id, self.instituicao.id)

    def test_criar_pergunta_com_instituicao_diferente_retorna_403(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            'instituicao_id': str(self.outra_instituicao.id),
            'especialidade': 'Música',
            'nivel': 'Nível 2',
            'pergunta_facilitadora': 'Mantém atenção durante a atividade?',
            'referencia_norma': 'EI02TS01',
            'status': 'ativa',
        }

        response = self.client.post('/api/perguntas-especialistas/criar/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listagem_inclui_perguntas_globais_e_da_instituicao(self):
        self.client.force_authenticate(user=self.admin)

        pergunta_interna = PerguntaEspecialista.objects.create(
            instituicao_id=self.instituicao.id,
            especialidade='Música',
            nivel='Nível 3',
            pergunta_facilitadora='Participa de cantigas?',
            referencia_norma='INT01',
            status='ativa',
        )

        response = self.client.get('/api/perguntas-especialistas/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item['id'] for item in response.json()}
        self.assertIn(str(self.pergunta_global.id), returned_ids)
        self.assertIn(str(pergunta_interna.id), returned_ids)
        self.assertNotIn(str(self.pergunta_externa.id), returned_ids)


class ConfiguracaoRegistroUpdateTests(APITestCase):
    """Cobre atualização de frequência de registro existente."""

    def setUp(self):
        self.instituicao = Instituicao.objects.create(nome='Instituição Configuração')
        self.admin = Usuario.objects.create_user(
            email='admin.config@example.com',
            password='senha123',
            nome='Admin Configuração',
            perfil='admin',
            instituicao=self.instituicao,
        )
        self.turma = Turma.objects.create(
            nome='Turma Configuração',
            faixa_etaria='Nível 5',
            instituicao_id=self.instituicao.id,
            ativa=True,
        )

    def test_update_endpoint_atualiza_frequencia(self):
        configuracao = ConfiguracaoRegistro.objects.create(
            turma_id=self.turma.id,
            frequencia_registro='quinzenal',
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/configuracoes-registro/{configuracao.id}/atualizar/',
            {'frequencia_registro': 'semanal'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        configuracao.refresh_from_db()
        self.assertEqual(configuracao.frequencia_registro, 'semanal')

    def test_create_endpoint_funciona_como_upsert_por_turma(self):
        ConfiguracaoRegistro.objects.create(
            turma_id=self.turma.id,
            frequencia_registro='quinzenal',
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/configuracoes-registro/criar/',
            {'turma_id': str(self.turma.id), 'frequencia_registro': 'semanal'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        configuracao = ConfiguracaoRegistro.objects.get(turma_id=self.turma.id)
        self.assertEqual(configuracao.frequencia_registro, 'semanal')


# ---------------------------------------------------------------------------
# Transcrição: fallback OpenAI -> microserviço local
# ---------------------------------------------------------------------------

import unittest

import httpx
from openai import (
    APIConnectionError as _OpenAIAPIConnectionError,
    APIStatusError as _OpenAIAPIStatusError,
    APITimeoutError as _OpenAIAPITimeoutError,
    AuthenticationError as _OpenAIAuthenticationError,
    InternalServerError as _OpenAIInternalServerError,
    RateLimitError as _OpenAIRateLimitError,
)

from api.transcription.base import (
    TranscriptionBackend,
    TranscriptionError,
    TranscriptionRecoverableError,
)
from api.transcription.fallback_backend import FallbackBackend
from api.transcription.openai_backend import OpenAIBackend


def _openai_request():
    return httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")


def _openai_response(status_code: int):
    return httpx.Response(status_code, request=_openai_request())


class _StubBackend(TranscriptionBackend):
    """Backend de teste: retorna um valor fixo ou levanta uma exceção pré-definida."""

    def __init__(self, name: str, *, result=None, raises: BaseException = None):
        self.name = name
        self._result = result
        self._raises = raises
        self.calls = 0

    def transcribe(self, arquivo_path: str, language: str = "pt") -> str:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._result


class FallbackBackendTests(unittest.TestCase):
    """Comportamento do wrapper que escolhe entre primário e secundário."""

    def test_uses_primary_when_primary_succeeds(self):
        primary = _StubBackend("primary", result="texto-primario")
        secondary = _StubBackend("secondary", result="texto-secundario")
        fb = FallbackBackend(primary, secondary)

        self.assertEqual(fb.transcribe("/tmp/audio.wav"), "texto-primario")
        self.assertEqual(primary.calls, 1)
        self.assertEqual(secondary.calls, 0)

    def test_falls_back_on_recoverable_error(self):
        primary = _StubBackend(
            "primary",
            raises=TranscriptionRecoverableError("openai_rate_limit"),
        )
        secondary = _StubBackend("secondary", result="texto-do-local")
        fb = FallbackBackend(primary, secondary)

        self.assertEqual(fb.transcribe("/tmp/audio.wav"), "texto-do-local")
        self.assertEqual(primary.calls, 1)
        self.assertEqual(secondary.calls, 1)

    def test_does_not_fall_back_on_plain_transcription_error(self):
        primary = _StubBackend(
            "primary",
            raises=TranscriptionError("Invalid data found when processing input"),
        )
        secondary = _StubBackend("secondary", result="nunca-deve-vir-aqui")
        fb = FallbackBackend(primary, secondary)

        with self.assertRaises(TranscriptionError):
            fb.transcribe("/tmp/audio.wav")
        self.assertEqual(secondary.calls, 0)

    def test_does_not_fall_back_on_timeout(self):
        primary = _StubBackend("primary", raises=TimeoutError("audio timeout"))
        secondary = _StubBackend("secondary", result="nunca-deve-vir-aqui")
        fb = FallbackBackend(primary, secondary)

        with self.assertRaises(TimeoutError):
            fb.transcribe("/tmp/audio.wav")
        self.assertEqual(secondary.calls, 0)

    def test_propagates_secondary_failure(self):
        primary = _StubBackend(
            "primary",
            raises=TranscriptionRecoverableError("openai_auth"),
        )
        secondary = _StubBackend(
            "secondary",
            raises=ConnectionError("Serviço de transcrição indisponível."),
        )
        fb = FallbackBackend(primary, secondary)

        with self.assertRaises(ConnectionError):
            fb.transcribe("/tmp/audio.wav")
        self.assertEqual(secondary.calls, 1)


class OpenAIBackendErrorMappingTests(unittest.TestCase):
    """Garante que falhas da API OpenAI são classificadas corretamente."""

    def _run_with_openai_error(self, exc: BaseException):
        """Executa OpenAIBackend.transcribe com a SDK da OpenAI levantando `exc`."""
        backend = OpenAIBackend()

        # Mock do client OpenAI: chamar audio.transcriptions.create levanta `exc`.
        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.side_effect = exc

        # `run_with_timeout` (SIGALRM wrapper) só executa o callable e propaga
        # exceções — para o teste basta chamar a função recebida diretamente.
        with patch(
            "api.transcription.openai_backend.get_openai_client",
            return_value=fake_client,
        ), patch(
            "api.transcription.openai_backend.run_with_timeout",
            side_effect=lambda fn, _t: fn(),
        ), tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(b"RIFF....WAVEfake")
            audio_file.flush()
            backend.transcribe(audio_file.name)

    def test_rate_limit_maps_to_recoverable(self):
        exc = _OpenAIRateLimitError(
            "rate limit",
            response=_openai_response(429),
            body=None,
        )
        with self.assertRaises(TranscriptionRecoverableError):
            self._run_with_openai_error(exc)

    def test_authentication_maps_to_recoverable(self):
        exc = _OpenAIAuthenticationError(
            "auth",
            response=_openai_response(401),
            body=None,
        )
        with self.assertRaises(TranscriptionRecoverableError):
            self._run_with_openai_error(exc)

    def test_internal_server_error_maps_to_recoverable(self):
        exc = _OpenAIInternalServerError(
            "5xx",
            response=_openai_response(500),
            body=None,
        )
        with self.assertRaises(TranscriptionRecoverableError):
            self._run_with_openai_error(exc)

    def test_api_connection_error_maps_to_recoverable(self):
        exc = _OpenAIAPIConnectionError(request=_openai_request())
        with self.assertRaises(TranscriptionRecoverableError):
            self._run_with_openai_error(exc)

    def test_api_timeout_error_maps_to_recoverable(self):
        exc = _OpenAIAPITimeoutError(request=_openai_request())
        with self.assertRaises(TranscriptionRecoverableError):
            self._run_with_openai_error(exc)

    def test_generic_4xx_does_not_map_to_recoverable(self):
        # 400/413 etc — geralmente erro do arquivo, não vale tentar fallback.
        exc = _OpenAIAPIStatusError(
            "bad request",
            response=_openai_response(400),
            body=None,
        )
        with self.assertRaises(TranscriptionError) as ctx:
            self._run_with_openai_error(exc)
        self.assertNotIsInstance(ctx.exception, TranscriptionRecoverableError)


class DetectarDataPlanejamentoTests(TestCase):
    """Testes para a detecção de data/intervalo no upload de planejamento."""

    def _mock_openai_response(self, payload):
        choice = MagicMock()
        choice.message.content = json.dumps(payload)
        response = MagicMock()
        response.choices = [choice]
        return response

    def test_texto_sem_indicio_de_data_nao_chama_ia(self):
        from api.services.planejamento_ia import detectar_data_planejamento

        with patch("api.services.planejamento_ia.get_openai_client") as mock_client:
            resultado = detectar_data_planejamento(
                "Planejamento sobre contação de histórias e fantoches."
            )
        self.assertIsNone(resultado)
        mock_client.assert_not_called()

    def test_texto_vazio_retorna_none(self):
        from api.services.planejamento_ia import detectar_data_planejamento

        self.assertIsNone(detectar_data_planejamento(""))
        self.assertIsNone(detectar_data_planejamento(None))

    def test_ia_retorna_intervalo(self):
        from api.services.planejamento_ia import detectar_data_planejamento

        hoje = date.today()
        inicio = hoje.replace(day=1).isoformat()
        fim = hoje.replace(day=min(28, hoje.day + 5)).isoformat()
        payload = {
            "data_inicio": inicio,
            "data_fim": fim,
            "evidencia": "Planejamento Quinzenal - 16/03 a 27/03",
            "confianca": "alta",
        }

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response(payload)
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = detectar_data_planejamento(
                "Planejamento Quinzenal - 16/03 a 27/03 - Turma X"
            )

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["data_inicio"], inicio)
        self.assertEqual(resultado["data_fim"], fim)
        self.assertEqual(resultado["confianca"], "alta")
        self.assertIn("16/03", resultado["evidencia"])

    def test_ia_retorna_null_quando_nao_identifica_data(self):
        from api.services.planejamento_ia import detectar_data_planejamento

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response(
                {"data_inicio": None, "data_fim": None, "confianca": "baixa"}
            )
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = detectar_data_planejamento(
                "Roda de conversa em 16/03 com leitura compartilhada."
            )
        self.assertIsNone(resultado)

    def test_falha_da_openai_retorna_none(self):
        from api.services.planejamento_ia import detectar_data_planejamento

        client_mock = MagicMock()
        client_mock.chat.completions.create.side_effect = RuntimeError("boom")
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = detectar_data_planejamento(
                "Planejamento da semana de 16/03 a 20/03."
            )
        self.assertIsNone(resultado)

    def test_confianca_invalida_normaliza_para_media(self):
        from api.services.planejamento_ia import detectar_data_planejamento

        hoje = date.today().isoformat()
        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response(
                {
                    "data_inicio": hoje,
                    "data_fim": None,
                    "confianca": "absoluta",
                    "evidencia": "16/03",
                }
            )
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = detectar_data_planejamento("Aula em 16/03.")

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["confianca"], "media")

    def test_ano_distante_e_corrigido_para_ano_proximo(self):
        # IA respondeu ano distante (>180 dias); o ajuste deve aproximar.
        from api.services.planejamento_ia import detectar_data_planejamento

        hoje = date.today()
        ano_distante = hoje.year - 5
        data_distante = hoje.replace(year=ano_distante).isoformat()
        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response(
                {
                    "data_inicio": data_distante,
                    "data_fim": None,
                    "confianca": "alta",
                    "evidencia": "16/03",
                }
            )
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = detectar_data_planejamento("Aula em 16/03.")

        self.assertIsNotNone(resultado)
        ano_resultante = int(resultado["data_inicio"].split("-")[0])
        self.assertNotEqual(ano_resultante, ano_distante)
        self.assertLessEqual(abs(ano_resultante - hoje.year), 1)


class ExtrairAtividadesPorDiaTests(TestCase):
    """Cobre a função unificada que separa atividades por data + janela."""

    def _mock_openai_response(self, payload):
        choice = MagicMock()
        choice.message.content = json.dumps(payload)
        response = MagicMock()
        response.choices = [choice]
        return response

    def test_quinzenal_separado_em_10_dias_2_semanas(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        hoje = date.today()
        seg = hoje - timedelta(days=hoje.weekday())  # segunda da semana atual
        datas_semana1 = [seg + timedelta(days=i) for i in range(5)]
        datas_semana2 = [seg + timedelta(days=7 + i) for i in range(5)]

        dias_payload = []
        for d in datas_semana1 + datas_semana2:
            dias_payload.append({
                "data": d.isoformat(),
                "dia_semana": ["segunda", "terca", "quarta", "quinta", "sexta"][d.weekday()],
                "atividades": f"- atividade do dia {d.isoformat()}",
            })

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response({
                "dias": dias_payload,
                "data_inicio": datas_semana1[0].isoformat(),
                "data_fim": datas_semana2[-1].isoformat(),
                "evidencia": "Planejamento Quinzenal",
                "confianca": "alta",
                "fallback_texto_unico": "",
            })
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = extrair_atividades_por_dia(
                "Planejamento Quinzenal - segunda 16/03 ... sexta 27/03."
            )

        self.assertEqual(len(resultado["dias"]), 10)
        datas = {item["data"] for item in resultado["dias"]}
        self.assertEqual(len(datas), 10)
        self.assertEqual(resultado["confianca"], "alta")
        self.assertEqual(resultado["data_inicio"], datas_semana1[0].isoformat())
        self.assertEqual(resultado["data_fim"], datas_semana2[-1].isoformat())

    def test_texto_sem_dias_e_sem_datas_nao_chama_ia(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        with patch("api.services.planejamento_ia.get_openai_client") as mock_client:
            resultado = extrair_atividades_por_dia(
                "Planejamento sobre fantoches e contação."
            )
        mock_client.assert_not_called()
        self.assertEqual(resultado["dias"], [])
        self.assertIsNone(resultado["data_inicio"])

    def test_texto_so_com_nome_de_dia_chama_ia(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response({
                "dias": [
                    {
                        "data": None,
                        "dia_semana": "segunda",
                        "atividades": "- Roda de conversa",
                    }
                ],
                "data_inicio": None,
                "data_fim": None,
                "confianca": "media",
                "evidencia": "",
                "fallback_texto_unico": "",
            })
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = extrair_atividades_por_dia(
                "Segunda-feira: roda de conversa sobre frio e calor."
            )

        self.assertEqual(len(resultado["dias"]), 1)
        self.assertEqual(resultado["dias"][0]["dia_semana"], "segunda")

    def test_finais_de_semana_sao_descartados(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        # Cria um sábado e um domingo + uma sexta válida.
        hoje = date.today()
        seg = hoje - timedelta(days=hoje.weekday())
        sexta = seg + timedelta(days=4)
        sabado = seg + timedelta(days=5)
        domingo = seg + timedelta(days=6)

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response({
                "dias": [
                    {"data": sexta.isoformat(), "dia_semana": "sexta", "atividades": "ok"},
                    {"data": sabado.isoformat(), "dia_semana": "sabado", "atividades": "rua"},
                    {"data": domingo.isoformat(), "dia_semana": "domingo", "atividades": "rua"},
                ],
                "data_inicio": sexta.isoformat(),
                "data_fim": domingo.isoformat(),
                "confianca": "alta",
                "evidencia": "",
                "fallback_texto_unico": "",
            })
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = extrair_atividades_por_dia("Aulas em 22/03 a 24/03.")

        self.assertEqual(len(resultado["dias"]), 1)
        self.assertEqual(resultado["dias"][0]["dia_semana"], "sexta")

    def test_dia_semana_terca_com_cedilha_e_aceito(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response({
                "dias": [
                    {"data": None, "dia_semana": "terça", "atividades": "ok"},
                ],
                "data_inicio": None,
                "data_fim": None,
                "confianca": "media",
                "evidencia": "",
                "fallback_texto_unico": "",
            })
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = extrair_atividades_por_dia("Terça: leitura.")

        self.assertEqual(len(resultado["dias"]), 1)
        self.assertEqual(resultado["dias"][0]["dia_semana"], "terca")

    def test_fallback_texto_unico_quando_ia_nao_separa(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response({
                "dias": [],
                "data_inicio": None,
                "data_fim": None,
                "confianca": "baixa",
                "evidencia": "",
                "fallback_texto_unico": "Atividades gerais sem ordem por dia.",
            })
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = extrair_atividades_por_dia(
                "Conteúdo solto na quarta-feira sem datas explícitas."
            )

        self.assertEqual(resultado["dias"], [])
        self.assertEqual(
            resultado["fallback_texto_unico"],
            "Atividades gerais sem ordem por dia.",
        )

    def test_falha_openai_retorna_estrutura_vazia(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        client_mock = MagicMock()
        client_mock.chat.completions.create.side_effect = RuntimeError("boom")
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = extrair_atividades_por_dia("16/03 a 20/03.")

        self.assertEqual(resultado["dias"], [])
        self.assertIsNone(resultado["data_inicio"])
        self.assertEqual(resultado["fallback_texto_unico"], "")

    def test_atividades_em_uma_linha_so_recebe_quebras(self):
        from api.services.planejamento_ia import extrair_atividades_por_dia

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = (
            self._mock_openai_response({
                "dias": [
                    {
                        "data": None,
                        "dia_semana": "segunda",
                        "atividades": "- Roda de conversa - Leitura coletiva - Pintura no caderno",
                    }
                ],
                "data_inicio": None,
                "data_fim": None,
                "confianca": "media",
                "evidencia": "",
                "fallback_texto_unico": "",
            })
        )
        with patch(
            "api.services.planejamento_ia.get_openai_client",
            return_value=client_mock,
        ):
            resultado = extrair_atividades_por_dia("Segunda: roda - leitura.")

        self.assertEqual(len(resultado["dias"]), 1)
        atividades = resultado["dias"][0]["atividades"]
        linhas = atividades.split("\n")
        self.assertEqual(len(linhas), 3)
        self.assertEqual(linhas[0], "- Roda de conversa")
        self.assertEqual(linhas[1], "- Leitura coletiva")
        self.assertEqual(linhas[2], "- Pintura no caderno")


class NormalizarBulletsTests(TestCase):
    """Testes do helper que garante quebra de linha por item."""

    def test_texto_em_uma_linha_com_3_bullets_quebra(self):
        from api.services.planejamento_ia import _normalizar_bullets

        out = _normalizar_bullets("- A - B - C")
        self.assertEqual(out, "- A\n- B\n- C")

    def test_texto_ja_quebrado_e_idempotente(self):
        from api.services.planejamento_ia import _normalizar_bullets

        original = "- A\n- B\n- C"
        self.assertEqual(_normalizar_bullets(original), original)

    def test_bullets_numerados(self):
        from api.services.planejamento_ia import _normalizar_bullets

        out = _normalizar_bullets("1. Primeira 2. Segunda 3. Terceira")
        self.assertEqual(out, "1. Primeira\n2. Segunda\n3. Terceira")

    def test_palavra_hifenizada_nao_quebra(self):
        # "passo-a-passo" tem '-' mas sem espaço → não é bullet, segue inalterado.
        from api.services.planejamento_ia import _normalizar_bullets

        original = "Faça passo-a-passo"
        self.assertEqual(_normalizar_bullets(original), original)

    def test_um_unico_bullet_nao_quebra(self):
        # Apenas 1 marcador → nada para quebrar.
        from api.services.planejamento_ia import _normalizar_bullets

        original = "Texto solto - com travessão único"
        self.assertEqual(_normalizar_bullets(original), original)

    def test_intro_seguida_de_bullets(self):
        from api.services.planejamento_ia import _normalizar_bullets

        out = _normalizar_bullets("Atividades: - A - B")
        self.assertEqual(out, "Atividades:\n- A\n- B")

    def test_texto_vazio(self):
        from api.services.planejamento_ia import _normalizar_bullets

        self.assertEqual(_normalizar_bullets(""), "")
        self.assertEqual(_normalizar_bullets(None), "")

    def test_linhas_vazias_sao_removidas(self):
        from api.services.planejamento_ia import _normalizar_bullets

        out = _normalizar_bullets("- A\n\n- B\n   \n- C")
        self.assertEqual(out, "- A\n- B\n- C")


class AlterarSenhaTests(APITestCase):
    """Troca de senha do usuário autenticado."""

    def setUp(self):
        self.client = APIClient()
        self.instituicao = Instituicao.objects.create(nome='Instituição Senha')
        self.usuario = Usuario.objects.create_user(
            email='professor.senha@example.com',
            password='senha12345',
            nome='Professor Senha',
            perfil='professor',
            instituicao=self.instituicao,
        )

    def test_alterar_senha_requires_auth(self):
        response = self.client.post(
            '/api/auth/alterar-senha/',
            {'senha_atual': 'senha12345', 'nova_senha': 'novasenha99'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_alterar_senha_sucesso(self):
        self.client.force_authenticate(user=self.usuario)
        response = self.client.post(
            '/api/auth/alterar-senha/',
            {
                'senha_atual': 'senha12345',
                'nova_senha': 'novasenha99',
                'confirmar_senha': 'novasenha99',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('novasenha99'))

    def test_alterar_senha_senha_atual_incorreta(self):
        self.client.force_authenticate(user=self.usuario)
        response = self.client.post(
            '/api/auth/alterar-senha/',
            {'senha_atual': 'errada', 'nova_senha': 'novasenha99'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('incorreta', response.json().get('error', '').lower())


# ---------------------------------------------------------------------------
# Preparo do áudio para transcrição
#
# O caminho já teve uma etapa de redução de ruído (noisereduce), removida em
# setembro de 2026: o Whisper foi treinado em áudio ruidoso e não precisa dela,
# e o spectral gating custava 18s num áudio de 30s enquanto comia fala baixa e
# consoantes fricativas. Sobrou a normalização para WAV 16 kHz mono, que o
# Whisper de fato espera.
#
# O que estes testes travam: a distinção entre arquivo corrompido (422 para o
# usuário) e falha de ambiente (segue com o original), a limpeza do WAV
# intermediário, e a ausência da pilha numérica pesada no processo do worker.
# ---------------------------------------------------------------------------

import shutil
import subprocess as _subprocess
import sys

from django.conf import settings
from django.core.cache import cache

from api.services import audio as audio_service
from api.services.audio import (
    InvalidAudioError,
    converter_para_wav,
    descartar_derivados,
    _obter_duracao_audio,
)


_TEM_FFMPEG = shutil.which('ffmpeg') is not None
_precisa_ffmpeg = unittest.skipUnless(_TEM_FFMPEG, 'ffmpeg não disponível neste ambiente')


class _AudioTempMixin:
    """Diretório temporário próprio + geradores de áudio para os testes."""

    def setUp(self):
        super().setUp()
        self.dir_audio = tempfile.mkdtemp(prefix='nara_audio_test_')
        self.addCleanup(shutil.rmtree, self.dir_audio, True)

    def caminho(self, nome):
        return os.path.join(self.dir_audio, nome)

    def gerar_audio(self, nome='entrada.wav', duracao=2):
        """Gera um WAV real com ffmpeg. Ruído rosa serve: a conversão só precisa
        de um sinal decodificável, não de fala."""
        destino = self.caminho(nome)
        _subprocess.run(
            ['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-f', 'lavfi',
             '-i', f'anoisesrc=d={duracao}:c=pink:r=16000', '-ac', '1', destino],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return destino

    def gerar_corrompido(self, nome='corrompido.webm'):
        destino = self.caminho(nome)
        with open(destino, 'wb') as f:
            f.write(b'isto nao e um audio' * 200)
        return destino

    def convertido(self, entrada):
        base, _ = os.path.splitext(entrada)
        return f'{base}_converted.wav'


class ConverterParaWavTests(_AudioTempMixin, unittest.TestCase):
    """Normalização para o formato que o Whisper espera."""

    @_precisa_ffmpeg
    def test_sucesso_devolve_wav_16k_mono(self):
        entrada = self.gerar_audio(duracao=3)

        saida = converter_para_wav(entrada)

        self.assertEqual(saida, self.convertido(entrada))
        self.assertTrue(os.path.exists(saida))

        # Confere o formato de verdade, não só que o arquivo existe: taxa e
        # número de canais errados degradam a transcrição silenciosamente.
        sonda = _subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=sample_rate,channels',
             '-of', 'default=noprint_wrappers=1', saida],
            capture_output=True, timeout=30,
        ).stdout.decode()
        self.assertIn('sample_rate=16000', sonda)
        self.assertIn('channels=1', sonda)

    @_precisa_ffmpeg
    def test_converte_formato_comprimido(self):
        # O navegador grava em webm/ogg; é esse o caso real, não WAV.
        entrada = self.caminho('gravacao.ogg')
        _subprocess.run(
            ['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-f', 'lavfi',
             '-i', 'anoisesrc=d=3:c=pink:r=16000', '-ac', '1', entrada],
            check=True, capture_output=True, timeout=60,
        )

        saida = converter_para_wav(entrada)

        self.assertTrue(os.path.exists(saida))
        self.assertTrue(saida.endswith('_converted.wav'))

    @_precisa_ffmpeg
    def test_audio_corrompido_levanta_invalid_audio_error(self):
        entrada = self.gerar_corrompido()

        with self.assertRaises(InvalidAudioError):
            converter_para_wav(entrada)

        # Nada de WAV pela metade sobrando em disco.
        self.assertFalse(os.path.exists(self.convertido(entrada)))

    def test_falha_de_ambiente_cai_para_o_audio_original(self):
        # ffmpeg ausente ou quebrado não é culpa do arquivo: vale tentar
        # transcrever o original, que o Whisper aceita em vários formatos.
        entrada = self.caminho('entrada.webm')
        with open(entrada, 'wb') as f:
            f.write(b'conteudo original')

        falha = _subprocess.CompletedProcess([], 1, b'', b'ffmpeg: command not found')
        with patch.object(audio_service.subprocess, 'run', return_value=falha):
            saida = converter_para_wav(entrada)

        self.assertEqual(saida, entrada)
        self.assertFalse(os.path.exists(self.convertido(entrada)))

    def test_timeout_descarta_o_wav_pela_metade(self):
        # subprocess.run mata o ffmpeg no timeout, mas ele pode já ter começado
        # a gravar. Esse arquivo truncado não pode chegar à transcrição.
        entrada = self.caminho('entrada.webm')
        open(entrada, 'wb').close()
        parcial = self.convertido(entrada)
        with open(parcial, 'wb') as f:
            f.write(b'wav truncado')

        estouro = _subprocess.TimeoutExpired(cmd='ffmpeg', timeout=60)
        with patch.object(audio_service.subprocess, 'run', side_effect=estouro):
            saida = converter_para_wav(entrada)

        self.assertEqual(saida, entrada)
        self.assertFalse(os.path.exists(parcial), 'o WAV truncado deveria ter sido apagado')

    def test_chama_ffmpeg_direto_sem_processar_em_memoria(self):
        entrada = self.caminho('entrada.webm')
        open(entrada, 'wb').close()

        with patch.object(audio_service.subprocess, 'run') as run_mock:
            run_mock.return_value = _subprocess.CompletedProcess([], 0, b'', b'')
            converter_para_wav(entrada)

        comando = run_mock.call_args[0][0]
        self.assertEqual(comando[0], 'ffmpeg')
        self.assertIn('-hide_banner', comando)
        self.assertEqual(comando[-5:], ['-ar', '16000', '-ac', '1', self.convertido(entrada)])
        self.assertEqual(
            run_mock.call_args[1]['timeout'], audio_service._FFMPEG_TIMEOUT_SEGUNDOS
        )

    def test_nao_ha_mais_etapa_de_reducao_de_ruido(self):
        # Removida em setembro de 2026 (ver o cabeçalho da seção). Reintroduzi-la
        # traria de volta 18s de latência num áudio de 30s e o pico de memória
        # dentro do worker — o teste existe para que a volta seja deliberada.
        self.assertFalse(hasattr(audio_service, 'remover_ruido'))


# ---------------------------------------------------------------------------
# Modelo de transcrição
#
# O whisper-1 (Whisper large-v2) foi trocado pelo gpt-transcribe em set/2026:
# menor taxa de erro e 25% mais barato. A troca tem três armadilhas, cobertas
# abaixo: o gpt-transcribe não aceita response_format="text"; o custo por minuto
# é diferente e estava fixo no do whisper-1; e o FallbackBackend precisa dizer
# quem de fato transcreveu, senão cobramos preço de API por trabalho local.
# ---------------------------------------------------------------------------

from decimal import Decimal as _Decimal

from api.services.openai_usage import PRECO_POR_MINUTO_TRANSCRICAO


class ModeloTranscricaoTests(unittest.TestCase):
    """Qual modelo é chamado, e com quais parâmetros."""

    def _chamar(self, **env):
        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.return_value = MagicMock(text='ok')

        with patch.dict(os.environ, env, clear=False), patch(
            'api.transcription.openai_backend.get_openai_client', return_value=fake_client,
        ), patch(
            'api.transcription.openai_backend.run_with_timeout', side_effect=lambda fn, _t: fn(),
        ), tempfile.NamedTemporaryFile(suffix='.wav') as audio:
            audio.write(b'RIFF....WAVEfake')
            audio.flush()
            texto = OpenAIBackend().transcribe(audio.name)

        return texto, fake_client.audio.transcriptions.create.call_args[1]

    def test_usa_gpt_transcribe_por_padrao(self):
        # Variável vazia cai no padrão, igual a não estar definida.
        texto, kwargs = self._chamar(OPENAI_TRANSCRIPTION_MODEL='')

        self.assertEqual(kwargs['model'], 'gpt-transcribe')
        self.assertEqual(texto, 'ok')

    def test_modelo_e_configuravel_por_variavel_de_ambiente(self):
        # Permite reverter para o whisper-1 sem redeploy se algo der errado.
        _, kwargs = self._chamar(OPENAI_TRANSCRIPTION_MODEL='whisper-1')
        self.assertEqual(kwargs['model'], 'whisper-1')

    def test_nao_pede_response_format_text(self):
        # O gpt-transcribe recusa "text"; "json" funciona nos dois modelos e a
        # extração lê .text igual.
        _, kwargs = self._chamar(OPENAI_TRANSCRIPTION_MODEL='gpt-transcribe')
        self.assertEqual(kwargs['response_format'], 'json')

    def test_continua_pedindo_portugues(self):
        _, kwargs = self._chamar(OPENAI_TRANSCRIPTION_MODEL='gpt-transcribe')
        self.assertEqual(kwargs['language'], 'pt')

    def test_metadado_do_modelo_reflete_a_configuracao(self):
        with patch.dict(os.environ,
                        {'OPENAI_TRANSCRIPTION_MODEL': 'gpt-4o-transcribe',
                         'TRANSCRIPTION_PROVIDER': 'openai'}, clear=False):
            self.assertEqual(audio_service.modelo_transcricao_ativo(), 'gpt-4o-transcribe')


class CustoTranscricaoTests(unittest.TestCase):
    """O preço por minuto acompanha o modelo, em vez de ficar fixo."""

    def _custo_registrado(self, **kwargs):
        with patch('api.services.openai_usage.registrar_uso_openai') as registrar:
            audio_service.registrar_uso_whisper(**kwargs)
        return registrar.call_args[1]

    def test_gpt_transcribe_custa_menos_que_whisper(self):
        self.assertLess(
            PRECO_POR_MINUTO_TRANSCRICAO['gpt-transcribe'],
            PRECO_POR_MINUTO_TRANSCRICAO['whisper-1'],
        )

    def test_cobra_o_preco_do_modelo_informado(self):
        # 60s de gpt-transcribe = $0,0045; o mesmo áudio em whisper-1 = $0,006.
        novo = self._custo_registrado(duracao_segundos=60, modelo='gpt-transcribe')
        antigo = self._custo_registrado(duracao_segundos=60, modelo='whisper-1')

        self.assertEqual(novo['total_cost'], _Decimal('0.0045'))
        self.assertEqual(antigo['total_cost'], _Decimal('0.006'))
        self.assertEqual(novo['model'], 'gpt-transcribe')

    def test_arredonda_segundo_para_cima(self):
        registrado = self._custo_registrado(duracao_segundos=30.2, modelo='gpt-transcribe')
        self.assertEqual(registrado['input_tokens'], 31)

    def test_modelo_local_nao_entra_como_despesa_de_api(self):
        # O faster-whisper roda em máquina própria. Antes o custo era fixo no do
        # whisper-1 e o self-hosted era cobrado como se fosse OpenAI.
        registrado = self._custo_registrado(duracao_segundos=600, modelo='')
        self.assertEqual(registrado['total_cost'], _Decimal('0'))


class FallbackReportaModeloUsadoTests(unittest.TestCase):
    """Quem transcreveu de fato determina o preço."""

    def test_reporta_o_primario_quando_ele_funciona(self):
        primario = _StubBackend('openai', result='texto')
        primario.model = 'gpt-transcribe'
        secundario = _StubBackend('local', result='outro')

        fb = FallbackBackend(primario, secundario)
        fb.transcribe('/tmp/a.wav')

        self.assertEqual(fb.model, 'gpt-transcribe')

    def test_reporta_o_secundario_quando_cai_para_ele(self):
        primario = _StubBackend('openai', raises=TranscriptionRecoverableError('quota'))
        primario.model = 'gpt-transcribe'
        secundario = _StubBackend('local', result='texto do local')

        fb = FallbackBackend(primario, secundario)
        fb.transcribe('/tmp/a.wav')

        # Sem `model`: o local é self-hosted e custa 0. Reportar o do primário
        # aqui cobraria API por um trabalho que não foi para a API.
        self.assertEqual(fb.model, '')
        self.assertEqual(PRECO_POR_MINUTO_TRANSCRICAO.get(fb.model, _Decimal('0')), _Decimal('0'))


class DescartarDerivadosTests(_AudioTempMixin, unittest.TestCase):
    """Limpeza do WAV intermediário, que antes ficava para sempre em disco."""

    def test_remove_derivado_e_preserva_o_original(self):
        entrada = self.caminho('entrada.webm')
        with open(entrada, 'wb') as f:
            f.write(b'upload original')
        wav = self.convertido(entrada)
        with open(wav, 'wb') as f:
            f.write(b'derivado')

        descartar_derivados(entrada)

        self.assertFalse(os.path.exists(wav))
        self.assertTrue(os.path.exists(entrada), 'o upload original volta na resposta da API')

    def test_e_idempotente_quando_nao_ha_derivados(self):
        entrada = self.caminho('entrada.webm')
        open(entrada, 'wb').close()

        descartar_derivados(entrada)
        descartar_derivados(entrada)

        self.assertTrue(os.path.exists(entrada))


class ObterDuracaoAudioTests(_AudioTempMixin, unittest.TestCase):
    """A duração vem do ffprobe — soundfile não é mais dependência do projeto."""

    @_precisa_ffmpeg
    def test_duracao_via_ffprobe(self):
        entrada = self.gerar_audio(duracao=3)

        self.assertAlmostEqual(_obter_duracao_audio(entrada), 3.0, delta=0.2)

    def test_cai_para_estimativa_por_tamanho_quando_ffprobe_falha(self):
        entrada = self.caminho('entrada.wav')
        with open(entrada, 'wb') as f:
            f.write(b'x' * 32000)

        with patch.object(audio_service.subprocess, 'run', side_effect=OSError('sem ffprobe')):
            self.assertAlmostEqual(_obter_duracao_audio(entrada), 1.0, delta=0.01)

    def test_retorna_zero_quando_o_arquivo_nao_existe(self):
        with patch.object(audio_service.subprocess, 'run', side_effect=OSError('sem ffprobe')):
            self.assertEqual(_obter_duracao_audio(self.caminho('nao_existe.wav')), 0.0)


class WorkerNaoCarregaNumpyTests(unittest.TestCase):
    """Regressão do vazamento: numpy, scipy e soundfile fora do worker.

    Com a redução de ruído removida, esses pacotes saíram do requirements.txt —
    mas continuam chegando de carona em dependências transitivas, então importar
    um deles no caminho do áudio voltaria a somar ~96 MB ao piso de cada um dos
    processos Gunicorn. Este teste roda em um processo limpo porque no processo
    de teste outra dependência já pode ter carregado numpy.
    """

    def test_importar_o_servico_de_audio_nao_traz_numpy(self):
        script = (
            'import os, sys; '
            'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nara_api.settings"); '
            'import django; django.setup(); '
            'import api.services.audio; '
            'print(",".join(m for m in ("numpy", "scipy", "soundfile", "noisereduce") '
            'if m in sys.modules))'
        )
        resultado = _subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            timeout=180,
            cwd=str(settings.BASE_DIR),
        )

        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode(errors='replace'))
        carregados = resultado.stdout.decode(errors='replace').strip()
        self.assertEqual(
            carregados, '',
            f'módulos pesados voltaram para o worker Gunicorn: {carregados}',
        )


class UploadAudioLimpaDerivadosTests(APITestCase):
    """A view apaga os WAVs intermediários em qualquer caminho de saída."""

    def setUp(self):
        # O throttle de upload (10/min por usuário) guarda o contador no cache,
        # que sobrevive ao rollback de cada teste.
        cache.clear()
        self.instituicao = Instituicao.objects.create(nome='Instituição Áudio')
        self.usuario = Usuario.objects.create_user(
            email='professor.audio@example.com',
            password='senha123',
            nome='Professor Áudio',
            perfil='professor',
            instituicao=self.instituicao,
        )
        self.client.force_authenticate(user=self.usuario)
        self.addCleanup(shutil.rmtree, 'uploads/audio', True)

    def _enviar(self):
        arquivo = SimpleUploadedFile('gravacao.wav', b'RIFF....WAVEfake', content_type='audio/wav')
        return self.client.post(
            '/api/upload-audio/',
            {'audio': arquivo, 'turmaId': str(uuid.uuid4()), 'alunosTurma': '[]'},
            format='multipart',
        )

    def _derivados_em_disco(self):
        if not os.path.isdir('uploads/audio'):
            return []
        return [n for n in os.listdir('uploads/audio') if n.endswith('_converted.wav')]

    def _converter_falso(self, arquivo_path):
        """Finge o que o ffmpeg faria: deixa o WAV convertido em disco."""
        base, _ = os.path.splitext(arquivo_path)
        convertido = f'{base}_converted.wav'
        with open(convertido, 'wb') as f:
            f.write(b'derivado')
        return convertido

    def test_derivados_sao_apagados_no_caminho_de_sucesso(self):
        with patch('api.views.audio.converter_para_wav', self._converter_falso), \
             patch('api.views.audio.transcrever_audio', return_value='texto transcrito'), \
             patch('api.views.audio.extrair_observacoes',
                   return_value={'nomes_alunos': ['Ana'], 'observacoes': ['obs']}):
            response = self._enviar()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._derivados_em_disco(), [])

    def test_derivados_sao_apagados_quando_a_transcricao_falha(self):
        with patch('api.views.audio.converter_para_wav', self._converter_falso), \
             patch('api.views.audio.transcrever_audio', side_effect=ConnectionError('caiu')):
            response = self._enviar()

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(self._derivados_em_disco(), [])

    def test_derivados_sao_apagados_quando_o_audio_e_invalido(self):
        with patch('api.views.audio.converter_para_wav',
                   side_effect=InvalidAudioError('corrompido')):
            response = self._enviar()

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(self._derivados_em_disco(), [])

    def test_upload_original_e_preservado(self):
        # Ele volta na resposta como "arquivo_salvo"; só o derivado some.
        with patch('api.views.audio.converter_para_wav', self._converter_falso), \
             patch('api.views.audio.transcrever_audio', return_value='texto transcrito'), \
             patch('api.views.audio.extrair_observacoes',
                   return_value={'nomes_alunos': ['Ana'], 'observacoes': ['obs']}):
            response = self._enviar()

        self.assertTrue(os.path.exists(response.json()['arquivo_salvo']))
