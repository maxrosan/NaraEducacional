/**
 * Cliente de API Django/Postgres.
 * Mantém uma interface semelhante ao cliente legado apenas para compatibilidade interna.
 */
import * as Sentry from "@sentry/react";

// Origem da API. Sem valor (ou só espaços) usa caminho relativo, que cai no
// proxy /api do Vite — funciona em dev, em produção no mesmo domínio e atrás
// de túnel. O `.trim()` importa: um valor com espaço montava " /api/..." e
// dependia de o navegador tolerar o espaço à esquerda da URL.
// Mesma regra de `services/api.js` — as duas leituras precisam concordar.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim();
const REQUEST_TIMEOUT = 15000; // 15 seconds

/*
 * `fetch` deste módulo = o global + o header `ngrok-skip-browser-warning`.
 *
 * Servida por um túnel ngrok gratuito, a aplicação recebe a página
 * "You are about to visit…" em vez da resposta da API sempre que o
 * User-Agent é de navegador — o fetch devolve HTML, o `.json()` estoura e a
 * tela fica vazia sem erro visível. O header desliga essa interstitial; fora
 * do túnel é um header desconhecido e ignorado.
 *
 * A troca é feita aqui, sombreando o global, em vez de em cada uma das 8
 * chamadas do arquivo: esquecer uma reintroduziria o problema exatamente numa
 * tela e não nas outras, que é o tipo de bug caro de achar.
 */
const fetchGlobal = globalThis.fetch.bind(globalThis);
const fetch = (url, opts = {}) => fetchGlobal(url, {
  ...opts,
  headers: { 'ngrok-skip-browser-warning': '1', ...(opts.headers || {}) },
});

// Armazenar callbacks de mudança de estado
let authStateListeners = [];
let currentSession = null;
let currentUser = null;

function enrichUserPayload(data) {
  if (!data?.user) {
    return null;
  }

  const baseUser = data.user;
  const metadata = baseUser.user_metadata || {};
  const mergedMetadata = {
    ...metadata,
    ...(data.nome ? { nome: data.nome } : {}),
    ...(data.instituicao_id ? { instituicao_id: data.instituicao_id } : {}),
    ...(data.perfil ? { perfil: data.perfil } : {}),
    ...(data.tipo_especialista ? { tipo_especialista: data.tipo_especialista } : {}),
  };

  return {
    ...baseUser,
    instituicao_id: data.instituicao_id ?? baseUser.instituicao_id,
    perfil: data.perfil ?? baseUser.perfil,
    nome: data.nome ?? baseUser.nome,
    tipo_especialista: data.tipo_especialista ?? baseUser.tipo_especialista,
    user_metadata: mergedMetadata,
  };
}

/**
 * Extrai o CSRF token do cookie.
 */
function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

function humanizeFieldName(field) {
  return (field || '')
    .toString()
    .replace(/_/g, ' ')
    .trim();
}

