import * as Sentry from "@sentry/react";

/*
 * src/services/api.js — alinhado ao backend multi-tenant.
 *
 * Marcadores usados neste arquivo:
 *   ALTERADO   — rota, método, parâmetro ou payload ajustado ao backend novo.
 *   VERIFICAR  — mapeamento provável; confirmar o formato da resposta na tela que usa.
 *   REMOVIDO   — o backend não tem mais o endpoint. A função continua exportada
 *                (para não quebrar imports), mas lança EndpointRemovidoError.
 */

// Usa variável de ambiente com fallback inteligente para desenvolvimento/produção
// Em desenvolvimento, usa proxy do Vite (caminho relativo /api)
// Em produção, usa URL completa definida em VITE_API_BASE_URL
const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() !== '') {
    return `${envUrl}/api`;
  }
  return '/api';
};

export const API_BASE_URL = getApiBaseUrl();

/*
 * Cabeçalhos que toda chamada à API leva.
 *
 * `ngrok-skip-browser-warning`: quando a aplicação é servida por um túnel
 * ngrok gratuito, o ngrok intercepta requisições com User-Agent de navegador e
 * devolve a página "You are about to visit…" — inclusive nos fetch de API, que
 * então recebem HTML no lugar de JSON e falham em silêncio. O header desliga
 * essa tela. Fora do túnel é um header desconhecido e é ignorado.
 */
export const HEADERS_PADRAO = { 'ngrok-skip-browser-warning': '1' };

// =============================================================================
// Tokens JWT (ALTERADO)
// =============================================================================
// O backend autentica por `Authorization: Bearer <access>` (TenantJWTAuthentication).
// É esse header que define o tenant (instituição/escola) da requisição.
// VERIFICAR: alinhar as chaves abaixo com onde o login (AuthContext) grava os tokens.
const CHAVE_ACCESS = 'access_token';
const CHAVE_REFRESH = 'refresh_token';

export function getAccessToken() {
  return localStorage.getItem(CHAVE_ACCESS);
}

export function getRefreshToken() {
  return localStorage.getItem(CHAVE_REFRESH);
}

/** Chamar após POST auth/login/ (resposta traz `access` e `refresh`). */
export function salvarTokens({ access, refresh }) {
  if (access) localStorage.setItem(CHAVE_ACCESS, access);
  if (refresh) localStorage.setItem(CHAVE_REFRESH, refresh);
}

export function limparTokens() {
  localStorage.removeItem(CHAVE_ACCESS);
  localStorage.removeItem(CHAVE_REFRESH);
}

/*
 * Refresh com rotação: o backend usa ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION,
 * então cada refresh devolve um NOVO refresh token e invalida o anterior. Por isso
 * só pode haver um refresh em andamento por vez (várias chamadas com 401 simultâneas
 * esperam a mesma promise) e o novo par precisa ser salvo.
 */
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

/** Disparado quando a sessão expira de vez. O AuthContext deve ouvir e mandar para o login. */
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

/**
 * Wrapper do fetch que envia o JWT e, num 401, tenta renovar o token uma vez
 * e repetir a requisição.
 *
 * ALTERADO: antes enviava cookie de sessão + X-CSRFToken. Com JWT, CSRF não se
 * aplica e `credentials: 'include'` deixa de ser necessário.
 */
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

