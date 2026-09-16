import * as Sentry from "@sentry/react";

// Usa variável de ambiente com fallback inteligente para desenvolvimento/produção
// Em desenvolvimento, usa proxy do Vite (caminho relativo /api)
// Em produção, usa URL completa definida em VITE_API_BASE_URL
const getApiBaseUrl = () => {
  // Se VITE_API_BASE_URL está definido e não é vazio, usar ele
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() !== '') {
    return `${envUrl}/api`;
  }
  // Fallback: caminho relativo funciona em dev (proxy Vite) e produção (mesmo domínio)
  return '/api';
};

export const API_BASE_URL = getApiBaseUrl();

const getCsrfToken = () => {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
};

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

/**
 * Wrapper do fetch que adiciona credentials e CSRF token automaticamente.
 * Garante que cookies de sessão sejam enviados em requisições cross-origin
 * e que o CSRF token seja incluído em métodos de escrita (POST/PUT/PATCH/DELETE).
 */
export async function authFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = {
    ...HEADERS_PADRAO,
    ...(options.headers instanceof Headers
      ? Object.fromEntries(options.headers.entries())
      : (options.headers || {})),
  };

  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && !headers['X-CSRFToken']) {
    headers['X-CSRFToken'] = getCsrfToken();
  }

  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'include',
      headers,
    });

    if (!response.ok) {
      Sentry.addBreadcrumb({
        category: 'api',
        message: `${method} ${url} → ${response.status}`,
        level: 'error',
      });
    }

    return response;
  } catch (error) {
    Sentry.captureException(error, {
      extra: { url, method },
    });
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
    const mensagem = (data && data.error) || `Erro ${response.status} em ${contexto}`;
    const err = new Error(mensagem);
    err.status = response.status;
    err.payload = data;
    throw err;
  }
  return data;
}

