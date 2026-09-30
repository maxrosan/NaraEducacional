import React, { useState, useRef, useEffect } from 'react';
import { Helmet } from 'react-helmet-async';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Building, Users, BookUser, CalendarDays, ClipboardList, FileCog,
  HelpCircle, UserPlus, GraduationCap, Activity, Wand2,
  ChevronDown, LogOut, User, ShieldCheck, Menu, X,
} from 'lucide-react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  TurmasTab, UsuariosTab, PeriodosTab,
  RegistrosTab, RelatoriosConfigTab, PerguntasTab,
  AlunosTab, PromptsTab, CategoriasPromptTab,
  DispositivosTab
} from '@/components/admin';
import DisciplinasTab from '@/components/admin/DisciplinasTab';
import EscolasTab from '@/components/admin/EscolasTab';
import { useAuth } from '@/contexts/AuthContext';
import OpenAIUsagePage from '@/pages/OpenAIUsagePage';

// ─── Nav items ────────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { label: "Dashboard", tab: "dashboard" },
  {
    label: "Cadastros",
    children: [
      { label: "Turmas", tab: "turmas" },
      { label: "Alunos", tab: "alunos" },
      { label: "Disciplinas", tab: "disciplinas" },
      { label: "Dispositivos", tab: "dispositivos" },
    ],
  },
  { label: "Relatórios", tab: "relatorios" },
  {
    label: "Configurações",
    children: [
      { label: "Períodos",   tab: "periodos"          },
      { label: "Usuários",   tab: "usuarios"          },
      { label: "Perguntas",  tab: "perguntas"         },
      { label: "Registros",  tab: "registros"         },
      { label: "OpenAI",     tab: "openai"            },
      { label: "Prompts",    tab: "prompts"           },
      { label: "Categorias", tab: "categorias-prompt" },
    ],
  },
];

// ─── Helpers de usuário ───────────────────────────────────────────────────────

const PERFIL_LABEL = {
  admin:                  "Administrador",
  coordenador:            "Coordenador",
  professor:              "Professor",
  professor_infantil:     "Prof. Educação Infantil",
  professor_fundamental:  "Prof. Ensino Fundamental",
  professor_especialista: "Prof. Especialista",
  especialista:           "Especialista",
};

