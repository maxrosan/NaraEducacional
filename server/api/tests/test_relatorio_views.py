"""Regressões das views de relatório ativas (as de avaliacao.py)."""
from unittest.mock import patch

from api.models import Relatorio

from .base import CenarioMultiTenant


class DetalheRelatorioTests(CenarioMultiTenant):

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
