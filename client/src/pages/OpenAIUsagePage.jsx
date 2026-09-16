/**
 * client/src/pages/OpenAIUsagePage.jsx
 *
 * Painel administrativo de uso da API OpenAI.
 * Tema claro — segue o mesmo padrão visual da AdminPage (SeriesTab, etc.)
 */

import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import {
  DollarSign, Zap, TrendingUp, Clock, Database,
  RefreshCw, Filter, X, ChevronLeft, ChevronRight,
  Users, BarChart2, AlertCircle,
} from "lucide-react";

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

// ─── Endpoints ───────────────────────────────────────────────────────────────
const URL_SUMMARY = "/api/admin/openai-usage/summary/";
const URL_REGISTROS = "/api/admin/openai-usage/";

// ─── Paleta dos gráficos ─────────────────────────────────────────────────────
const PALETA = [
  "#8b5cf6", "#6366f1", "#10b981", "#f59e0b",
  "#ef4444", "#06b6d4", "#f97316", "#84cc16",
];

// ─── Formatadores ─────────────────────────────────────────────────────────────
const fmt$ = v => {
  const n = parseFloat(v) || 0;
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(6)}`;
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
};
const fmtTk = n => {
  if (!n && n !== 0) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
};
const fmtDate = iso => {
  if (!iso) return "—";
  const d = new Date(iso);
  const data = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${data} ${hora}`;
};
const fmtDia = s => {
  if (!s) return "";
  const [, m, d] = s.split("-");
  return `${d}/${m}`;
};

// ─── Sub-componentes ──────────────────────────────────────────────────────────

function Sk({ className = "" }) {
  return <div className={`animate-pulse rounded-lg bg-gray-100 ${className}`} />;
}

function Vazio({ msg = "Nenhum dado." }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-gray-400">
      <Database size={32} className="opacity-30" />
      <p className="text-sm">{msg}</p>
    </div>
  );
}

