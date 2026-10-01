import * as Sentry from "@sentry/react";

const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() !== '') {
    return `${envUrl}/api`;
  }
  return '/api';
};

export const API_BASE_URL = getApiBaseUrl();

export const HEADERS_PADRAO = { 'ngrok-skip-browser-warning': '1' };

const CHAVE_ACCESS = 'access_token';
const CHAVE_REFRESH = 'refresh_token';

export function getAccessToken() {
  return localStorage.getItem(CHAVE_ACCESS);
}

export function getRefreshToken() {
  return localStorage.getItem(CHAVE_REFRESH);
}

export function salvarTokens({ access, refresh }) {
  if (access) localStorage.setItem(CHAVE_ACCESS, access);
  if (refresh) localStorage.setItem(CHAVE_REFRESH, refresh);
}

export function limparTokens() {
  localStorage.removeItem(CHAVE_ACCESS);
  localStorage.removeItem(CHAVE_REFRESH);
}

let refreshEmAndamento = null;

async function renovarAccessToken() {
  if (refreshEmAndamento) return refreshEmAndamento;

  refreshEmAndamento = (async () => {
    const refresh = getRefreshToken();
    if (!refresh) throw new Error('Sem refresh token.');

    const response = await fetch(`${API_BASE_URL}/auth/refresh/`, {
      method: 'POST',
      headers: { ...HEADERS_PADRAO, 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) throw new Error(`Refresh falhou: ${response.status}`);

    const data = await response.json();
    salvarTokens(data);
    return data.access;
  })();

  try {
    return await refreshEmAndamento;
  } finally {
    refreshEmAndamento = null;
  }
}

export const EVENTO_SESSAO_EXPIRADA = 'auth:sessao-expirada';

function montarHeaders(options) {
  const headers = {
    ...HEADERS_PADRAO,
    ...(options.headers instanceof Headers
      ? Object.fromEntries(options.headers.entries())
      : (options.headers || {})),
  };
  const token = getAccessToken();
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function authFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();

  try {
    let response = await fetch(url, { ...options, headers: montarHeaders(options) });

    if (response.status === 401 && getRefreshToken()) {
      try {
        await renovarAccessToken();
        response = await fetch(url, { ...options, headers: montarHeaders({ ...options, headers: { ...options.headers } }) });
      } catch (_) {
        limparTokens();
        window.dispatchEvent(new Event(EVENTO_SESSAO_EXPIRADA));
      }
    }

    if (!response.ok) {
      Sentry.addBreadcrumb({
        category: 'api',
        message: `${method} ${url} → ${response.status}`,
        level: 'error',
      });
    }

    return response;
  } catch (error) {
    Sentry.captureException(error, { extra: { url, method } });
    throw error;
  }
}

function mensagensDeCampo(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  const mensagens = Object.values(data)
    .flat(Infinity)
    .filter((m) => typeof m === 'string' && m.trim());
  return mensagens.length ? mensagens.join(' ') : null;
}

async function parseJsonOrThrow(response, contexto) {
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
  }
  if (!response.ok) {
    const mensagem = (data && (data.error || data.detail || mensagensDeCampo(data)))
      || `Erro ${response.status} em ${contexto}`;
    const err = new Error(mensagem);
    err.status = response.status;
    err.payload = data;
    throw err;
  }
  return data;
}

async function getJson(caminho, contexto) {
  const response = await authFetch(`${API_BASE_URL}${caminho}`);
  return parseJsonOrThrow(response, contexto);
}

async function enviarJson(caminho, method, corpo, contexto) {
  const response = await authFetch(`${API_BASE_URL}${caminho}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo ?? {}),
  });
  return parseJsonOrThrow(response, contexto);
}

function comQuery(caminho, params) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.append(k, v);
  });
  const s = qs.toString();
  return s ? `${caminho}?${s}` : caminho;
}

export class EndpointRemovidoError extends Error {
  constructor(nome) {
    super(`"${nome}" não existe mais no backend multi-tenant.`);
    this.name = 'EndpointRemovidoError';
    this.status = 410;
  }
}

function endpointRemovido(nome) {
  const err = new EndpointRemovidoError(nome);
  console.error(`[API] ${err.message}`);
  return Promise.reject(err);
}

const CAMPOS_ANTIGOS_PARA_NOVOS = {
  crianca_id: 'aluno',
  id_crianca: 'aluno',
  aluno_id: 'aluno',
  turma_id: 'turma',
  escola_id: 'escola',
  instituicao_id: 'instituicao',
  projeto_id: 'projeto',
  pergunta_id: 'pergunta',
  disciplina_id: 'disciplina',
  usuario_id: 'usuario',
  perfil: 'nivel',
};

const ALIASES_DE_RESPOSTA = {
  aluno: ['crianca_id', 'id_crianca', 'aluno_id'],
  turma: ['turma_id'],
  escola: ['escola_id'],
  instituicao: ['instituicao_id'],
  professor: ['professor_id'],
  usuario: ['usuario_id'],
  projeto: ['projeto_id'],
  pergunta: ['pergunta_id'],
  disciplina: ['disciplina_id'],
  nivel: ['perfil'],
};

export function traduzirPayload(dados = {}) {
  if (!dados || typeof dados !== 'object' || Array.isArray(dados)) return dados;
  const saida = {};
  Object.entries(dados).forEach(([k, v]) => {
    const novo = CAMPOS_ANTIGOS_PARA_NOVOS[k];
    if (novo && dados[novo] === undefined) saida[novo] = v;
    else if (!novo) saida[k] = v;
  });
  return saida;
}

export function adicionarAliases(registro) {
  if (!registro || typeof registro !== 'object' || Array.isArray(registro)) return registro;
  const saida = { ...registro };
  Object.entries(ALIASES_DE_RESPOSTA).forEach(([novo, antigos]) => {
    const valor = registro[novo];
    if (valor === undefined || (valor !== null && typeof valor === 'object')) return;
    antigos.forEach((antigo) => {
      if (saida[antigo] === undefined) saida[antigo] = valor;
    });
  });
  return saida;
}

export function normalizarUsuario(u) {
  if (!u) return null;
  return {
    ...adicionarAliases(u),
    user_metadata: { full_name: u.nome, nome: u.nome, perfil: u.nivel, instituicao_id: u.instituicao },
  };
}

export const apiService = {
  async iniciarAnaliseLeitura(formData) {
    const response = await authFetch(`${API_BASE_URL}/leitura/analisar/`, {
      method: 'POST',
      body: formData,
    });
    return parseJsonOrThrow(response, 'iniciar análise de leitura');
  },

  async consultarAnaliseLeitura(registroId) {
    return getJson(`/leitura/${registroId}/status/`, 'consultar análise de leitura');
  },

  async confirmarAnaliseLeitura(registroId, payload) {
    return enviarJson(`/leitura/${registroId}/confirmar/`, 'POST', payload, 'confirmar análise de leitura');
  },

  async cancelarAnaliseLeitura(registroId) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/`, { method: 'DELETE' });
    return parseJsonOrThrow(response, 'cancelar análise de leitura');
  },

  async listarAnalisesLeitura({ criancaId, dataInicio, dataFim } = {}) {
    if (!criancaId) throw new Error('criancaId é obrigatório.');
    return getJson(
      comQuery('/leitura/', { crianca_id: criancaId, data_inicio: dataInicio, data_fim: dataFim }),
      'listar análises de leitura',
    );
  },

  async deletarAnaliseLeitura(registroId) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/deletar/`, { method: 'DELETE' });
    return parseJsonOrThrow(response, 'excluir análise de leitura');
  },

  async listarDispositivos() {
    return getJson('/dispositivos/', 'listar dispositivos');
  },

  async gerarCodigoPareamento({ professoraId, turmaIds } = {}) {
    return enviarJson('/dispositivos/codigo/', 'POST', {
      ...(professoraId ? { professora_id: professoraId } : {}),
      ...(turmaIds?.length ? { turma_ids: turmaIds } : {}),
    }, 'gerar código de pareamento');
  },

  async atualizarDispositivo(dispositivoId, dados) {
    return enviarJson(`/dispositivos/${dispositivoId}/`, 'PATCH', dados, 'atualizar dispositivo');
  },

  async revogarDispositivo(dispositivoId) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/${dispositivoId}/revogar/`, { method: 'DELETE' });
    return parseJsonOrThrow(response, 'revogar dispositivo');
  },

  async reativarDispositivo(dispositivoId) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/${dispositivoId}/reativar/`, { method: 'POST' });
    return parseJsonOrThrow(response, 'reativar dispositivo');
  },

  async uploadEAnaliseEscrita(dadosAnalise, arquivo) {
    const formData = new FormData();
    formData.append('arquivo', arquivo);
    formData.append('nomeAluno', dadosAnalise.nomeAluno);
    formData.append('serieAluno', dadosAnalise.serieAluno);
    formData.append('turmaId', dadosAnalise.turmaId);

    const response = await authFetch(`${API_BASE_URL}/upload-escrita/`, {
      method: 'POST',
      body: formData,
    });
    return parseJsonOrThrow(response, 'upload e análise de escrita');
  },

  async uploadEAnaliseDesenho(formData) {
    const response = await authFetch(`${API_BASE_URL}/upload-desenho/`, {
      method: 'POST',
      body: formData,
    });
    return parseJsonOrThrow(response, 'upload e análise de desenho');
  },

  async analiseDeEscrita() {
    return endpointRemovido('analise-escrita/');
  },

  async atualizarClassificacaoRegistro(tipo, arquivoHash, classificacao) {
    return enviarJson('/registros/classificacao/', 'POST', {
      tipo,
      arquivo_hash: arquivoHash,
      classificacao,
    }, 'atualizar classificação');
  },

  async salvarAnotacoesProfessora() {
    return endpointRemovido('salvar-anotacoes/');
  },

  async listarRegistrosEscrita() {
    return getJson('/registros-escrita/', 'listar registros de escrita');
  },

  async listarRegistrosDesenho() {
    return getJson('/registros-desenho/', 'listar registros de desenho');
  },

  async buscarRegistrosPorAluno() {
    return endpointRemovido('registros-aluno/<nome>/');
  },

  async testarConexao() {
    return endpointRemovido('hello/');
  },

  async healthCheck() {
    const response = await fetch(`${API_BASE_URL}/health/`, { headers: HEADERS_PADRAO });
    return parseJsonOrThrow(response, 'health check');
  },

  async listarNotificacoes({ apenasNaoLidas = true } = {}) {
    return getJson(apenasNaoLidas ? '/notificacoes/?lidas=false' : '/notificacoes/', 'listar notificações');
  },

  async listarAlertas() {
    return apiService.listarNotificacoes({ apenasNaoLidas: true });
  },

  async buscarDetalheAlerta() {
    return endpointRemovido('alertas/detalhe/');
  },

  async marcarNotificacaoLida(notificacaoId) {
    const response = await authFetch(`${API_BASE_URL}/notificacoes/${notificacaoId}/marcar-lida/`, { method: 'POST' });
    return parseJsonOrThrow(response, 'marcar notificação como lida');
  },

  async buscarCacheCoordenacao(recorte = {}) {
    const { periodoId, dataInicio, dataFim, escolaId } = recorte;
    const params = { escola_id: escolaId };
    if (dataInicio && dataFim) {
      params.data_inicio = dataInicio;
      params.data_fim = dataFim;
    } else if (periodoId) {
      params.periodo_id = periodoId;
    }
    return getJson(comQuery('/coordenacao/cache/', params), 'buscar indicadores da coordenação');
  },

  async buscarPeriodosCoordenacao({ escolaId } = {}) {
    return getJson(comQuery('/coordenacao/periodos/', { escola_id: escolaId }), 'buscar períodos da coordenação');
  },

  async atualizarCacheCoordenacao() {
    return endpointRemovido('coordenacao/cache/refresh/');
  },

  async listarIndicadorLinguagem(_instituicaoId, turmaId = null, periodoId = null) {
    return getJson(
      comQuery('/coordenacao/indicadores-turma/', { turma_id: turmaId, periodo_id: periodoId }),
      'listar indicadores da turma',
    );
  },

  async listarHabilidadesBNCC(componente = null, anoSerie = null) {
    return getJson(
      comQuery('/habilidades-bncc/', { componente, ano_serie: anoSerie }),
      'listar habilidades BNCC',
    );
  },

  async criarHabilidadeBNCC(dadosHabilidade) {
    return enviarJson('/habilidades-bncc/criar/', 'POST', dadosHabilidade, 'criar habilidade BNCC');
  },

  async popularHabilidadesBNCC() {
    return endpointRemovido('habilidades-bncc/popular/');
  },

  async processarArquivoPlanejamento(turmaId, diaSemana, file) {
    const formData = new FormData();
    formData.append('arquivo', file);
    formData.append('turma_id', turmaId);
    formData.append('dia_semana', diaSemana);

    const response = await authFetch(`${API_BASE_URL}/planejamento/processar-arquivo/`, {
      method: 'POST',
      body: formData,
    });
    return parseJsonOrThrow(response, 'processar arquivo de planejamento');
  },

  async sugerirAtividadesPlanejamento(payload) {
    return enviarJson('/planejamento/sugerir-atividades/', 'POST', payload, 'sugerir atividades de planejamento');
  },

  async aplicarPlanejamentoEmSemanas(payload) {
    return enviarJson('/planejamento/aplicar-em-semanas/', 'POST', payload, 'aplicar planejamento em semanas');
  },

  async sugerirBnccPlanejamento(payload) {
    return enviarJson('/planejamento/sugerir-bncc/', 'POST', payload, 'sugerir habilidades BNCC');
  },

  async criarPlanejamentoSemanal(dadosPlanejamento) {
    return enviarJson('/planejamento/criar/', 'POST', dadosPlanejamento, 'criar planejamento semanal');
  },

  async buscarPlanejamentoSemanal(turmaId, semanaInicio) {
    const lista = await getJson(
      comQuery('/planejamento/', {
        turma_id: turmaId,
        semana_referencia__gte: semanaInicio,
        semana_referencia__lte: semanaInicio,
      }),
      'buscar planejamento semanal',
    );
    return Array.isArray(lista) && lista.length ? lista[0] : null;
  },

  async atualizarPlanejamentoSemanal(planejamentoId, dadosPlanejamento) {
    return enviarJson(`/planejamento/${planejamentoId}/atualizar/`, 'PUT', dadosPlanejamento, 'atualizar planejamento semanal');
  },

  async listarPlanejamentosTurma(turmaId, inicioPeriodo = null, fimPeriodo = null) {
    return getJson(
      comQuery('/planejamento/', {
        turma_id: turmaId,
        semana_referencia__gte: inicioPeriodo,
        semana_referencia__lte: fimPeriodo,
      }),
      'listar planejamentos da turma',
    );
  },

  async gerarRelatorio(dadosRelatorio) {
    return enviarJson('/gerar-relatorio/', 'POST', dadosRelatorio, 'gerar relatório');
  },

  async gerarRelatorioPorCrianca(criancaId, periodoId) {
    return enviarJson(
      `/gerar-relatorio/${criancaId}/`,
      'POST',
      periodoId ? { periodo_id: periodoId } : {},
      'gerar relatório por criança',
    );
  },

  async salvarRelatorio(dadosRelatorio) {
    return enviarJson('/relatorios/criar/', 'POST', {
      aluno: dadosRelatorio.id_crianca ?? dadosRelatorio.aluno,
      periodo: dadosRelatorio.periodo,
      conteudo: dadosRelatorio.conteudo,
      ...(dadosRelatorio.template ? { template: dadosRelatorio.template } : {}),
    }, 'salvar relatório');
  },

  async baixarPdfRelatorio(relatorioId) {
    const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/pdf/download/`);

    if (!response.ok) {
      await parseJsonOrThrow(response, 'baixar PDF do relatório');
    }

    const blob = await response.blob();
    const cached = response.headers.get('X-Pdf-Cached') === 'true';

    let filename = `relatorio_${relatorioId}.pdf`;
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) {
      filename = match[1];
    }

    return { blob, filename, cached };
  },

  async bulkPdfRelatoriosStream({ ids, signal, onEvent }) {
    const response = await authFetch(`${API_BASE_URL}/relatorios/bulk-pdf/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
      signal,
    });

    if (!response.ok) {
      await parseJsonOrThrow(response, 'gerar PDFs em lote');
    }

    if (!response.body) {
      throw new Error('Resposta do servidor não suporta streaming.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let doneEvent = null;

    const processarLinha = (linha) => {
      if (!linha) return;
      let evt;
      try {
        evt = JSON.parse(linha);
      } catch (_) {
        console.warn('[bulkPdf] linha NDJSON inválida:', linha);
        return;
      }
      onEvent?.(evt);
      if (evt?.type === 'done') doneEvent = evt;
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let newlineIdx;
      while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
        processarLinha(buffer.slice(0, newlineIdx).trim());
        buffer = buffer.slice(newlineIdx + 1);
      }
    }

    processarLinha(buffer.trim());

    if (!doneEvent) {
      throw new Error('Stream encerrado sem evento final.');
    }
    return doneEvent;
  },

  async uploadRelatorioPdf() {
    return endpointRemovido('relatorios/<id>/pdf/ (upload)');
  },

  async refreshRelatorioPdf() {
    return endpointRemovido('relatorios/<id>/pdf/refresh/');
  },

  async buscarDadosRelatorio() {
    return endpointRemovido('dados-relatorio/<id>/');
  },
};

export const uploadEAnaliseEscrita = apiService.uploadEAnaliseEscrita;
export const uploadEAnaliseDesenho = apiService.uploadEAnaliseDesenho;
export const analiseDeEscrita = apiService.analiseDeEscrita;
export const testarConexao = apiService.testarConexao;
export const healthCheck = apiService.healthCheck;
export const salvarAnotacoesProfessora = apiService.salvarAnotacoesProfessora;
export const listarRegistrosEscrita = apiService.listarRegistrosEscrita;
export const listarNotificacoes = apiService.listarNotificacoes;
export const marcarNotificacaoLida = apiService.marcarNotificacaoLida;
export const buscarRegistrosPorAluno = apiService.buscarRegistrosPorAluno;

export const listarHabilidadesBNCC = apiService.listarHabilidadesBNCC;
export const criarHabilidadeBNCC = apiService.criarHabilidadeBNCC;
export const popularHabilidadesBNCC = apiService.popularHabilidadesBNCC;
export const processarArquivoPlanejamento = apiService.processarArquivoPlanejamento;
export const aplicarPlanejamentoEmSemanas = apiService.aplicarPlanejamentoEmSemanas;
export const sugerirAtividadesPlanejamento = apiService.sugerirAtividadesPlanejamento;
export const sugerirBnccPlanejamento = apiService.sugerirBnccPlanejamento;
export const criarPlanejamentoSemanal = apiService.criarPlanejamentoSemanal;
export const buscarPlanejamentoSemanal = apiService.buscarPlanejamentoSemanal;
export const atualizarPlanejamentoSemanal = apiService.atualizarPlanejamentoSemanal;
export const listarPlanejamentosTurma = apiService.listarPlanejamentosTurma;

export const gerarRelatorio = apiService.gerarRelatorio;
export const gerarRelatorioPorCrianca = apiService.gerarRelatorioPorCrianca;
export const salvarRelatorio = apiService.salvarRelatorio;
export const uploadRelatorioPdf = apiService.uploadRelatorioPdf;
export const baixarPdfRelatorio = apiService.baixarPdfRelatorio;
export const bulkPdfRelatoriosStream = apiService.bulkPdfRelatoriosStream;
export const refreshRelatorioPdf = apiService.refreshRelatorioPdf;
export const buscarDadosRelatorio = apiService.buscarDadosRelatorio;

export async function listarCriancas(filtros = {}) {
  const alunos = await getJson(comQuery('/alunos/', { turma: filtros.turma_id }), 'listar alunos');

  const status = filtros.status_vinculo;
  return status && status !== 'all'
    ? alunos.filter((a) => a.status_vinculo === status)
    : alunos;
}

export async function listarAlunosPaginado({ status, escola, turma, busca, page = 1, pageSize } = {}) {
  const dados = await getJson(
    comQuery('/alunos/', { status, escola, turma, busca, page, page_size: pageSize }),
    'listar alunos',
  );
  return { ...dados, results: (dados.results || []).map(adicionarAliases) };
}

export async function buscarCrianca(criancaId) {
  return getJson(`/alunos/${criancaId}/`, 'buscar aluno');
}

export async function criarCrianca(dados) {
  return enviarJson('/alunos/criar/', 'POST', traduzirPayload(dados), 'criar aluno');
}

export async function atualizarCrianca(criancaId, dados) {
  return enviarJson(`/alunos/${criancaId}/atualizar/`, 'PATCH', traduzirPayload(dados), 'atualizar aluno');
}

export async function deletarCrianca(criancaId) {
  return atualizarCrianca(criancaId, { status_vinculo: 'inativo' });
}

export async function criarCriancasLote(criancas, onProgress) {
  const errors = [];
  let successCount = 0;

  for (let i = 0; i < criancas.length; i++) {
    const dados = criancas[i];
    if (onProgress) onProgress(i + 1, criancas.length, dados.nome_completo);
    try {
      await criarCrianca(dados);
      successCount++;
    } catch (error) {
      errors.push({
        nome: dados.nome_completo || `Aluno ${i + 1}`,
        message: error.message || 'Erro desconhecido',
      });
    }
  }

  return { successCount, errors };
}

export async function uploadFotoCrianca(criancaId, arquivo) {
  const corpo = new FormData();
  corpo.append('foto', arquivo);

  const response = await authFetch(`${API_BASE_URL}/alunos/${criancaId}/foto/`, { method: 'POST', body: corpo });
  return adicionarAliases(await parseJsonOrThrow(response, 'enviar foto do aluno'));
}

export async function listarRelatorios(filtros = {}) {
  return getJson(comQuery('/relatorios/', { aluno: filtros.id_crianca ?? filtros.aluno }), 'listar relatórios');
}

export async function buscarRelatorio(relatorioId) {
  return getJson(`/relatorios/${relatorioId}/`, 'buscar relatório');
}

export async function atualizarRelatorio(relatorioId, dados) {
  return enviarJson(`/relatorios/${relatorioId}/atualizar/`, 'PUT', traduzirPayload(dados), 'atualizar relatório');
}

export async function deletarRelatorio(relatorioId) {
  const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/deletar/`, { method: 'DELETE' });
  return parseJsonOrThrow(response, 'excluir relatório');
}

