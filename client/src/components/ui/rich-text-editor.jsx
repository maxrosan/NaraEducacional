import React from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import { Node, Mark } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Image from '@tiptap/extension-image';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { cssVarsPaleta, cssVarsTipografia } from '@/lib/templateRelatorioShared';
import {
  Bold,
  Italic,
  List,
  ListOrdered,
  Heading2,
  Heading3,
  Undo,
  Redo,
  RemoveFormatting,
} from 'lucide-react';
import '../../styles/relatorio-editor.css';

// ── Extensões para preservar HTML estrutural do relatório ──

const DivBlock = Node.create({
  name: 'divBlock',
  group: 'block',
  content: 'block*',
  defining: true,

  addAttributes() {
    return {
      class: { default: null },
      style: { default: null },
    };
  },

  parseHTML() {
    return [{ tag: 'div' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', HTMLAttributes, 0];
  },
});

// Spans puramente decorativos (sem nenhum filho — nem texto, nem outro
// elemento) usados só como "caixa" pro CSS desenhar linhas, bolinhas,
// divisores etc. (ex.: <span class="linha"></span> na régua do modelo
// Essencial, <span class="capa-sum-dot"></span> no sumário do Clássico).
//
// Precisam de um Node atômico à parte — e não podem depender do
// SpanInline abaixo — porque SpanInline é uma Mark, e Marks só existem
// "em cima" de conteúdo inline real. Um <span> sem filho nenhum não tem
// o que a Mark marque, então o ProseMirror descarta silenciosamente o
// elemento inteiro no parse. Mesmo padrão que SvgInline já usa pra SVGs.
//
// getAttrs retorna `false` quando o span TEM filhos — nesse caso a regra
// não se aplica, e o parser cai pra próxima regra que casar (SpanInline),
// preservando o comportamento normal de spans com conteúdo (ex.: texto
// colorido no título da capa).
const EmptySpanBlock = Node.create({
  name: 'emptySpanBlock',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: false,

  addAttributes() {
    return {
      html: { default: '' },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span',
        // prioridade > 50 (padrão): garante que essa regra seja avaliada
        // ANTES da regra genérica do SpanInline. Sem isso, mesmo com
        // EmptySpanBlock listado antes no array de extensions, a regra da
        // Mark venceria de qualquer forma — o ProseMirror processa todas
        // as regras de Marks antes das regras de Nodes quando empatam em
        // prioridade, independente da ordem de registro das extensions.
        priority: 100,
        getAttrs: (el) => (el.childNodes.length === 0 ? { html: el.outerHTML } : false),
      },
    ];
  },

  renderHTML({ node }) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = node.attrs.html;
    return wrapper.firstElementChild;
  },
});

