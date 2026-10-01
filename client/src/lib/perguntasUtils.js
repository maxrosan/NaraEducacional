import { Users, MessageCircle, Shapes, ToyBrick, Palette, BookOpen } from 'lucide-react';
import { getIconComponent } from '@/components/ui/icon-picker';

/*
 * Helpers comuns às telas de perguntas (BNCC e especialistas).
 */

// Ícones dos Campos de Experiência oficiais da BNCC (Educação Infantil).
const ICONES_CAMPOS_OFICIAIS = {
    'O eu, o outro e o nós': Users,
    'Escuta, fala, pensamento e imaginação': MessageCircle,
    'Espaços, tempos, quantidades, relações e transformações': Shapes,
    'Corpo, gestos e movimentos': ToyBrick,
    'Traços, sons, cores e formas': Palette,
};

/** Componente de ícone de um campo: oficial pelo nome, customizado pelo `icone` salvo. */
export const iconeDoCampo = (nome, icone) =>
    ICONES_CAMPOS_OFICIAIS[nome] || (icone ? getIconComponent(icone) : null) || BookOpen;

// --- Níveis: Nível 1–5 (infantil) + "Nº ANO" deduzidos das turmas ativas ---

export const NIVEIS_BASE = ['Nível 1', 'Nível 2', 'Nível 3', 'Nível 4', 'Nível 5'];

const anoDoRotulo = (valor) => {
    const m = valor?.match(/(\d+)\s*º?\s*ANO(?!S)/i);
    return m ? Number(m[1]) : null;
};

const nivelDaTurma = (turma) => {
    const ano = anoDoRotulo(turma?.nome);
    if (ano) return `${ano}º ANO`;
    const faixa = turma?.faixa_etaria || '';
    const nivel = faixa.match(/nível\s*(\d+)/i);
    if (nivel) return `Nível ${nivel[1]}`;
    const anoFaixa = anoDoRotulo(faixa);
    if (anoFaixa) return `${anoFaixa}º ANO`;
    const idade = Number(faixa.match(/(\d+)\s*anos?/i)?.[1]);
    if (idade >= 1 && idade <= 5) return `Nível ${idade}`;
    if (idade >= 6 && idade <= 10) return `${idade - 5}º ANO`;
    return null;
};

/** Níveis para os selects: os base + os anos do fundamental das turmas informadas. */
export const montarNiveis = (turmas) => {
    const anos = [...new Set(turmas.map(nivelDaTurma).filter((n) => n && !NIVEIS_BASE.includes(n)))];
    anos.sort((a, b) => (anoDoRotulo(a) ?? 99) - (anoDoRotulo(b) ?? 99) || a.localeCompare(b, 'pt-BR'));
    return [...NIVEIS_BASE, ...anos];
};

/** `{ error }` (permissão/escopo) ou `{ campo: [mensagens] }` (validação). */
export function mensagemDeErro(err) {
    const payload = err?.payload;
    if (payload && typeof payload === 'object' && !payload.error && !payload.detail) {
        const mensagens = Object.values(payload).flat().filter(Boolean);
        if (mensagens.length) return mensagens.join(' ');
    }
    return err?.message || 'Erro inesperado.';
}