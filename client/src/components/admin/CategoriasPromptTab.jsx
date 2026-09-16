/**
 * CategoriasPromptTab.jsx
 * Listagem, criação, edição de nome e ativação/inativação de categorias de prompt.
 */

import { useState, useEffect, useRef } from "react";
import { Plus, Loader2, Tag, Pencil, X } from "lucide-react";

// ─── Helper CSRF ──────────────────────────────────────────────────────────────

function csrfToken() {
  return (
    document.cookie
      .split("; ")
      .find((r) => r.startsWith("csrftoken="))
      ?.split("=")[1] ?? ""
  );
}

// ─── Modal de criação ─────────────────────────────────────────────────────────

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
      const rCat = await fetch("/api/prompts/categorias/criar/", {
        method:      "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ titulo: titulo.trim(), ativo }),
      });
      const categoria = await rCat.json();
      if (!rCat.ok) { setErro(categoria.error || "Erro ao criar categoria."); return; }

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
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Nova categoria de prompt</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
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

          <div className="flex items-center justify-between rounded-xl border border-gray-200 px-4 py-3">
            <span className="text-sm font-medium text-gray-700">Ativar imediatamente</span>
            <button
              type="button"
              onClick={() => setAtivo((v) => !v)}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
                ativo ? "bg-purple-600" : "bg-gray-200"
              }`}
            >
              <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${ativo ? "translate-x-5" : "translate-x-0.5"}`} />
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

// ─── Modal de edição de nome ──────────────────────────────────────────────────