const SpanInline = Mark.create({
  name: 'spanInline',

  addAttributes() {
    return {
      class: { default: null },
      style: { default: null },
    };
  },

  parseHTML() {
    return [{ tag: 'span' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', HTMLAttributes, 0];
  },
});

const LabelBlock = Node.create({
  name: 'labelBlock',
  group: 'block',
  content: 'inline*',

  addAttributes() {
    return { class: { default: null } };
  },

  parseHTML() {
    return [{ tag: 'label' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['label', HTMLAttributes, 0];
  },
});

// SVGs (ícones, decorações) são tratados como conteúdo "opaco": guardamos
// o HTML bruto inteiro como atributo e reconstruímos na hora de desenhar/
// salvar, sem tentar modelar cada <path>/<circle> no schema do editor —
// catalogar cada elemento interno possível de um SVG seria inviável.
// inline:true pra funcionar tanto dentro de spans (ícones do infocard)
// quanto como filho direto de divs (decorações de fundo posicionadas
// absolutamente, como o confete do Mascote ou a folha do Memórias).
const SvgInline = Node.create({
  name: 'svgInline',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: false,

  addAttributes() {
    return {
      html: { default: '' },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'svg',
        getAttrs: (el) => ({ html: el.outerHTML }),
      },
    ];
  },

  renderHTML({ node }) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = node.attrs.html;
    return wrapper.firstElementChild;
  },
});

// Calcula as mesmas CSS vars que a tela de template já usa (paleta +
// tipografia), a partir do RelatorioTemplate.config vinculado a ESTE
// relatório específico — faz o editor mostrar a capa com a cara real do
// PDF, em vez de sempre cair no tema padrão do sistema.
function estiloTemplateCapa(templateConfig) {
  if (!templateConfig) return {};
  // config.paleta salvo é só o dict de cores (roxo/verde/...), sem o
  // wrapper {nome, desc, amostra, cores} que a tela de template usa
  // internamente — cssVarsPaleta espera esse wrapper, então recriamos aqui.
  const paletaObj = { cores: templateConfig.paleta || {} };
  return {
    ...cssVarsPaleta(paletaObj),
    ...cssVarsTipografia(templateConfig),
  };
}

const ToolbarButton = ({ onClick, active, disabled, children, title }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    title={title}
    className={`p-1.5 rounded transition-colors ${
      active
        ? 'bg-roxo-principal text-white'
        : 'text-gray-600 hover:bg-gray-100'
    } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
  >
    {children}
  </button>
);

function Toolbar({ editor }) {
  if (!editor) return null;

  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b border-gray-200 px-2 py-1.5 bg-gray-50 rounded-t-md">
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBold().run()}
        active={editor.isActive('bold')}
        title="Negrito"
      >
        <Bold className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleItalic().run()}
        active={editor.isActive('italic')}
        title="Itálico"
      >
        <Italic className="h-4 w-4" />
      </ToolbarButton>

      <div className="w-px h-5 bg-gray-300 mx-1" />

      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        active={editor.isActive('heading', { level: 2 })}
        title="Título"
      >
        <Heading2 className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        active={editor.isActive('heading', { level: 3 })}
        title="Subtítulo"
      >
        <Heading3 className="h-4 w-4" />
      </ToolbarButton>

      <div className="w-px h-5 bg-gray-300 mx-1" />

      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        active={editor.isActive('bulletList')}
        title="Lista"
      >
        <List className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        active={editor.isActive('orderedList')}
        title="Lista numerada"
      >
        <ListOrdered className="h-4 w-4" />
      </ToolbarButton>

      <div className="w-px h-5 bg-gray-300 mx-1" />

      <ToolbarButton
        onClick={() => editor.chain().focus().clearNodes().unsetAllMarks().run()}
        title="Limpar formatação"
      >
        <RemoveFormatting className="h-4 w-4" />
      </ToolbarButton>

      <div className="w-px h-5 bg-gray-300 mx-1" />

      <ToolbarButton
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        title="Desfazer"
      >
        <Undo className="h-4 w-4" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        title="Refazer"
      >
        <Redo className="h-4 w-4" />
      </ToolbarButton>
    </div>
  );
}

function RichTextEditor({ content, onUpdate, editable = true, placeholder = '', templateConfig = null }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Image.configure({ inline: false, allowBase64: true }),
      Placeholder.configure({ placeholder }),
      DivBlock,
      EmptySpanBlock,
      SpanInline,
      LabelBlock,
      SvgInline,
      Table.configure({ resizable: false }),
      TableRow,
      TableCell,
      TableHeader,
    ],
    content,
    editable,
    onUpdate: ({ editor }) => {
      onUpdate?.(editor.getHTML());
    },
  });

  const estiloCapa = React.useMemo(() => estiloTemplateCapa(templateConfig), [templateConfig]);

  // Sync content from outside (e.g. when a new report is generated)
  React.useEffect(() => {
    if (editor && content !== undefined && editor.getHTML() !== content) {
      editor.commands.setContent(content || '');
    }
  }, [content, editor]);

  React.useEffect(() => {
    if (editor) {
      editor.setEditable(editable);
    }
  }, [editable, editor]);

  return (
    <div className="border border-gray-200 rounded-md overflow-hidden">
      {editable && <Toolbar editor={editor} />}
      <div style={estiloCapa}>
        <EditorContent
          editor={editor}
          className="prose prose-sm max-w-none min-h-[400px] p-4 focus:outline-none
            [&_.ProseMirror]:outline-none [&_.ProseMirror]:min-h-[400px]
            [&_.ProseMirror_img]:max-w-[180px] [&_.ProseMirror_img]:h-auto [&_.ProseMirror_img]:rounded-md [&_.ProseMirror_img]:inline-block [&_.ProseMirror_img]:mr-3 [&_.ProseMirror_img]:mb-2
            [&_.ProseMirror_p.is-editor-empty:first-child::before]:text-gray-400
            [&_.ProseMirror_p.is-editor-empty:first-child::before]:content-[attr(data-placeholder)]
            [&_.ProseMirror_p.is-editor-empty:first-child::before]:float-left
            [&_.ProseMirror_p.is-editor-empty:first-child::before]:h-0
            [&_.ProseMirror_p.is-editor-empty:first-child::before]:pointer-events-none"
        />
      </div>
    </div>
  );
}

export { RichTextEditor };
export default RichTextEditor;