export const apiService = {
  /**
   * Inicia uma análise de leitura no NaraNN.
   * @param {FormData} formData — campos: audio (Blob), crianca_id, turma_id (opcional)
   * @returns {Promise<{id: number, status: string, ...}>}
   */
  async iniciarAnaliseLeitura(formData) {
    const response = await authFetch(`${API_BASE_URL}/leitura/analisar/`, {
      method: 'POST',
      body: formData,
    });
    return parseJsonOrThrow(response, 'iniciar análise de leitura');
  },

  /**
   * Consulta o status atual da análise (probabilidades + classe predita).
   */
  async consultarAnaliseLeitura(registroId) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/status/`);
    return parseJsonOrThrow(response, 'consultar análise de leitura');
  },

  /**
   * Confirma a classe escolhida pela professora e salva o áudio no S3.
   * @param {number} registroId
   * @param {{ classe_escolhida: string, anotacoes_professora?: string }} payload
   */
  async confirmarAnaliseLeitura(registroId, payload) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/confirmar/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return parseJsonOrThrow(response, 'confirmar análise de leitura');
  },

  /**
   * Cancela um registro pendente (apaga áudio em cache + job no NaraNN).
   */
  async cancelarAnaliseLeitura(registroId) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/`, {
      method: 'DELETE',
    });
    return parseJsonOrThrow(response, 'cancelar análise de leitura');
  },

  /**
   * Lista análises de leitura confirmadas para uma criança no período informado.
   * @param {{ criancaId: string, dataInicio?: string, dataFim?: string }} params
   * @returns {Promise<{ registros: Array<{ id: number, classe_escolhida: string, ... }> }>}
   */
  async listarAnalisesLeitura({ criancaId, dataInicio, dataFim } = {}) {
    if (!criancaId) throw new Error('criancaId é obrigatório.');
    const qs = new URLSearchParams({ crianca_id: criancaId });
    if (dataInicio) qs.set('data_inicio', dataInicio);
    if (dataFim) qs.set('data_fim', dataFim);
    const response = await authFetch(`${API_BASE_URL}/leitura/?${qs}`);
    return parseJsonOrThrow(response, 'listar análises de leitura');
  },

  // ── Dispositivos gravadores (Cadastros → Dispositivos) ──────────────

  /** Lista dispositivos (admin/coordenador: todos da instituição). */
  async listarDispositivos() {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/`);
    return parseJsonOrThrow(response, 'listar dispositivos');
  },

  /**
   * Gera um código de pareamento (validade curta, uso único).
   * @param {{professoraId?: string, turmaIds?: string[]}} params
   */
  async gerarCodigoPareamento({ professoraId, turmaIds } = {}) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/codigo/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(professoraId ? { professora_id: professoraId } : {}),
        ...(turmaIds?.length ? { turma_ids: turmaIds } : {}),
      }),
    });
    return parseJsonOrThrow(response, 'gerar código de pareamento');
  },

  /**
   * Atualiza nome e/ou vínculo (professora, turmas) — não exige mexer no aparelho.
   * @param {string} dispositivoId
   * @param {{nome?: string, professora_id?: string, turma_ids?: string[]}} dados
   */
  async atualizarDispositivo(dispositivoId, dados) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/${dispositivoId}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    return parseJsonOrThrow(response, 'atualizar dispositivo');
  },

  /** Revoga o dispositivo: o token para de funcionar imediatamente. */
  async revogarDispositivo(dispositivoId) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/${dispositivoId}/revogar/`, {
      method: 'DELETE',
    });
    return parseJsonOrThrow(response, 'revogar dispositivo');
  },

  /** Reativa um dispositivo revogado por engano (exige novo pareamento). */
  async reativarDispositivo(dispositivoId) {
    const response = await authFetch(`${API_BASE_URL}/dispositivos/${dispositivoId}/reativar/`, {
      method: 'POST',
    });
    return parseJsonOrThrow(response, 'reativar dispositivo');
  },

  /**
   * Exclui definitivamente uma análise de leitura (qualquer status).
   * Diferente do cancelamento (DELETE /leitura/<id>/), funciona também para
   * registros confirmados — é o que o botão de exclusão do relatório usa.
   * @param {number} registroId
   */
  async deletarAnaliseLeitura(registroId) {
    const response = await authFetch(`${API_BASE_URL}/leitura/${registroId}/deletar/`, {
      method: 'DELETE',
    });
    return parseJsonOrThrow(response, 'excluir análise de leitura');
  },

  /**
   * Função para upload e análise de escrita
   * @param {Object} dadosAnalise - Dados para análise
   * @param {File} arquivo - Arquivo para upload
   */
  async uploadEAnaliseEscrita(dadosAnalise, arquivo) {
    try {
      const formData = new FormData();
      formData.append('arquivo', arquivo);
      formData.append('nomeAluno', dadosAnalise.nomeAluno);
      formData.append('serieAluno', dadosAnalise.serieAluno);
      formData.append('turmaId', dadosAnalise.turmaId);

      const response = await authFetch(`${API_BASE_URL}/upload-escrita/`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao fazer upload e análise:', error);
      throw error;
    }
  },

  /**
   * Função para upload e análise de desenho
   * @param {FormData} formData - FormData já montado com arquivo e dados
   */
  async uploadEAnaliseDesenho(formData) {
    try {
      const response = await authFetch(`${API_BASE_URL}/upload-desenho/`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao fazer upload e análise de desenho:', error);
      throw error;
    }
  },

  /**
   * Função para análise de escrita (apenas metadados - versão antiga)
   * @param {Object} dadosAnalise - Dados para análise
   */
  async analiseDeEscrita(dadosAnalise) {
    try {
      const response = await authFetch(`${API_BASE_URL}/analise-escrita/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosAnalise),
      });

      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao chamar análise de escrita:', error);
      throw error;
    }
  },

  /**
   * Função de teste para verificar conexão com a API
   */
  async testarConexao() {
    try {
      const response = await fetch(`${API_BASE_URL}/hello/`);
      return await response.json();
    } catch (error) {
      console.error('Erro ao conectar com API:', error);
      throw error;
    }
  },

  /**
   * Health check da API
   */
  async healthCheck() {
    try {
      const response = await fetch(`${API_BASE_URL}/health/`);
      return await response.json();
    } catch (error) {
      console.error('Erro no health check:', error);
      throw error;
    }
  },

  /**
   * Listar alertas não lidos para o usuário autenticado.
   */
  async listarAlertas() {
    try {
      const response = await authFetch(`${API_BASE_URL}/alertas/`);
      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Erro ao listar alertas:', error);
      throw error;
    }
  },

  /**
   * Buscar detalhe de um alerta específico.
   * @param {string} alertaTipo
   * @param {string} alertaChave
   */
  async buscarDetalheAlerta(alertaTipo, alertaChave) {
    try {
      const params = new URLSearchParams({
        alerta_tipo: alertaTipo,
        alerta_chave: alertaChave,
      });
      const response = await authFetch(`${API_BASE_URL}/alertas/detalhe/?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Erro ao buscar detalhe do alerta:', error);
      throw error;
    }
  },

  /**
   * Buscar os agregados do painel da coordenação para um recorte de tempo.
   * Calculado ao vivo no backend (não é mais snapshot D-1).
   * @param {{periodoId?: string, dataInicio?: string, dataFim?: string}} [recorte]
   *   `dataInicio`+`dataFim` (YYYY-MM-DD) têm precedência sobre `periodoId`;
   *   nada = o período avaliativo vigente hoje.
   * Retorna { periodo_id, periodo_descricao, periodo_personalizado, gerado_em, payload }.
   */
  async buscarCacheCoordenacao(recorte = {}) {
    try {
      const { periodoId, dataInicio, dataFim } = recorte;
      const params = new URLSearchParams();
      if (dataInicio && dataFim) {
        params.set('data_inicio', dataInicio);
        params.set('data_fim', dataFim);
      } else if (periodoId) {
        params.set('periodo_id', periodoId);
      }
      const qs = params.toString();
      const response = await authFetch(`${API_BASE_URL}/coordenacao/cache/${qs ? `?${qs}` : ''}`);
      if (!response.ok) {
        const corpo = await response.json().catch(() => ({}));
        throw new Error(corpo.error || `Erro na API: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Erro ao buscar indicadores da coordenação:', error);
      throw error;
    }
  },

  /**
   * Períodos avaliativos disponíveis no select da coordenação.
   * Retorna { periodo_vigente_id, periodos: [{ id, descricao, data_inicio, data_fim, em_curso }] }.
   */
  async buscarPeriodosCoordenacao() {
    const response = await authFetch(`${API_BASE_URL}/coordenacao/periodos/`);
    if (!response.ok) {
      throw new Error(`Erro na API: ${response.status}`);
    }
    return await response.json();
  },

  /**
   * Regenera o snapshot da coordenação a pedido do coordenador (botão
   * "Atualizar" do painel). Retorna { gerado_em, data_referencia, ... }.
   */
  async atualizarCacheCoordenacao() {
    const response = await authFetch(`${API_BASE_URL}/coordenacao/cache/refresh/`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`Erro na API: ${response.status}`);
    }
    return await response.json();
  },

  /**
   * Listar indicador de desenvolvimento de linguagem por turma.
   * @param {string} instituicaoId
   * @param {string} turmaId
   */
  async listarIndicadorLinguagem(instituicaoId, turmaId = null) {
    try {
      const params = new URLSearchParams();
      if (instituicaoId) params.append('instituicao_id', instituicaoId);
      if (turmaId) params.append('turma_id', turmaId);
      const response = await authFetch(`${API_BASE_URL}/indicadores/linguagem/?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Erro ao listar indicador de linguagem:', error);
      throw error;
    }
  },

  /**
   * Salvar anotações adicionais da professora
   * @param {string} arquivoHash - Hash do arquivo analisado
   * @param {string} anotacoes - Anotações da professora
   * @param {string} professora - Nome da professora
   */
  async salvarAnotacoesProfessora(arquivoHash, anotacoes, professora = 'Professora') {
    try {
      const response = await authFetch(`${API_BASE_URL}/salvar-anotacoes/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          arquivo_hash: arquivoHash,
          anotacoes: anotacoes,
          professora: professora
        }),
      });

      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao salvar anotações:', error);
      throw error;
    }
  },

  /**
   * Atualiza a classificação de um registro de escrita/desenho quando a
   * professora discorda da sugestão da IA (modal de confirmação).
   * @param {'escrita'|'desenho'} tipo
   * @param {string} arquivoHash - Hash do arquivo analisado
   * @param {string} classificacao - Fase escolhida pela professora
   */
  async atualizarClassificacaoRegistro(tipo, arquivoHash, classificacao) {
    const response = await authFetch(`${API_BASE_URL}/registros/classificacao/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tipo,
        arquivo_hash: arquivoHash,
        classificacao,
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || `Erro na API: ${response.status}`);
    }

    return await response.json();
  },

  /**
   * Listar todos os registros de escrita
   */
  async listarRegistrosEscrita() {
    try {
      const response = await authFetch(`${API_BASE_URL}/registros-escrita/`);
      
      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao listar registros:', error);
      throw error;
    }
  },

  /**
   * Listar todos os registros de desenho
   */
  async listarRegistrosDesenho() {
    try {
      const response = await authFetch(`${API_BASE_URL}/registros-desenho/`);

      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao listar registros de desenho:', error);
      throw error;
    }
  },

  /**
   * Buscar registros de escrita por aluno
   * @param {string} nomeAluno - Nome do aluno para buscar registros
   */
  async buscarRegistrosPorAluno(nomeAluno, { dataInicio, dataFim } = {}) {
    try {
      let url = `${API_BASE_URL}/registros-aluno/${encodeURIComponent(nomeAluno)}/`;
      const params = new URLSearchParams();
      if (dataInicio) params.append('data_inicio', dataInicio);
      if (dataFim) params.append('data_fim', dataFim);
      if (params.toString()) url += `?${params.toString()}`;
      const response = await authFetch(url);
      
      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao buscar registros do aluno:', error);
      throw error;
    }
  },

  /**
   * Listar habilidades da BNCC
   * @param {string} componente - Filtro por componente curricular (opcional)
   * @param {string} anoSerie - Filtro por ano/série (opcional)
   */
  async listarHabilidadesBNCC(componente = null, anoSerie = null) {
    try {
      const params = new URLSearchParams();
      if (componente) params.append('componente', componente);
      if (anoSerie) params.append('ano_serie', anoSerie);
      
      const response = await authFetch(`${API_BASE_URL}/habilidades-bncc/?${params}`);
      
      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao listar habilidades BNCC:', error);
      throw error;
    }
  },

  /**
   * Processa um arquivo de planejamento (PDF/DOC/DOCX): sobe para o S3,
   * extrai o texto e devolve uma sugestão de "Atividades Propostas".
   * @param {string} turmaId
   * @param {string} diaSemana - 'segunda' | 'terca' | 'quarta' | 'quinta' | 'sexta'
   * @param {File} file
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
   * Assistente IA: gera sugestão de atividades a partir de uma descrição
   * livre da professora.
   * @param {{prompt: string, ano_serie?: string, contexto?: string}} payload
   */
  async sugerirAtividadesPlanejamento(payload) {
    const response = await authFetch(`${API_BASE_URL}/planejamento/sugerir-atividades/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    return parseJsonOrThrow(response, 'sugerir atividades de planejamento');
  },

  /**
   * Aplica atividades extraídas de um arquivo em uma ou mais semanas
   * (cria/atualiza PlanejamentoSemanal por semana). Sobrescreve apenas os
   * dias informados; mantém os demais.
   * @param {{
   *   turma_id: string,
   *   professora_id?: string,
   *   professora_nome?: string,
   *   arquivo?: { storage_key: string, arquivo_nome_original?: string, arquivo_content_type?: string },
   *   semanas: Array<{ semana_inicio: string, dias: Object<string, { atividades_propostas: string }> }>
   * }} payload
   */
  async aplicarPlanejamentoEmSemanas(payload) {
    const response = await authFetch(`${API_BASE_URL}/planejamento/aplicar-em-semanas/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    return parseJsonOrThrow(response, 'aplicar planejamento em semanas');
  },

  /**
   * Sugere habilidades BNCC com base no texto de "Atividades Propostas".
   * Substitui o antigo `sugerirHabilidadesPlanejamento`.
   * @param {{atividades_texto: string, ano_serie?: string, limite?: number}} payload
   */
  async sugerirBnccPlanejamento(payload) {
    const response = await authFetch(`${API_BASE_URL}/planejamento/sugerir-bncc/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    return parseJsonOrThrow(response, 'sugerir habilidades BNCC');
  },

  /**
   * Criar nova habilidade BNCC
   * @param {Object} dadosHabilidade - Dados da habilidade
   */
  async criarHabilidadeBNCC(dadosHabilidade) {
    try {
      const response = await authFetch(`${API_BASE_URL}/habilidades-bncc/criar/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosHabilidade),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao criar habilidade BNCC:', error);
      throw error;
    }
  },
  async popularHabilidadesBNCC() {
    try {
      const response = await authFetch(`${API_BASE_URL}/habilidades-bncc/popular/`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao popular habilidades BNCC:', error);
      throw error;
    }
  },

  /**
   * Criar planejamento semanal
   * @param {Object} dadosPlanejamento - Dados do planejamento
   */
  async criarPlanejamentoSemanal(dadosPlanejamento) {
    try {
      const response = await authFetch(`${API_BASE_URL}/planejamento/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosPlanejamento),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao criar planejamento semanal:', error);
      throw error;
    }
  },

  /**
   * Buscar planejamento semanal
   * @param {string} turmaId - ID da turma
   * @param {string} semanaInicio - Data de início da semana (formato: YYYY-MM-DD)
   */
  async buscarPlanejamentoSemanal(turmaId, semanaInicio) {
    try {
      const params = new URLSearchParams();
      params.append('semana_inicio', semanaInicio);
      
      const response = await authFetch(`${API_BASE_URL}/planejamento/${turmaId}/?${params}`);
      
      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao buscar planejamento semanal:', error);
      throw error;
    }
  },

  /**
   * Atualizar planejamento semanal
   * @param {number} planejamentoId - ID do planejamento
   * @param {Object} dadosPlanejamento - Dados atualizados do planejamento
   */
  async atualizarPlanejamentoSemanal(planejamentoId, dadosPlanejamento) {
    try {
      const response = await authFetch(`${API_BASE_URL}/planejamento/atualizar/${planejamentoId}/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosPlanejamento),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao atualizar planejamento semanal:', error);
      throw error;
    }
  },

  /**
   * Listar planejamentos de uma turma
   * @param {string} turmaId - ID da turma
   * @param {string} inicioPeriodo - Data de início do período (opcional)
   * @param {string} fimPeriodo - Data de fim do período (opcional)
   */
  async listarPlanejamentosTurma(turmaId, inicioPeriodo = null, fimPeriodo = null) {
    try {
      let url = `${API_BASE_URL}/planejamentos/turma/${turmaId}/`;
      const params = new URLSearchParams();
      
      if (inicioPeriodo) params.append('inicio_periodo', inicioPeriodo);
      if (fimPeriodo) params.append('fim_periodo', fimPeriodo);
      
      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const response = await authFetch(url);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao listar planejamentos da turma:', error);
      throw error;
    }
  },

  /**
   * Gerar relatório usando IA
   * @param {Object} dadosRelatorio - Dados para geração do relatório
   */
  async gerarRelatorio(dadosRelatorio) {
    try {
      console.log('📡 [API] Enviando dados para gerar relatório:', dadosRelatorio);
      
      const response = await authFetch(`${API_BASE_URL}/gerar-relatorio/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosRelatorio),
      });

      console.log('📡 [API] Response status:', response.status, response.statusText);

      if (!response.ok) {
        const errorData = await response.json();
        console.error('❌ [API] Error response:', errorData);
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      const data = await response.json();
      console.log('✅ [API] Relatório gerado com sucesso:', data);
      return data;
    } catch (error) {
      console.error('💥 [API] Erro ao gerar relatório:', error);
      throw error;
    }
  },

  /**
   * Gerar relatório para uma criança usando período avaliativo
   * @param {string} criancaId - UUID da criança
   * @param {string} periodoId - UUID do período avaliativo (opcional)
   */
  async gerarRelatorioPorCrianca(criancaId, periodoId) {
    try {
      const body = periodoId ? { periodo_id: periodoId } : {};
      const response = await authFetch(`${API_BASE_URL}/gerar-relatorio/${criancaId}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[API] Erro ao gerar relatório por criança:', error);
      throw error;
    }
  },

  /**
   * Salvar relatório no banco de dados via API Django
   * @param {Object} dadosRelatorio - Dados do relatório para salvar
   */
  async salvarRelatorio(dadosRelatorio) {
    try {
      console.log('[API] Salvando relatório via Django API:', dadosRelatorio);

      const response = await authFetch(`${API_BASE_URL}/relatorios/salvar/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_crianca: dadosRelatorio.id_crianca,
          periodo: dadosRelatorio.periodo,
          conteudo: dadosRelatorio.conteudo,
          instituicao_id: dadosRelatorio.instituicao_id,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error('[API] Erro ao salvar relatório:', errorData);
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      const data = await response.json();
      console.log('[API] Relatório salvo com sucesso:', data);
      return data;
    } catch (error) {
      console.error('[API] Erro geral ao salvar relatório:', error);
      throw error;
    }
  },

  /**
   * Baixa o PDF do relatório gerado pelo backend (serviço report_generator + S3).
   * Retorna { blob, filename, cached }.
   * @param {string} relatorioId - ID do relatorio
   */
  async baixarPdfRelatorio(relatorioId) {
    const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/pdf/download/`, {
      method: 'GET',
    });

    if (!response.ok) {
      let detail = `Erro na API: ${response.status}`;
      try {
        const errorData = await response.json();
        detail = errorData.error || errorData.detail || detail;
      } catch (_) { /* resposta sem JSON */ }
      throw new Error(detail);
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
   *
   * @param {Object} params
   * @param {string[]} params.ids - IDs dos relatórios.
   * @param {AbortSignal} [params.signal] - para cancelar o download.
   * @param {(evt: Object) => void} params.onEvent - callback por evento.
   * @returns {Promise<Object>} o evento `done` final.
   */
  async bulkPdfRelatoriosStream({ ids, signal, onEvent }) {
    const response = await authFetch(`${API_BASE_URL}/relatorios/bulk-pdf/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
      signal,
    });

    if (!response.ok) {
      let detail = `Erro na API: ${response.status}`;
      try {
        const errorData = await response.json();
        detail = errorData.error || errorData.detail || detail;
      } catch (_) { /* resposta sem JSON */ }
      throw new Error(detail);
    }

    if (!response.body) {
      throw new Error('Resposta do servidor não suporta streaming.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let doneEvent = null;

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let newlineIdx;
      while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newlineIdx).trim();
        buffer = buffer.slice(newlineIdx + 1);
        if (!line) continue;
        let evt;
        try {
          evt = JSON.parse(line);
        } catch (err) {
          console.warn('[bulkPdf] linha NDJSON inválida:', line);
          continue;
        }
        onEvent?.(evt);
        if (evt?.type === 'done') doneEvent = evt;
      }
    }
    // Flush final (caso último evento venha sem \n).
    const tail = buffer.trim();
    if (tail) {
      try {
        const evt = JSON.parse(tail);
        onEvent?.(evt);
        if (evt?.type === 'done') doneEvent = evt;
      } catch (err) {
        console.warn('[bulkPdf] tail NDJSON inválido:', tail);
      }
    }

    if (!doneEvent) {
      throw new Error('Stream encerrado sem evento final.');
    }
    return doneEvent;
  },

  /**
   * Enviar PDF do relatorio para armazenamento (S3) via backend.
   * @param {string} relatorioId - ID do relatorio
   * @param {Blob} pdfBlob - PDF gerado no frontend
   * @param {string} filename - Nome sugerido do arquivo
   */
  async uploadRelatorioPdf(relatorioId, pdfBlob, filename) {
    try {
      const formData = new FormData();
      formData.append('file', pdfBlob, filename || `relatorio_${relatorioId}.pdf`);

      const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/pdf/`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao enviar PDF do relatorio:', error);
      throw error;
    }
  },

  /**
   * Regenerar URL presigned do PDF do relatorio.
   * @param {string} relatorioId - ID do relatorio
   */
  async refreshRelatorioPdf(relatorioId) {
    try {
      const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/pdf/refresh/`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao regenerar URL do relatorio:', error);
      throw error;
    }
  },

  /**
   * Buscar dados de observações para geração de relatório
   * @param {string} criancaId - ID da criança
   * @param {Object} periodo - Período para buscar observações
   */
  async buscarDadosRelatorio(criancaId, periodo) {
    try {
      const response = await authFetch(`${API_BASE_URL}/dados-relatorio/${criancaId}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(periodo),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Erro na API: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Erro ao buscar dados para relatório:', error);
      throw error;
    }
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
// Funções REST para substituir chamadas diretas ao banco
// =============================================================================

/**
 * Listar crianças com filtros opcionais
 * @param {Object} filtros - { turma_id, instituicao_id, status_vinculo }
 */
export async function listarCriancas(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.turma_id) params.append('turma_id', filtros.turma_id);
    if (filtros.instituicao_id) params.append('instituicao_id', filtros.instituicao_id);
    if (filtros.status_vinculo) params.append('status_vinculo', filtros.status_vinculo);
    if (filtros.page) params.append('page', filtros.page);
    if (filtros.page_size) params.append('page_size', filtros.page_size);

    const response = await authFetch(`${API_BASE_URL}/criancas/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar crianças:', error);
    throw error;
  }
}

/**
 * Buscar detalhes de uma criança
 * @param {string} criancaId - UUID da criança
 */
export async function buscarCrianca(criancaId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/criancas/${criancaId}/`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao buscar criança:', error);
    throw error;
  }
}

/**
 * Listar relatórios com filtros
 * @param {Object} filtros - { id_crianca, instituicao_id }
 */
export async function listarRelatorios(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.id_crianca) params.append('id_crianca', filtros.id_crianca);
    if (filtros.instituicao_id) params.append('instituicao_id', filtros.instituicao_id);

    const response = await authFetch(`${API_BASE_URL}/relatorios/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar relatórios:', error);
    throw error;
  }
}

/**
 * Listar registros de observação
 * @param {Object} filtros - { crianca_id, professor_id, data_inicio, data_fim }
 */
export async function listarObservacoes(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.crianca_id) params.append('crianca_id', filtros.crianca_id);
    if (filtros.turma_id) params.append('turma_id', filtros.turma_id);
    if (filtros.professor_id) params.append('professor_id', filtros.professor_id);
    if (filtros.data_inicio) params.append('data_inicio', filtros.data_inicio);
    if (filtros.data_fim) params.append('data_fim', filtros.data_fim);

    const response = await authFetch(`${API_BASE_URL}/observacoes/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar observações:', error);
    throw error;
  }
}

/**
 * Listar perguntas BNCC com filtros
 * @param {Object} filtros - { faixa_etaria, campo_experiencia, ids }
 */
export async function listarPerguntasBncc(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.faixa_etaria) params.append('faixa_etaria', filtros.faixa_etaria);
    if (filtros.campo_experiencia) params.append('campo_experiencia', filtros.campo_experiencia);
    if (filtros.ids && filtros.ids.length > 0) {
      params.append('ids', filtros.ids.join(','));
    }

    const response = await authFetch(`${API_BASE_URL}/perguntas-bncc/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar perguntas BNCC:', error);
    throw error;
  }
}

/**
 * Criar registros de observação em lote
 * @param {Array} registros - Lista de registros para criar
 */
export async function criarObservacoesLote(registros) {
  try {
    const response = await authFetch(`${API_BASE_URL}/observacoes/lote/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ registros }),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao criar observações em lote:', error);
    throw error;
  }
}

/**
 * Listar perguntas BNCC
 * @param {Object} filtros - { faixa_etaria, campo_experiencia }
 */
export async function listarPerguntasBNCC(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.faixa_etaria) params.append('faixa_etaria', filtros.faixa_etaria);
    if (filtros.campo_experiencia) params.append('campo_experiencia', filtros.campo_experiencia);

    const response = await authFetch(`${API_BASE_URL}/perguntas-bncc/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar perguntas BNCC:', error);
    throw error;
  }
}

/**
 * Listar turmas
 * @param {Object} filtros - { instituicao_id, ativa }
 */
export async function listarTurmas(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.id) params.append('id', filtros.id);
    if (filtros.instituicao_id) params.append('instituicao_id', filtros.instituicao_id);
    if (filtros.ativa !== undefined) params.append('ativa', filtros.ativa);

    const response = await authFetch(`${API_BASE_URL}/turmas/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar turmas:', error);
    throw error;
  }
}

/**
 * Listar produções das crianças (portfólio)
 * @param {Object} filtros - { crianca_id, turma_id, instituicao_id }
 */
export async function listarProducoesCrianca(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.crianca_id) params.append('crianca_id', filtros.crianca_id);
    if (filtros.turma_id) params.append('turma_id', filtros.turma_id);
    if (filtros.instituicao_id) params.append('instituicao_id', filtros.instituicao_id);

    const response = await authFetch(`${API_BASE_URL}/producoes-criancas/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar produções:', error);
    throw error;
  }
}

/**
 * Listar projetos
 * @param {Object} filtros - { instituicao_id, status }
 */
export async function listarProjetos(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.instituicao_id) params.append('instituicao_id', filtros.instituicao_id);
    if (filtros.status) params.append('status', filtros.status);

    const response = await authFetch(`${API_BASE_URL}/projetos/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar projetos:', error);
    throw error;
  }
}

// =============================================================================
// INSTITUIÇÕES
// =============================================================================

/**
 * Listar instituições
 * @param {Object} filtros - { ativa }
 */
export async function listarInstituicoes(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.ativa !== undefined) params.append('ativa', filtros.ativa);

    const response = await authFetch(`${API_BASE_URL}/instituicoes/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar instituições:', error);
    throw error;
  }
}

/**
 * Buscar detalhes de uma instituição
 * @param {string} instituicaoId - UUID da instituição
 */
export async function buscarInstituicao(instituicaoId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/instituicoes/${instituicaoId}/`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao buscar instituição:', error);
    throw error;
  }
}

/**
 * Criar instituição
 * @param {Object} dados - Dados da instituição
 */
export async function criarInstituicao(dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/instituicoes/criar/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao criar instituição:', error);
    throw error;
  }
}

/**
 * Atualizar instituição
 * @param {string} instituicaoId - UUID da instituição
 * @param {Object} dados - Dados atualizados
 */
export async function atualizarInstituicao(instituicaoId, dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/instituicoes/${instituicaoId}/atualizar/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao atualizar instituição:', error);
    throw error;
  }
}

/**
 * Upload do logo da instituição.
 * @param {string} instituicaoId - UUID da instituição
 * @param {File} arquivo - Arquivo do logo
 */
export async function uploadLogoInstituicao(instituicaoId, arquivo) {
  try {
    const formData = new FormData();
    formData.append('arquivo', arquivo);

    const response = await authFetch(`${API_BASE_URL}/instituicoes/${instituicaoId}/logo/`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `Erro: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao fazer upload do logo:', error);
    throw error;
  }
}

/**
 * Upload de produção da criança (mídia simples).
 * @param {Object} dados - Dados da produção e arquivo
 */
export async function uploadProducaoCrianca(dados) {
  try {
    const formData = new FormData();
    formData.append('arquivo', dados.arquivo);
    formData.append('crianca_id', dados.crianca_id);
    formData.append('turma_id', dados.turma_id);
    formData.append('professor_id', dados.professor_id);
    if (dados.instituicao_id) formData.append('instituicao_id', dados.instituicao_id);
    if (dados.tipo) formData.append('tipo', dados.tipo);
    if (dados.descricao) formData.append('descricao', dados.descricao);
    if (dados.titulo) formData.append('titulo', dados.titulo);
    if (dados.projeto) formData.append('projeto', dados.projeto);
    if (dados.data_registro) formData.append('data_registro', dados.data_registro);

    const response = await authFetch(`${API_BASE_URL}/producoes-criancas/upload/`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `Erro: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao fazer upload da produção:', error);
    throw error;
  }
}

// =============================================================================
// USUÁRIOS
// =============================================================================

/**
 * Listar usuários
 * @param {Object} filtros - { instituicao_id, perfil, ativo }
 */
export async function listarUsuarios(filtros = {}) {
  try {
    const params = new URLSearchParams();
    if (filtros.instituicao_id) params.append('instituicao_id', filtros.instituicao_id);
    if (filtros.perfil) params.append('perfil', filtros.perfil);
    if (filtros.ativo !== undefined) params.append('ativo', filtros.ativo);

    const response = await authFetch(`${API_BASE_URL}/usuarios/?${params}`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao listar usuários:', error);
    throw error;
  }
}

/**
 * Buscar detalhes de um usuário
 * @param {string} usuarioId - UUID do usuário
 */
export async function buscarUsuario(usuarioId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/usuarios/${usuarioId}/`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao buscar usuário:', error);
    throw error;
  }
}

/**
 * Criar usuário
 * @param {Object} dados - Dados do usuário (incluindo password)
 */
export async function criarUsuario(dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/usuarios/criar/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao criar usuário:', error);
    throw error;
  }
}

/**
 * Atualizar usuário
 * @param {string} usuarioId - UUID do usuário
 * @param {Object} dados - Dados atualizados
 */
export async function atualizarUsuario(usuarioId, dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/usuarios/${usuarioId}/atualizar/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao atualizar usuário:', error);
    throw error;
  }
}

/**
 * Deletar usuário (soft delete)
 * @param {string} usuarioId - UUID do usuário
 */
export async function deletarUsuario(usuarioId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/usuarios/${usuarioId}/deletar/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao deletar usuário:', error);
    throw error;
  }
}

// =============================================================================
// CRIANCAS - CRUD completo
// =============================================================================

/**
 * Criar criança
 * @param {Object} dados - Dados da criança
 */
export async function criarCrianca(dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/criancas/criar/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao criar criança:', error);
    throw error;
  }
}

/**
 * Atualizar criança
 * @param {string} criancaId - UUID da criança
 * @param {Object} dados - Dados atualizados
 */
export async function atualizarCrianca(criancaId, dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/criancas/${criancaId}/atualizar/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao atualizar criança:', error);
    throw error;
  }
}

/**
 * Deletar criança (soft delete via status)
 * @param {string} criancaId - UUID da criança
 */
export async function deletarCrianca(criancaId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/criancas/${criancaId}/deletar/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao deletar criança:', error);
    throw error;
  }
}

// =============================================================================
// RELATORIOS - funções adicionais
// =============================================================================

/**
 * Buscar detalhes de um relatório
 * @param {string} relatorioId - UUID do relatório
 */
export async function buscarRelatorio(relatorioId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao buscar relatório:', error);
    throw error;
  }
}

/**
 * Atualizar relatório
 * @param {string} relatorioId - UUID do relatório
 * @param {Object} dados - Dados atualizados
 */
export async function atualizarRelatorio(relatorioId, dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/atualizar/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao atualizar relatório:', error);
    throw error;
  }
}

// =============================================================================
// OBSERVACOES - função adicional
// =============================================================================

/**
 * Criar registro de observação (individual)
 * @param {Object} dados - Dados da observação
 */
export async function criarObservacao(dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/observacoes/criar/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao criar observação:', error);
    throw error;
  }
}

// =============================================================================
// PRODUCOES CRIANCA - funções adicionais
// =============================================================================

/**
 * Criar produção de criança
 * @param {Object} dados - Dados da produção
 */
export async function criarProducaoCrianca(dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/producoes-criancas/criar/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao criar produção:', error);
    throw error;
  }
}

/**
 * Deletar produção de criança
 * @param {string} producaoId - UUID da produção
 */
export async function deletarProducaoCrianca(producaoId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/producoes-criancas/${producaoId}/deletar/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao deletar produção:', error);
    throw error;
  }
}

// =============================================================================
// TURMAS - função adicional
// =============================================================================

/**
 * Buscar detalhes de uma turma
 * @param {string} turmaId - ID da turma
 */
export async function buscarTurma(turmaId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/turmas/${turmaId}/`);
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao buscar turma:', error);
    throw error;
  }
}

// =============================================================================
// PROJETOS - CRUD completo
// =============================================================================

/**
 * Criar projeto
 * @param {Object} dados - Dados do projeto
 */
export async function criarProjeto(dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/projetos/criar/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao criar projeto:', error);
    throw error;
  }
}

