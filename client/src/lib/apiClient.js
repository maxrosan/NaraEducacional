/**
 * Cliente de API com interface estilo Supabase (`apiClient.from('tabela')...`),
 * mantida para compatibilidade com as telas antigas.
 *
 * ALTERADO para o backend multi-tenant:
 *   - Autenticação por JWT (via `authFetch` de services/api.js), sem sessão
 *     Django, cookie de CSRF ou /auth/csrf/.
 *   - Tabelas antigas mapeadas para as rotas novas (criancas → alunos etc.).
 *   - FILTROS NO FRONT: a maioria das listagens do backend novo ignora query
 *     params — já devolve tudo o que está no escopo do usuário (escola ou rede).
 *     Por isso .eq/.in/.gte/.ilike/.order/.limit são aplicados aqui, depois da
 *     resposta. O isolamento entre tenants continua garantido pelo backend;
 *     o filtro local só recorta dentro do que o usuário já pode ver.
 *   - Respostas ganham aliases dos nomes antigos (turma_id, crianca_id, perfil...).
 *   - Tabelas sem equivalente no backend devolvem erro explícito, não 404 mudo.
 */
import * as Sentry from '@sentry/react';
import {
  API_BASE_URL,
  HEADERS_PADRAO,
  EVENTO_SESSAO_EXPIRADA,
  authFetch,
  getAccessToken,
  getRefreshToken,
  salvarTokens,
  limparTokens,
  traduzirPayload,
  adicionarAliases,
  normalizarUsuario,
} from '@/services/api';

const REQUEST_TIMEOUT = 15000; // 15 segundos

// =============================================================================
// Mapeamento de tabelas → recursos do backend
// =============================================================================

/** Nome antigo (tabela ou rota) → recurso novo. Nomes não listados só trocam _ por -. */
const TABELAS = {
  criancas: 'alunos',
  perguntas_bncc: 'perguntas',
  'perguntas-bncc': 'perguntas',
  producoes_criancas: 'producoes',
  'producoes-criancas': 'producoes',
  portfolios: 'producoes',
  registros_observacao: 'registros-observacao',
  observacoes: 'registros-observacao',
  // A rota do backend é no singular (planejamento/); a tabela é planejamentos_semanais.
  planejamentos: 'planejamento',
  planejamentos_semanais: 'planejamento',
  'planejamentos-semanais': 'planejamento',
  planejamento_semanal: 'planejamento',
  // VERIFICAR: atendimentos viraram sessões do especialista no backend novo.
  atendimentos_especialistas: 'sessoes-especialista',
  'atendimentos-especialistas': 'sessoes-especialista',
};

/** Operações que cada recurso tem no backend (conferido em api/urls.py). */
const RECURSOS = {
  alunos: ['criar', 'atualizar'],
  'campos-pedagogicos': ['criar', 'atualizar'],
  contratos: ['criar', 'atualizar'],
  disciplinas: ['criar', 'atualizar'],
  escolas: ['criar', 'atualizar'],
  especialistas: ['criar', 'atualizar'],
  'habilidades-bncc': ['criar', 'atualizar'],
  instituicoes: ['criar', 'atualizar'],
  'logs-auditoria': [],
  'metas-paee': ['criar', 'atualizar'],
  notificacoes: ['criar'],
  'observacoes-transcricao': ['criar', 'atualizar', 'deletar'],
  perguntas: ['criar', 'atualizar'],
  'perguntas-especialistas': ['criar', 'atualizar'],
  'periodos-avaliativos': ['criar', 'atualizar'],
  'permissoes-usuario': ['criar', 'deletar'],
  planejamento: ['criar', 'atualizar'],
  producoes: ['criar', 'atualizar', 'deletar'],
  projetos: ['criar', 'atualizar'],
  'registros-desenho': ['atualizar', 'deletar'],
  'registros-escrita': ['atualizar', 'deletar'],
  'registros-observacao': ['criar', 'atualizar', 'deletar'],
  'relatorio-templates': ['criar', 'atualizar'],
  relatorios: ['criar', 'atualizar', 'deletar'],
  'sessoes-especialista': ['criar', 'atualizar'],
  'tarefas-paee': ['criar', 'atualizar'],
  'templates-documento': ['criar', 'atualizar'],
  tickets: ['criar', 'atualizar'],
  turmas: ['criar', 'atualizar'],
  usuarios: ['criar', 'atualizar'],
};

