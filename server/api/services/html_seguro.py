"""Fecha o HTML que a IA devolve antes de ele virar página do relatório.

POR QUE EXISTE
O relato de uma criança voltou da IA terminando em `</p></final` — uma tag
cortada, sem o `>`. Montada na página, virou `...</p></final</div></div>`, e o
parser HTML5 do navegador lê `</final</div>` como UMA tag de fechamento
inválida: o `</div>` que fechava o corpo da seção sumiu, todas as páginas
seguintes ficaram DENTRO da página do relato, e o paginador da impressão, que
clona a página para a continuação, multiplicou o relatório — 37 folhas, a
assinatura cinco vezes, páginas sem cabeçalho.

Um fragmento só não pode desmontar o documento: o que sai daqui é HTML
equilibrado, que abre e fecha dentro de si mesmo.

O QUE FAZ
1. Apaga tag inacabada: `<` de tag que chega a outro `<` (ou ao fim do texto)
   sem ter fechado com `>`.
2. Reequilibra: fecha no fim o que ficou aberto e descarta fechamento que não
   tem abertura correspondente.

Não é sanitização de segurança (não tira script, atributo nem estilo) — o HTML
vem da IA e da própria aplicação, e o PDF é renderizado no servidor. É só
estrutura.
"""

import re
from html.parser import HTMLParser

# `<` seguido de começo de tag (`/x`, `!`, letra) que chega a outro `<`, ou ao
# fim, antes de um `>`.
_TAG_INACABADA_RE = re.compile(r"<(?=[/!]?[A-Za-z])[^<>]*(?=<|$)")

_VAZIAS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
})


class _Equilibrador(HTMLParser):
    """Reescreve o fragmento tag a tag, preservando o texto original de cada
    abertura (atributos, aspas, maiúsculas do SVG), e controla a pilha."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.saida = []
        self.pilha = []

    def handle_starttag(self, tag, attrs):
        self.saida.append(self.get_starttag_text())
        if tag not in _VAZIAS:
            self.pilha.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.saida.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in _VAZIAS or tag not in self.pilha:
            return  # fechamento sem abertura: descartado
        # Fecha também o que ficou aberto por dentro (<p><strong>texto</p>).
        while self.pilha:
            aberta = self.pilha.pop()
            self.saida.append(f"</{aberta}>")
            if aberta == tag:
                break

    def handle_data(self, data):
        self.saida.append(data)

    def handle_entityref(self, name):
        self.saida.append(f"&{name};")

    def handle_charref(self, name):
        self.saida.append(f"&#{name};")

    def handle_comment(self, data):
        self.saida.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.saida.append(f"<!{decl}>")

    def unknown_decl(self, data):
        self.saida.append(f"<![{data}]>")

    def handle_pi(self, data):
        self.saida.append(f"<?{data}>")

    def resultado(self):
        self.close()
        while self.pilha:
            self.saida.append(f"</{self.pilha.pop()}>")
        return "".join(self.saida)


def fechar_html(fragmento: str) -> str:
    """Devolve o fragmento com toda tag inteira e toda abertura fechada."""
    if not fragmento:
        return fragmento or ""
    sem_inacabadas = _TAG_INACABADA_RE.sub("", fragmento)
    equilibrador = _Equilibrador()
    equilibrador.feed(sem_inacabadas)
    return equilibrador.resultado()
