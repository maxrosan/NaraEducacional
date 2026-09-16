import { apiClient } from '@/lib/apiClient';

// Rótulos de exibição das classes de LEITURA. O `classe_escolhida` é gravado em
// caixa baixa sem acento (ex.: "silabico"); aqui mapeamos para o rótulo legível.
// Fonte única reusada pelo relatório (ReadingAnalysisBlock) e pela coordenação.
export const classesLeituraLabels = {
  'pre-silabico': 'Pré-silábico',
  'silabico': 'Silábico',
  'transicao': 'Transição',
  'leitura-fluente': 'Leitura fluente',
  'alfabetico': 'Alfabético',
};

// Rótulo legível de uma classe de leitura; valores fora do mapa (ex.: "Sem
// classificação") passam inalterados.
export const formatLeituraLabel = (className) =>
  classesLeituraLabels[className] || className || '—';

/*
 * `PerguntaBNCC.campo_experiencia` guarda DUAS taxonomias diferentes conforme
 * a etapa de ensino:
 *   - Educação Infantil → os 5 campos de experiência da BNCC
 *   - Ensino Fundamental → componentes curriculares (Língua Portuguesa, ...)
 *
 * São réguas distintas e não devem ser misturadas numa lista só. Por isso há
 * dois mapas, e a tela escolhe qual usar pela composição dos dados.
 */
export const campoExperienciaMap = {
  'O eu, o outro e o nós': { iconName: 'Users', name: 'O eu, o outro e o nós' },
  'Escuta, fala, pensamento e imaginação': { iconName: 'MessageCircle', name: 'Escuta, fala, pensamento e imaginação' },
  'Corpo, gestos e movimentos': { iconName: 'ToyBrick', name: 'Corpo, gestos e movimentos' },
  'Traços, sons, cores e formas': { iconName: 'Palette', name: 'Traços, sons, cores e formas' },
  'Espaços, tempos, quantidades, relações e transformações': { iconName: 'Shapes', name: 'Espaços, tempos, quantidades...' },
};

// Componentes do Fundamental. Antes caíam todos numa linha "Outros" — 44% das
// marcações da escola colapsavam ali, incluindo Língua Portuguesa, que sozinha
// tem mais marcações que quase todos os campos da Infantil.
export const componenteCurricularMap = {
  'Língua Portuguesa': { iconName: 'BookOpen', name: 'Língua Portuguesa' },
  'Matemática': { iconName: 'Calculator', name: 'Matemática' },
  'Ciências': { iconName: 'Sprout', name: 'Ciências' },
  'História': { iconName: 'Landmark', name: 'História' },
  'Geografia': { iconName: 'Globe', name: 'Geografia' },
  'Arte': { iconName: 'Palette', name: 'Arte' },
  'Educação Física': { iconName: 'Activity', name: 'Educação Física' },
  'Filosofia': { iconName: 'Lightbulb', name: 'Filosofia' },
};

/*
 * `Disciplina.nome` é cadastro livre feito pela escola (ex: "Português",
 * "Matemática", "Inglês"...) e nem sempre bate letra por letra com o nome
 * oficial usado em `PerguntaBNCC.campo_experiencia` pro Ensino Fundamental
 * (ex: "Língua Portuguesa"). O filtro de "Registro por pergunta" em
 * NewObservationPage.jsx compara essas duas strings diretamente — sem esse
 * mapa, qualquer apelido de disciplina diferente do nome oficial zera
 * silenciosamente a lista de perguntas do professor.
 *
 * Chaves = nomes comuns que podem aparecer em Disciplina.nome (normalizados
 * em minúsculo/sem acento pela função abaixo, então adicionar aqui já cobre
 * variações de caixa/acentuação).
 * Valores = valor exato esperado em PerguntaBNCC.campo_experiencia
 * (ver componenteCurricularMap acima — precisa ser uma dessas chaves).
 */