/** Recursos cuja rota de atualização só aceita PUT (os demais aceitam PATCH). */
const SO_PUT = new Set(['planejamento']);

/** Recursos com rota de detalhe `<recurso>/<id>/`. */
const COM_DETALHE = new Set(
  Object.keys(RECURSOS).filter((r) => !['planejamento', 'notificacoes', 'permissoes-usuario'].includes(r)),
);

/**
 * Filtros que o backend realmente aplica no servidor (coluna antiga → param).
 * Enviá-los só reduz o tráfego; o resultado é filtrado no front de qualquer jeito.
 */
const PARAMS_NO_SERVIDOR = {
  alunos: { turma_id: 'turma', turma: 'turma' },
  producoes: { turma_id: 'turma', turma: 'turma', crianca_id: 'aluno', aluno_id: 'aluno', aluno: 'aluno' },
  'registros-observacao': { crianca_id: 'aluno', aluno_id: 'aluno', aluno: 'aluno' },
  relatorios: { crianca_id: 'aluno', id_crianca: 'aluno', aluno_id: 'aluno', aluno: 'aluno' },
  perguntas: { faixa_etaria: 'faixa_etaria' },
  planejamento: { turma_id: 'turma_id', professora_id: 'professora_id' },
};

/**
 * Tabelas de vínculo que não existem como recurso próprio: no backend novo o
 * vínculo fica aninhado na entidade pai (turmas/<id>/professores/...).
 */
const VINCULOS = {
  usuario_turmas: { pai: 'turmas', chavePai: 'turma_id', campoPai: 'turma' },
  'usuario-turmas': { pai: 'turmas', chavePai: 'turma_id', campoPai: 'turma' },
  usuario_disciplinas: { pai: 'disciplinas', chavePai: 'disciplina_id', campoPai: 'disciplina' },
  'usuario-disciplinas': { pai: 'disciplinas', chavePai: 'disciplina_id', campoPai: 'disciplina' },
};

/** Tabelas do sistema antigo sem equivalente no backend multi-tenant. */
const SEM_EQUIVALENTE = new Set([
  'mensagens_lidas', 'mensagens-lidas',
  'mensagens_coordenacao', 'mensagens-coordenacao',
  'alertas_lidos', 'alertas-lidos',
  'observacoes_especialistas', 'observacoes-especialistas',
  'especialista_funcoes', 'especialista-funcoes',
  'projeto_turmas', 'projeto-turmas',
  'observacoes_comentarios', 'observacoes-comentarios',
  'configuracoes_registro', 'configuracoes-registro',
  'series_config', 'series-config',
]);

function resolverRecurso(tabela) {
  return TABELAS[tabela] || tabela.replace(/_/g, '-');
}

// =============================================================================
// Utilitários
// =============================================================================

function humanizeFieldName(field) {
  return (field || '').toString().replace(/_/g, ' ').trim();
}

function flattenValidationErrors(errors, prefix = '') {
  if (!errors || typeof errors !== 'object') return [];
  const messages = [];
  Object.entries(errors).forEach(([field, value]) => {
    const label = prefix || humanizeFieldName(field);
    if (Array.isArray(value)) {
      value.forEach((item) => messages.push(label ? `${label}: ${item}` : `${item}`));
      return;
    }
    if (value && typeof value === 'object') {
      messages.push(...flattenValidationErrors(value, label));
      return;
    }
    messages.push(label ? `${label}: ${value}` : `${value}`);
  });
  return messages;
}

