"""Taxonomia canônica das fases de escrita e desenho — fonte única.

Usada pelo serviço de análise (`analise_producao.py`, enum do JSON estruturado),
pelo cache da coordenação (`coordenacao_cache.py`, ordenação da distribuição) e
por qualquer view que precise agrupar/exibir classificações.

A lista de desenho segue o vocabulário do prompt (`prompts/desenho.txt`,
Lowenfeld/Luquet): garatujas e "Realismo nascente" — e não mais a lista antiga
('Rabisco', 'Pseudonaturalista') que nunca aparecia nas respostas da IA e
deixava registros presos em "Análise em processamento".
"""

import re
import unicodedata

# Psicogênese da escrita (Ferreiro/Teberosky), em ordem de progressão.
FASES_ESCRITA = [
    'Pré-silábica',
    'Silábica sem valor sonoro',
    'Silábica com valor sonoro',
    'Silábico-alfabética',
    'Alfabética',
]

# Estágios do desenho (Lowenfeld/Luquet), em ordem de progressão —
# alinhados ao guia de classificação de prompts/desenho.txt.
FASES_DESENHO = [
    'Garatuja desordenada',
    'Garatuja controlada',
    'Pré-esquemático',
    'Esquemático',
    'Realismo nascente',
]

# Rótulos de estado (não são fases): IA respondeu mas recusou classificar
# (imagem ilegível/baixa confiança) ou a fase não pôde ser extraída da resposta.
NAO_CLASSIFICAVEL = 'Não classificável'
FASE_NAO_IDENTIFICADA = 'Fase não identificada'

# Valores antigos de `fase_desenho` gravados no banco → rótulo canônico.
# 'Pseudonaturalista' não tem equivalente no guia atual (estágio posterior ao
# Realismo nascente); mantido como está para não inventar classificação.
MAPA_DESENHO_LEGADO = {
    'Rabisco': 'Garatuja desordenada',
    'Realismo': 'Realismo nascente',
}


def fase_desenho_canonica(valor: str | None) -> str | None:
    """Traduz valores legados de `fase_desenho` para o rótulo canônico atual."""
    if not valor:
        return valor
    return MAPA_DESENHO_LEGADO.get(valor.strip(), valor)


def _normalizar(texto: str) -> str:
    """minúsculo + sem acentos (para matching tolerante)."""
    texto = (texto or '').lower()
    return ''.join(
        c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)
    )


def _regex_da_fase(fase: str) -> re.Pattern:
    """Regex tolerante a acento e flexão de gênero no fim de cada palavra.

    'Pré-silábica' → casa 'pre-silabico', 'pré-silábica' etc. Âncoras impedem
    casar 'esquemático' dentro de 'pré-esquemático'.
    """
    palavras = _normalizar(fase).split()
    partes = []
    for p in palavras:
        esc = re.escape(p)
        # flexiona a última vogal a/o de cada palavra (silabica → silabic[ao])
        esc = re.sub(r'(?<=c)a$|(?<=c)o$|(?<=ad)a$|(?<=ad)o$', '[ao]', esc)
        partes.append(esc)
    corpo = r'\s+'.join(partes)
    return re.compile(r'(?<![a-z0-9-])' + corpo + r'(?![a-z0-9])')


def detectar_fase_em_texto(texto: str, fases: list[str]) -> str | None:
    """Fallback textual: procura uma fase na resposta livre da IA.

    Normaliza acentos/gênero e testa das fases mais específicas (mais longas)
    para as mais genéricas. Retorna o rótulo canônico ou None.
    """
    texto_norm = _normalizar(texto)
    for fase in sorted(fases, key=len, reverse=True):
        if _regex_da_fase(fase).search(texto_norm):
            return fase
    return None
