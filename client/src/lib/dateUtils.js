import { format, parse, parseISO, isValid } from 'date-fns';
import { apiClient } from '@/lib/apiClient';

// Coerce arbitrary input (Date | string | number | null | undefined) into a
// valid Date or null. Strings are first attempted as ISO via parseISO, then
// fall back to the Date constructor.
export function toValidDate(value) {
  if (value === null || value === undefined || value === '') return null;
  if (value instanceof Date) return isValid(value) ? value : null;
  if (typeof value === 'string') {
    const iso = parseISO(value);
    if (isValid(iso)) return iso;
    const fallback = new Date(value);
    return isValid(fallback) ? fallback : null;
  }
  const date = new Date(value);
  return isValid(date) ? date : null;
}

// Safe wrapper around date-fns format. Returns the provided fallback when the
// value cannot be coerced to a valid Date, instead of throwing
// "RangeError: Invalid time value".
export function safeFormatDate(value, formatStr, options, fallback = '') {
  const date = toValidDate(value);
  if (!date) return fallback;
  try {
    return format(date, formatStr, options);
  } catch {
    return fallback;
  }
}

export function formatDateForApi(dateInput) {
  if (dateInput === null || dateInput === undefined || dateInput === '') return null;

  let date;

  if (dateInput instanceof Date) {
    if (isValid(dateInput)) {
      date = dateInput;
    }
  } else if (typeof dateInput === 'number') {
    // Converte serial Excel para data local (não UTC) para evitar
    // que o fuso horário desloque o dia ao formatar com date-fns.
    const excelEpoch = new Date(Date.UTC(1899, 11, 30));
    const utcDate = new Date(excelEpoch.getTime() + dateInput * 24 * 60 * 60 * 1000);
    date = new Date(utcDate.getUTCFullYear(), utcDate.getUTCMonth(), utcDate.getUTCDate());
  } else if (typeof dateInput === 'string') {
    const cleanedDateString = dateInput.replace(/\./g, '/').trim();
    const formatsToTry = [
      'dd/MM/yyyy', 'd/M/yyyy', 'dd-MM-yyyy', 'd-M-yyyy',
      'yyyy-MM-dd', 'yyyy/MM/dd', 'dd/MM/yy', 'd/M/yy', 'M/d/yy'
    ];

    for (const fmt of formatsToTry) {
      const parsedDate = parse(cleanedDateString, fmt, new Date());
      if (isValid(parsedDate)) {
        date = parsedDate;
        break;
      }
    }
    
    if (!date) {
        const directParse = new Date(dateInput);
        if (isValid(directParse)) {
            date = directParse;
        }
    }
  }

  if (date && isValid(date)) {
    let year = date.getFullYear();
    if (year >= 0 && year <= 99) {
      year += 2000;
      date.setFullYear(year);
    }
    return format(date, 'yyyy-MM-dd');
  }

  return null;
}

export async function getCurrentBimester(institutionId) {
  if (!institutionId) return null;

  const today = new Date().toISOString().split('T')[0];
  try {
    // Tentar período ativo (hoje entre data_inicio e data_fim)
    const { data } = await apiClient
      .from('periodos_avaliativos')
      .select('id, descricao, data_inicio, data_fim')
      .eq('instituicao_id', institutionId)
      .lte('data_inicio', today)
      .gte('data_fim', today)
      .order('data_inicio', { ascending: false })
      .limit(1);

    let current = Array.isArray(data) ? data[0] : null;

    // Fallback: período mais recente
    if (!current) {
      const { data: fallback } = await apiClient
        .from('periodos_avaliativos')
        .select('id, descricao, data_inicio, data_fim')
        .eq('instituicao_id', institutionId)
        .order('data_inicio', { ascending: false })
        .limit(1);
      current = Array.isArray(fallback) ? fallback[0] : null;
    }

    return current || null;
  } catch (error) {
    console.error('Erro ao buscar período atual:', error);
    return null;
  }
}

export async function getCurrentSemester(institutionId) {
  if (!institutionId) return null;
  return getSemesterDateRange();
}

export async function fetchPeriodosAvaliativos(instituicaoId) {
  if (!instituicaoId) return [];
  try {
    const { data } = await apiClient
      .from('periodos_avaliativos')
      .select('id, descricao, data_inicio, data_fim')
      .eq('instituicao_id', instituicaoId)
      .order('data_inicio', { ascending: true });
    return data || [];
  } catch (error) {
    console.error('Erro ao buscar períodos avaliativos:', error);
    return [];
  }
}

export function findPeriodoForDate(dateString, periodos) {
  if (!dateString || !periodos?.length) return null;
  const date = dateString.split('T')[0];
  return periodos.find(p => p.data_inicio <= date && p.data_fim >= date) || null;
}

export function getSemesterDateRange() {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth() + 1; // getMonth() returns 0-11

  if (month <= 6) {
    // Primeiro semestre (Janeiro a Junho)
    return {
      numero_semestre: 1,
      inicio: `${year}-01-01`,
      fim: `${year}-06-30`
    };
  } else {
    // Segundo semestre (Julho a Dezembro)
    return {
      numero_semestre: 2,
      inicio: `${year}-07-01`,
      fim: `${year}-12-31`
    };
  }
}