export async function listarObservacoes(filtros = {}) {
  const registros = await getJson(
    comQuery('/registros-observacao/', { aluno: filtros.crianca_id }),
    'listar observações',
  );
  return registros.filter((r) => {
    if (filtros.professor_id && r.professor !== filtros.professor_id) return false;
    if (filtros.data_inicio && r.data_observacao < filtros.data_inicio) return false;
    if (filtros.data_fim && r.data_observacao > filtros.data_fim) return false;
    return true;
  });
}

export async function criarObservacao(dados) {
  return enviarJson('/registros-observacao/criar/', 'POST', traduzirPayload(dados), 'criar observação');
}

export async function criarObservacoesLote(registros) {
  const criados = [];
  const errors = [];
  for (const registro of registros) {
    try {
      criados.push(await criarObservacao(registro));
    } catch (error) {
      errors.push({ registro, message: error.message || 'Erro desconhecido' });
    }
  }
  return { criados, successCount: criados.length, errors };
}

export async function listarPerguntasBncc(filtros = {}) {
  let perguntas = await getJson(
    comQuery('/perguntas/', { faixa_etaria: filtros.faixa_etaria }),
    'listar perguntas',
  );
  if (filtros.campo_experiencia) {
    perguntas = perguntas.filter((p) => (p.campo_experiencia ?? p.campo) === filtros.campo_experiencia);
  }
  if (filtros.ids?.length) {
    const ids = new Set(filtros.ids.map(String));
    perguntas = perguntas.filter((p) => ids.has(String(p.id)));
  }
  return perguntas;
}