function flattenValidationErrors(errors, prefix = '') {
  if (!errors || typeof errors !== 'object') {
    return [];
  }

  const messages = [];

  Object.entries(errors).forEach(([field, value]) => {
    const label = prefix || humanizeFieldName(field);

    if (Array.isArray(value)) {
      value.forEach((item) => {
        messages.push(label ? `${label}: ${item}` : `${item}`);
      });
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

function formatErrorMessage(data) {
  if (!data) {
    return 'Erro ao salvar dados';
  }

  if (typeof data === 'string') {
    return data;
  }

  const details = data.details && typeof data.details === 'object' ? data.details : null;
  const validationMessages = flattenValidationErrors(details || data);

  if (typeof data.error === 'string' && data.error.trim()) {
    if (validationMessages.length > 0) {
      return `${data.error} ${validationMessages.join(' ')}`.trim();
    }
    return data.error;
  }

  if (typeof data.detail === 'string' && data.detail.trim()) {
    if (validationMessages.length > 0) {
      return `${data.detail} ${validationMessages.join(' ')}`.trim();
    }
    return data.detail;
  }

  if (validationMessages.length > 0) {
    return validationMessages.join(' ');
  }

  return 'Erro ao salvar dados';
}

async function ensureCsrfToken() {
  const existingToken = getCsrfToken();
  if (existingToken) {
    return existingToken;
  }

  try {
    await fetch(`${API_BASE_URL}/api/auth/csrf/`, {
      method: 'GET',
      credentials: 'include',
    });
  } catch (error) {
    console.warn('[API Client] Não foi possível obter CSRF token automaticamente.', error);
  }

  return getCsrfToken();
}

/**
 * Busca o usuário atual da sessão Django.
 */
async function fetchCurrentUser() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me/`, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      return { user: null, session: null };
    }

    const data = await response.json();

    if (data.user) {
      const enrichedUser = enrichUserPayload(data);
      currentUser = enrichedUser;
      currentSession = data.session;
      return {
        user: enrichedUser,
        session: data.session,
        perfil: data.perfil,
        nome: data.nome,
        instituicao_id: data.instituicao_id,
        tipo_especialista: data.tipo_especialista
      };
    }

    return { user: null, session: null };
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      Sentry.captureException(new Error('Auth session check timeout: /api/auth/me/'));
    } else {
      Sentry.captureException(error);
    }
    console.error('Erro ao buscar usuário:', error);
    return { user: null, session: null };
  }
}

/**
 * Notifica todos os listeners sobre mudança de estado.
 */
function notifyAuthStateChange(event, session) {
  authStateListeners.forEach(callback => {
    try {
      callback(event, session);
    } catch (e) {
      console.error('Erro no callback de auth:', e);
    }
  });
}

const TABLE_MAPPING = {
  'perguntas_bncc': 'perguntas-bncc',
  'producoes_criancas': 'producoes-criancas',
  'portfolios': 'producoes-criancas',
  'usuario_turmas': 'usuario-turmas',
  'mensagens_lidas': 'mensagens-lidas',
  'mensagens_coordenacao': 'mensagens-coordenacao',
  'registros_observacao': 'observacoes',
  'alertas_lidos': 'alertas-lidos',
  'periodos_avaliativos': 'periodos-avaliativos',
  'perguntas_especialistas': 'perguntas-especialistas',
  'observacoes_especialistas': 'observacoes-especialistas',
  'especialista_funcoes': 'especialista-funcoes',
  'atendimentos_especialistas': 'atendimentos-especialistas',
  'projeto_turmas': 'projeto-turmas',
  'observacoes_comentarios': 'observacoes-comentarios',
  'configuracoes_registro': 'configuracoes-registro',
  'series_config': 'series-config',
  'usuario_disciplinas': 'usuario-disciplinas',
};

const MUTATION_ENDPOINTS = {
  'criancas': {
    create: 'criancas/criar/',
    update: 'criancas/{id}/atualizar/',
    delete: 'criancas/{id}/deletar/',
  },
  'relatorios': {
    create: 'relatorios/salvar/',
    update: 'relatorios/{id}/atualizar/',
  },
  'observacoes': {
    create: 'observacoes/criar/',
    bulkCreate: 'observacoes/lote/',
  },
  'producoes-criancas': {
    create: 'producoes-criancas/criar/',
    update: 'producoes-criancas/{id}/atualizar/',
    delete: 'producoes-criancas/{id}/deletar/',
  },
  'registros-escrita': {
    delete: 'registros-escrita/{id}/deletar/',
  },
  'registros-desenho': {
    delete: 'registros-desenho/{id}/deletar/',
  },
  'projetos': {
    create: 'projetos/criar/',
    update: 'projetos/{id}/atualizar/',
    delete: 'projetos/{id}/deletar/',
  },
  'turmas': {
    create: 'turmas/criar/',
    update: 'turmas/{id}/atualizar/',
    delete: 'turmas/{id}/deletar/',
  },
  'instituicoes': {
    create: 'instituicoes/criar/',
    update: 'instituicoes/{id}/atualizar/',
  },
  'usuarios': {
    create: 'usuarios/criar/',
    update: 'usuarios/{id}/atualizar/',
    delete: 'usuarios/{id}/deletar/',
  },
  'mensagens-coordenacao': {
    create: 'mensagens-coordenacao/criar/',
  },
  'mensagens-lidas': {
    create: 'mensagens-lidas/criar/',
  },
  'alertas-lidos': {
    create: 'alertas-lidos/criar/',
  },
  'periodos-avaliativos': {
    create: 'periodos-avaliativos/criar/',
    update: 'periodos-avaliativos/{id}/atualizar/',
    delete: 'periodos-avaliativos/{id}/deletar/',
  },
  'perguntas-especialistas': {
    create: 'perguntas-especialistas/criar/',
    update: 'perguntas-especialistas/{id}/atualizar/',
    delete: 'perguntas-especialistas/{id}/deletar/',
  },
  'usuario-turmas': {
    create: 'usuario-turmas/criar/',
    delete: 'usuario-turmas/deletar/',
  },
  'configuracoes-registro': {
    create: 'configuracoes-registro/criar/',
    update: 'configuracoes-registro/{id}/atualizar/',
  },
  'perguntas-bncc': {
    create: 'perguntas-bncc/criar/',
    update: 'perguntas-bncc/{id}/atualizar/',
    delete: 'perguntas-bncc/{id}/deletar/',
  },
  'series-config': {
    create: 'series-config/criar/',
    update: 'series-config/{id}/atualizar/',
    delete: 'series-config/{id}/deletar/',
  },
  'disciplinas': {
    create: 'disciplinas/criar/',
    update: 'disciplinas/{id}/atualizar/',
    delete: 'disciplinas/{id}/deletar/',
  },
  'usuario-disciplinas': {
    create: 'usuario-disciplinas/criar/',
    delete: 'usuario-disciplinas/{id}/deletar/',
  },
};

function buildUrl(path, params) {
  const query = params?.toString();
  return `${API_BASE_URL}/api/${path}${query ? `?${query}` : ''}`;
}

function resolveIdFilter(filters) {
  const idFilter = filters.find(f => f.column === 'id' && f.op === 'eq');
  return idFilter ? idFilter.value : null;
}

async function requestJson(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(url, {
      ...options,
      signal: options.signal || controller.signal,
    });
    clearTimeout(timeoutId);
    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }
    return { response, data };
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      Sentry.captureException(new Error(`Request timeout: ${url}`));
    } else {
      Sentry.captureException(error);
    }
    throw error;
  }
}

export const apiClient = {
  auth: {
    /**
     * Retorna a sessão atual.
     */
    async getSession() {
      const result = await fetchCurrentUser();
      if (result.user) {
        return {
          data: {
            session: {
              user: result.user,
              access_token: 'django-session'
            }
          },
          error: null
        };
      }
      return { data: { session: null }, error: null };
    },

    /**
     * Retorna o usuário atual.
     */
    async getUser() {
      const result = await fetchCurrentUser();
      if (result.user) {
        return { data: { user: result.user }, error: null };
      }
      return { data: { user: null }, error: null };
    },

    /**
     * Registra callback para mudanças de estado de autenticação.
     */
    onAuthStateChange(callback) {
      authStateListeners.push(callback);

      // Verificar estado inicial
      fetchCurrentUser().then(result => {
        if (result.user) {
          callback('SIGNED_IN', { user: result.user });
        }
      });

      return {
        data: {
          subscription: {
            unsubscribe: () => {
              authStateListeners = authStateListeners.filter(cb => cb !== callback);
            }
          }
        }
      };
    },

    /**
     * Login com email e senha.
     */
    async signInWithPassword({ email, password, remember_me = false }) {
      try {
        // Primeiro, obter CSRF token
        await fetch(`${API_BASE_URL}/api/auth/csrf/`, {
          method: 'GET',
          credentials: 'include',
        });

        const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ email, password, remember_me }),
        });

        const data = await response.json();

        if (!response.ok) {
          return {
            data: { user: null, session: null },
            error: { message: data.error || 'Erro ao fazer login' }
          };
        }

        const enrichedUser = enrichUserPayload(data);
        currentUser = enrichedUser;
        currentSession = data.session;

        // Notificar listeners
        notifyAuthStateChange('SIGNED_IN', { user: enrichedUser });

        return {
          data: {
            user: enrichedUser,
            session: data.session
          },
          error: null
        };
      } catch (error) {
        console.error('Erro no login:', error);
        return {
          data: { user: null, session: null },
          error: { message: 'Erro de conexão com o servidor' }
        };
      }
    },

    /**
     * Logout.
     *
     * O estado local é limpo SEMPRE, mesmo quando o servidor recusa: sem isso
     * a pessoa fica presa numa tela que diz que ela saiu. Mas o status é
     * devolvido, para a UI poder avisar que a sessão do servidor continua
     * aberta.
     *
     * Antes esta função ignorava a resposta e devolvia `{error: null}` de
     * qualquer jeito. Como o endpoint exige CSRF, um POST sem o cookie
     * `csrftoken` levava 403 — e o app tratava como sucesso, limpava o estado,
     * redirecionava para '/' e o `/auth/me/` seguinte trazia o usuário de
     * volta. Do lado de quem clicava: "saí e continuo logado".
     */
    async signOut() {
      let erro = null;
      try {
        // Garante o cookie de CSRF antes do POST (mesmo passo do login).
        if (!getCsrfToken()) {
          await fetch(`${API_BASE_URL}/api/auth/csrf/`, {
            method: 'GET',
            credentials: 'include',
          });
        }

        const response = await fetch(`${API_BASE_URL}/api/auth/logout/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
        });

        if (!response.ok) {
          erro = { message: `Não foi possível encerrar a sessão no servidor (${response.status}).` };
          console.error('Logout recusado pelo servidor:', response.status);
        }
      } catch (error) {
        console.error('Erro no logout:', error);
        erro = { message: 'Erro de rede ao fazer logout' };
      }

      currentUser = null;
      currentSession = null;
      notifyAuthStateChange('SIGNED_OUT', null);

      return { error: erro };
    },

    /**
     * Notifica listeners de sessão expirada sem fazer requisição de logout.
     */
    notifySignedOut() {
      currentUser = null;
      currentSession = null;
      notifyAuthStateChange('SESSION_EXPIRED', null);
    },

    /**
     * Registro de novo usuário (não implementado - apenas admin cria usuários).
     */
    async signUp() {
      return {
        data: { user: null, session: null },
        error: { message: 'Registro de usuários deve ser feito pelo administrador.' }
      };
    },
  },

  /**
   * Simula interface de RPC, retornando dados vazios.
   */
  rpc(functionName) {
    console.warn(`[API Client] RPC '${functionName}' não implementado. Retornando dados vazios.`);

    const emptyResponses = {
      'alunos_sem_registro_recente': [],
      'get_audit_logs': [],
      'get_professores_da_instituicao': [],
    };

    return Promise.resolve({
      data: emptyResponses[functionName] || [],
      error: null
    });
  },

  /**
   * Simula interface de consultas com chain.
   */
  from(table) {
    const apiTable = TABLE_MAPPING[table] || table;

    const queryState = {
      table: apiTable,
      columns: '*',
      filters: [],
      orderBy: null,
      limitCount: null,
      page: null,
      singleResult: false,
      countMode: null,
      headOnly: false,
      mutation: null,
    };

    const applyFiltersToParams = (params) => {
      queryState.filters.forEach(f => {
        if (f.op === 'eq') {
          params.append(f.column, f.value);
        } else if (f.op === 'lte') {
          params.append(`${f.column}__lte`, f.value);
        } else if (f.op === 'gte') {
          params.append(`${f.column}__gte`, f.value);
        } else if (f.op === 'lt') {
          params.append(`${f.column}__lt`, f.value);
        } else if (f.op === 'gt') {
          params.append(`${f.column}__gt`, f.value);
        } else if (f.op === 'in') {
          params.append(`${f.column}__in`, f.value.join(','));
        } else if (f.op === 'ilike') {
          const sanitized = typeof f.value === 'string' ? f.value.replace(/%/g, '') : f.value;
          params.append(`${f.column}__icontains`, sanitized);
        }
      });
    };

    const executeQuery = async () => {
      let timeoutId;
      let url;

      try {
        if (table === 'usuarios') {
          const idFilter = queryState.filters.find(f => f.column === 'id' && f.op === 'eq');
          if (idFilter) {
            const result = await fetchCurrentUser();
            if (result.user && result.user.id === idFilter.value) {
              const userData = {
                id: result.user.id,
                perfil: result.perfil,
                nome: result.nome,
                instituicao_id: result.instituicao_id,
                tipo_especialista: result.tipo_especialista,
              };
              return {
                data: queryState.singleResult ? userData : [userData],
                error: null
              };
            }
            return { data: queryState.singleResult ? null : [], error: null };
          }
        }

        const params = new URLSearchParams();
        applyFiltersToParams(params);

        if (queryState.orderBy) {
          params.append('ordering', queryState.orderBy);
        }
        if (queryState.limitCount) {
          params.append('limit', queryState.limitCount);
          // O backend paginado usa `page_size`, não `limit` — mandamos os dois
          // pra cobrir tanto endpoints paginados quanto os que ainda usam
          // `limit` puro, sem precisar saber qual é qual aqui.
          params.append('page_size', queryState.limitCount);
        }
        if (queryState.page) {
          params.append('page', queryState.page);
        }

        url = buildUrl(
          queryState.table,
          params
        );
        const controller = new AbortController();
        timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

        const response = await fetch(url, {
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
          if (response.status === 401) {
            notifyAuthStateChange('SESSION_EXPIRED', null);
          }
          Sentry.captureMessage(`API query failed: ${queryState.table} → ${response.status}`, {
            level: 'warning',
            extra: { url, status: response.status, table: queryState.table },
          });
          return { data: queryState.singleResult ? null : [], count: null, error: { message: 'Erro ao buscar dados' } };
        }

        const data = await response.json();
        // Suporte a respostas paginadas do DRF ({ count, next, previous, results })
        // sem quebrar o contrato de array puro que o resto do app espera.
        const isPaginated = data && !Array.isArray(data) && Array.isArray(data.results);
        const dataList = isPaginated ? data.results : (Array.isArray(data) ? data : [data]);
        const count = queryState.countMode
          ? (isPaginated ? data.count : dataList.length)
          : null;

        if (queryState.headOnly) {
          return { data: null, count, error: null };
        }

        if (queryState.singleResult) {
          return { data: dataList[0] || null, count, error: null };
        }

        return { data: dataList, count, error: null };
      } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
          Sentry.captureException(new Error(`Query timeout: ${queryState.table} - ${url}`));
        } else {
          Sentry.captureException(error);
        }
        console.error('Erro na query:', error);
        return { data: queryState.singleResult ? null : [], count: null, error: { message: error.name === 'AbortError' ? 'A requisição demorou demais. Tente novamente.' : error.message } };
      }
    };

    const executeMutation = async () => {
      const mutation = queryState.mutation;
      if (!mutation) {
        return executeQuery();
      }

      const endpoints = MUTATION_ENDPOINTS[queryState.table];
      if (!endpoints) {
        return {
          data: null,
          error: { message: `Operação não suportada para ${queryState.table}` }
        };
      }

      const params = new URLSearchParams();
      applyFiltersToParams(params);

      const resolvePayload = () => mutation.payload ?? {};
      const resolveId = () => resolveIdFilter(queryState.filters) || mutation.payload?.id;

      const requestHeaders = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      };

      const sendRequest = async (path, method, body) => {
        const csrfToken = await ensureCsrfToken();
        if (csrfToken) {
          requestHeaders['X-CSRFToken'] = csrfToken;
        }

        const url = buildUrl(path, params);
        const { response, data } = await requestJson(url, {
          method,
          credentials: 'include',
          headers: requestHeaders,
          body: body ? JSON.stringify(body) : undefined,
        });

        if (!response.ok) {
          if (response.status === 401) {
            notifyAuthStateChange('SESSION_EXPIRED', null);
          }
          Sentry.captureMessage(`API mutation failed: ${method} ${path} → ${response.status}`, {
            level: 'warning',
            extra: { url, method, status: response.status, table: queryState.table, errorMessage: formatErrorMessage(data) },
          });
          return { data: null, error: { message: formatErrorMessage(data) } };
        }
        return { data, error: null };
      };

      if (mutation.type === 'insert') {
        if (Array.isArray(mutation.payload) && endpoints.bulkCreate) {
          return sendRequest(endpoints.bulkCreate, 'POST', mutation.payload);
        }
        if (Array.isArray(mutation.payload)) {
          const results = await Promise.all(
            mutation.payload.map(item => sendRequest(endpoints.create, 'POST', item))
          );
          const hasError = results.find(r => r.error);
          return hasError || { data: results.map(r => r.data), error: null };
        }
        return sendRequest(endpoints.create, 'POST', resolvePayload());
      }

      if (mutation.type === 'update') {
        const id = resolveId();
        if (!id || !endpoints.update) {
          return { data: null, error: { message: 'Atualização requer id válido.' } };
        }
        const path = endpoints.update.replace('{id}', id);
        return sendRequest(path, 'PATCH', resolvePayload());
      }

      if (mutation.type === 'upsert') {
        const id = resolveId();
        if (id && endpoints.update) {
          const path = endpoints.update.replace('{id}', id);
          return sendRequest(path, 'PATCH', resolvePayload());
        }
        return sendRequest(endpoints.create, 'POST', resolvePayload());
      }

      if (mutation.type === 'delete') {
        if (endpoints.delete) {
          const id = resolveId();
          const path = id ? endpoints.delete.replace('{id}', id) : endpoints.delete;
          return sendRequest(path, 'DELETE', resolvePayload());
        }
        return { data: null, error: { message: 'Remoção não suportada.' } };
      }

      return { data: null, error: { message: 'Operação não suportada.' } };
    };

    const queryBuilder = {
      select(columns = '*', options = {}) {
        queryState.columns = columns;
        if (options?.count) {
          queryState.countMode = options.count;
        }
        if (options?.head) {
          queryState.headOnly = true;
        }
        return queryBuilder;
      },
      eq(column, value) {
        queryState.filters.push({ column, op: 'eq', value });
        return queryBuilder;
      },
      lte(column, value) {
        queryState.filters.push({ column, op: 'lte', value });
        return queryBuilder;
      },
      gte(column, value) {
        queryState.filters.push({ column, op: 'gte', value });
        return queryBuilder;
      },
      lt(column, value) {
        queryState.filters.push({ column, op: 'lt', value });
        return queryBuilder;
      },
      gt(column, value) {
        queryState.filters.push({ column, op: 'gt', value });
        return queryBuilder;
      },
      in(column, values) {
        queryState.filters.push({ column, op: 'in', value: values });
        return queryBuilder;
      },
      ilike(column, value) {
        queryState.filters.push({ column, op: 'ilike', value });
        return queryBuilder;
      },
      match(criteria) {
        Object.entries(criteria || {}).forEach(([column, value]) => {
          queryState.filters.push({ column, op: 'eq', value });
        });
        return queryBuilder;
      },
      order(column, { ascending = true } = {}) {
        queryState.orderBy = ascending ? column : `-${column}`;
        return queryBuilder;
      },
      limit(count) {
        queryState.limitCount = count;
        return queryBuilder;
      },
      page(pageNumber) {
        queryState.page = pageNumber;
        return queryBuilder;
      },
      insert(payload) {
        queryState.mutation = { type: 'insert', payload };
        return queryBuilder;
      },
      update(payload) {
        queryState.mutation = { type: 'update', payload };
        return queryBuilder;
      },
      upsert(payload) {
        queryState.mutation = { type: 'upsert', payload };
        return queryBuilder;
      },
      delete() {
        queryState.mutation = { type: 'delete', payload: null };
        return queryBuilder;
      },
      async single() {
        queryState.singleResult = true;
        return queryState.mutation ? executeMutation() : executeQuery();
      },
      async maybeSingle() {
        queryState.singleResult = true;
        return queryState.mutation ? executeMutation() : executeQuery();
      },
      then(resolve, reject) {
        const executor = queryState.mutation ? executeMutation : executeQuery;
        return executor().then(resolve, reject);
      },
    };

    return queryBuilder;
  }
};

export default apiClient;