function formatErrorMessage(data, padrao = 'Erro ao salvar dados') {
  if (!data) return padrao;
  if (typeof data === 'string') return data;

  const details = data.details && typeof data.details === 'object' ? data.details : null;
  const principal = (typeof data.error === 'string' && data.error.trim())
    || (typeof data.detail === 'string' && data.detail.trim())
    || '';
  const semPrincipal = { ...(details || data) };
  delete semPrincipal.error;
  delete semPrincipal.detail;
  delete semPrincipal.code;
  const validacao = flattenValidationErrors(semPrincipal);

  if (principal) return validacao.length ? `${principal} ${validacao.join(' ')}` : principal;
  return validacao.length ? validacao.join(' ') : padrao;
}

/** GET/POST/... autenticado, com timeout. Devolve { response, data }. */
async function requisitar(caminho, { method = 'GET', body, signal } = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
  const url = `${API_BASE_URL}/${caminho}`;

  try {
    const response = await authFetch(url, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: signal || controller.signal,
    });
    let data = null;
    try {
      data = await response.json();
    } catch (_) { /* resposta sem corpo JSON */ }
    return { response, data };
  } catch (error) {
    if (error.name === 'AbortError') {
      Sentry.captureException(new Error(`Request timeout: ${method} ${url}`));
      const err = new Error('A requisição demorou demais. Tente novamente.');
      err.name = 'AbortError';
      throw err;
    }
    Sentry.captureException(error);
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

function comoLista(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results; // resposta paginada do DRF
  return data ? [data] : [];
}

// ── Filtros aplicados no front ─────────────────────────────────────────────

const avisosEmitidos = new Set();
function avisarUmaVez(chave, mensagem) {
  if (avisosEmitidos.has(chave)) return;
  avisosEmitidos.add(chave);
  console.warn(mensagem);
}

function comparar(a, b) {
  if (a === b) return 0;
  if (a === null || a === undefined) return 1; // nulos por último
  if (b === null || b === undefined) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(a) - Number(b);
  return String(a).localeCompare(String(b), 'pt-BR', { numeric: true });
}

function mesmoValor(a, b) {
  if (a === null || b === null || a === undefined || b === undefined) return a === b;
  if (typeof a === 'boolean' || typeof b === 'boolean') return String(a) === String(b);
  return String(a) === String(b);
}

function passaNoFiltro(registro, { column, op, value }) {
  const atual = registro[column];
  switch (op) {
    case 'eq': return mesmoValor(atual, value);
    case 'neq': return !mesmoValor(atual, value);
    case 'in': return (value || []).some((v) => mesmoValor(atual, v));
    case 'gte': return atual !== null && atual !== undefined && comparar(atual, value) >= 0;
    case 'gt': return atual !== null && atual !== undefined && comparar(atual, value) > 0;
    case 'lte': return atual !== null && atual !== undefined && comparar(atual, value) <= 0;
    case 'lt': return atual !== null && atual !== undefined && comparar(atual, value) < 0;
    case 'is': return value === null ? atual === null || atual === undefined : atual === value;
    case 'ilike': {
      const termo = String(value ?? '').replace(/%/g, '').toLowerCase();
      return String(atual ?? '').toLowerCase().includes(termo);
    }
    default: return true;
  }
}

/**
 * Aplica filtros, ordenação e paginação localmente.
 * Coluna que não existe em NENHUM registro é ignorada (com aviso no console):
 * o campo provavelmente foi renomeado no backend, e filtrar por ele esvaziaria
 * a tela sem explicação. O aviso diz exatamente qual coluna revisar.
 */
function aplicarNoFront(registros, estado, recurso) {
  let lista = registros;

  estado.filters.forEach((filtro) => {
    const colunaExiste = lista.some((r) => r[filtro.column] !== undefined);
    if (!colunaExiste && lista.length > 0) {
      avisarUmaVez(
        `${recurso}.${filtro.column}`,
        `[apiClient] Filtro "${filtro.column}" ignorado em "${recurso}": o campo não existe na resposta do backend. Revise a tela que faz essa consulta.`,
      );
      return;
    }
    lista = lista.filter((r) => passaNoFiltro(r, filtro));
  });

  if (estado.orderBy) {
    const desc = estado.orderBy.startsWith('-');
    const coluna = desc ? estado.orderBy.slice(1) : estado.orderBy;
    lista = [...lista].sort((a, b) => (desc ? -1 : 1) * comparar(a[coluna], b[coluna]));
  }

  const total = lista.length;

  if (estado.rangeFrom !== null) {
    lista = lista.slice(estado.rangeFrom, estado.rangeTo + 1);
  } else if (estado.limitCount) {
    const inicio = estado.page ? (estado.page - 1) * estado.limitCount : 0;
    lista = lista.slice(inicio, inicio + estado.limitCount);
  }

  return { lista, total };
}

// =============================================================================
// Autenticação (JWT)
// =============================================================================

let authStateListeners = [];

function notifyAuthStateChange(event, session) {
  authStateListeners.forEach((callback) => {
    try {
      callback(event, session);
    } catch (e) {
      console.error('Erro no callback de auth:', e);
    }
  });
}

// O authFetch dispara este evento quando nem o refresh token vale mais.
if (typeof window !== 'undefined') {
  window.addEventListener(EVENTO_SESSAO_EXPIRADA, () => notifyAuthStateChange('SESSION_EXPIRED', null));
}

function montarSessao(usuario) {
  return usuario ? { user: usuario, access_token: getAccessToken() } : null;
}

/** Usuário logado via GET /me/ (null se não houver token ou se ele não valer). */
async function fetchCurrentUser() {
  if (!getAccessToken()) return null;
  try {
    const { response, data } = await requisitar('me/');
    return response.ok ? normalizarUsuario(data) : null;
  } catch (error) {
    console.error('[apiClient] Erro ao buscar usuário:', error);
    return null;
  }
}

const auth = {
  async getSession() {
    const user = await fetchCurrentUser();
    return { data: { session: montarSessao(user) }, error: null };
  },

  async getUser() {
    const user = await fetchCurrentUser();
    return { data: { user }, error: null };
  },

  onAuthStateChange(callback) {
    authStateListeners.push(callback);
    fetchCurrentUser().then((user) => {
      if (user) callback('SIGNED_IN', montarSessao(user));
    });
    return {
      data: {
        subscription: {
          unsubscribe: () => {
            authStateListeners = authStateListeners.filter((cb) => cb !== callback);
          },
        },
      },
    };
  },

  /** `remember_me` não tem mais efeito (a duração é a do refresh token). */
  // eslint-disable-next-line no-unused-vars
  async signInWithPassword({ email, password, remember_me = false }) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { ...HEADERS_PADRAO, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const message = response.status === 401
          ? 'E-mail ou senha inválidos.'
          : formatErrorMessage(data, 'Erro ao fazer login');
        return { data: { user: null, session: null }, error: { message } };
      }

      salvarTokens(data);
      const user = normalizarUsuario(data.usuario);
      const session = montarSessao(user);
      notifyAuthStateChange('SIGNED_IN', session);
      return { data: { user, session }, error: null };
    } catch (error) {
      console.error('Erro no login:', error);
      return { data: { user: null, session: null }, error: { message: 'Erro de conexão com o servidor' } };
    }
  },

  /**
   * Invalida o refresh token no backend (auth/logout/) e apaga os tokens locais.
   * O estado local é limpo mesmo se a chamada falhar.
   */
  async signOut() {
    let erro = null;
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/logout/`, {
          method: 'POST',
          headers: { ...HEADERS_PADRAO, 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
        if (!response.ok) {
          erro = { message: `Não foi possível encerrar a sessão no servidor (${response.status}).` };
        }
      } catch (error) {
        console.error('Erro no logout:', error);
        erro = { message: 'Erro de rede ao fazer logout' };
      }
    }
    limparTokens();
    notifyAuthStateChange('SIGNED_OUT', null);
    return { error: erro };
  },

  notifySignedOut() {
    limparTokens();
    notifyAuthStateChange('SESSION_EXPIRED', null);
  },

  async signUp() {
    return {
      data: { user: null, session: null },
      error: { message: 'Registro de usuários deve ser feito pelo administrador.' },
    };
  },
};

// =============================================================================
// Consultas e mutações
// =============================================================================

function erroSemEquivalente(tabela, singleResult) {
  const message = `A tabela "${tabela}" não existe no backend multi-tenant.`;
  avisarUmaVez(`sem-equivalente.${tabela}`, `[apiClient] ${message}`);
  return { data: singleResult ? null : [], count: null, error: { message } };
}

function respostaDeErro(response, data, contexto, estado) {
  Sentry.captureMessage(`API ${contexto} → ${response.status}`, {
    level: 'warning',
    extra: { status: response.status, recurso: estado.recurso, erro: formatErrorMessage(data) },
  });
  const message = response.status === 404
    ? `Não encontrado (${contexto}).`
    : formatErrorMessage(data, 'Erro ao buscar dados');
  return { data: estado.singleResult ? null : [], count: null, error: { message, status: response.status } };
}

function filtroIgual(estado, ...colunas) {
  const f = estado.filters.find((x) => x.op === 'eq' && colunas.includes(x.column));
  return f ? f.value : null;
}

/** Lista registros de vínculo (usuario_turmas / usuario_disciplinas). */
async function listarVinculos(estado, vinculo) {
  const paiId = filtroIgual(estado, vinculo.chavePai, vinculo.campoPai);
  let pais;
  if (paiId) {
    pais = [{ id: paiId }];
  } else {
    const { response, data } = await requisitar(`${vinculo.pai}/`);
    if (!response.ok) return { response, data };
    pais = comoLista(data);
  }

  const listas = await Promise.all(pais.map(async (pai) => {
    const { response, data } = await requisitar(`${vinculo.pai}/${pai.id}/professores/`);
    if (!response.ok) return [];
    return comoLista(data).map((v) => ({
      ...v,
      [vinculo.campoPai]: v[vinculo.campoPai] ?? pai.id,
      ...(pai.nome ? { [`${vinculo.campoPai}_nome`]: pai.nome } : {}),
    }));
  }));

  return { response: { ok: true }, data: listas.flat() };
}

async function executarConsulta(estado) {
  const { tabela, recurso } = estado;
  if (SEM_EQUIVALENTE.has(tabela)) return erroSemEquivalente(tabela, estado.singleResult);

  try {
    let resultado;
    const vinculo = VINCULOS[tabela];
    const idBuscado = filtroIgual(estado, 'id');

    const eu = recurso === 'usuarios' && idBuscado ? await fetchCurrentUser() : null;

    if (vinculo) {
      resultado = await listarVinculos(estado, vinculo);
    } else if (eu && String(eu.id) === String(idBuscado)) {
      // Próprio usuário: /me/ funciona para qualquer nível (a listagem é só da gestão).
      resultado = { response: { ok: true }, data: eu };
    } else if (idBuscado && COM_DETALHE.has(recurso)) {
      resultado = await requisitar(`${recurso}/${idBuscado}/`);
      if (resultado.response.status === 404) {
        return { data: estado.singleResult ? null : [], count: 0, error: null };
      }
    } else {
      const params = new URLSearchParams();
      const aceitos = PARAMS_NO_SERVIDOR[recurso] || {};
      estado.filters.forEach((f) => {
        if (f.op === 'eq' && aceitos[f.column] && f.value !== null && f.value !== undefined) {
          params.set(aceitos[f.column], f.value);
        }
      });
      const qs = params.toString();
      resultado = await requisitar(`${recurso}/${qs ? `?${qs}` : ''}`);
    }

    const { response, data } = resultado;
    if (!response.ok) return respostaDeErro(response, data, `GET ${recurso}`, estado);

    const registros = comoLista(data).map(adicionarAliases);
    const { lista, total } = aplicarNoFront(registros, estado, recurso);
    const count = estado.countMode ? total : null;

    if (estado.headOnly) return { data: null, count, error: null };
    if (estado.singleResult) return { data: lista[0] || null, count, error: null };
    return { data: lista, count, error: null };
  } catch (error) {
    console.error('[apiClient] Erro na consulta:', error);
    return { data: estado.singleResult ? null : [], count: null, error: { message: error.message } };
  }
}

async function enviarMutacao(estado, caminho, method, body) {
  const { response, data } = await requisitar(caminho, { method, body });
  if (!response.ok) {
    Sentry.captureMessage(`API ${method} ${caminho} → ${response.status}`, {
      level: 'warning',
      extra: { status: response.status, recurso: estado.recurso, erro: formatErrorMessage(data) },
    });
    return { data: null, error: { message: formatErrorMessage(data), status: response.status } };
  }
  return { data: adicionarAliases(data), error: null };
}

async function mutarVinculo(estado, vinculo) {
  const { type, payload } = estado.mutation;

  if (type === 'insert' || type === 'upsert') {
    const itens = Array.isArray(payload) ? payload : [payload];
    const resultados = [];
    for (const item of itens) {
      const paiId = item[vinculo.chavePai] ?? item[vinculo.campoPai];
      const usuario = item.usuario_id ?? item.usuario;
      if (!paiId || !usuario) {
        return { data: null, error: { message: `Vínculo requer ${vinculo.chavePai} e usuario_id.` } };
      }
      const r = await enviarMutacao(estado, `${vinculo.pai}/${paiId}/professores/vincular/`, 'POST', { usuario });
      if (r.error) return r;
      resultados.push(r.data);
    }
    return { data: Array.isArray(payload) ? resultados : resultados[0], error: null };
  }

  if (type === 'delete') {
    // Resolve quais vínculos casam com os filtros e desfaz um a um.
    const consulta = await executarConsulta({ ...estado, mutation: null, singleResult: false, headOnly: false });
    if (consulta.error) return consulta;
    for (const v of consulta.data) {
      const paiId = v[vinculo.campoPai];
      const r = await enviarMutacao(estado, `${vinculo.pai}/${paiId}/professores/${v.usuario}/desvincular/`, 'DELETE');
      if (r.error) return r;
    }
    return { data: consulta.data, error: null };
  }

  return { data: null, error: { message: 'Vínculos só aceitam insert e delete.' } };
}

async function executarMutacao(estado) {
  const { tabela, recurso, mutation } = estado;
  if (SEM_EQUIVALENTE.has(tabela)) return erroSemEquivalente(tabela, true);

  const vinculo = VINCULOS[tabela];
  if (vinculo) return mutarVinculo(estado, vinculo);

  const ops = RECURSOS[recurso];
  if (!ops) {
    return { data: null, error: { message: `Operação não suportada para "${tabela}".` } };
  }
  const naoSuportada = (op) => ({
    data: null,
    error: { message: `O backend não permite ${op} em "${recurso}".` },
  });
  const idAlvo = () => filtroIgual(estado, 'id') || mutation.payload?.id;
  const semId = (p) => {
    if (!p || typeof p !== 'object') return p;
    const { id, ...resto } = p;
    return resto;
  };
  const criar = async (item) => enviarMutacao(estado, `${recurso}/criar/`, 'POST', traduzirPayload(item));
  const atualizar = async (id, item) => enviarMutacao(
    estado,
    `${recurso}/${id}/atualizar/`,
    SO_PUT.has(recurso) ? 'PUT' : 'PATCH',
    traduzirPayload(semId(item)),
  );

  if (mutation.type === 'insert') {
    if (!ops.includes('criar')) return naoSuportada('criar');
    if (Array.isArray(mutation.payload)) {
      // Sem rota de lote no backend: cria em sequência e para no primeiro erro.
      const criados = [];
      for (const item of mutation.payload) {
        const r = await criar(item);
        if (r.error) return r;
        criados.push(r.data);
      }
      return { data: criados, error: null };
    }
    return criar(mutation.payload ?? {});
  }

  if (mutation.type === 'update') {
    if (!ops.includes('atualizar')) return naoSuportada('atualizar');
    const id = idAlvo();
    if (!id) return { data: null, error: { message: 'Atualização requer .eq("id", ...).' } };
    return atualizar(id, mutation.payload ?? {});
  }

  if (mutation.type === 'upsert') {
    const id = idAlvo();
    if (id && ops.includes('atualizar')) return atualizar(id, mutation.payload ?? {});
    if (!ops.includes('criar')) return naoSuportada('criar');
    return criar(mutation.payload ?? {});
  }

  if (mutation.type === 'delete') {
    if (!ops.includes('deletar')) {
      return naoSuportada('excluir (sem rota de exclusão; talvez seja desativação via update)');
    }
    const id = idAlvo();
    if (!id) return { data: null, error: { message: 'Remoção requer .eq("id", ...).' } };
    return enviarMutacao(estado, `${recurso}/${id}/deletar/`, 'DELETE');
  }

  return { data: null, error: { message: 'Operação não suportada.' } };
}

// =============================================================================
// Interface pública
// =============================================================================

export const apiClient = {
  auth,

  /** Mantido como antes: RPCs não existem no backend e devolvem listas vazias. */
  rpc(functionName) {
    console.warn(`[API Client] RPC '${functionName}' não implementado. Retornando dados vazios.`);
    return Promise.resolve({ data: [], error: null });
  },

  from(tabela) {
    const estado = {
      tabela,
      recurso: resolverRecurso(tabela),
      columns: '*',
      filters: [],
      orderBy: null,
      limitCount: null,
      page: null,
      rangeFrom: null,
      rangeTo: null,
      singleResult: false,
      countMode: null,
      headOnly: false,
      mutation: null,
    };

    const executar = () => (estado.mutation ? executarMutacao(estado) : executarConsulta(estado));
    const filtro = (op) => (column, value) => {
      estado.filters.push({ column, op, value });
      return queryBuilder;
    };

    const queryBuilder = {
      select(columns = '*', options = {}) {
        estado.columns = columns;
        if (options?.count) estado.countMode = options.count;
        if (options?.head) estado.headOnly = true;
        return queryBuilder;
      },
      eq: filtro('eq'),
      neq: filtro('neq'),
      lte: filtro('lte'),
      gte: filtro('gte'),
      lt: filtro('lt'),
      gt: filtro('gt'),
      is: filtro('is'),
      in: filtro('in'),
      ilike: filtro('ilike'),
      match(criteria) {
        Object.entries(criteria || {}).forEach(([column, value]) => {
          estado.filters.push({ column, op: 'eq', value });
        });
        return queryBuilder;
      },
      order(column, { ascending = true } = {}) {
        estado.orderBy = ascending ? column : `-${column}`;
        return queryBuilder;
      },
      limit(count) {
        estado.limitCount = count;
        return queryBuilder;
      },
      page(pageNumber) {
        estado.page = pageNumber;
        return queryBuilder;
      },
      range(from, to) {
        estado.rangeFrom = from;
        estado.rangeTo = to;
        return queryBuilder;
      },
      insert(payload) {
        estado.mutation = { type: 'insert', payload };
        return queryBuilder;
      },
      update(payload) {
        estado.mutation = { type: 'update', payload };
        return queryBuilder;
      },
      upsert(payload) {
        estado.mutation = { type: 'upsert', payload };
        return queryBuilder;
      },
      delete() {
        estado.mutation = { type: 'delete', payload: null };
        return queryBuilder;
      },
      async single() {
        estado.singleResult = true;
        return executar();
      },
      async maybeSingle() {
        estado.singleResult = true;
        return executar();
      },
      then(resolve, reject) {
        return executar().then(resolve, reject);
      },
    };

    return queryBuilder;
  },
};

export default apiClient;