export const disciplinaAliasMap = {
  // Língua Portuguesa
  'português': 'Língua Portuguesa',
  'lingua portuguesa': 'Língua Portuguesa',
  'portugues': 'Língua Portuguesa',

  // Matemática
  'matematica': 'Matemática',
  'matemática': 'Matemática',

  // Ciências
  'ciencias': 'Ciências',
  'ciências': 'Ciências',
  'ciencias da natureza': 'Ciências',

  // História
  'historia': 'História',
  'história': 'História',

  // Geografia
  'geografia': 'Geografia',

  // Arte
  'arte': 'Arte',
  'artes': 'Arte',
  'educacao artistica': 'Arte',
  'educação artística': 'Arte',

  // Educação Física
  'educacao fisica': 'Educação Física',
  'educação física': 'Educação Física',
  'ed. fisica': 'Educação Física',

  // Filosofia
  'filosofia': 'Filosofia',
};

// Remove acentos e baixa a caixa, pra normalizar antes de comparar/consultar
// o alias map (evita duplicar entradas por causa de maiúscula/acento).
const normalizarNomeDisciplina = (nome) =>
  (nome || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase();

/**
 * Resolve o nome de uma Disciplina (cadastro livre da escola) para o valor
 * oficial de `campo_experiencia`/componente curricular usado em
 * PerguntaBNCC, usando `disciplinaAliasMap`.
 *
 * Se não houver alias cadastrado, devolve o nome original sem alterar —
 * assim disciplinas que já usam o nome oficial (ex: "Matemática",
 * "Geografia") continuam funcionando normalmente.
 */
export const resolverCampoExperiencia = (nomeDisciplina) => {
  if (!nomeDisciplina) return nomeDisciplina;
  const alias = disciplinaAliasMap[normalizarNomeDisciplina(nomeDisciplina)];
  return alias || nomeDisciplina;
};

export const getStandardizedFaixaEtaria = (faixaEtaria) => {
  if (!faixaEtaria) return null;
  const trimmed = faixaEtaria.trim();
  const lower = trimmed.toLowerCase();

  // Legado BNCC
  if (lower.includes('bebês')) return 'Bebês';
  if (lower.includes('crianças bem pequenas')) return 'Crianças bem pequenas';
  if (lower.includes('crianças pequenas')) return 'Crianças pequenas';

  // Adaptação
  if (lower === 'adaptação') return 'Adaptação';

  // Nível X (com ou sem sufixo de letra, ex: "Nível 2A")
  const nivelMatch = trimmed.match(/Nível\s*(\d+[A-Z]?)/i);
  if (nivelMatch) return `Nível ${nivelMatch[1]}`;

  // Xº ANO
  const anoMatch = trimmed.match(/(\d+)\s*º\s*ANO/i);
  if (anoMatch) return `${anoMatch[1]}º ANO`;

  return trimmed;
};

export const fetchQuestionsByFaixaEtaria = async (faixaEtaria) => {
  const standardizedFaixa = getStandardizedFaixaEtaria(faixaEtaria);
  if (!standardizedFaixa) {
    console.error("Não foi possível padronizar a faixa etária:", faixaEtaria);
    return { data: [], error: { message: `Faixa etária não reconhecida: ${faixaEtaria}` } };
  }

  const { data: bnccData, error: bnccError } = await apiClient
    .from('perguntas_bncc')
    .select('*')
    .ilike('faixa_etaria', `%${standardizedFaixa}%`);

  if (bnccError) {
    return { data: [], error: bnccError };
  }

  // Busca perguntas de especialistas (vinculadas à instituição via sessão)
  const { data: espData } = await apiClient
    .from('perguntas_especialistas')
    .select('*')
    .ilike('nivel', `%${standardizedFaixa}%`)
    .eq('status', 'ativa');

  // Normaliza perguntas de especialistas para o mesmo formato das BNCC
  const normalizedEsp = (espData || []).map(q => ({
    ...q,
    pergunta: q.pergunta_facilitadora,
    faixa_etaria: q.nivel,
  }));

  return { data: [...(bnccData || []), ...normalizedEsp], error: null };
};