function ModalEditarCategoria({ categoria, onClose, onSalvo }) {
  const [titulo,   setTitulo]   = useState(categoria.titulo);
  const [erro,     setErro]     = useState(null);
  const [salvando, setSalvando] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    // Seleciona o texto ao abrir para facilitar a edição
    inputRef.current?.select();
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const novoTitulo = titulo.trim();
    if (!novoTitulo)               { setErro("O título não pode ser vazio."); return; }
    if (novoTitulo === categoria.titulo) { onClose(); return; }

    setSalvando(true);
    setErro(null);
    try {
      const r = await fetch(`/api/prompts/categorias/${categoria.id}/atualizar/`, {
        method:      "PATCH",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken":  csrfToken(),
        },
        body: JSON.stringify({ titulo: novoTitulo }),
      });
      const data = await r.json();
      if (!r.ok) { setErro(data.error || "Erro ao salvar."); return; }
      onSalvo({ ...categoria, titulo: novoTitulo });
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
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Editar categoria</h2>
            <p className="mt-0.5 text-sm text-gray-400">Altere o nome da categoria de prompt.</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Título <span className="text-red-400">*</span>
            </label>
            <input
              ref={inputRef}
              type="text"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-700 outline-none transition focus:border-purple-400 focus:ring-2 focus:ring-purple-100"
            />
            <p className="mt-1.5 text-xs text-amber-500">
              ⚠ Alterar o nome pode quebrar a integração com o backend se ele estiver
              usando este título como chave de busca.
            </p>
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
              {salvando ? "Salvando…" : "Salvar alteração"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Tab principal ────────────────────────────────────────────────────────────

export default function CategoriasPromptTab() {
  const [categorias,       setCategorias]       = useState([]);
  const [loading,          setLoading]          = useState(true);
  const [erro,             setErro]             = useState(null);
  const [modalCriar,       setModalCriar]       = useState(false);
  const [categoriaEditando, setCategoriaEditando] = useState(null); // categoria sendo editada
  const [togglingId,       setTogglingId]       = useState(null);

  // ── Carrega lista ──────────────────────────────────────────────────────────
  async function carregarCategorias() {
    setLoading(true);
    setErro(null);
    try {
      const r = await fetch("/api/prompts/categorias/?todas=1", { credentials: "include" });
      if (!r.ok) throw new Error(`Erro ${r.status}`);
      setCategorias(await r.json());
    } catch (e) {
      setErro(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { carregarCategorias(); }, []);

  // ── Alterna ativo/inativo ──────────────────────────────────────────────────
  async function handleToggleAtivo(cat) {
    setTogglingId(cat.id);
    try {
      const r = await fetch(`/api/prompts/categorias/${cat.id}/atualizar/`, {
        method:      "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ ativo: !cat.ativo }),
      });
      if (!r.ok) throw new Error();
      setCategorias((prev) =>
        prev.map((c) => (c.id === cat.id ? { ...c, ativo: !cat.ativo } : c))
      );
    } catch {
      alert("Não foi possível atualizar o status.");
    } finally {
      setTogglingId(null);
    }
  }

  // ── Callbacks ──────────────────────────────────────────────────────────────
  function handleCategoriaCriada(nova) {
    setCategorias((prev) => [...prev, { ...nova, template: null }]);
    setModalCriar(false);
  }

  function handleCategoriaEditada(atualizada) {
    setCategorias((prev) =>
      prev.map((c) => (c.id === atualizada.id ? atualizada : c))
    );
    setCategoriaEditando(null);
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* Cabeçalho */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Categorias de Prompt</h2>
          <p className="mt-1 text-sm text-gray-400">
            Gerencie as categorias usadas nos prompts de IA da plataforma.
          </p>
        </div>
        <button
          onClick={() => setModalCriar(true)}
          className="shrink-0 flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 active:scale-95 transition-all"
        >
          <Plus size={15} />
          Nova categoria
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-purple-400" />
        </div>
      )}

      {/* Erro */}
      {!loading && erro && (
        <div className="rounded-xl border border-red-100 bg-red-50 px-6 py-5 text-sm text-red-500">
          {erro}{" "}
          <button onClick={carregarCategorias} className="ml-2 underline">
            Tentar novamente
          </button>
        </div>
      )}

      {/* Tabela — desktop */}
      {!loading && !erro && (
        <>
          <div className="hidden sm:block overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/60">
                  <th className="px-6 py-4 text-left font-medium text-gray-500">#</th>
                  <th className="px-6 py-4 text-left font-medium text-gray-500">Título</th>
                  <th className="px-6 py-4 text-left font-medium text-gray-500">Templates</th>
                  <th className="px-6 py-4 text-left font-medium text-gray-500">Status</th>
                  <th className="px-6 py-4 text-left font-medium text-gray-500">Ações</th>
                </tr>
              </thead>
              <tbody>
                {categorias.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                      <Tag size={32} className="mx-auto mb-3 opacity-30" />
                      Nenhuma categoria cadastrada ainda.
                    </td>
                  </tr>
                )}
                {categorias.map((cat, idx) => (
                  <tr
                    key={cat.id}
                    className="border-b border-gray-100 last:border-0 hover:bg-gray-50/50 transition-colors"
                  >
                    <td className="px-6 py-4 text-gray-400">{idx + 1}</td>

                    <td className="px-6 py-4 font-medium text-gray-700">{cat.titulo}</td>

                    <td className="px-6 py-4">
                      {cat.template ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-50 px-2.5 py-1 text-xs font-medium text-purple-600">
                          Prompt configurado
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-400">
                          Sem prompt
                        </span>
                      )}
                    </td>

                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleToggleAtivo(cat)}
                          disabled={togglingId === cat.id}
                          title={cat.ativo ? "Clique para inativar" : "Clique para ativar"}
                          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
                            cat.ativo ? "bg-purple-600" : "bg-gray-200"
                          }`}
                        >
                          {togglingId === cat.id ? (
                            <Loader2 size={12} className="absolute inset-0 m-auto animate-spin text-white" />
                          ) : (
                            <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${cat.ativo ? "translate-x-5" : "translate-x-0.5"}`} />
                          )}
                        </button>
                        <span className={`text-xs font-medium ${cat.ativo ? "text-purple-600" : "text-gray-400"}`}>
                          {cat.ativo ? "Ativo" : "Inativo"}
                        </span>
                      </div>
                    </td>

                    <td className="px-6 py-4">
                      <button
                        onClick={() => setCategoriaEditando(cat)}
                        title="Editar nome"
                        className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-500 transition-colors hover:border-purple-300 hover:bg-purple-50 hover:text-purple-600"
                      >
                        <Pencil size={13} />
                        Editar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cards — mobile */}
          <div className="sm:hidden space-y-3">
            {categorias.length === 0 && (
              <div className="rounded-2xl border border-gray-200 bg-white px-6 py-12 text-center text-gray-400">
                <Tag size={32} className="mx-auto mb-3 opacity-30" />
                Nenhuma categoria cadastrada ainda.
              </div>
            )}
            {categorias.map((cat) => (
              <div key={cat.id} className="rounded-2xl border border-gray-200 bg-white px-4 py-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-800 truncate">{cat.titulo}</p>
                    <div className="mt-1.5">
                      {cat.template ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2.5 py-0.5 text-xs font-medium text-purple-600">
                          Prompt configurado
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-400">
                          Sem prompt
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Editar — mobile */}
                    <button
                      onClick={() => setCategoriaEditando(cat)}
                      title="Editar nome"
                      className="rounded-lg border border-gray-200 p-1.5 text-gray-400 transition-colors hover:border-purple-300 hover:bg-purple-50 hover:text-purple-600"
                    >
                      <Pencil size={14} />
                    </button>
                    {/* Toggle — mobile */}
                    <button
                      onClick={() => handleToggleAtivo(cat)}
                      disabled={togglingId === cat.id}
                      title={cat.ativo ? "Clique para inativar" : "Clique para ativar"}
                      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
                        cat.ativo ? "bg-purple-600" : "bg-gray-200"
                      }`}
                    >
                      {togglingId === cat.id ? (
                        <Loader2 size={12} className="absolute inset-0 m-auto animate-spin text-white" />
                      ) : (
                        <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${cat.ativo ? "translate-x-5" : "translate-x-0.5"}`} />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Modal de criação */}
      {modalCriar && (
        <ModalCriarCategoria
          onClose={() => setModalCriar(false)}
          onSalvo={handleCategoriaCriada}
        />
      )}

      {/* Modal de edição */}
      {categoriaEditando && (
        <ModalEditarCategoria
          categoria={categoriaEditando}
          onClose={() => setCategoriaEditando(null)}
          onSalvo={handleCategoriaEditada}
        />
      )}
    </div>
  );
}