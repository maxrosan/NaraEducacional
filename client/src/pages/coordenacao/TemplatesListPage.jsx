import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet, apiPost, apiDelete, MODELOS, useEscolaTemplate, useRotasTemplate } from '@/lib/templateRelatorioShared';

export default function TemplatesListPage() {
  const navigate = useNavigate();
  const { escolaUuid, escolas, trocarEscola, comEscola, pronto } = useEscolaTemplate();
  const rotas = useRotasTemplate();
  const [templates, setTemplates] = useState(null); // null = carregando
  const [erro, setErro] = useState(null);
  const [acaoPendente, setAcaoPendente] = useState(null); // uuid do template com ação em andamento

  async function carregar() {
    try {
      // Só os templates da escola em configuração.
      const data = await apiGet(comEscola('/relatorio-templates/'));
      setTemplates(data);
    } catch (e) {
      setErro(e.message);
    }
  }

  useEffect(() => {
    if (!pronto) return;
    setTemplates(null);
    setErro(null);
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pronto, escolaUuid]);

  // Recebem o UUID do template: ele vai na URL da API.
  async function ativar(uuid) {
    setAcaoPendente(uuid);
    try {
      await apiPost(`/api/templates-relatorio/${uuid}/ativar/`, {});
      await carregar();
    } catch (e) {
      setErro(e.message);
    } finally {
      setAcaoPendente(null);
    }
  }

  async function excluir(uuid) {
    if (!window.confirm('Excluir este template? Essa ação não pode ser desfeita.')) return;
    setAcaoPendente(uuid);
    try {
      await apiDelete(`/api/templates-relatorio/${uuid}/deletar/`);
      await carregar();
    } catch (e) {
      setErro(e.message);
    } finally {
      setAcaoPendente(null);
    }
  }

  const nomeModelo = (id) => MODELOS.find((m) => m.id === id)?.nome || id;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900">Templates de relatório</h1>
          <p className="text-gray-500 mt-1">
            O template ativo define a capa e as seções usadas em todos os próximos relatórios gerados.
          </p>
        </div>
        <button
          onClick={() => navigate(comEscola(rotas.modelos))}
          className="flex-none bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl px-4 py-2.5 transition"
        >
          + Criar novo template
        </button>
      </div>

      {escolas.length > 1 && (
        <div className="mb-6 max-w-sm">
          <label htmlFor="escola-templates" className="block text-sm font-medium text-gray-700 mb-1">Escola</label>
          <select
            id="escola-templates"
            value={escolaUuid || ''}
            onChange={(e) => trocarEscola(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            {escolas.map((e) => <option key={e.uuid} value={e.uuid}>{e.nome}</option>)}
          </select>
        </div>
      )}

      {erro && <p className="text-sm text-red-600 mb-4">{erro}</p>}

      {templates === null && <p className="text-gray-400">Carregando...</p>}

      {templates && templates.length === 0 && (
        <div className="text-center py-16 border border-dashed border-gray-200 rounded-2xl">
          <p className="text-gray-500">Nenhum template criado ainda.</p>
          <p className="text-gray-400 text-sm mt-1">O relatório usa o layout padrão do sistema até você criar um.</p>
        </div>
      )}

      {templates && templates.length > 0 && (
        <div className="space-y-3">
          {templates.map((t) => (
            <div
              key={t.id}
              className={`flex items-center gap-4 border rounded-xl px-4 py-3 ${
                t.ativo ? 'border-violet-300 bg-violet-50' : 'border-gray-200 bg-white'
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900 truncate">{t.nome}</span>
                  {t.ativo && (
                    <span className="flex-none text-[10px] font-bold uppercase tracking-wide bg-violet-600 text-white rounded-full px-2 py-0.5">
                      Ativo
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {nomeModelo(t.modelo)} · atualizado em{' '}
                  {/* O backend devolve atualizado_em (updated_at era do legado). */}
                  {new Date(t.atualizado_em ?? t.updated_at).toLocaleDateString('pt-BR')}
                </div>
              </div>

              <button
                onClick={() => navigate(comEscola(rotas.editar(t.uuid)))}
                className="flex-none text-sm text-violet-700 hover:underline"
              >
                Editar
              </button>

              {!t.ativo && (
                <button
                  onClick={() => ativar(t.uuid)}
                  disabled={acaoPendente === t.uuid}
                  className="flex-none text-sm text-gray-600 hover:text-violet-700 disabled:opacity-40"
                >
                  Ativar
                </button>
              )}

              {!t.ativo && (
                <button
                  onClick={() => excluir(t.uuid)}
                  disabled={acaoPendente === t.uuid}
                  className="flex-none text-sm text-red-500 hover:text-red-700 disabled:opacity-40"
                >
                  Excluir
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}