async function parseJsonOrThrow(response, contexto) {
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    /* resposta sem corpo JSON */
  }
  if (!response.ok) {
    const mensagem = (data && (data.error || data.detail)) || `Erro ${response.status} em ${contexto}`;
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

/*
 * Nomes de campo: o front antigo usa `crianca_id`, `turma_id`, `perfil`...; o
 * backend novo usa `aluno`, `turma`, `nivel` (FKs sem sufixo _id).
 * `traduzirPayload` converte o que o front ENVIA; `adicionarAliases` acrescenta
 * os nomes antigos ao que o backend DEVOLVE, para as telas continuarem lendo
 * `registro.turma_id` enquanto não são migradas. Usados também pelo apiClient.
 */
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

/**
 * Renomeia campos antigos para os do backend. Escola e instituição são
 * mantidas (renomeadas): admin e superadmin PRECISAM informar a escola ao
 * criar turma/projeto/pergunta; para coordenador e professor o backend ignora
 * o valor e usa a escola do próprio usuário.
 */
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

/** Acrescenta os nomes antigos (turma_id, crianca_id...) a um registro vindo do backend. */
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

/**
 * Usuário do backend (`nivel`, `nome`, `escola`...) no formato que as telas
 * antigas esperam (`perfil`, `user_metadata.full_name`, `escola_id`...).
 */
export function normalizarUsuario(u) {
  if (!u) return null;
  return {
    ...adicionarAliases(u),
    user_metadata: { full_name: u.nome, nome: u.nome, perfil: u.nivel, instituicao_id: u.instituicao },
  };
}

export const apiService = {
  // ── Leitura ─────────────────────────────────────────────────────────

  /**
   * Inicia uma análise de leitura no NaraNN.
   * @param {FormData} formData — campos: audio (Blob), crianca_id, turma_id (opcional)
   */
  async iniciarAnaliseLeitura(formData) {
    const response = await authFetch(`${API_BASE_URL}/leitura/analisar/`, {
      method: 'POST',
      body: formData,
    });
    return parseJsonOrThrow(response, 'iniciar análise de leitura');
  },

  /** Consulta o status atual da análise (probabilidades + classe predita). */
  async consultarAnaliseLeitura(registroId) {
    return getJson(`/leitura/${registroId}/status/`, 'consultar análise de leitura');
  },

  /**
   * Confirma a classe escolhida pela professora e salva o áudio no S3.
   * @param {{ classe_escolhida: string, anotacoes_professora?: string }} payload
   */
  async confirmarAnaliseLeitura(registroId, payload) {
    return enviarJson(`/leitura/${registroId}/confirmar/`, 'POST', payload, 'confirmar análise de leitura');
  },

  /** Cancela um registro pendente (apaga áudio em cache + job no NaraNN). */
  async cancelarAnaliseLeitura(registroId) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/`, { method: 'DELETE' });
    return parseJsonOrThrow(response, 'cancelar análise de leitura');
  },

  /**
   * Lista análises de leitura confirmadas para uma criança no período informado.
   * @param {{ criancaId: string, dataInicio?: string, dataFim?: string }} params
   */
  async listarAnalisesLeitura({ criancaId, dataInicio, dataFim } = {}) {
    if (!criancaId) throw new Error('criancaId é obrigatório.');
    return getJson(
      comQuery('/leitura/', { crianca_id: criancaId, data_inicio: dataInicio, data_fim: dataFim }),
      'listar análises de leitura',
    );
  },

  /**
   * Exclui definitivamente uma análise de leitura (qualquer status).
   * Diferente do cancelamento (DELETE /leitura/<id>/), funciona também para
   * registros confirmados — é o que o botão de exclusão do relatório usa.
   */
  async deletarAnaliseLeitura(registroId) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/deletar/`, { method: 'DELETE' });
    return parseJsonOrThrow(response, 'excluir análise de leitura');
  },

  // ── Dispositivos gravadores (Cadastros → Dispositivos) ──────────────

  /** Lista dispositivos (admin/coordenador: todos do escopo). */
  async listarDispositivos() {
    return getJson('/dispositivos/', 'listar dispositivos');
  },

  /**
   * Gera um código de pareamento (validade curta, uso único).
   * @param {{professoraId?: string, turmaIds?: string[]}} params
   */
  async gerarCodigoPareamento({ professoraId, turmaIds } = {}) {
    return enviarJson('/dispositivos/codigo/', 'POST', {
      ...(professoraId ? { professora_id: professoraId } : {}),
      ...(turmaIds?.length ? { turma_ids: turmaIds } : {}),
    }, 'gerar código de pareamento');
  },

  /**
   * Atualiza nome e/ou vínculo (professora, turmas) — não exige mexer no aparelho.
   * @param {{nome?: string, professora_id?: string, turma_ids?: string[]}} dados
   */
  async atualizarDispositivo(dispositivoId, dados) {
    return enviarJson(`/dispositivos/${dispositivoId}/`, 'PATCH', dados, 'atualizar dispositivo');
  },

  /** Revoga o dispositivo: o token para de funcionar imediatamente. */
  async revogarDispositivo(dispositivoId) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/${dispositivoId}/revogar/`, { method: 'DELETE' });
    return parseJsonOrThrow(response, 'revogar dispositivo');
  },

  /** Reativa um dispositivo revogado por engano (exige novo pareamento). */
  async reativarDispositivo(dispositivoId) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/${dispositivoId}/reativar/`, { method: 'POST' });
    return parseJsonOrThrow(response, 'reativar dispositivo');
  },

  // ── Escrita / desenho ───────────────────────────────────────────────

  /**
   * Upload e análise de escrita.
   * @param {Object} dadosAnalise - { nomeAluno, serieAluno, turmaId }
   * @param {File} arquivo
   */
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

  /** Upload e análise de desenho. @param {FormData} formData */
  async uploadEAnaliseDesenho(formData) {
    const response = await authFetch(`${API_BASE_URL}/upload-desenho/`, {
      method: 'POST',
      body: formData,
    });
    return parseJsonOrThrow(response, 'upload e análise de desenho');
  },

  /** REMOVIDO: versão antiga (só metadados). Use uploadEAnaliseEscrita. */
  async analiseDeEscrita() {
    return endpointRemovido('analise-escrita/');
  },

  /**
   * Atualiza a classificação de um registro de escrita/desenho quando a
   * professora discorda da sugestão da IA (modal de confirmação).
   * @param {'escrita'|'desenho'} tipo
   */
  async atualizarClassificacaoRegistro(tipo, arquivoHash, classificacao) {
    return enviarJson('/registros/classificacao/', 'POST', {
      tipo,
      arquivo_hash: arquivoHash,
      classificacao,
    }, 'atualizar classificação');
  },

  /**
   * REMOVIDO: salvar-anotacoes/. As anotações passaram a ser campo do próprio
   * registro — VERIFICAR se a tela pode usar PATCH registros-escrita/<id>/atualizar/.
   */
  async salvarAnotacoesProfessora() {
    return endpointRemovido('salvar-anotacoes/');
  },

  /** Lista registros de escrita (já recortados pelo tenant). */
  async listarRegistrosEscrita() {
    return getJson('/registros-escrita/', 'listar registros de escrita');
  },

  /** Lista registros de desenho (já recortados pelo tenant). */
  async listarRegistrosDesenho() {
    return getJson('/registros-desenho/', 'listar registros de desenho');
  },

  /**
   * REMOVIDO: registros-aluno/<nome>/ (busca por nome). O backend novo identifica
   * aluno por UUID; a tela precisa passar a trabalhar com o id do aluno.
   */
  async buscarRegistrosPorAluno() {
    return endpointRemovido('registros-aluno/<nome>/');
  },

  // ── Utilitários ─────────────────────────────────────────────────────

  /** REMOVIDO: hello/. Use healthCheck. */
  async testarConexao() {
    return endpointRemovido('hello/');
  },

  /** Health check da API (público, sem token). */
  async healthCheck() {
    const response = await fetch(`${API_BASE_URL}/health/`, { headers: HEADERS_PADRAO });
    return parseJsonOrThrow(response, 'health check');
  },

  // ── Alertas → Notificações ──────────────────────────────────────────

  /**
   * Notificações do usuário logado (substituem mensagens da coordenação e alertas).
   * Cada destinatário tem a própria cópia; `lido_em` nulo = não lida.
   * @param {{ apenasNaoLidas?: boolean }} [opcoes]
   * @returns {Promise<Array<{id, tipo, titulo, conteudo, lido_em, remetente, remetente_nome, criado_em}>>}
   */
  async listarNotificacoes({ apenasNaoLidas = true } = {}) {
    return getJson(apenasNaoLidas ? '/notificacoes/?lidas=false' : '/notificacoes/', 'listar notificações');
  },

  /** ALTERADO: alertas/ virou notificacoes/. Mantido como alias de listarNotificacoes. */
  async listarAlertas() {
    return apiService.listarNotificacoes({ apenasNaoLidas: true });
  },

  /** REMOVIDO: alertas/detalhe/. As notificações já vêm completas na listagem. */
  async buscarDetalheAlerta() {
    return endpointRemovido('alertas/detalhe/');
  },

  /** ALTERADO: marca notificação como lida (novo no backend). */
  async marcarNotificacaoLida(notificacaoId) {
    const response = await authFetch(`${API_BASE_URL}/notificacoes/${notificacaoId}/marcar-lida/`, { method: 'POST' });
    return parseJsonOrThrow(response, 'marcar notificação como lida');
  },

  // ── Coordenação ─────────────────────────────────────────────────────

  /**
   * Agregados do painel da coordenação para um recorte de tempo (calculado ao vivo).
   * `dataInicio`+`dataFim` (YYYY-MM-DD) têm precedência sobre `periodoId`.
   * ALTERADO: admin/superadmin precisam informar `escolaId` (coordenador usa a própria escola).
   * @param {{periodoId?: string, dataInicio?: string, dataFim?: string, escolaId?: string}} [recorte]
   */
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

  /**
   * Períodos avaliativos disponíveis no select da coordenação.
   * ALTERADO: admin/superadmin precisam informar `escolaId`.
   */
  async buscarPeriodosCoordenacao({ escolaId } = {}) {
    return getJson(comQuery('/coordenacao/periodos/', { escola_id: escolaId }), 'buscar períodos da coordenação');
  },

  /**
   * REMOVIDO: o refresh virou rota interna (internal/coordenacao/refresh/, com
   * X-Internal-Token) usada só pelo scheduler. Como o painel agora é calculado
   * ao vivo, o botão "Atualizar" pode simplesmente chamar buscarCacheCoordenacao de novo.
   */
  async atualizarCacheCoordenacao() {
    return endpointRemovido('coordenacao/cache/refresh/');
  },

  /**
   * ALTERADO / VERIFICAR: indicadores/linguagem/ virou coordenacao/indicadores-turma/.
   * O instituicaoId é ignorado (o escopo vem do usuário logado). O formato da
   * resposta provavelmente mudou — conferir na tela.
   */
  async listarIndicadorLinguagem(_instituicaoId, turmaId = null, periodoId = null) {
    return getJson(
      comQuery('/coordenacao/indicadores-turma/', { turma_id: turmaId, periodo_id: periodoId }),
      'listar indicadores da turma',
    );
  },

  // ── BNCC ────────────────────────────────────────────────────────────

  /** Lista habilidades da BNCC (filtros opcionais). */
  async listarHabilidadesBNCC(componente = null, anoSerie = null) {
    return getJson(
      comQuery('/habilidades-bncc/', { componente, ano_serie: anoSerie }),
      'listar habilidades BNCC',
    );
  },

  /** Cria nova habilidade BNCC. */
  async criarHabilidadeBNCC(dadosHabilidade) {
    return enviarJson('/habilidades-bncc/criar/', 'POST', dadosHabilidade, 'criar habilidade BNCC');
  },

  /** REMOVIDO: habilidades-bncc/popular/. A carga inicial agora é feita no backend (migration/comando). */
  async popularHabilidadesBNCC() {
    return endpointRemovido('habilidades-bncc/popular/');
  },

  // ── Planejamento ────────────────────────────────────────────────────

  /**
   * Processa um arquivo de planejamento (PDF/DOC/DOCX): sobe para o S3,
   * extrai o texto e devolve uma sugestão de "Atividades Propostas".
   * @param {string} diaSemana - 'segunda' | 'terca' | 'quarta' | 'quinta' | 'sexta'
   */
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

  /**
   * Assistente IA: gera sugestão de atividades a partir de uma descrição livre.
   * @param {{prompt: string, ano_serie?: string, contexto?: string}} payload
   */
  async sugerirAtividadesPlanejamento(payload) {
    return enviarJson('/planejamento/sugerir-atividades/', 'POST', payload, 'sugerir atividades de planejamento');
  },

  /**
   * Aplica atividades extraídas de um arquivo em uma ou mais semanas.
   * Sobrescreve apenas os dias informados; mantém os demais.
   */
  async aplicarPlanejamentoEmSemanas(payload) {
    return enviarJson('/planejamento/aplicar-em-semanas/', 'POST', payload, 'aplicar planejamento em semanas');
  },

  /**
   * Sugere habilidades BNCC com base no texto de "Atividades Propostas".
   * @param {{atividades_texto: string, ano_serie?: string, limite?: number}} payload
   */
  async sugerirBnccPlanejamento(payload) {
    return enviarJson('/planejamento/sugerir-bncc/', 'POST', payload, 'sugerir habilidades BNCC');
  },

  /** ALTERADO: POST planejamento/ → POST planejamento/criar/. */
  async criarPlanejamentoSemanal(dadosPlanejamento) {
    return enviarJson('/planejamento/criar/', 'POST', dadosPlanejamento, 'criar planejamento semanal');
  },

  /**
   * ALTERADO: GET planejamento/<turma>/?semana_inicio= não existe mais.
   * Agora é a listagem filtrada por turma e pela semana. Mantém o retorno de
   * UM planejamento (ou null), como a tela esperava.
   * @param {string} semanaInicio - YYYY-MM-DD
   */
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

  /** ALTERADO: PUT planejamento/atualizar/<id>/ → PUT planejamento/<id>/atualizar/. */
  async atualizarPlanejamentoSemanal(planejamentoId, dadosPlanejamento) {
    return enviarJson(`/planejamento/${planejamentoId}/atualizar/`, 'PUT', dadosPlanejamento, 'atualizar planejamento semanal');
  },

  /** ALTERADO: planejamentos/turma/<id>/ → planejamento/?turma_id=<id>. */
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

  // ── Relatórios ──────────────────────────────────────────────────────

  /** Gera relatório usando IA. */
  async gerarRelatorio(dadosRelatorio) {
    return enviarJson('/gerar-relatorio/', 'POST', dadosRelatorio, 'gerar relatório');
  },

  /**
   * Gera relatório para uma criança usando período avaliativo.
   * @param {string} criancaId - UUID do aluno
   * @param {string} [periodoId] - UUID do período avaliativo
   */
  async gerarRelatorioPorCrianca(criancaId, periodoId) {
    return enviarJson(
      `/gerar-relatorio/${criancaId}/`,
      'POST',
      periodoId ? { periodo_id: periodoId } : {},
      'gerar relatório por criança',
    );
  },

  /**
   * ALTERADO: relatorios/salvar/ → relatorios/criar/.
   * `id_crianca` virou `aluno`; `instituicao_id` não é mais enviado (vem do aluno).
   */
  async salvarRelatorio(dadosRelatorio) {
    return enviarJson('/relatorios/criar/', 'POST', {
      aluno: dadosRelatorio.id_crianca ?? dadosRelatorio.aluno,
      periodo: dadosRelatorio.periodo,
      conteudo: dadosRelatorio.conteudo,
      ...(dadosRelatorio.template ? { template: dadosRelatorio.template } : {}),
    }, 'salvar relatório');
  },

  /**
   * Baixa o PDF do relatório gerado pelo backend (serviço report_generator + S3).
   * Retorna { blob, filename, cached }.
   */
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

  /**
   * Gera PDFs em lote e empacota em um ZIP no S3. O backend responde com um
   * stream NDJSON (um JSON por linha) com eventos de progresso e, no final,
   * um evento `done` contendo a URL presigned para baixar o ZIP.
   */
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

    // eslint-disable-next-line no-constant-condition
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
    // Flush final (caso último evento venha sem \n).
    processarLinha(buffer.trim());

    if (!doneEvent) {
      throw new Error('Stream encerrado sem evento final.');
    }
    return doneEvent;
  },

  /** REMOVIDO: o PDF agora é gerado no backend. Use baixarPdfRelatorio. */
  async uploadRelatorioPdf() {
    return endpointRemovido('relatorios/<id>/pdf/ (upload)');
  },

  /** REMOVIDO: o download já devolve o PDF direto. Use baixarPdfRelatorio. */
  async refreshRelatorioPdf() {
    return endpointRemovido('relatorios/<id>/pdf/refresh/');
  },

  /** REMOVIDO: dados-relatorio/<id>/. Os dados são montados pelo backend em gerar-relatorio/<id>/. */
  async buscarDadosRelatorio() {
    return endpointRemovido('dados-relatorio/<id>/');
  },
};