export async function listarPerguntasBNCC(filtros = {}) {
  return listarPerguntasBncc(filtros);
}

export async function listarTurmas(filtros = {}) {
  if (filtros.id) {
    return [await buscarTurma(filtros.id)];
  }
  const turmas = await getJson('/turmas/', 'listar turmas');
  if (filtros.ativa === undefined) return turmas;
  const ativa = filtros.ativa === true || filtros.ativa === 'true';
  return turmas.filter((t) => t.ativa === undefined || t.ativa === ativa);
}

export async function listarTurmasPaginado({ ativa, escola, page = 1, pageSize } = {}) {
  return getJson(
    comQuery('/turmas/', { ativa, escola, page, page_size: pageSize }),
    'listar turmas',
  );
}

export async function buscarTurma(turmaId) {
  return getJson(`/turmas/${turmaId}/`, 'buscar turma');
}

export async function criarTurma(dados) {
  return enviarJson('/turmas/criar/', 'POST', dados, 'criar turma');
}

export async function atualizarTurma(turmaId, dados) {
  return enviarJson(`/turmas/${turmaId}/atualizar/`, 'PATCH', dados, 'atualizar turma');
}

export async function listarProfessoresTurma(turmaId) {
  return getJson(`/turmas/${turmaId}/professores/`, 'listar professores da turma');
}