function MetricaCard({ icon: Icon, label, value, sub, iconColor = "text-purple-500", loading }) {
  if (loading) return <Sk className="h-28" />;
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
            <p className="mt-1.5 text-2xl font-bold text-gray-800 truncate">{value}</p>
            {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
          </div>
          <div className="shrink-0 rounded-lg bg-gray-50 p-2.5">
            <Icon size={18} className={iconColor} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-gray-600">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-medium">
          {p.name}: <b>{p.name === "Custo" ? fmt$(p.value) : fmtTk(p.value)}</b>
        </p>
      ))}
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function OpenAIUsagePage() {
  const [summary, setSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [erroSummary, setErroSummary] = useState(null);

  const [registros, setRegistros] = useState([]);
  const [paginacao, setPaginacao] = useState({});
  const [loadingReg, setLoadingReg] = useState(true);
  const [erroReg, setErroReg] = useState(null);

  const [pagina, setPagina] = useState(1);
  const [filtros, setFiltros] = useState({ model: "", data_inicio: "", data_fim: "" });
  const [filtrosAbertos, setFiltrosAbertos] = useState(false);
  const [ultimaAtu, setUltimaAtu] = useState(null);

  const temFiltros = Object.values(filtros).some(Boolean);

  // ── Fetches ───────────────────────────────────────────────────────────────
  const buscarSummary = useCallback(async (f = filtros) => {
    setLoadingSummary(true);
    setErroSummary(null);
    try {
      const p = new URLSearchParams();
      if (f.model) p.set("model", f.model);
      if (f.data_inicio) p.set("data_inicio", f.data_inicio);
      if (f.data_fim) p.set("data_fim", f.data_fim);
      const res = await fetch(`${URL_SUMMARY}?${p}`, { credentials: "include" });
      if (res.status === 403) { setErroSummary("403"); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSummary(await res.json());
      setUltimaAtu(new Date());
    } catch (e) {
      setErroSummary(e.message);
    } finally {
      setLoadingSummary(false);
    }
  }, [filtros]);

  const buscarRegistros = useCallback(async (pg = pagina, f = filtros) => {
    setLoadingReg(true);
    setErroReg(null);
    try {
      const p = new URLSearchParams({ page: pg, page_size: 10 });
      if (f.model) p.set("model", f.model);
      if (f.data_inicio) p.set("data_inicio", f.data_inicio);
      if (f.data_fim) p.set("data_fim", f.data_fim);
      const res = await fetch(`${URL_REGISTROS}?${p}`, { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setRegistros(json.registros || []);
      setPaginacao(json.paginacao || {});
    } catch (e) {
      setErroReg(e.message);
    } finally {
      setLoadingReg(false);
    }
  }, [pagina, filtros]);

  useEffect(() => {
    buscarSummary();
    buscarRegistros(1);
  }, []);

  useEffect(() => {
    buscarRegistros(pagina);
  }, [pagina]);

  // ── Ações ─────────────────────────────────────────────────────────────────
  function aplicar() {
    setPagina(1);
    buscarSummary(filtros);
    buscarRegistros(1, filtros);
    setFiltrosAbertos(false);
  }

  function limpar() {
    const z = { model: "", data_inicio: "", data_fim: "" };
    setFiltros(z);
    setPagina(1);
    buscarSummary(z);
    buscarRegistros(1, z);
  }

  // ── Erro 403 ─────────────────────────────────────────────────────────────
  if (erroSummary === "403") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
          <AlertCircle size={32} className="text-red-400" />
          <p className="font-semibold text-gray-700">Acesso restrito a administradores.</p>
        </CardContent>
      </Card>
    );
  }

  const tot = summary?.totais || {};
  const porDia = summary?.por_dia || [];
  const porMod = summary?.por_modelo || [];
  const topU = summary?.top_usuarios || [];
  const modelos = summary?.modelos_disponiveis || [];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── Cabeçalho ──────────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="flex-row items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-purple-100 p-2">
              <BarChart2 size={16} className="text-purple-600" />
            </div>
            <div>
              <CardTitle className="text-base">Uso da API OpenAI</CardTitle>
              {ultimaAtu && (
                <CardDescription className="flex items-center gap-1 mt-0.5">
                  <Clock size={10} />
                  Atualizado às {ultimaAtu.toLocaleTimeString("pt-BR")}
                </CardDescription>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant={temFiltros ? "default" : "outline"}
              size="sm"
              onClick={() => setFiltrosAbertos(v => !v)}
              className={temFiltros ? "bg-purple-600 hover:bg-purple-700" : ""}
            >
              <Filter className="mr-1.5 h-3.5 w-3.5" />
              Filtros
              {temFiltros && (
                <Badge className="ml-1.5 bg-white text-purple-600 text-[10px] px-1.5 py-0">
                  {Object.values(filtros).filter(Boolean).length}
                </Badge>
              )}
            </Button>

            {temFiltros && (
              <Button variant="ghost" size="sm" onClick={limpar} className="text-gray-500 hover:text-red-500">
                <X className="mr-1.5 h-3.5 w-3.5" />
                Limpar filtros
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={() => { buscarSummary(filtros); buscarRegistros(pagina, filtros); }}
              disabled={loadingSummary && loadingReg}
            >
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${(loadingSummary || loadingReg) ? "animate-spin" : ""}`} />
              Atualizar
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* ── Filtros ────────────────────────────────────────────────────── */}
      {filtrosAbertos && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Filtros</CardTitle>
              {temFiltros && (
                <Button variant="ghost" size="sm" onClick={limpar} className="h-7 text-xs text-gray-500">
                  <X className="mr-1 h-3 w-3" /> Limpar
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Modelo</Label>
                <Select
                  value={filtros.model || "_all"}
                  onValueChange={v => setFiltros(f => ({ ...f, model: v === "_all" ? "" : v }))}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="Todos os modelos" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_all">Todos</SelectItem>
                    {modelos.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Data início</Label>
                <Input
                  type="date"
                  className="h-8 text-xs"
                  value={filtros.data_inicio}
                  onChange={e => setFiltros(f => ({ ...f, data_inicio: e.target.value }))}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Data fim</Label>
                <Input
                  type="date"
                  className="h-8 text-xs"
                  value={filtros.data_fim}
                  onChange={e => setFiltros(f => ({ ...f, data_fim: e.target.value }))}
                />
              </div>
              <div className="flex items-end">
                <Button className="w-full bg-purple-600 hover:bg-purple-700" size="sm" onClick={aplicar}>
                  Aplicar filtros
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Cards de métricas ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricaCard
          icon={DollarSign} label="Custo total" iconColor="text-emerald-500"
          value={fmt$(tot.total_cost)}
          sub={`${(tot.registros || 0).toLocaleString()} chamadas`}
          loading={loadingSummary}
        />
        <MetricaCard
          icon={Zap} label="Tokens entrada" iconColor="text-purple-500"
          value={fmtTk(tot.input_tokens)}
          loading={loadingSummary}
        />
        <MetricaCard
          icon={TrendingUp} label="Tokens saída" iconColor="text-amber-500"
          value={fmtTk(tot.output_tokens)}
          loading={loadingSummary}
        />
        <MetricaCard
          icon={Clock} label="Último uso" iconColor="text-blue-500"
          value={tot.ultimo_uso ? fmtDate(tot.ultimo_uso).split(" ")[0] : "—"}
          sub={tot.ultimo_uso ? fmtDate(tot.ultimo_uso).split(" ")[1] : ""}
          loading={loadingSummary}
        />
      </div>

      {/* ── Gráficos ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">

        {/* Custo por dia */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">Custo diário (USD)</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingSummary ? <Sk className="h-48" /> : porDia.length === 0 ? (
              <Vazio msg="Sem dados no período." />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={porDia} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="dia" tickFormatter={fmtDia}
                    tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false}
                  />
                  <YAxis
                    tickFormatter={v => `$${parseFloat(v).toFixed(4)}`}
                    tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} width={72}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Line
                    type="monotone" dataKey="custo" name="Custo"
                    stroke="#8b5cf6" strokeWidth={2}
                    dot={{ fill: "#8b5cf6", r: 4 }} activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Custo por modelo */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">Por modelo</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingSummary ? <Sk className="h-48" /> : porMod.length === 0 ? <Vazio /> : (
              <>
                <ResponsiveContainer width="100%" height={150}>
                  <BarChart data={porMod} layout="vertical" margin={{ top: 0, right: 4, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                    <XAxis
                      type="number" tickFormatter={v => `$${parseFloat(v).toFixed(3)}`}
                      tick={{ fontSize: 9, fill: "#9ca3af" }} axisLine={false} tickLine={false}
                    />
                    <YAxis
                      type="category" dataKey="model"
                      tick={{ fontSize: 9, fill: "#6b7280" }} axisLine={false} tickLine={false} width={90}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="custo" name="Custo" radius={[0, 4, 4, 0]}>
                      {porMod.map((_, i) => <Cell key={i} fill={PALETA[i % PALETA.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
                  {porMod.slice(0, 4).map((m, i) => (
                    <div key={m.model} className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-xs text-gray-500 min-w-0">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: PALETA[i % PALETA.length] }} />
                        <span className="truncate">{m.model}</span>
                      </span>
                      <span className="ml-2 shrink-0 font-mono text-xs font-semibold text-gray-700">
                        {fmt$(m.custo)}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Top usuários ───────────────────────────────────────────────── */}
      {(loadingSummary || topU.length > 0) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <Users size={14} className="text-purple-500" />
              Top usuários por custo
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {loadingSummary
                ? Array.from({ length: 3 }).map((_, i) => <Sk key={i} className="h-14" />)
                : topU.map((u, i) => (
                  <div key={u.usuario_id} className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-4 py-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-purple-100 text-xs font-bold text-purple-600">
                        {i + 1}
                      </span>
                      <span className="truncate text-sm text-gray-700">{u.nome}</span>
                    </div>
                    <div className="shrink-0 text-right ml-2">
                      <p className="text-sm font-bold text-gray-800">{fmt$(u.custo)}</p>
                      <p className="text-[10px] text-gray-400">{u.registros} chamadas</p>
                    </div>
                  </div>
                ))
              }
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Tabela de registros ────────────────────────────────────────── */}
      <Card>
        <CardHeader className="flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-sm font-semibold text-gray-700">
              Registros detalhados
              {loadingReg && <span className="ml-2 text-xs font-normal text-gray-400">carregando…</span>}
            </CardTitle>
            {paginacao.total > 0 && (
              <CardDescription className="mt-0.5">
                {((paginacao.page - 1) * paginacao.page_size) + 1}–
                {Math.min(paginacao.page * paginacao.page_size, paginacao.total)} de{" "}
                {paginacao.total.toLocaleString()} registros
              </CardDescription>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">

          {/* Desktop */}
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Data</TableHead>
                  <TableHead>Usuário</TableHead>
                  <TableHead>Modelo</TableHead>
                  <TableHead className="text-right">Tokens entrada</TableHead>
                  <TableHead className="text-right">Tokens saída</TableHead>
                  <TableHead className="text-right">Custo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loadingReg ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 6 }).map((_, j) => (
                        <TableCell key={j}><Sk className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : erroReg ? (
                  <TableRow>
                    <TableCell colSpan={6}><Vazio msg={`Erro: ${erroReg}`} /></TableCell>
                  </TableRow>
                ) : registros.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6}><Vazio msg="Nenhum registro encontrado." /></TableCell>
                  </TableRow>
                ) : (
                  registros.map(r => (
                    <TableRow key={r.id}>
                      <TableCell className="text-xs text-gray-500">{fmtDate(r.created_at)}</TableCell>
                      <TableCell className="text-sm text-gray-700">{r.usuario?.nome || "Sistema"}</TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="font-mono text-xs">
                          {r.model || "—"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-gray-600">
                        {fmtTk(r.input_tokens)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-gray-600">
                        {fmtTk(r.output_tokens)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm font-semibold text-emerald-600">
                        {fmt$(r.total_cost)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Mobile */}
          <div className="block space-y-2 p-4 md:hidden">
            {loadingReg
              ? Array.from({ length: 4 }).map((_, i) => <Sk key={i} className="h-16" />)
              : registros.map(r => (
                <div key={r.id} className="flex items-start justify-between rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <div className="min-w-0 space-y-1">
                    <Badge variant="secondary" className="font-mono text-[10px]">{r.model || "—"}</Badge>
                    <p className="text-xs text-gray-600">{r.usuario?.nome || "Sistema"}</p>
                    <p className="text-[10px] text-gray-400">{fmtDate(r.created_at)}</p>
                  </div>
                  <div className="shrink-0 text-right ml-2">
                    <p className="text-sm font-bold text-emerald-600">{fmt$(r.total_cost)}</p>
                    <p className="text-xs text-gray-400">{fmtTk(r.input_tokens + r.output_tokens)} tokens</p>
                  </div>
                </div>
              ))
            }
          </div>

          {/* Paginação */}
          {paginacao.total_pages > 1 && (
            <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
              <Button
                variant="outline" size="sm"
                onClick={() => setPagina(p => Math.max(1, p - 1))}
                disabled={pagina <= 1 || loadingReg}
              >
                <ChevronLeft className="mr-1 h-3.5 w-3.5" /> Anterior
              </Button>

              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(7, paginacao.total_pages) }, (_, i) => {
                  const pg = i + 1;
                  return (
                    <button
                      key={pg}
                      onClick={() => setPagina(pg)}
                      className={`h-7 w-7 rounded text-xs transition ${pagina === pg
                        ? "bg-purple-600 font-bold text-white"
                        : "text-gray-500 hover:bg-gray-100"
                        }`}
                    >
                      {pg}
                    </button>
                  );
                })}
                {paginacao.total_pages > 7 && (
                  <span className="px-1 text-xs text-gray-400">… {paginacao.total_pages}</span>
                )}
              </div>

              <Button
                variant="outline" size="sm"
                onClick={() => setPagina(p => Math.min(paginacao.total_pages, p + 1))}
                disabled={pagina >= paginacao.total_pages || loadingReg}
              >
                Próxima <ChevronRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </div>
          )}

        </CardContent>
      </Card>

    </div>
  );
}