// Exportações individuais para compatibilidade
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

// Planejamento, funções relacionadas
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

// Relatórios
export const gerarRelatorio = apiService.gerarRelatorio;
export const gerarRelatorioPorCrianca = apiService.gerarRelatorioPorCrianca;
export const salvarRelatorio = apiService.salvarRelatorio;
export const uploadRelatorioPdf = apiService.uploadRelatorioPdf;
export const baixarPdfRelatorio = apiService.baixarPdfRelatorio;
export const bulkPdfRelatoriosStream = apiService.bulkPdfRelatoriosStream;
export const refreshRelatorioPdf = apiService.refreshRelatorioPdf;
export const buscarDadosRelatorio = apiService.buscarDadosRelatorio;

// =============================================================================
// ALUNOS (antigo "crianças") — ALTERADO: /criancas/ → /alunos/
// =============================================================================

/**
 * Lista alunos. Já vem recortado pelo tenant.
 * ALTERADO: o backend só filtra por turma (`?turma=`). `instituicao_id` deixou de
 * existir e `status_vinculo` é aplicado aqui no front.
 * VERIFICAR: o backend devolve um ARRAY, sem paginação (page/page_size são ignorados).
 * Se a tela lia `data.results`/`data.count`, precisa ajustar.
 * @param {Object} filtros - { turma_id, status_vinculo }
 */