export async function vincularProfessorTurma(turmaId, usuarioId) {
  return enviarJson(`/turmas/${turmaId}/professores/vincular/`, 'POST', { usuario: usuarioId }, 'vincular professor à turma');
}

export async function desvincularProfessorTurma(turmaId, usuarioId) {
  const response = await authFetch(
    `${API_BASE_URL}/turmas/${turmaId}/professores/${usuarioId}/desvincular/`,
    { method: 'DELETE' },
  );
  return parseJsonOrThrow(response, 'desvincular professor da turma');
}

export const FREQUENCIAS_REGISTRO = [
  { valor: 'semanal', rotulo: 'Semanal' },
  { valor: 'quinzenal', rotulo: 'Quinzenal' },
  { valor: 'mensal', rotulo: 'Mensal' },
];

export async function listarFrequenciasRegistro({
  escola, frequencia, busca, ativa, page = 1, pageSize,
} = {}) {
  return getJson(
    comQuery('/turmas/frequencia-registro/', {
      escola, frequencia, busca, ativa, page, page_size: pageSize,
    }),
    'listar frequências de registro',
  );
}

export async function atualizarFrequenciaRegistro(frequencia, { turmas, escola } = {}) {
  const corpo = { frequencia_registro: frequencia };
  if (escola) corpo.escola = escola;
  else corpo.turmas = turmas;
  return enviarJson(
    '/turmas/frequencia-registro/atualizar/', 'PATCH', corpo,
    'atualizar frequência de registro',
  );
}

