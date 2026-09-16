import { useState, useEffect, useRef } from "react";

export default function EscolaDetalhe({ onVoltar }) {
  const [notaModalOpen, setNotaModalOpen] = useState(false);
  const [dangerModalOpen, setDangerModalOpen] = useState(false);
  const [selectedTag, setSelectedTag] = useState("check-in");
  const [notaText, setNotaText] = useState("");
  const [notaTextError, setNotaTextError] = useState(false);
  const [dangerConfirm, setDangerConfirm] = useState("");
  const [isDesativada, setIsDesativada] = useState(false);
  const [toast, setToast] = useState({ show: false, text: "" });
  const [notes, setNotes] = useState([
    { id: 1, date: "22/04/2026", author: "Beatriz Dantas", text: "Reunião de check-in: Maria Letícia super engajada. Quer apresentar a Nara em 2 escolas parceiras dela. Marcamos demo conjunta dia 5/05." },
    { id: 2, date: "15/04/2026", author: "Beatriz Dantas", text: "Treinamento prof. Geise — não consegue usar a modalidade Análise. Agendado novo onboarding individual." },
    { id: 3, date: "02/04/2026", author: "Beatriz Dantas", text: "Escola perguntou sobre integração com sistema de gestão (eduConnect). Resposta: não temos integração ainda mas está no roadmap." },
    { id: 4, date: "28/03/2026", author: "Max Júnior", text: "Migração concluída. 158 alunos importados, 8 professoras cadastradas. Tudo OK." },
  ]);
  const [newNoteId, setNewNoteId] = useState(null);
  const notaTextareaRef = useRef(null);
  const dangerInputRef = useRef(null);

  const ESCOLA_NOME = "Centro Educacional Reluz";

  const tagEmojis = { "check-in": "📞", treinamento: "🎓", suporte: "🛠️", comercial: "💼", feedback: "💭", outro: "📝" };
  const tagLabels = { "check-in": "Check-in", treinamento: "Treinamento", suporte: "Suporte", comercial: "Comercial", feedback: "Feedback", outro: "Anotação" };
  const tagOptions = [
    { key: "check-in", label: "📞 Check-in" },
    { key: "treinamento", label: "🎓 Treinamento" },
    { key: "suporte", label: "🛠️ Suporte" },
    { key: "comercial", label: "💼 Comercial" },
    { key: "feedback", label: "💭 Feedback" },
    { key: "outro", label: "📝 Outro" },
  ];

  function showToast(msg) {
    setToast({ show: true, text: msg });
    setTimeout(() => setToast({ show: false, text: "" }), 2400);
  }

  function impersonate(papel) {
    alert("Impersonate: " + papel + "\n\nNa versão final, isso vai abrir a app principal da escola em modo admin.");
  }

  function impersonateUser(nome, papel) {
    alert("Impersonate: " + nome + " (" + papel + ")\n\nNa versão final, isso vai abrir a app principal logado como esta pessoa.");
  }

  function openNotaModal() {
    setNotaModalOpen(true);
    setTimeout(() => notaTextareaRef.current?.focus(), 100);
  }

  function closeNotaModal() {
    setNotaModalOpen(false);
    setNotaText("");
    setNotaTextError(false);
    setSelectedTag("check-in");
  }

  function saveNota() {
    if (!notaText.trim()) {
      setNotaTextError(true);
      notaTextareaRef.current?.focus();
      setTimeout(() => setNotaTextError(false), 1500);
      return;
    }
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, "0");
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const yyyy = today.getFullYear();
    const id = Date.now();
    const newNote = {
      id,
      date: `${dd}/${mm}/${yyyy}`,
      author: "Beatriz Dantas",
      tag: selectedTag,
      text: notaText.trim(),
      isNew: true,
    };
    setNotes((prev) => [newNote, ...prev]);
    setNewNoteId(id);
    setTimeout(() => setNewNoteId(null), 3000);
    closeNotaModal();
    showToast("Anotação salva com sucesso");
  }

  function openDesativarModal() {
    setDangerModalOpen(true);
    setTimeout(() => dangerInputRef.current?.focus(), 100);
  }

  function closeDesativarModal() {
    setDangerModalOpen(false);
    setDangerConfirm("");
  }

  function confirmarDesativacao() {
    closeDesativarModal();
    setIsDesativada(true);
    showToast("Escola desativada · login bloqueado");
  }

  function reativarEscola() {
    if (confirm("Reativar Centro Educacional Reluz?\n\nO login será restaurado para toda a equipe e cobrança recorrente reestabelecida.")) {
      setIsDesativada(false);
      showToast("Escola reativada · login restaurado");
    }
  }

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === "Escape") { closeNotaModal(); closeDesativarModal(); }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && notaModalOpen) saveNota();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [notaModalOpen, notaText, selectedTag]);

  const professors = [
    { initials: "LB", name: "Lúcia Bezerra", email: "lucia.bezerra@unicamaster.com.br", turma: "Nível 5-A", acesso: "agora há pouco", acessoClass: "acesso-recent", registros: 1275, health: 92, healthColor: "#4CAF50", healthW: 92 },
    { initials: "NS", name: "Nilsiene Souza", email: "nilsiene@unicamaster.com.br", turma: "Nível 4-A", acesso: "há 2 horas", acessoClass: "acesso-recent", registros: 1084, health: 88, healthColor: "#4CAF50", healthW: 88 },
    { initials: "SC", name: "Silvana Cavalcanti", email: "silvana@unicamaster.com.br", turma: "Nível 4-C", acesso: "há 1 dia", acessoClass: "acesso-recent", registros: 813, health: 81, healthColor: "#4CAF50", healthW: 81 },
    { initials: "AM", name: "Ana Carla Mendes", email: "anacarla@unicamaster.com.br", turma: "Nível 5-C", acesso: "há 5 horas", acessoClass: "acesso-recent", registros: 752, health: 79, healthColor: "#4CAF50", healthW: 79 },
    { initials: "DA", name: "Dijanile Albuquerque", email: "dijanile@unicamaster.com.br", turma: "Nível 5-B", acesso: "há 17 horas", acessoClass: "acesso-recent", registros: 682, health: 76, healthColor: "#4CAF50", healthW: 76 },
    { initials: "AV", name: "Alana Vieira", email: "alanasoares@unicamaster.com.br", turma: "Nível 5-D", acesso: "há 2 dias", acessoClass: "acesso-medium", registros: 513, health: 67, healthColor: "#FFA726", healthW: 67 },
    { initials: "GL", name: "Gabriela Lima", email: "anagabriela@unicamaster.com.br", turma: "Nível 4-D", acesso: "há 6 dias", acessoClass: "acesso-late", registros: 284, health: 48, healthColor: "#EF5350", healthW: 48 },
    { initials: "GM", name: "Geise Mayara", email: "geise@unicamaster.com.br", turma: "Nível 4-B", acesso: "há 4 dias", acessoClass: "acesso-late", registros: 187, health: 32, healthColor: "#EF5350", healthW: 32 },
  ];

  return (
    <>
      <style>{`
        .ed { font-family: 'Poppins', -apple-system, sans-serif; font-size: 14px; line-height: 1.5; -webkit-font-smoothing: antialiased; }

        .ed .breadcrumb-admin { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #6B7280; margin-bottom: 14px; font-weight: 500; }
        .ed .breadcrumb-admin a { color: #6B7280; text-decoration: none; transition: color 0.15s; cursor: pointer; }
        .ed .breadcrumb-admin a:hover { color: #7E5BBE; }

        .ed .school-hero { background: #fff; border-radius: 18px; padding: 24px 28px; border: 1px solid #F3F4F6; margin-bottom: 20px; display: flex; align-items: center; gap: 20px; animation: ed-fadeUp 0.5s ease-out; flex-wrap: wrap; }
        .ed .school-hero.desativada { opacity: 0.75; filter: grayscale(0.4); }
        .ed .hero-avatar { width: 72px; height: 72px; border-radius: 18px; background: linear-gradient(135deg, #EDE7F6, #A5D6A7); display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 800; color: #4A3370; flex-shrink: 0; }
        .ed .hero-info { flex: 1; min-width: 240px; }
        .ed .hero-name { font-size: 22px; font-weight: 800; color: #1A1A2E; letter-spacing: -0.5px; }
        .ed .hero-meta { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 6px; font-size: 12px; color: #6B7280; }
        .ed .hero-meta-item { display: inline-flex; align-items: center; gap: 5px; }
        .ed .hero-meta-item strong { color: #1A1A2E; font-weight: 700; }
        .ed .health-large { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 0 16px; border-left: 1px solid #F3F4F6; }
        .ed .health-num-big { font-size: 36px; font-weight: 800; line-height: 1; color: #4CAF50; letter-spacing: -1px; }
        .ed .health-num-big.inativo { color: #9CA3AF; }
        .ed .health-label { font-size: 10px; font-weight: 700; color: #6B7280; text-transform: uppercase; letter-spacing: 0.6px; }
        .ed .hero-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .ed .hero-btn { display: inline-flex; align-items: center; gap: 7px; padding: 10px 16px; border-radius: 10px; border: 1px solid #E5E7EB; background: white; color: #2F2F42; font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .ed .hero-btn:hover { border-color: #7E5BBE; color: #7E5BBE; }
        .ed .hero-btn.primary { background: #7E5BBE; border-color: #7E5BBE; color: white; }
        .ed .hero-btn.primary:hover { background: #6B4FA8; border-color: #6B4FA8; transform: translateY(-1px); }
        .ed .hero-btn.danger { background: white; border-color: #EF5350; color: #EF5350; }
        .ed .hero-btn.danger:hover { background: #EF5350; color: white; border-color: #EF5350; transform: translateY(-1px); }
        .ed .hero-btn.green-btn { background: #4CAF50; border-color: #4CAF50; color: white; }
        .ed .hero-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .ed .escola-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
        .ed .escola-grid.three-col { grid-template-columns: repeat(3, 1fr); }

        .ed .panel { background: #fff; border-radius: 16px; padding: 20px 22px; border: 1px solid #F3F4F6; animation: ed-fadeUp 0.5s ease-out backwards; }
        .ed .panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; gap: 8px; }
        .ed .panel-title { font-size: 13px; font-weight: 700; color: #1A1A2E; display: inline-flex; align-items: center; gap: 8px; }
        .ed .panel-icon { width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; }
        .ed .panel-icon.purple { background: #F5F0FB; color: #7E5BBE; }
        .ed .panel-icon.green { background: #E8F5E9; color: #4CAF50; }
        .ed .panel-icon.blue { background: #E3F2FD; color: #5C9CE6; }
        .ed .panel-icon.amber { background: #FFF3E0; color: #FFA726; }
        .ed .panel-trend { font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 99px; }
        .ed .panel-trend.up { background: #E8F5E9; color: #4CAF50; }
        .ed .panel-trend.down { background: #FFEBEE; color: #EF5350; }
        .ed .panel-trend.flat { background: #F5F5F7; color: #6B7280; }
        .ed .panel-big-number { font-size: 32px; font-weight: 800; color: #1A1A2E; letter-spacing: -1px; line-height: 1; }
        .ed .panel-big-suffix { font-size: 14px; color: #6B7280; font-weight: 600; margin-left: 4px; }
        .ed .panel-sub { font-size: 11px; color: #6B7280; margin-top: 6px; }
        .ed .sparkline-box { height: 60px; margin-top: 12px; }

        .ed .tip { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; border-radius: 50%; border: 1.5px solid #9CA3AF; color: #9CA3AF; font-size: 9px; font-weight: 700; cursor: help; position: relative; margin-left: 6px; background: transparent; line-height: 1; vertical-align: middle; }
        .ed .tip:hover { border-color: #7E5BBE; color: #7E5BBE; background: #F5F0FB; }
        .ed .tip::before { content: attr(data-tip); position: absolute; bottom: calc(100% + 10px); left: 50%; transform: translateX(-50%) translateY(6px); background: #1A1A2E; color: white; padding: 10px 12px; border-radius: 8px; font-size: 11px; font-weight: 400; line-height: 1.5; width: max-content; max-width: 260px; white-space: normal; text-align: left; opacity: 0; visibility: hidden; pointer-events: none; transition: all 0.18s; z-index: 100; box-shadow: 0 12px 32px rgba(0,0,0,0.2); }
        .ed .tip:hover::before { opacity: 1; visibility: visible; transform: translateX(-50%) translateY(0); }

        .ed .signal-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-radius: 10px; margin-bottom: 10px; }
        .ed .signal-item:last-child { margin-bottom: 0; }
        .ed .signal-item.green { background: #E8F5E9; }
        .ed .signal-item.amber { background: #FFF3E0; }
        .ed .signal-item.blue { background: #E3F2FD; }
        .ed .signal-title { font-weight: 700; font-size: 13px; line-height: 1.3; }
        .ed .signal-detail { font-size: 11px; color: #6B7280; margin-top: 3px; }
        .ed .signal-item.green .signal-title { color: #4CAF50; }
        .ed .signal-item.amber .signal-title { color: #FFA726; }
        .ed .signal-item.blue .signal-title { color: #5C9CE6; }

        .ed .note-item { padding: 14px 0; border-bottom: 1px solid #F3F4F6; display: flex; gap: 12px; transition: background 0.3s; }
        .ed .note-item:last-child { border-bottom: none; padding-bottom: 0; }
        .ed .note-item:first-child { padding-top: 0; }
        .ed .note-item.new-note { animation: ed-slideInNote 0.5s cubic-bezier(0.16,1,0.3,1); background: #E8F5E9; margin: 0 -14px; padding: 14px; border-radius: 10px; border-bottom: none !important; }
        .ed .note-date { font-size: 11px; color: #6B7280; font-weight: 700; flex-shrink: 0; width: 80px; padding-top: 2px; }
        .ed .note-body { flex: 1; }
        .ed .note-author { font-size: 11px; color: #7E5BBE; font-weight: 700; margin-bottom: 3px; }
        .ed .note-text { font-size: 13px; color: #2F2F42; line-height: 1.5; }
        .ed .note-tag-prefix { color: #7E5BBE; font-weight: 700; }

        .ed .users-panel { background: #fff; border-radius: 16px; padding: 24px; border: 1px solid #F3F4F6; margin-bottom: 16px; overflow-x: auto; animation: ed-fadeUp 0.5s ease-out backwards; }
        .ed .users-panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; flex-wrap: wrap; gap: 12px; }
        .ed .users-tabs { display: flex; gap: 4px; background: #F5F5F7; border-radius: 10px; padding: 4px; }
        .ed .users-tab { padding: 7px 14px; border: none; background: transparent; border-radius: 7px; font-size: 12px; font-weight: 600; color: #6B7280; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .ed .users-tab:hover { color: #1A1A2E; }
        .ed .users-tab.active { background: #EDE7F6; color: #7E5BBE; }
        .ed .users-table { width: 100%; min-width: 800px; border-collapse: collapse; }
        .ed .users-table thead th { text-align: left; padding: 10px 12px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #6B7280; border-bottom: 1px solid #F3F4F6; }
        .ed .users-table tbody tr { border-bottom: 1px solid #F3F4F6; transition: background 0.12s; }
        .ed .users-table tbody tr:hover { background: #F5F0FB; }
        .ed .users-table td { padding: 12px; vertical-align: middle; }
        .ed .user-cell { display: flex; align-items: center; gap: 10px; }
        .ed .user-avatar { width: 32px; height: 32px; border-radius: 10px; background: #EDE7F6; color: #7E5BBE; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 11px; flex-shrink: 0; }
        .ed .user-name { font-size: 13px; font-weight: 700; color: #1A1A2E; line-height: 1.2; }
        .ed .user-email { font-size: 11px; color: #6B7280; margin-top: 1px; }
        .ed .turma-badge { display: inline-block; padding: 3px 9px; border-radius: 6px; background: #EDE7F6; color: #7E5BBE; font-size: 11px; font-weight: 700; }
        .ed .acesso-pill { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 99px; font-size: 10.5px; font-weight: 700; }
        .ed .acesso-pill.acesso-recent { background: #E8F5E9; color: #4CAF50; }
        .ed .acesso-pill.acesso-medium { background: #FFF3E0; color: #FFA726; }
        .ed .acesso-pill.acesso-late { background: #FFEBEE; color: #EF5350; }
        .ed .acesso-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; animation: ed-pulse 2.5s infinite; }
        .ed .num-cell { font-size: 13px; font-weight: 700; color: #1A1A2E; }
        .ed .health-bar-mini { display: inline-block; width: 60px; height: 6px; background: #F5F5F7; border-radius: 99px; margin-right: 8px; vertical-align: middle; overflow: hidden; }
        .ed .health-bar-fill { height: 100%; border-radius: 99px; transition: width 0.6s; }
        .ed .health-num { font-size: 12px; font-weight: 800; vertical-align: middle; }
        .ed .row-action-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 11px; border: 1px solid #E5E7EB; background: transparent; color: #6B7280; border-radius: 7px; font-size: 11px; font-weight: 700; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .ed .row-action-btn:hover { border-color: #7E5BBE; color: #7E5BBE; background: #F5F0FB; }

        /* Modal nota */
        .ed .nota-modal-overlay { position: fixed; inset: 0; background: rgba(26,26,46,0.5); backdrop-filter: blur(4px); display: none; align-items: center; justify-content: center; z-index: 200; padding: 20px; }
        .ed .nota-modal-overlay.open { display: flex; }
        .ed .nota-modal { background: white; border-radius: 22px; max-width: 540px; width: 100%; max-height: 90vh; overflow-y: auto; padding: 28px; position: relative; animation: ed-modalIn 0.3s cubic-bezier(0.16,1,0.3,1); }
        .ed .nota-modal-close { position: absolute; top: 18px; right: 18px; width: 36px; height: 36px; border-radius: 50%; background: #F5F5F7; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; color: #6B7280; }
        .ed .nota-modal-close:hover { background: #FFEBEE; color: #EF5350; }
        .ed .nota-modal-header { display: flex; align-items: center; gap: 12px; margin-bottom: 22px; padding-right: 40px; }
        .ed .nota-modal-icon { width: 44px; height: 44px; border-radius: 12px; background: #F5F0FB; color: #7E5BBE; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .ed .nota-modal-title { font-size: 18px; font-weight: 700; color: #1A1A2E; }
        .ed .nota-modal-subtitle { font-size: 12px; color: #6B7280; margin-top: 3px; }
        .ed .nota-form-group { margin-bottom: 16px; }
        .ed .nota-form-group:last-of-type { margin-bottom: 22px; }
        .ed .nota-label { display: block; font-size: 11px; font-weight: 700; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
        .ed .nota-textarea { width: 100%; padding: 11px 14px; border: 1px solid #E5E7EB; border-radius: 10px; background: #F5F5F7; color: #1A1A2E; font-size: 13px; font-family: inherit; font-weight: 500; transition: all 0.15s; resize: none; min-height: 120px; line-height: 1.5; }
        .ed .nota-textarea:focus { outline: none; border-color: #7E5BBE; background: white; }
        .ed .nota-textarea.error { border-color: #EF5350; }
        .ed .nota-tag-row { display: flex; gap: 8px; flex-wrap: wrap; }
        .ed .nota-tag { padding: 6px 12px; border-radius: 99px; background: #F5F5F7; border: 1px solid #E5E7EB; color: #6B7280; font-size: 11px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .ed .nota-tag:hover { border-color: #7E5BBE; color: #7E5BBE; }
        .ed .nota-tag.selected { background: #EDE7F6; border-color: #7E5BBE; color: #7E5BBE; }
        .ed .nota-modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding-top: 18px; border-top: 1px solid #F3F4F6; }
        .ed .nota-btn-action { padding: 10px 18px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit; border: 1px solid #E5E7EB; background: white; color: #1A1A2E; transition: all 0.15s; }
        .ed .nota-btn-action:hover { border-color: #7E5BBE; color: #7E5BBE; }
        .ed .nota-btn-action.primary { background: #7E5BBE; border-color: #7E5BBE; color: white; }
        .ed .nota-btn-action.primary:hover { background: #6B4FA8; border-color: #6B4FA8; transform: translateY(-1px); }

        /* Toast */
        .ed .toast { position: fixed; bottom: 24px; right: 24px; background: #1A1A2E; color: white; padding: 12px 18px; border-radius: 12px; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.2); z-index: 300; opacity: 0; transform: translateY(20px); transition: all 0.3s cubic-bezier(0.16,1,0.3,1); pointer-events: none; }
        .ed .toast.show { opacity: 1; transform: translateY(0); }
        .ed .toast-icon { width: 22px; height: 22px; border-radius: 50%; background: #4CAF50; color: white; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }

        /* Modal desativar */
        .ed .danger-modal-overlay { position: fixed; inset: 0; background: rgba(26,26,46,0.55); backdrop-filter: blur(4px); display: none; align-items: center; justify-content: center; z-index: 200; padding: 20px; }
        .ed .danger-modal-overlay.open { display: flex; }
        .ed .danger-modal { background: white; border-radius: 22px; max-width: 480px; width: 100%; padding: 30px 28px; position: relative; animation: ed-modalIn 0.3s cubic-bezier(0.16,1,0.3,1); }
        .ed .danger-modal-icon-large { width: 64px; height: 64px; border-radius: 50%; background: #FFEBEE; color: #EF5350; display: flex; align-items: center; justify-content: center; margin: 0 auto 18px; }
        .ed .danger-modal-title { font-size: 20px; font-weight: 800; color: #1A1A2E; text-align: center; letter-spacing: -0.3px; margin-bottom: 8px; }
        .ed .danger-modal-subtitle { font-size: 13.5px; color: #2F2F42; text-align: center; line-height: 1.5; margin-bottom: 22px; }
        .ed .danger-modal-warning { background: #FFEBEE; border-left: 3px solid #EF5350; border-radius: 10px; padding: 14px 16px; margin-bottom: 22px; }
        .ed .danger-warning-title { font-size: 12px; font-weight: 700; color: #EF5350; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
        .ed .danger-warning-list { list-style: none; padding: 0; margin: 0; font-size: 12.5px; color: #2F2F42; line-height: 1.7; }
        .ed .danger-warning-list li { padding-left: 18px; position: relative; }
        .ed .danger-warning-list li::before { content: '×'; position: absolute; left: 0; color: #EF5350; font-weight: 800; }
        .ed .danger-confirm-input { width: 100%; padding: 11px 14px; border: 1px solid #E5E7EB; border-radius: 10px; background: #F5F5F7; color: #1A1A2E; font-size: 13px; font-family: 'Poppins', sans-serif; font-weight: 600; margin-bottom: 6px; transition: all 0.15s; }
        .ed .danger-confirm-input:focus { outline: none; border-color: #EF5350; background: white; }
        .ed .danger-confirm-help { font-size: 11px; color: #6B7280; margin-bottom: 22px; }
        .ed .danger-confirm-help code { background: #F5F5F7; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: 700; color: #EF5350; }
        .ed .danger-modal-footer { display: flex; gap: 8px; justify-content: flex-end; }
        .ed .danger-btn { padding: 11px 20px; border-radius: 10px; font-size: 13px; font-weight: 700; cursor: pointer; font-family: inherit; border: 1px solid #E5E7EB; background: white; color: #1A1A2E; transition: all 0.15s; }
        .ed .danger-btn:hover { border-color: #7E5BBE; color: #7E5BBE; }
        .ed .danger-btn.confirm { background: #EF5350; border-color: #EF5350; color: white; }
        .ed .danger-btn.confirm:hover { background: #C62828; border-color: #C62828; }
        .ed .danger-btn.confirm:disabled { background: #E5E7EB; border-color: #E5E7EB; color: #9CA3AF; cursor: not-allowed; }

        @keyframes ed-fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes ed-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes ed-modalIn { from { opacity: 0; transform: translateY(20px) scale(0.96); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @keyframes ed-slideInNote { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }

        @media (max-width: 1100px) {
          .ed .escola-grid, .ed .escola-grid.three-col { grid-template-columns: 1fr; }
        }
      `}</style>

      <div className="ed">

        {/* Breadcrumb */}
        <div className="breadcrumb-admin">
          <a onClick={onVoltar || (() => window.history.back())}>Escolas</a>
          <span>›</span>
          <span>Centro Educacional Reluz</span>
        </div>

        {/* Hero */}
        <section className={`school-hero${isDesativada ? " desativada" : ""}`}>
          <div className="hero-avatar">CR</div>
          <div className="hero-info">
            <h1 className="hero-name">Centro Educacional Reluz</h1>
            <div className="hero-meta">
              <div className="hero-meta-item">📍 <strong>Currais Novos · RN</strong></div>
              <div className="hero-meta-item">📅 cliente desde <strong>Jan/2026</strong></div>
              <div className="hero-meta-item">📦 plano <strong>Padrão</strong></div>
              <div className="hero-meta-item">👥 <strong>158</strong> alunos · <strong>8</strong> prof. · <strong>1</strong> coord.</div>
            </div>
          </div>
          <div className="health-large">
            <div className={`health-num-big${isDesativada ? " inativo" : ""}`}>{isDesativada ? "—" : "92"}</div>
            <div className="health-label">{isDesativada ? "Inativa" : "Health Score"}</div>
          </div>
          <div className="hero-actions">
            {isDesativada ? (
              <>
                <button className="hero-btn" disabled>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  Acesso bloqueado
                </button>
                <button className="hero-btn green-btn" onClick={reativarEscola}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="9 12 12 15 16 9"/></svg>
                  Reativar escola
                </button>
              </>
            ) : (
              <>
                <button className="hero-btn" onClick={() => impersonate("coord")}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Entrar como Coordenadora
                </button>
                <button className="hero-btn primary" onClick={() => impersonate("prof")}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
                  Entrar como Professora
                </button>
                <button className="hero-btn danger" onClick={openDesativarModal}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
                  Desativar escola
                </button>
              </>
            )}
          </div>
        </section>

        {/* Métricas — 3 colunas */}
        <div className="escola-grid three-col">
          <div className="panel" style={{ animationDelay: "0.05s" }}>
            <div className="panel-head">
              <div className="panel-title">
                <div className="panel-icon purple">🤖</div>
                Tokens IA · 30 dias
                <span className="tip" data-tip="Total de tokens consumidos na geração de relatórios, classificação de hipóteses, análise de produções e mediações automáticas. Indicador direto de custo operacional.">i</span>
              </div>
              <span className="panel-trend up">↑ 18%</span>
            </div>
            <div className="panel-big-number">142<span className="panel-big-suffix">k</span></div>
            <div className="panel-sub">de 250k contratados · 57% utilizados</div>
            <div className="sparkline-box">
              <svg viewBox="0 0 600 70" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
                <defs><linearGradient id="g-7E5BBE" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7E5BBE" stopOpacity="0.25"/><stop offset="100%" stopColor="#7E5BBE" stopOpacity="0"/></linearGradient></defs>
                <polygon points="0,70 0.0,64.0 20.7,61.9 41.4,57.3 62.1,58.8 82.8,55.3 103.4,51.7 124.1,58.8 144.8,65.0 165.5,60.9 186.2,56.8 206.9,50.1 227.6,43.5 248.3,40.4 269.0,37.3 289.7,31.1 310.3,33.2 331.0,29.6 351.7,26.0 372.4,28.1 393.1,24.0 413.8,20.9 434.5,22.9 455.2,19.9 475.9,15.8 496.6,17.3 517.2,14.2 537.9,10.6 558.6,12.7 579.3,9.1 600.0,5.5 600,70" fill="url(#g-7E5BBE)"/>
                <path d="M 0.0,64.0 L 20.7,61.9 L 41.4,57.3 L 62.1,58.8 L 82.8,55.3 L 103.4,51.7 L 124.1,58.8 L 144.8,65.0 L 165.5,60.9 L 186.2,56.8 L 206.9,50.1 L 227.6,43.5 L 248.3,40.4 L 269.0,37.3 L 289.7,31.1 L 310.3,33.2 L 331.0,29.6 L 351.7,26.0 L 372.4,28.1 L 393.1,24.0 L 413.8,20.9 L 434.5,22.9 L 455.2,19.9 L 475.9,15.8 L 496.6,17.3 L 517.2,14.2 L 537.9,10.6 L 558.6,12.7 L 579.3,9.1 L 600.0,5.5" stroke="#7E5BBE" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </div>

          <div className="panel" style={{ animationDelay: "0.1s" }}>
            <div className="panel-head">
              <div className="panel-title">
                <div className="panel-icon green">📈</div>
                Engajamento docente
                <span className="tip" data-tip="% de professoras que registraram pelo menos 3 evidências por dia útil nos últimos 30 dias.">i</span>
              </div>
              <span className="panel-trend up">↑ 4%</span>
            </div>
            <div className="panel-big-number">87<span className="panel-big-suffix">%</span></div>
            <div className="panel-sub">7 de 8 professoras ativas regularmente</div>
            <div className="sparkline-box">
              <svg viewBox="0 0 600 70" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
                <defs><linearGradient id="g-4CAF50" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4CAF50" stopOpacity="0.25"/><stop offset="100%" stopColor="#4CAF50" stopOpacity="0"/></linearGradient></defs>
                <polygon points="0,70 0.0,65.0 20.7,55.6 41.4,36.8 62.1,46.2 82.8,33.7 103.4,24.3 124.1,18.0 144.8,27.4 165.5,21.2 186.2,11.8 206.9,5.5 227.6,14.9 248.3,18.0 269.0,24.3 289.7,14.9 310.3,18.0 331.0,11.8 351.7,21.2 372.4,14.9 393.1,18.0 413.8,24.3 434.5,14.9 455.2,11.8 475.9,18.0 496.6,14.9 517.2,18.0 537.9,21.2 558.6,14.9 579.3,18.0 600.0,18.0 600,70" fill="url(#g-4CAF50)"/>
                <path d="M 0.0,65.0 L 20.7,55.6 L 41.4,36.8 L 62.1,46.2 L 82.8,33.7 L 103.4,24.3 L 124.1,18.0 L 144.8,27.4 L 165.5,21.2 L 186.2,11.8 L 206.9,5.5 L 227.6,14.9 L 248.3,18.0 L 269.0,24.3 L 289.7,14.9 L 310.3,18.0 L 331.0,11.8 L 351.7,21.2 L 372.4,14.9 L 393.1,18.0 L 413.8,24.3 L 434.5,14.9 L 455.2,11.8 L 475.9,18.0 L 496.6,14.9 L 517.2,18.0 L 537.9,21.2 L 558.6,14.9 L 579.3,18.0 L 600.0,18.0" stroke="#4CAF50" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </div>

          <div className="panel" style={{ animationDelay: "0.15s" }}>
            <div className="panel-head">
              <div className="panel-title">
                <div className="panel-icon blue">📊</div>
                Registros · 30 dias
                <span className="tip" data-tip="Total de registros pedagógicos criados pela equipe nos últimos 30 dias. Soma de todas as modalidades.">i</span>
              </div>
              <span className="panel-trend up">↑ 24%</span>
            </div>
            <div className="panel-big-number">5.590</div>
            <div className="panel-sub">média de 32 registros/dia útil</div>
            <div className="sparkline-box">
              <svg viewBox="0 0 600 70" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
                <defs><linearGradient id="g-5C9CE6" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#5C9CE6" stopOpacity="0.25"/><stop offset="100%" stopColor="#5C9CE6" stopOpacity="0"/></linearGradient></defs>
                <polygon points="0,70 0.0,65.0 20.7,59.9 41.4,54.6 62.1,56.8 82.8,49.7 103.4,44.8 124.1,54.0 144.8,57.5 165.5,51.6 186.2,46.7 206.9,41.8 227.6,37.9 248.3,35.0 269.0,32.0 289.7,29.1 310.3,30.4 331.0,26.1 351.7,22.2 372.4,24.5 393.1,19.8 413.8,17.3 434.5,18.3 455.2,15.3 475.9,12.4 496.6,13.9 517.2,10.8 537.9,8.1 558.6,9.4 579.3,6.9 600.0,5.5 600,70" fill="url(#g-5C9CE6)"/>
                <path d="M 0.0,65.0 L 20.7,59.9 L 41.4,54.6 L 62.1,56.8 L 82.8,49.7 L 103.4,44.8 L 124.1,54.0 L 144.8,57.5 L 165.5,51.6 L 186.2,46.7 L 206.9,41.8 L 227.6,37.9 L 248.3,35.0 L 269.0,32.0 L 289.7,29.1 L 310.3,30.4 L 331.0,26.1 L 351.7,22.2 L 372.4,24.5 L 393.1,19.8 L 413.8,17.3 L 434.5,18.3 L 455.2,15.3 L 475.9,12.4 L 496.6,13.9 L 517.2,10.8 L 537.9,8.1 L 558.6,9.4 L 579.3,6.9 L 600.0,5.5" stroke="#5C9CE6" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </div>
        </div>

        {/* Sinais + Notas */}
        <div className="escola-grid">
          <div className="panel" style={{ animationDelay: "0.2s" }}>
            <div className="panel-head">
              <div className="panel-title"><div className="panel-icon amber">⚠️</div>Sinais de saúde</div>
            </div>
            <div>
              <div className="signal-item green"><div><div className="signal-title">✓ Coordenadora muito ativa</div><div className="signal-detail">Maria Letícia entra na plataforma em média 3.2x/dia</div></div></div>
              <div className="signal-item green"><div><div className="signal-title">✓ Tendência de uso crescente</div><div className="signal-detail">Token usage cresceu 18% nos últimos 30 dias</div></div></div>
              <div className="signal-item amber"><div><div className="signal-title">⚠ 2 professoras com baixo engajamento</div><div className="signal-detail">Geise Mayara · Gabriela Lima — sugerir treinamento</div></div></div>
              <div className="signal-item blue"><div><div className="signal-title">ℹ Aproximando da capacidade</div><div className="signal-detail">158 de 180 alunos contratados (88%) — possível upgrade</div></div></div>
            </div>
          </div>

          <div className="panel" style={{ animationDelay: "0.25s" }}>
            <div className="panel-head">
              <div className="panel-title"><div className="panel-icon purple">📝</div>Anotações &amp; follow-up</div>
              <button className="row-action-btn" onClick={openNotaModal} style={{ fontSize: "11px" }}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Nova nota
              </button>
            </div>
            <div>
              {notes.map((note) => (
                <div key={note.id} className={`note-item${note.id === newNoteId ? " new-note" : ""}`}>
                  <div className="note-date">{note.date}</div>
                  <div className="note-body">
                    <div className="note-author">{note.author}</div>
                    <div className="note-text">
                      {note.tag && <span className="note-tag-prefix">{tagEmojis[note.tag]} {tagLabels[note.tag]}: </span>}
                      {note.text}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Tabela de professoras */}
        <div className="users-panel" style={{ animationDelay: "0.3s" }}>
          <div className="users-panel-head">
            <div className="panel-title"><div className="panel-icon blue">👥</div>Equipe da escola · 9 pessoas</div>
            <div className="users-tabs">
              <button className="users-tab active">Professoras (8)</button>
              <button className="users-tab">Coordenadoras (1)</button>
            </div>
          </div>
          <table className="users-table">
            <thead>
              <tr>
                <th>Pessoa</th>
                <th>Turma</th>
                <th>Último acesso</th>
                <th>Registros / 30d</th>
                <th>Health</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {professors.map((p) => (
                <tr key={p.name} className="user-row">
                  <td>
                    <div className="user-cell">
                      <div className="user-avatar">{p.initials}</div>
                      <div>
                        <div className="user-name">{p.name}</div>
                        <div className="user-email">{p.email}</div>
                      </div>
                    </div>
                  </td>
                  <td><span className="turma-badge">{p.turma}</span></td>
                  <td><span className={`acesso-pill ${p.acessoClass}`}><span className="acesso-dot"></span>{p.acesso}</span></td>
                  <td className="num-cell">{p.registros}</td>
                  <td>
                    <div className="health-bar-mini"><div className="health-bar-fill" style={{ width: `${p.healthW}%`, background: p.healthColor }}></div></div>
                    <span className="health-num" style={{ color: p.healthColor }}>{p.health}</span>
                  </td>
                  <td>
                    <button className="row-action-btn" onClick={() => impersonateUser(p.name, "prof")}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
                      Entrar como
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Modal Nova Nota */}
        <div className={`nota-modal-overlay${notaModalOpen ? " open" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) closeNotaModal(); }}>
          <div className="nota-modal">
            <button className="nota-modal-close" onClick={closeNotaModal} aria-label="Fechar">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
            <div className="nota-modal-header">
              <div className="nota-modal-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              </div>
              <div>
                <div className="nota-modal-title">Nova anotação</div>
                <div className="nota-modal-subtitle">Centro Educacional Reluz · CRM</div>
              </div>
            </div>
            <div className="nota-form-group">
              <label className="nota-label">Tipo de anotação</label>
              <div className="nota-tag-row">
                {tagOptions.map((t) => (
                  <button key={t.key} className={`nota-tag${selectedTag === t.key ? " selected" : ""}`} onClick={() => setSelectedTag(t.key)}>{t.label}</button>
                ))}
              </div>
            </div>
            <div className="nota-form-group">
              <label className="nota-label" htmlFor="nota-text">Conteúdo da anotação</label>
              <textarea
                className={`nota-textarea${notaTextError ? " error" : ""}`}
                id="nota-text"
                ref={notaTextareaRef}
                value={notaText}
                onChange={(e) => setNotaText(e.target.value)}
                placeholder="Ex: Reunião com Maria Letícia sobre planejamento do 2º bimestre. Pediu ajuda para configurar relatórios automáticos..."
              />
            </div>
            <div className="nota-modal-footer">
              <button className="nota-btn-action" onClick={closeNotaModal}>Cancelar</button>
              <button className="nota-btn-action primary" onClick={saveNota}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 5 }}><polyline points="20 6 9 17 4 12"/></svg>
                Salvar anotação
              </button>
            </div>
          </div>
        </div>

        {/* Toast */}
        <div className={`toast${toast.show ? " show" : ""}`}>
          <div className="toast-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <span>{toast.text}</span>
        </div>

        {/* Modal Desativar */}
        <div className={`danger-modal-overlay${dangerModalOpen ? " open" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) closeDesativarModal(); }}>
          <div className="danger-modal">
            <div className="danger-modal-icon-large">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
            </div>
            <div className="danger-modal-title">Desativar {ESCOLA_NOME}?</div>
            <div className="danger-modal-subtitle">Esta ação bloqueia imediatamente o acesso de toda a equipe à plataforma.</div>
            <div className="danger-modal-warning">
              <div className="danger-warning-title">⚠ O que vai acontecer</div>
              <ul className="danger-warning-list">
                <li>Login bloqueado para 8 professoras e 1 coordenadora</li>
                <li>Sessões ativas serão encerradas no próximo refresh</li>
                <li>Cobrança recorrente será suspensa</li>
                <li>Dados ficam preservados (read-only no admin)</li>
                <li>A escola pode ser reativada a qualquer momento</li>
              </ul>
            </div>
            <label className="nota-label" htmlFor="danger-confirm">Para confirmar, digite o nome da escola:</label>
            <input
              type="text"
              className="danger-confirm-input"
              id="danger-confirm"
              ref={dangerInputRef}
              placeholder={ESCOLA_NOME}
              value={dangerConfirm}
              onChange={(e) => setDangerConfirm(e.target.value)}
            />
            <div className="danger-confirm-help">Digite exatamente <code>{ESCOLA_NOME}</code></div>
            <div className="danger-modal-footer">
              <button className="danger-btn" onClick={closeDesativarModal}>Cancelar</button>
              <button className="danger-btn confirm" disabled={dangerConfirm !== ESCOLA_NOME} onClick={confirmarDesativacao}>
                Desativar escola
              </button>
            </div>
          </div>
        </div>

      </div>
    </>
  );
}