export async function listarCriancas(filtros = {}) {
  const alunos = await getJson(comQuery('/alunos/', { turma: filtros.turma_id }), 'listar alunos');
  return filtros.status_vinculo
    ? alunos.filter((a) => a.status_vinculo === filtros.status_vinculo)
    : alunos;
}

/** Detalhe de um aluno. @param {string} criancaId - UUID do aluno */
export async function buscarCrianca(criancaId) {
  return getJson(`/alunos/${criancaId}/`, 'buscar aluno');
}

/**
 * Cria aluno. ALTERADO: `turma_id` vira `turma` (obrigatório); escola e
 * instituição são definidas pelo backend a partir da turma.
 */
export async function criarCrianca(dados) {
  return enviarJson('/alunos/criar/', 'POST', traduzirPayload(dados), 'criar aluno');
}

/** Atualiza aluno. ALTERADO: /criancas/<id>/atualizar/ → /alunos/<id>/atualizar/. */
export async function atualizarCrianca(criancaId, dados) {
  return enviarJson(`/alunos/${criancaId}/atualizar/`, 'PATCH', traduzirPayload(dados), 'atualizar aluno');
}

/**
 * ALTERADO: não existe mais rota de exclusão de aluno. O "soft delete" é feito
 * mudando o status_vinculo pelo endpoint de atualização.
 */