export async function listarDisciplinas(filtros = {}) {
  return getJson(comQuery('/disciplinas/', { ativo: filtros.ativo, escola: filtros.escola }), 'listar disciplinas');
}

export async function listarDisciplinasPaginado({ ativo, escola, busca, page = 1, pageSize } = {}) {
  return getJson(
    comQuery('/disciplinas/', { ativo, escola, busca, page, page_size: pageSize }),
    'listar disciplinas',
  );
}

export async function criarDisciplina(dados) {
  return enviarJson('/disciplinas/criar/', 'POST', dados, 'criar disciplina');
}

export async function atualizarDisciplina(disciplinaId, dados) {
  return enviarJson(`/disciplinas/${disciplinaId}/atualizar/`, 'PATCH', dados, 'atualizar disciplina');
}

export async function listarPeriodosAvaliativos(filtros = {}) {
  return getJson(comQuery('/periodos-avaliativos/', { escola: filtros.escola }), 'listar períodos avaliativos');
}

export async function listarPeriodosPaginado({ situacao, escola, page = 1, pageSize } = {}) {
  return getJson(
    comQuery('/periodos-avaliativos/', { situacao, escola, page, page_size: pageSize }),
    'listar períodos avaliativos',
  );
}

export async function criarPeriodoAvaliativo(dados) {
  return enviarJson('/periodos-avaliativos/criar/', 'POST', dados, 'criar período avaliativo');
}