function nomeIniciais(nome) {
  if (!nome) return "?";
  const partes = nome.trim().split(/\s+/);
  if (partes.length === 1) return partes[0][0].toUpperCase();
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

// ─── Dropdown genérico (desktop) ─────────────────────────────────────────────

function Dropdown({ trigger, children, align = "left" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handler(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen((v) => !v)}>{trigger(open)}</div>
      {open && (
        <div className={`absolute z-50 mt-1 min-w-[180px] rounded-xl border border-gray-100 bg-white py-2 shadow-xl shadow-gray-200/60 ${
          align === "right" ? "right-0" : "left-0"
        }`}>
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

// ─── Navbar ───────────────────────────────────────────────────────────────────

function Navbar({ onTabChange, tabAtiva }) {
  const { user, signOut } = useAuth();
  const [menuAberto, setMenuAberto] = useState(false);
  const [grupoAberto, setGrupoAberto] = useState(null); // label do grupo expandido no mobile

  const nomeCompleto = user?.user_metadata?.full_name || user?.nome || user?.email || "Usuário";
  const email        = user?.email ?? "";
  const perfil       = user?.perfil ?? user?.user_metadata?.perfil ?? "";
  const iniciais     = nomeIniciais(nomeCompleto);
  const perfilLabel  = PERFIL_LABEL[perfil] || perfil || "Usuário";

  async function handleSair(close) {
    close?.();
    setMenuAberto(false);
    await signOut();
  }

  function handleNavClick(tab, close) {
    close?.();
    setMenuAberto(false);
    onTabChange(tab);
  }

  return (
    <>
      <header className="sticky top-0 z-40 flex h-16 items-center border-b border-gray-100 bg-white px-4 sm:px-8">

        {/* Logo */}
        <div className="flex flex-1 items-center">
          <a href="/" className="flex shrink-0 items-center">
            <img alt="NARA icon logo" className="h-12 w-auto sm:h-14" src="/nara-logo.png" />
          </a>
        </div>

        {/* Menu central — desktop */}
        <nav className="hidden lg:flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            if (!item.children) {
              const ativo = tabAtiva === item.tab;
              return (
                <button
                  key={item.label}
                  onClick={() => handleNavClick(item.tab, null)}
                  className={`rounded-lg px-4 py-2 text-base font-medium transition-colors ${
                    ativo
                      ? "bg-purple-50 text-purple-700"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  }`}
                >
                  {item.label}
                </button>
              );
            }

            const filhoAtivo = item.children.some((c) => c.tab === tabAtiva);
            return (
              <Dropdown
                key={item.label}
                trigger={(open) => (
                  <button className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-base font-medium transition-colors ${
                    open || filhoAtivo
                      ? "bg-purple-50 text-purple-700"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  }`}>
                    {item.label}
                    <ChevronDown size={15} className={`transition-transform ${open ? "rotate-180 text-purple-600" : "text-gray-400"}`} />
                  </button>
                )}
              >
                {(close) =>
                  item.children.map((child) => {
                    const ativo = tabAtiva === child.tab;
                    return (
                      <button
                        key={child.label}
                        onClick={() => handleNavClick(child.tab, close)}
                        className={`flex w-full items-center px-5 py-2.5 text-sm transition-colors ${
                          ativo
                            ? "bg-purple-50 font-medium text-purple-700"
                            : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                        }`}
                      >
                        {ativo && <span className="mr-2 h-1.5 w-1.5 rounded-full bg-purple-600" />}
                        {child.label}
                      </button>
                    );
                  })
                }
              </Dropdown>
            );
          })}
        </nav>

        {/* Lado direito: avatar (desktop) + hamburguer (mobile) */}
        <div className="flex flex-1 items-center justify-end gap-2">

          {/* Avatar — desktop */}
          <div className="hidden lg:block">
            <Dropdown
              align="right"
              trigger={(open) => (
                <button className="flex items-center gap-2 rounded-xl p-1 transition-colors hover:bg-gray-50">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors ${
                    open ? "border-purple-400 bg-purple-100 text-purple-700" : "border-gray-200 bg-purple-100 text-purple-700"
                  }`}>
                    {iniciais}
                  </div>
                  <ChevronDown size={15} className={`transition-transform ${open ? "rotate-180 text-purple-600" : "text-gray-400"}`} />
                </button>
              )}
            >
              {(close) => (
                <>
                  <div className="flex items-center gap-3 px-5 py-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-purple-100 text-sm font-bold text-purple-700">
                      {iniciais}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-gray-800">{nomeCompleto}</p>
                      <p className="truncate text-xs text-gray-400">{email}</p>
                    </div>
                  </div>
                  <div className="my-1 border-t border-gray-100" />
                  {perfil && (
                    <div className="px-5 py-2">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-50 px-3 py-1 text-xs font-semibold text-purple-700">
                        <ShieldCheck size={12} />
                        {perfilLabel}
                      </span>
                    </div>
                  )}
                  <a href="#" onClick={close} className="flex items-center gap-3 px-5 py-2.5 text-sm text-gray-600 hover:bg-gray-50">
                    <User size={15} className="text-gray-400" />
                    Meu Perfil
                  </a>
                  <div className="my-1 border-t border-gray-100" />
                  <button onClick={() => handleSair(close)} className="flex w-full items-center gap-3 px-5 py-2.5 text-sm text-red-500 hover:bg-red-50">
                    <LogOut size={15} />
                    Sair
                  </button>
                </>
              )}
            </Dropdown>
          </div>

          {/* Hamburguer — mobile */}
          <button
            onClick={() => setMenuAberto((v) => !v)}
            className="lg:hidden flex h-10 w-10 items-center justify-center rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50"
          >
            {menuAberto ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>

      {/* Drawer mobile */}
      <AnimatePresence>
        {menuAberto && (
          <>
            {/* Overlay */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-30 bg-black/30 lg:hidden"
              onClick={() => setMenuAberto(false)}
            />

            {/* Painel lateral */}
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.25 }}
              className="fixed left-0 top-0 z-40 flex h-full w-72 flex-col bg-white shadow-2xl lg:hidden"
            >
              {/* Cabeçalho do drawer */}
              <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
                <img alt="NARA icon logo" className="h-10 w-auto" src="/nara-logo.png" />
                <button onClick={() => setMenuAberto(false)} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100">
                  <X size={18} />
                </button>
              </div>

              {/* Info do usuário */}
              <div className="flex items-center gap-3 border-b border-gray-100 px-5 py-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-purple-100 text-sm font-bold text-purple-700">
                  {iniciais}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-gray-800">{nomeCompleto}</p>
                  {perfil && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2 py-0.5 text-xs font-semibold text-purple-700 mt-0.5">
                      <ShieldCheck size={10} />
                      {perfilLabel}
                    </span>
                  )}
                </div>
              </div>

              {/* Navegação */}
              <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
                {NAV_ITEMS.map((item) => {
                  if (!item.children) {
                    const ativo = tabAtiva === item.tab;
                    return (
                      <button
                        key={item.label}
                        onClick={() => handleNavClick(item.tab, null)}
                        className={`flex w-full items-center rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
                          ativo
                            ? "bg-purple-50 text-purple-700"
                            : "text-gray-600 hover:bg-gray-50"
                        }`}
                      >
                        {ativo && <span className="mr-2 h-1.5 w-1.5 rounded-full bg-purple-600" />}
                        {item.label}
                      </button>
                    );
                  }

                  const filhoAtivo = item.children.some((c) => c.tab === tabAtiva);
                  const esteGrupoAberto = grupoAberto === item.label;

                  return (
                    <div key={item.label}>
                      <button
                        onClick={() => setGrupoAberto(esteGrupoAberto ? null : item.label)}
                        className={`flex w-full items-center justify-between rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
                          filhoAtivo || esteGrupoAberto
                            ? "bg-purple-50 text-purple-700"
                            : "text-gray-600 hover:bg-gray-50"
                        }`}
                      >
                        {item.label}
                        <ChevronDown size={14} className={`transition-transform ${esteGrupoAberto ? "rotate-180" : ""}`} />
                      </button>
                      <AnimatePresence>
                        {esteGrupoAberto && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="ml-4 mt-0.5 space-y-0.5 border-l-2 border-gray-100 pl-3">
                              {item.children.map((child) => {
                                const ativo = tabAtiva === child.tab;
                                return (
                                  <button
                                    key={child.label}
                                    onClick={() => handleNavClick(child.tab, null)}
                                    className={`flex w-full items-center rounded-lg px-3 py-2 text-sm transition-colors ${
                                      ativo
                                        ? "bg-purple-50 font-medium text-purple-700"
                                        : "text-gray-500 hover:bg-gray-50 hover:text-gray-700"
                                    }`}
                                  >
                                    {ativo && <span className="mr-2 h-1.5 w-1.5 rounded-full bg-purple-600" />}
                                    {child.label}
                                  </button>
                                );
                              })}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );
                })}
              </nav>

              {/* Rodapé do drawer */}
              <div className="border-t border-gray-100 px-3 py-3 space-y-0.5">
                <a href="#" className="flex w-full items-center gap-3 rounded-xl px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50">
                  <User size={15} className="text-gray-400" />
                  Meu Perfil
                </a>
                <button onClick={() => handleSair(null)} className="flex w-full items-center gap-3 rounded-xl px-4 py-2.5 text-sm text-red-500 hover:bg-red-50">
                  <LogOut size={15} />
                  Sair
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

// ─── AdminPage ────────────────────────────────────────────────────────────────

// Aba removida → aba que a substitui.
//   instituicoes: era a página inicial antiga; hoje é o dashboard.
//   series: o banco multi-tenant não tem séries; etapa, faixa etária, idades e
//           ordem são campos da própria turma.
const ABAS_REMOVIDAS = { instituicoes: 'dashboard', series: 'turmas' };

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

const AdminPage = () => {
  const navigate = useNavigate();
  const { tab }  = useParams();
  const query    = useQuery();
  const turmaId  = query.get('turma_id');

  // /admin sem aba abre o dashboard; /admin?turma_id=... continua abrindo Alunos.
  const initialTab = tab || (turmaId ? 'alunos' : 'dashboard');

  // Garante a URL /admin/dashboard (e não só /admin) ao entrar no painel e
  // redireciona abas que deixaram de existir (links e favoritos antigos).
  useEffect(() => {
    if (!tab && !turmaId) navigate('/admin/dashboard', { replace: true });
    else if (ABAS_REMOVIDAS[tab]) navigate(`/admin/${ABAS_REMOVIDAS[tab]}`, { replace: true });
  }, [tab, turmaId, navigate]);

  function handleTabChange(value) {
    navigate(`/admin/${value}`);
  }

  return (
    <>
      <Helmet>
        <title>NARA - Painel Administrativo</title>
        <meta name="description" content="Área de administração e configuração do NARA." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <Navbar onTabChange={handleTabChange} tabAtiva={initialTab} />

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col min-h-[calc(100vh-4rem)]">
          <motion.h2
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-xl sm:text-2xl font-bold text-gray-800 mb-6"
          >
            Painel de Controle do NARA
          </motion.h2>

          <Tabs defaultValue={initialTab} onValueChange={handleTabChange} value={initialTab} className="w-full">
            <TabsList className="hidden">
              <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
              <TabsTrigger value="turmas">Turmas</TabsTrigger>
              <TabsTrigger value="alunos">Alunos</TabsTrigger>
              <TabsTrigger value="disciplinas">Disciplinas</TabsTrigger>
              <TabsTrigger value="relatorios">Relatórios</TabsTrigger>
              <TabsTrigger value="periodos">Períodos</TabsTrigger>
              <TabsTrigger value="usuarios">Usuários</TabsTrigger>
              <TabsTrigger value="perguntas">Perguntas</TabsTrigger>
              <TabsTrigger value="registros">Registros</TabsTrigger>
              <TabsTrigger value="openai">OpenAI</TabsTrigger>
              <TabsTrigger value="prompts">Prompts</TabsTrigger>
              <TabsTrigger value="categorias-prompt">Categorias</TabsTrigger>
            </TabsList>

            <AnimatePresence mode="wait">
              <motion.div
                key={initialTab}
                initial={{ y: 10, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: -10, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="mt-6"
              >
                <TabsContent value="dashboard"><EscolasTab /></TabsContent>
                <TabsContent value="turmas"><TurmasTab /></TabsContent>
                <TabsContent value="alunos"><AlunosTab /></TabsContent>
                <TabsContent value="disciplinas"><DisciplinasTab /></TabsContent>
                <TabsContent value="dispositivos"><DispositivosTab /></TabsContent>
                <TabsContent value="relatorios"><RelatoriosConfigTab /></TabsContent>
                <TabsContent value="periodos"><PeriodosTab /></TabsContent>
                <TabsContent value="usuarios"><UsuariosTab /></TabsContent>
                <TabsContent value="perguntas"><PerguntasTab /></TabsContent>
                <TabsContent value="registros"><RegistrosTab /></TabsContent>
                <TabsContent value="openai"><OpenAIUsagePage /></TabsContent>
                <TabsContent value="prompts"><PromptsTab /></TabsContent>
                <TabsContent value="categorias-prompt"><CategoriasPromptTab /></TabsContent>
              </motion.div>
            </AnimatePresence>
          </Tabs>

          <footer className="py-6 text-center mt-auto">
            <p className="text-sm text-gray-500">
              Todos os direitos reservados a Nara Educacional &copy; {new Date().getFullYear()}
            </p>
          </footer>
        </main>
      </div>
    </>
  );
};

export default AdminPage;