export async function deletarCrianca(criancaId) {
  return atualizarCrianca(criancaId, { status_vinculo: 'inativo' });
}

/**
 * Cria vários alunos em sequência, com progresso.
 * @returns {{ successCount: number, errors: Array<{ nome: string, message: string }> }}
 */
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

/** REMOVIDO: criancas/<id>/foto/. O aluno tem o campo foto_url, mas não há endpoint de upload. */
export async function uploadFotoCrianca() {
  return endpointRemovido('criancas/<id>/foto/');
}

// =============================================================================
// RELATÓRIOS
// =============================================================================

/**
 * Lista relatórios. ALTERADO: o filtro `id_crianca` virou `?aluno=`;
 * `instituicao_id` é ignorado (escopo vem do usuário).
 * @param {Object} filtros - { id_crianca }
 */
export async function listarRelatorios(filtros = {}) {
  return getJson(comQuery('/relatorios/', { aluno: filtros.id_crianca ?? filtros.aluno }), 'listar relatórios');
}

/** Detalhe de um relatório. */
export async function buscarRelatorio(relatorioId) {
  return getJson(`/relatorios/${relatorioId}/`, 'buscar relatório');
}

/** Atualiza relatório (PUT = todos os campos editáveis; PATCH também é aceito). */
export async function atualizarRelatorio(relatorioId, dados) {
  return enviarJson(`/relatorios/${relatorioId}/atualizar/`, 'PUT', traduzirPayload(dados), 'atualizar relatório');
}