export async function atualizarPeriodoAvaliativo(periodoId, dados) {
  return enviarJson(`/periodos-avaliativos/${periodoId}/atualizar/`, 'PATCH', dados, 'atualizar período avaliativo');
}

export async function listarPerguntasEspecialistasPaginado({ status, escola, nivel, campo, busca, page = 1, pageSize } = {}) {
  return getJson(
    comQuery('/perguntas-especialistas/', { status, escola, nivel, campo, busca, page, page_size: pageSize }),
    'listar perguntas',
  );
}

export async function criarPerguntaEspecialista(dados) {
  return enviarJson('/perguntas-especialistas/criar/', 'POST', dados, 'criar pergunta');
}

export async function atualizarPerguntaEspecialista(perguntaId, dados) {
  return enviarJson(`/perguntas-especialistas/${perguntaId}/atualizar/`, 'PATCH', dados, 'atualizar pergunta');
}

export async function listarCamposPedagogicos({ ativo, comUso } = {}) {
  return getJson(
    comQuery('/campos-pedagogicos/', { ativo, com_uso: comUso ? 1 : undefined }),
    'listar campos de experiência',
  );
}

export async function atualizarCampoPedagogico(campoId, dados) {
  return enviarJson(`/campos-pedagogicos/${campoId}/atualizar/`, 'PATCH', dados, 'atualizar campo de experiência');
}

