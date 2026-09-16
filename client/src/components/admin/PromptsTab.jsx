/**
 * PromptsTab.jsx
 * Componente de configuração de prompts — para uso dentro do AdminPage.
 * Sem navbar/layout de página, só o conteúdo.
 */

import { useState, useEffect } from "react";
import { FileText, Mic, Pencil, CalendarDays, Copy, Check, Loader2, Plus } from "lucide-react";

// ─── Ícones por título de categoria ──────────────────────────────────────────

const ICONE_CATEGORIA = {
  "Relatórios":   FileText,
  "Voz":          Mic,
  "Desenho":      Pencil,
  "Planejamento": CalendarDays,
};

// ─── Helper CSRF ──────────────────────────────────────────────────────────────

function csrfToken() {
  return (
    document.cookie
      .split("; ")
      .find((r) => r.startsWith("csrftoken="))
      ?.split("=")[1] ?? ""
  );
}

// ─── Modal de criação de categoria ───────────────────────────────────────────

function ModalCriarCategoria({ onClose, onSalvo }) {
  const [titulo,       setTitulo]       = useState("");
  const [promptGlobal, setPromptGlobal] = useState("");
  const [ativo,        setAtivo]        = useState(true);
  const [erro,         setErro]         = useState(null);
  const [salvando,     setSalvando]     = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!titulo.trim()) { setErro("O título é obrigatório."); return; }

    setSalvando(true);
    setErro(null);
    try {
      // 1. Cria a categoria
      const rCat = await fetch("/api/prompts/categorias/criar/", {
        method:      "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ titulo: titulo.trim(), ativo }),
      });
      const categoria = await rCat.json();
      if (!rCat.ok) { setErro(categoria.error || "Erro ao criar categoria."); return; }

      // 2. Cria o template global vinculado à categoria
      const rTpl = await fetch("/api/prompts/salvar/", {
        method:      "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({
          categoria_id:  categoria.id,
          prompt_global: promptGlobal.trim(),
          personalizado: "",
        }),
      });
      if (!rTpl.ok) { setErro("Categoria criada, mas erro ao salvar o prompt."); return; }
      const template = await rTpl.json();

      onSalvo({ ...categoria, template });
    } catch {
      setErro("Erro de conexão.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-2xl">
        <h2 className="mb-6 text-lg font-semibold text-gray-800">Nova categoria de prompt</h2>

        <form onSubmit={handleSubmit} className="space-y-5">

          {/* Título */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Título <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex: Escrita, Matemática…"
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-700 outline-none transition focus:border-purple-400 focus:ring-2 focus:ring-purple-100"
              autoFocus
            />
          </div>

          {/* Prompt global */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Prompt global
              <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                default
              </span>
            </label>
            <div
              className="flex flex-col rounded-xl border border-gray-200 ring-0 transition focus-within:border-purple-400 focus-within:ring-2 focus-within:ring-purple-100"
              style={{ height: "180px" }}
            >
              <textarea
                value={promptGlobal}
                onChange={(e) => setPromptGlobal(e.target.value)}
                placeholder="Descreva o comportamento esperado da IA para esta categoria…"
                className="min-h-0 w-full flex-1 resize-none rounded-xl bg-transparent px-4 py-3 text-sm leading-relaxed text-gray-700 outline-none placeholder:text-gray-300"
              />
            </div>
          </div>

          {/* Toggle ativo */}
          <div className="flex items-center justify-between rounded-xl border border-gray-200 px-4 py-3">
            <span className="text-sm font-medium text-gray-700">Ativar imediatamente</span>
            <button
              type="button"
              onClick={() => setAtivo((v) => !v)}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
                ativo ? "bg-purple-600" : "bg-gray-200"
              }`}
            >
              <span
                className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  ativo ? "translate-x-5" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>

          {erro && (
            <p className="rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-500">{erro}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-500 hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={salvando}
              className="flex items-center gap-2 rounded-lg bg-purple-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-60"
            >
              {salvando && <Loader2 size={14} className="animate-spin" />}
              {salvando ? "Salvando…" : "Criar categoria"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function PromptsTab() {
  const [categorias,    setCategorias]    = useState([]);
  const [tabAtiva,      setTabAtiva]      = useState(null);
  const [globalPrompts, setGlobalPrompts] = useState({});
  const [customPrompts, setCustomPrompts] = useState({});
  const [loading,       setLoading]       = useState(true);
  const [erro,          setErro]          = useState(null);
  const [saved,         setSaved]         = useState(false);
  const [saving,        setSaving]        = useState(false);
  const [copied,        setCopied]        = useState(false);
  const [modalAberto,   setModalAberto]   = useState(false);

  // ── Carrega categorias + templates ─────────────────────────────────────────
  useEffect(() => {
    fetch("/api/prompts/categorias/", { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error(`Erro ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setCategorias(data);
        if (data.length > 0) setTabAtiva(data[0].id);

        const globals = {};
        const customs = {};
        data.forEach((cat) => {
          globals[cat.id] = cat.template?.prompt_global ?? "";
          customs[cat.id] = cat.template?.personalizado  ?? "";
        });
        setGlobalPrompts(globals);
        setCustomPrompts(customs);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  // ── Callback após criação de categoria ─────────────────────────────────────
  function handleCategoriaCriada(nova) {
    setCategorias((prev) => [...prev, nova]);
    setGlobalPrompts((prev) => ({ ...prev, [nova.id]: nova.template?.prompt_global ?? "" }));
    setCustomPrompts((prev) => ({ ...prev, [nova.id]: nova.template?.personalizado  ?? "" }));
    setTabAtiva(nova.id);
    setModalAberto(false);
  }

  // ── Salvar ─────────────────────────────────────────────────────────────────
  async function handleSalvar() {
    if (tabAtiva === null || saving) return;
    setSaving(true);
    try {
      const r = await fetch("/api/prompts/salvar/", {
        method:      "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken":  csrfToken(),
        },
        body: JSON.stringify({
          categoria_id:  tabAtiva,
          prompt_global: globalPrompts[tabAtiva] ?? "",
          personalizado: customPrompts[tabAtiva] ?? "",
        }),
      });
      if (!r.ok) throw new Error(`Erro ${r.status}`);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      alert(`Não foi possível salvar: ${e.message}`);
    } finally {
      setSaving(false);
    }
  }

  // ── Copiar ─────────────────────────────────────────────────────────────────
  function handleCopiar() {
    navigator.clipboard.writeText(globalPrompts[tabAtiva] ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={24} className="animate-spin text-purple-400" />
      </div>
    );
  }

  // ── Erro ───────────────────────────────────────────────────────────────────
  if (erro) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16">
        <p className="font-medium text-red-400">Erro ao carregar prompts</p>
        <p className="text-sm text-gray-400">{erro}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 rounded-lg bg-purple-600 px-5 py-2 text-sm font-medium text-white hover:bg-purple-700"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  const tabInfo = categorias.find((c) => c.id === tabAtiva);

  return (
    <div className="space-y-6">

      {/* Cabeçalho — título + botão na mesma row */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Prompts</h2>
          <p className="mt-1 text-sm text-gray-400">
            Personalize os prompts usados pela IA em cada módulo da plataforma.
          </p>
        </div>
        <button
          onClick={() => setModalAberto(true)}
          className="shrink-0 flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2 text-sm font-medium text-white transition-all hover:bg-purple-700 active:scale-95"
        >
          <Plus size={15} />
          <span className="hidden xs:inline">Nova categoria</span>
          <span className="xs:hidden">Nova categoria</span>
        </button>
      </div>

      {/* Card */}
      <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">

        {/* Tabs de categoria */}
        <div className="border-b border-gray-100 px-4 sm:px-8 pt-6">
          <div className="flex flex-wrap items-center gap-2">
            {categorias.map((cat) => {
              const ativo   = tabAtiva === cat.id;
              const TabIcon = ICONE_CATEGORIA[cat.titulo] ?? FileText;
              return (
                <button
                  key={cat.id}
                  onClick={() => setTabAtiva(cat.id)}
                  className={`flex items-center gap-2 rounded-lg px-5 py-2.5 text-base font-medium transition-all ${
                    ativo
                      ? "bg-purple-600 text-white shadow-sm"
                      : "text-gray-500 hover:bg-gray-50 hover:text-gray-700"
                  }`}
                >
                  <TabIcon size={15} />
                  {cat.titulo}
                </button>
              );
            })}
          </div>
        </div>

        {/* Corpo */}
        <div className="p-4 sm:p-8">

          {/* Labels das colunas */}
          <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="flex items-center gap-2">
              <span className="text-base font-medium text-gray-500">Global</span>
              <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                default
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-base font-medium text-gray-500">Personalizado</span>
              <span className="rounded-full bg-purple-50 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-purple-400">
                Editável
              </span>
            </div>
          </div>

          {/* Textareas */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">

            {/* Global */}
            <div
              className="flex flex-col rounded-xl border border-gray-200 bg-white ring-0 transition-shadow focus-within:border-purple-300 focus-within:ring-2 focus-within:ring-purple-100"
              style={{ height: "320px" }}
            >
              <textarea
                value={globalPrompts[tabAtiva] ?? ""}
                onChange={(e) =>
                  setGlobalPrompts((p) => ({ ...p, [tabAtiva]: e.target.value }))
                }
                className="min-h-0 w-full flex-1 resize-none rounded-t-xl bg-transparent p-5 text-base leading-relaxed text-gray-600 outline-none"
              />
              <div className="flex shrink-0 justify-end border-t border-gray-200 px-4 py-3">
                <button
                  onClick={handleCopiar}
                  className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all ${
                    copied
                      ? "border-emerald-200 bg-emerald-50 text-emerald-600"
                      : "border-gray-200 bg-white text-gray-400 hover:border-gray-300 hover:text-gray-600"
                  }`}
                >
                  {copied ? <><Check size={14} /> Copiado!</> : <><Copy size={14} /> Copiar prompt</>}
                </button>
              </div>
            </div>

            {/* Personalizado */}
            <div
              className="flex flex-col rounded-xl border border-gray-200 bg-white ring-0 transition-shadow focus-within:border-purple-300 focus-within:ring-2 focus-within:ring-purple-100"
              style={{ height: "320px" }}
            >
              <textarea
                value={customPrompts[tabAtiva] ?? ""}
                onChange={(e) =>
                  setCustomPrompts((p) => ({ ...p, [tabAtiva]: e.target.value }))
                }
                placeholder={`Substitua o prompt global de ${tabInfo?.titulo?.toLowerCase() ?? ""} aqui…`}
                className="min-h-0 w-full flex-1 resize-none rounded-t-xl bg-transparent p-5 text-base leading-relaxed text-gray-700 outline-none placeholder:text-gray-300"
              />
              <div className="shrink-0 border-t border-gray-100 px-4 py-3">
                <p className="text-sm text-gray-300">Digite para substituir o prompt global…</p>
              </div>
            </div>
          </div>

          {/* Rodapé */}
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-gray-400">
              {customPrompts[tabAtiva]
                ? "O prompt personalizado substitui o global neste módulo."
                : "Nenhum prompt personalizado — usando o global."}
            </p>
            <button
              onClick={handleSalvar}
              disabled={saving}
              className={`flex items-center justify-center gap-2 rounded-lg px-6 py-2.5 text-base font-medium transition-all disabled:opacity-60 ${
                saved
                  ? "bg-emerald-500 text-white"
                  : "bg-purple-600 text-white hover:bg-purple-700 active:scale-95"
              }`}
            >
              {saved ? (
                <>
                  <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="2">
                    <path d="M3 8l4 4 6-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Salvo!
                </>
              ) : saving ? (
                <><Loader2 size={14} className="animate-spin" /> Salvando…</>
              ) : (
                "Salvar"
              )}
            </button>
          </div>
        </div>
      </div>

      <p className="text-center text-sm text-gray-300">
        Alterações salvas aplicam-se imediatamente às próximas chamadas da IA neste módulo.
      </p>

      {/* Modal */}
      {modalAberto && (
        <ModalCriarCategoria
          onClose={() => setModalAberto(false)}
          onSalvo={handleCategoriaCriada}
        />
      )}
    </div>
  );
}