/** Exclui relatório e o PDF associado. */
export async function deletarRelatorio(relatorioId) {
  const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/deletar/`, { method: 'DELETE' });
  return parseJsonOrThrow(response, 'excluir relatório');
}

// =============================================================================
// OBSERVAÇÕES — ALTERADO: /observacoes/ → /registros-observacao/
// =============================================================================

/**
 * Lista registros de observação.
 * ALTERADO: o backend só filtra por aluno (`?aluno=`). Professor e datas
 * são filtrados aqui no front; `turma_id` não é mais suportado.
 * @param {Object} filtros - { crianca_id, professor_id, data_inicio, data_fim }
 */
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

/**
 * Cria registro de observação. ALTERADO: `crianca_id` → `aluno`, `pergunta_id` → `pergunta`;
 * professor, escola e instituição são definidos pelo backend.
 */
export async function criarObservacao(dados) {
  return enviarJson('/registros-observacao/criar/', 'POST', traduzirPayload(dados), 'criar observação');
}

/**
 * ALTERADO: observacoes/lote/ não existe mais. Cria um a um e reporta falhas,
 * no mesmo formato de criarCriancasLote.
 */
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

// =============================================================================
// PERGUNTAS — ALTERADO / VERIFICAR: /perguntas-bncc/ → /perguntas/
// =============================================================================

/**
 * Lista perguntas. O backend filtra só por `faixa_etaria`; `campo_experiencia`
 * e `ids` são aplicados aqui no front.
 * VERIFICAR: nome do campo de campo de experiência no PerguntaSerializer.
 * @param {Object} filtros - { faixa_etaria, campo_experiencia, ids }
 */
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

/** Mesmo endpoint de listarPerguntasBncc (mantido por compatibilidade de nome). */
export async function listarPerguntasBNCC(filtros = {}) {
  return listarPerguntasBncc(filtros);
}

// =============================================================================
// TURMAS
// =============================================================================

/**
 * Lista turmas. Já vem recortado pelo tenant.
 * ALTERADO: o backend ignora todos os query params. Se `id` for informado,
 * busca o detalhe (antes, mandar ?id= devolvia TODAS as turmas). `ativa` é
 * filtrado aqui no front; `instituicao_id` é ignorado.
 * @param {Object} filtros - { id, ativa }
 */
export async function listarTurmas(filtros = {}) {
  if (filtros.id) {
    return [await buscarTurma(filtros.id)];
  }
  const turmas = await getJson('/turmas/', 'listar turmas');
  if (filtros.ativa === undefined) return turmas;
  const ativa = filtros.ativa === true || filtros.ativa === 'true';
  return turmas.filter((t) => t.ativa === undefined || t.ativa === ativa);
}

/** Detalhe de uma turma. */
export async function buscarTurma(turmaId) {
  return getJson(`/turmas/${turmaId}/`, 'buscar turma');
}

// =============================================================================
// PRODUÇÕES — ALTERADO: /producoes-criancas/ → /producoes/
// =============================================================================

/**
 * Lista produções. ALTERADO: filtros viraram `?turma=` e `?aluno=`;
 * `instituicao_id` é ignorado.
 * @param {Object} filtros - { crianca_id, turma_id }
 */
export async function listarProducoesCrianca(filtros = {}) {
  return getJson(
    comQuery('/producoes/', { aluno: filtros.crianca_id, turma: filtros.turma_id }),
    'listar produções',
  );
}

/**
 * Cria produção. ALTERADO: no backend novo a produção pertence à TURMA e os
 * alunos são vinculados depois. Se vier `crianca_id`, faz o vínculo em seguida.
 * Professor, escola e instituição são definidos pelo backend.
 */
export async function criarProducaoCrianca(dados) {
  const { crianca_id: alunoId, ...resto } = dados;
  const producao = await enviarJson('/producoes/criar/', 'POST', traduzirPayload(resto), 'criar produção');
  if (alunoId) {
    await enviarJson(`/producoes/${producao.id}/alunos/vincular/`, 'POST', { aluno: alunoId }, 'vincular aluno à produção');
  }
  return producao;
}

/** Exclui produção. */
export async function deletarProducaoCrianca(producaoId) {
  const response = await authFetch(`${API_BASE_URL}/producoes/${producaoId}/deletar/`, { method: 'DELETE' });
  return parseJsonOrThrow(response, 'excluir produção');
}

/**
 * REMOVIDO: producoes-criancas/upload/ (multipart). O /producoes/criar/ novo
 * recebe JSON com arquivo_url — falta um endpoint de upload no backend.
 */
export async function uploadProducaoCrianca() {
  return endpointRemovido('producoes-criancas/upload/');
}

// =============================================================================
// PROJETOS
// =============================================================================

/**
 * Lista projetos. Já vem recortado pelo tenant.
 * ALTERADO: o backend ignora query params; `status` é filtrado aqui no front.
 * @param {Object} filtros - { status }
 */
export async function listarProjetos(filtros = {}) {
  const projetos = await getJson('/projetos/', 'listar projetos');
  return filtros.status ? projetos.filter((p) => p.status === filtros.status) : projetos;
}

/** Cria projeto (escola/instituição definidas pelo backend). */
export async function criarProjeto(dados) {
  return enviarJson('/projetos/criar/', 'POST', traduzirPayload(dados), 'criar projeto');
}

/** Atualiza projeto. */
export async function atualizarProjeto(projetoId, dados) {
  return enviarJson(`/projetos/${projetoId}/atualizar/`, 'PATCH', traduzirPayload(dados), 'atualizar projeto');
}

/** REMOVIDO: não existe rota de exclusão de projeto. VERIFICAR se basta mudar o status. */
export async function deletarProjeto() {
  return endpointRemovido('projetos/<id>/deletar/');
}

// =============================================================================
// INSTITUIÇÕES
// =============================================================================

/** Lista instituições (o backend decide quais o usuário pode ver). */
export async function listarInstituicoes(filtros = {}) {
  return getJson(comQuery('/instituicoes/', { ativa: filtros.ativa }), 'listar instituições');
}

/** Detalhe de uma instituição. */
export async function buscarInstituicao(instituicaoId) {
  return getJson(`/instituicoes/${instituicaoId}/`, 'buscar instituição');
}

/** Cria instituição (só perfis globais). */
export async function criarInstituicao(dados) {
  return enviarJson('/instituicoes/criar/', 'POST', dados, 'criar instituição');
}

/** Atualiza instituição. */
export async function atualizarInstituicao(instituicaoId, dados) {
  return enviarJson(`/instituicoes/${instituicaoId}/atualizar/`, 'PATCH', dados, 'atualizar instituição');
}

/** REMOVIDO: instituicoes/<id>/logo/ não existe no backend novo. */
export async function uploadLogoInstituicao() {
  return endpointRemovido('instituicoes/<id>/logo/');
}

// =============================================================================
// ESCOLAS
// =============================================================================

/**
 * Escolas do escopo do usuário com os totais para os cards do painel do admin:
 * [{ id, nome, tipo_unidade, cidade, estado, ativa, totais: { turmas, alunos, professores, coordenadores } }]
 * Só gestão (admin, coordenador, superadmin).
 */
export async function listarResumoEscolas() {
  return getJson('/admin/dashboard/', 'carregar o dashboard do admin');
}

// =============================================================================
// USUÁRIOS
// =============================================================================

/**
 * Lista usuários. Só gestão (admin/coordenador/superadmin) tem acesso; os
 * demais recebem 403 e devem usar /me/.
 * ALTERADO: o backend ignora query params; `perfil` e `ativo` são filtrados aqui.
 * O antigo `perfil` agora se chama `nivel`.
 * @param {Object} filtros - { perfil, ativo }
 */
export async function listarUsuarios(filtros = {}) {
  let usuarios = await getJson('/usuarios/', 'listar usuários');
  if (filtros.perfil) {
    usuarios = usuarios.filter((u) => u.nivel === filtros.perfil);
  }
  if (filtros.ativo !== undefined) {
    const ativo = filtros.ativo === true || filtros.ativo === 'true';
    usuarios = usuarios.filter((u) => u.is_active === ativo);
  }
  return usuarios;
}

/** Detalhe de um usuário. */
export async function buscarUsuario(usuarioId) {
  return getJson(`/usuarios/${usuarioId}/`, 'buscar usuário');
}

/** Cria usuário (incluindo password). */
export async function criarUsuario(dados) {
  return enviarJson('/usuarios/criar/', 'POST', dados, 'criar usuário');
}

/** Atualiza usuário. */
export async function atualizarUsuario(usuarioId, dados) {
  return enviarJson(`/usuarios/${usuarioId}/atualizar/`, 'PATCH', dados, 'atualizar usuário');
}

/**
 * ALTERADO: não existe rota de exclusão. O soft delete é feito desativando.
 */
export async function deletarUsuario(usuarioId) {
  return atualizarUsuario(usuarioId, { is_active: false });
}