export async function desativarCampoPedagogico(campoId, remanejarPara = null) {
  return enviarJson(
    `/campos-pedagogicos/${campoId}/desativar/`, 'POST',
    { remanejar_para: remanejarPara }, 'desativar campo de experiência',
  );
}

export async function listarPerguntasBnccGestao({ ativa, origem, escola, campo, faixa_etaria, busca, page, pageSize } = {}) {
  return getJson(
    comQuery('/perguntas/', { ativa, origem, escola, campo, faixa_etaria, busca, page, page_size: pageSize }),
    'listar perguntas BNCC',
  );
}

export async function criarPerguntaBncc(dados) {
  return enviarJson('/perguntas/criar/', 'POST', dados, 'criar pergunta BNCC');
}

export async function atualizarPerguntaBncc(perguntaId, dados) {
  return enviarJson(`/perguntas/${perguntaId}/atualizar/`, 'PATCH', dados, 'atualizar pergunta BNCC');
}

export async function criarCampoPedagogico(dados) {
  return enviarJson('/campos-pedagogicos/criar/', 'POST', dados, 'criar campo de experiência');
}

export async function excluirPeriodoAvaliativo(periodoId) {
  const response = await authFetch(
    `${API_BASE_URL}/periodos-avaliativos/${periodoId}/excluir/`,
    { method: 'DELETE' },
  );
  return parseJsonOrThrow(response, 'excluir período avaliativo');
}