/**
 * Atualizar projeto
 * @param {string} projetoId - UUID do projeto
 * @param {Object} dados - Dados atualizados
 */
export async function atualizarProjeto(projetoId, dados) {
  try {
    const response = await authFetch(`${API_BASE_URL}/projetos/${projetoId}/atualizar/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao atualizar projeto:', error);
    throw error;
  }
}

/**
 * Deletar relatório e seu PDF associado
 * @param {string} relatorioId - UUID do relatório
 */
export async function deletarRelatorio(relatorioId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/relatorios/${relatorioId}/deletar/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao deletar relatório:', error);
    throw error;
  }
}

/**
 * Deletar projeto
 * @param {string} projetoId - UUID do projeto
 */
export async function deletarProjeto(projetoId) {
  try {
    const response = await authFetch(`${API_BASE_URL}/projetos/${projetoId}/deletar/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`Erro: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao deletar projeto:', error);
    throw error;
  }
}

// =============================================================================
// CRIANCAS - Bulk Operations
// =============================================================================

/**
 * Criar múltiplas crianças em lote (sequencial com progresso)
 * @param {Array} criancas - Lista de dados das crianças
 * @param {Function} [onProgress] - Callback (current, total, nome) chamado a cada aluno
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

/**
 * Upload da foto da criança.
 * @param {string} criancaId - UUID da criança
 * @param {File} arquivo - Arquivo de imagem
 */
export async function uploadFotoCrianca(criancaId, arquivo) {
  try {
    const formData = new FormData();
    formData.append('arquivo', arquivo);

    const response = await authFetch(`${API_BASE_URL}/criancas/${criancaId}/foto/`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `Erro: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('[API] Erro ao fazer upload da foto do aluno:', error);
    throw error;
  }
}