export async function listarProducoesCrianca(filtros = {}) {
  return getJson(
    comQuery('/producoes/', { aluno: filtros.crianca_id, turma: filtros.turma_id }),
    'listar produções',
  );
}

export async function criarProducaoCrianca(dados) {
  const { crianca_id: alunoId, ...resto } = dados;
  const producao = await enviarJson('/producoes/criar/', 'POST', traduzirPayload(resto), 'criar produção');
  if (alunoId) {
    await enviarJson(`/producoes/${producao.id}/alunos/vincular/`, 'POST', { aluno: alunoId }, 'vincular aluno à produção');
  }
  return producao;
}

export async function deletarProducaoCrianca(producaoId) {
  const response = await authFetch(`${API_BASE_URL}/producoes/${producaoId}/deletar/`, { method: 'DELETE' });
  return parseJsonOrThrow(response, 'excluir produção');
}

export async function uploadProducaoCrianca() {
  return endpointRemovido('producoes-criancas/upload/');
}

export async function listarProjetos(filtros = {}) {
  const projetos = await getJson('/projetos/', 'listar projetos');
  return filtros.status ? projetos.filter((p) => p.status === filtros.status) : projetos;
}

export async function criarProjeto(dados) {
  return enviarJson('/projetos/criar/', 'POST', traduzirPayload(dados), 'criar projeto');
}

export async function atualizarProjeto(projetoId, dados) {
  return enviarJson(`/projetos/${projetoId}/atualizar/`, 'PATCH', traduzirPayload(dados), 'atualizar projeto');
}

export async function deletarProjeto() {
  return endpointRemovido('projetos/<id>/deletar/');
}

export async function listarInstituicoes(filtros = {}) {
  return getJson(comQuery('/instituicoes/', { ativa: filtros.ativa }), 'listar instituições');
}

export async function buscarInstituicao(instituicaoId) {
  return getJson(`/instituicoes/${instituicaoId}/`, 'buscar instituição');
}

export async function criarInstituicao(dados) {
  return enviarJson('/instituicoes/criar/', 'POST', dados, 'criar instituição');
}

export async function atualizarInstituicao(instituicaoId, dados) {
  return enviarJson(`/instituicoes/${instituicaoId}/atualizar/`, 'PATCH', dados, 'atualizar instituição');
}

export async function uploadLogoInstituicao() {
  return endpointRemovido('instituicoes/<id>/logo/');
}

export async function listarEscolas() {
  return getJson('/escolas/', 'listar escolas');
}

export async function listarPromptsRede() {
  return getJson('/prompts/rede/', 'listar prompts da rede');
}

export async function listarPromptsDaEscola(escolaId) {
  return getJson(comQuery('/prompts/categorias/', { escola_id: escolaId }), 'listar prompts da escola');
}

export async function salvarPromptPersonalizado(categoriaId, escolaId, texto) {
  return enviarJson(
    '/prompts/salvar/', 'POST',
    { categoria: categoriaId, escola: escolaId, personalizado: texto },
    'salvar prompt personalizado',
  );
}

export async function salvarPromptGlobal(categoriaId, texto) {
  return enviarJson(
    '/prompts/salvar/', 'POST',
    { categoria: categoriaId, prompt_global: texto },
    'salvar prompt global',
  );
}

export async function listarResumoEscolas() {
  return getJson('/admin/dashboard/', 'carregar o dashboard do admin');
}

export async function listarUsuarios(filtros = {}) {
  const ativo = filtros.ativo === undefined ? undefined : filtros.ativo === true || filtros.ativo === 'true';
  return getJson(
    comQuery('/usuarios/', { nivel: filtros.nivel ?? filtros.perfil, ativo, escola: filtros.escola }),
    'listar usuários',
  );
}

export async function listarUsuariosPaginado({ ativo, escola, nivel, busca, page = 1, pageSize } = {}) {
  return getJson(
    comQuery('/usuarios/', { ativo, escola, nivel, busca, page, page_size: pageSize }),
    'listar usuários',
  );
}

export async function buscarUsuario(usuarioId) {
  return getJson(`/usuarios/${usuarioId}/`, 'buscar usuário');
}

export async function criarUsuario(dados) {
  return enviarJson('/usuarios/criar/', 'POST', dados, 'criar usuário');
}

export async function atualizarUsuario(usuarioId, dados) {
  return enviarJson(`/usuarios/${usuarioId}/atualizar/`, 'PATCH', dados, 'atualizar usuário');
}

export async function deletarUsuario(usuarioId) {
  return atualizarUsuario(usuarioId, { is_active: false });
}