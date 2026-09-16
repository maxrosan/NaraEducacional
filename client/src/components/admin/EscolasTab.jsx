export default function EscolasTab({ onEscolaClick }) {
  function impersonate(escolaId, papel) {
    alert(
      'Impersonate: ' + papel + ' da escola ' + escolaId +
      '\n\nNa versão final, isso vai abrir a app principal da escola em modo admin. Por enquanto é só prototype navegacional.'
    );
  }

  function ativarEscola(escolaId) {
    if (
      confirm(
        'Reativar Escolinha Jardim Encantado?\n\nO login será restaurado para todas as professoras e coordenadoras. A escola voltará a aparecer como ativa.'
      )
    ) {
      alert(
        'Escola reativada (mock).\n\nNa versão final, login das 6 pessoas seria reabilitado e cobrança recorrente reestabelecida.'
      );
    }
  }

  return (
    <>
      <style>{`
        .escolas-tab { font-family: 'Poppins', -apple-system, sans-serif; font-size: 14px; line-height: 1.5; -webkit-font-smoothing: antialiased; }

        .escolas-tab .admin-header { margin-bottom: 28px; animation: et-fadeIn 0.5s ease-out; }
        .escolas-tab .admin-title { font-size: 28px; font-weight: 800; color: #1A1A2E; letter-spacing: -0.5px; margin-bottom: 4px; }
        .escolas-tab .admin-subtitle { font-size: 14px; color: #6B7280; }

        .escolas-tab .global-stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 28px; }
        .escolas-tab .global-stat { background: #FFFFFF; border-radius: 14px; padding: 16px 18px; border: 1px solid #F3F4F6; transition: all 0.18s; animation: et-fadeUp 0.5s ease-out backwards; }
        .escolas-tab .global-stat:hover { border-color: #EDE7F6; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(126,91,190,0.08); }
        .escolas-tab .gs-label { font-size: 10px; color: #6B7280; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 6px; display: flex; align-items: center; }
        .escolas-tab .gs-value { font-size: 22px; font-weight: 800; color: #1A1A2E; line-height: 1; letter-spacing: -0.5px; }
        .escolas-tab .gs-value small { font-size: 12px; color: #6B7280; font-weight: 600; margin-left: 2px; }
        .escolas-tab .gs-trend { font-size: 11px; font-weight: 600; margin-top: 6px; }
        .escolas-tab .gs-trend.up { color: #4CAF50; }
        .escolas-tab .gs-trend.down { color: #EF5350; }
        .escolas-tab .gs-trend.flat { color: #6B7280; }

        .escolas-tab .admin-filters { background: #FFFFFF; border-radius: 14px; padding: 14px 16px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 20px; border: 1px solid #F3F4F6; }
        .escolas-tab .admin-search { flex: 1; min-width: 240px; position: relative; }
        .escolas-tab .admin-search input { width: 100%; padding: 9px 14px 9px 36px; background: #F5F5F7; border: 1px solid #E5E7EB; border-radius: 10px; color: #1A1A2E; font-family: inherit; font-size: 13px; }
        .escolas-tab .admin-search input:focus { outline: none; border-color: #7E5BBE; background: white; }
        .escolas-tab .admin-search input::placeholder { color: #9CA3AF; }
        .escolas-tab .admin-search svg { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #9CA3AF; }
        .escolas-tab .filter-chip { padding: 7px 13px; border-radius: 99px; background: #F5F5F7; border: none; color: #6B7280; font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .escolas-tab .filter-chip:hover { background: #F5F0FB; color: #7E5BBE; }
        .escolas-tab .filter-chip.active { background: #EDE7F6; color: #7E5BBE; }

        .escolas-tab .schools-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 18px; }

        .escolas-tab .school-card { background: #FFFFFF; border: 1px solid #F3F4F6; border-radius: 18px; padding: 0; overflow: hidden; transition: all 0.2s; cursor: pointer; text-decoration: none; color: inherit; display: block; animation: et-fadeUp 0.5s ease-out backwards; }
        .escolas-tab .school-card:hover { border-color: #EDE7F6; transform: translateY(-3px); box-shadow: 0 12px 32px rgba(126,91,190,0.10); }
        .escolas-tab .school-card.school-risk { border-left: 4px solid #EF5350; }
        .escolas-tab .school-card.school-attention { border-left: 4px solid #FFA726; }
        .escolas-tab .school-card.school-good { border-left: 4px solid #5C9CE6; }
        .escolas-tab .school-card.school-great { border-left: 4px solid #4CAF50; }

        .escolas-tab .school-card-head { padding: 16px 20px 12px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #F3F4F6; }
        .escolas-tab .school-avatar { width: 44px; height: 44px; border-radius: 12px; background: linear-gradient(135deg, #EDE7F6, #A5D6A7); color: #4A3370; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 800; flex-shrink: 0; }
        .escolas-tab .school-info { flex: 1; min-width: 0; }
        .escolas-tab .school-name { font-size: 15px; font-weight: 700; color: #1A1A2E; line-height: 1.2; }
        .escolas-tab .school-meta { font-size: 11px; color: #6B7280; margin-top: 3px; }
        .escolas-tab .health-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 99px; font-size: 11px; font-weight: 700; flex-shrink: 0; }
        .escolas-tab .health-dot { width: 6px; height: 6px; border-radius: 50%; animation: et-pulse 2.5s infinite; }

        .escolas-tab .school-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 14px 20px; background: #FAFAFB; border-bottom: 1px solid #F3F4F6; }
        .escolas-tab .stat-item { text-align: center; }
        .escolas-tab .stat-label { font-size: 9.5px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; margin-bottom: 4px; }
        .escolas-tab .stat-value { font-size: 20px; font-weight: 800; color: #1A1A2E; letter-spacing: -0.3px; line-height: 1; }
        .escolas-tab .stat-value small { font-size: 10px; color: #6B7280; font-weight: 600; margin-left: 1px; }

        .escolas-tab .school-bars { padding: 14px 20px; border-bottom: 1px solid #F3F4F6; }
        .escolas-tab .bar-row { margin-bottom: 12px; }
        .escolas-tab .bar-row:last-child { margin-bottom: 0; }
        .escolas-tab .bar-row-label { display: flex; justify-content: space-between; font-size: 11px; color: #6B7280; font-weight: 500; margin-bottom: 4px; }
        .escolas-tab .bar-row-value { font-weight: 700; color: #1A1A2E; }
        .escolas-tab .bar-row-value.bar-good { color: #4CAF50; }
        .escolas-tab .bar-row-value.bar-warn { color: #FFA726; }
        .escolas-tab .bar-row-value.bar-crit { color: #EF5350; }
        .escolas-tab .bar-track { height: 6px; background: #F5F5F7; border-radius: 99px; overflow: hidden; }
        .escolas-tab .bar-fill { height: 100%; border-radius: 99px; transition: width 0.8s cubic-bezier(0.16,1,0.3,1); }
        .escolas-tab .bar-fill-good { background: #4CAF50; }
        .escolas-tab .bar-fill-warn { background: #FFA726; }
        .escolas-tab .bar-fill-crit { background: #EF5350; }

        .escolas-tab .school-footer { padding: 12px 20px; background: #FAFAFB; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
        .escolas-tab .footer-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 11px; color: #6B7280; }
        .escolas-tab .footer-info strong { color: #1A1A2E; font-weight: 700; }
        .escolas-tab .footer-item { display: inline-flex; align-items: center; gap: 4px; }
        .escolas-tab .footer-access { display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 700; }
        .escolas-tab .footer-access.access-recent { background: #E8F5E9; color: #4CAF50; }
        .escolas-tab .footer-access.access-late { background: #FFEBEE; color: #EF5350; }
        .escolas-tab .access-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; animation: et-pulse 2.5s infinite; }
        .escolas-tab .footer-actions { display: flex; gap: 6px; }
        .escolas-tab .impersonate-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 11px; border-radius: 8px; border: 1px solid #E5E7EB; background: #FFFFFF; color: #2F2F42; font-size: 11px; font-weight: 700; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .escolas-tab .impersonate-btn:hover { background: #EDE7F6; border-color: #7E5BBE; color: #7E5BBE; }

        .escolas-tab .tip { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; border-radius: 50%; border: 1.5px solid #9CA3AF; color: #9CA3AF; font-size: 9px; font-weight: 700; cursor: help; position: relative; margin-left: 6px; background: transparent; line-height: 1; vertical-align: middle; }
        .escolas-tab .tip:hover { border-color: #7E5BBE; color: #7E5BBE; background: #F5F0FB; }
        .escolas-tab .tip::before { content: attr(data-tip); position: absolute; bottom: calc(100% + 10px); left: 50%; transform: translateX(-50%) translateY(6px); background: #1A1A2E; color: white; padding: 10px 12px; border-radius: 8px; font-size: 11px; font-weight: 400; line-height: 1.5; width: max-content; max-width: 260px; white-space: normal; text-align: left; opacity: 0; visibility: hidden; pointer-events: none; transition: all 0.18s; z-index: 100; box-shadow: 0 12px 32px rgba(0,0,0,0.2); }
        .escolas-tab .tip:hover::before { opacity: 1; visibility: visible; transform: translateX(-50%) translateY(0); }

        .escolas-tab .school-card.school-inactive { border-left: 4px solid #9CA3AF; opacity: 0.85; background: #FAFAFB; position: relative; }
        .escolas-tab .school-card.school-inactive:hover { opacity: 1; }
        .escolas-tab .inactive-banner { background: #6B7280; color: white; padding: 7px 16px; font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 7px; }
        .escolas-tab .inactive-banner strong { font-weight: 800; }

        @keyframes et-fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes et-fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes et-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        @media (max-width: 1100px) {
          .escolas-tab .global-stats { grid-template-columns: repeat(3, 1fr); }
          .escolas-tab .schools-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 600px) {
          .escolas-tab .global-stats { grid-template-columns: repeat(2, 1fr); }
          .escolas-tab .school-stats { grid-template-columns: 1fr 1fr; }
        }
      `}</style>

      <div className="escolas-tab">
        <div className="admin-header">
          <h1 className="admin-title">Escolas contratantes</h1>
          <div className="admin-subtitle">Visão completa das 6 escolas ativas no momento</div>
        </div>

        <div className="global-stats">
          <div className="global-stat" style={{ animationDelay: '0.05s' }}>
            <div className="gs-label">Escolas ativas</div>
            <div className="gs-value">6</div>
            <div className="gs-trend up">↑ 2 nos últimos 30 dias</div>
          </div>
          <div className="global-stat" style={{ animationDelay: '0.08s' }}>
            <div className="gs-label">Alunos totais</div>
            <div className="gs-value">672</div>
            <div className="gs-trend up">↑ 18% vs mês anterior</div>
          </div>
          <div className="global-stat" style={{ animationDelay: '0.11s' }}>
            <div className="gs-label">Professoras</div>
            <div className="gs-value">50</div>
            <div className="gs-trend flat">= sem mudança</div>
          </div>
          <div className="global-stat" style={{ animationDelay: '0.14s' }}>
            <div className="gs-label">Registros / mês</div>
            <div className="gs-value">22.921</div>
            <div className="gs-trend up">↑ 24%</div>
          </div>
          <div className="global-stat" style={{ animationDelay: '0.17s' }}>
            <div className="gs-label">
              Tokens consumidos
              <span className="tip" data-tip="Total de tokens de IA usados pelas escolas no mês corrente. INPUT: cada interação com modelos (geração de relatório, análise de hipótese, classificação de fase) consome tokens. Custo direto de operação.">i</span>
            </div>
            <div className="gs-value">645<small>k</small></div>
            <div className="gs-trend up">↑ 31%</div>
          </div>
          <div className="global-stat" style={{ animationDelay: '0.2s' }}>
            <div className="gs-label">
              Em risco
              <span className="tip" data-tip="Escolas com Health Score abaixo de 40. CÁLCULO: indicador composto que mistura engajamento, regularidade, atividade da equipe e crianças sem registro.">i</span>
            </div>
            <div className="gs-value" style={{ color: '#EF5350' }}>1</div>
            <div className="gs-trend down">↑ 1 este mês</div>
          </div>
        </div>

        <div className="admin-filters">
          <div className="admin-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
            <input type="text" placeholder="Buscar escola, cidade, contato..." />
          </div>
          <button className="filter-chip active">Todas (6)</button>
          <button className="filter-chip">Saudáveis (3)</button>
          <button className="filter-chip">Atenção</button>
          <button className="filter-chip">Em risco (1)</button>
          <button className="filter-chip">Onboarding</button>
          <button className="filter-chip">Inativas (1)</button>
        </div>

        <div className="schools-grid">

          {/* Centro Educacional Reluz */}
          <div className="school-card school-great" onClick={onEscolaClick} style={{ cursor: "pointer" }}>
            <div className="school-card-head">
              <div className="school-avatar">CR</div>
              <div className="school-info">
                <div className="school-name">Centro Educacional Reluz</div>
                <div className="school-meta">Currais Novos · RN · cliente desde Jan/2026</div>
              </div>
              <span className="health-pill" style={{ background: '#E8F5E9', color: '#4CAF50' }}>
                <span className="health-dot" style={{ background: '#4CAF50' }}></span>
                Saudável
              </span>
            </div>
            <div className="school-stats">
              <div className="stat-item"><div className="stat-label">Health Score</div><div className="stat-value" style={{ color: '#4CAF50' }}>92<small>/100</small></div></div>
              <div className="stat-item"><div className="stat-label">Engajamento</div><div className="stat-value" style={{ color: '#4CAF50' }}>87<small>%</small></div></div>
              <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value">158<small>/180</small></div></div>
            </div>
            <div className="school-bars">
              <div className="bar-row">
                <div className="bar-row-label"><span>📦 Ocupação de plano</span><span className="bar-row-value">88%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '88%', background: '#7E5BBE' }}></div></div>
              </div>
              <div className="bar-row">
                <div className="bar-row-label"><span>🤖 Tokens IA · 142k de 250k</span><span className="bar-row-value bar-good">57%</span></div>
                <div className="bar-track"><div className="bar-fill bar-fill-good" style={{ width: '57%' }}></div></div>
              </div>
            </div>
            <div className="school-footer">
              <div className="footer-info">
                <span className="footer-item"><strong>8</strong> prof.</span>
                <span className="footer-item"><strong>1</strong> coord.</span>
                <span className="footer-item"><strong>5.590</strong> reg./mês</span>
                <span className="footer-access access-recent"><span className="access-dot"></span>agora há pouco</span>
              </div>
              <div className="footer-actions">
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-001','coord'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Coord.
                </button>
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-001','prof'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
                  Prof.
                </button>
              </div>
            </div>
          </div>

          {/* Colégio Pequeno Mundo */}
          <div className="school-card school-great" onClick={onEscolaClick} style={{ cursor: "pointer" }}>
            <div className="school-card-head">
              <div className="school-avatar">PM</div>
              <div className="school-info">
                <div className="school-name">Colégio Pequeno Mundo</div>
                <div className="school-meta">Natal · RN · cliente desde Jan/2026</div>
              </div>
              <span className="health-pill" style={{ background: '#E8F5E9', color: '#4CAF50' }}>
                <span className="health-dot" style={{ background: '#4CAF50' }}></span>
                Saudável
              </span>
            </div>
            <div className="school-stats">
              <div className="stat-item"><div className="stat-label">Health Score</div><div className="stat-value" style={{ color: '#4CAF50' }}>95<small>/100</small></div></div>
              <div className="stat-item"><div className="stat-label">Engajamento</div><div className="stat-value" style={{ color: '#4CAF50' }}>92<small>%</small></div></div>
              <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value">142<small>/150</small></div></div>
            </div>
            <div className="school-bars">
              <div className="bar-row">
                <div className="bar-row-label"><span>📦 Ocupação de plano</span><span className="bar-row-value">95%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '95%', background: '#7E5BBE' }}></div></div>
              </div>
              <div className="bar-row">
                <div className="bar-row-label"><span>🤖 Tokens IA · 178k de 250k</span><span className="bar-row-value bar-warn">71%</span></div>
                <div className="bar-track"><div className="bar-fill bar-fill-warn" style={{ width: '71%' }}></div></div>
              </div>
            </div>
            <div className="school-footer">
              <div className="footer-info">
                <span className="footer-item"><strong>11</strong> prof.</span>
                <span className="footer-item"><strong>2</strong> coord.</span>
                <span className="footer-item"><strong>6.840</strong> reg./mês</span>
                <span className="footer-access access-recent"><span className="access-dot"></span>há 2 horas</span>
              </div>
              <div className="footer-actions">
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-002','coord'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Coord.
                </button>
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-002','prof'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
                  Prof.
                </button>
              </div>
            </div>
          </div>

          {/* Escola Casa da Brincadeira */}
          <div className="school-card school-good" onClick={onEscolaClick} style={{ cursor: "pointer" }}>
            <div className="school-card-head">
              <div className="school-avatar">CB</div>
              <div className="school-info">
                <div className="school-name">Escola Casa da Brincadeira</div>
                <div className="school-meta">Currais Novos · RN · cliente desde Fev/2026</div>
              </div>
              <span className="health-pill" style={{ background: '#E3F2FD', color: '#5C9CE6' }}>
                <span className="health-dot" style={{ background: '#5C9CE6' }}></span>
                Ativa
              </span>
            </div>
            <div className="school-stats">
              <div className="stat-item"><div className="stat-label">Health Score</div><div className="stat-value" style={{ color: '#5C9CE6' }}>71<small>/100</small></div></div>
              <div className="stat-item"><div className="stat-label">Engajamento</div><div className="stat-value" style={{ color: '#FFA726' }}>64<small>%</small></div></div>
              <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value">82<small>/100</small></div></div>
            </div>
            <div className="school-bars">
              <div className="bar-row">
                <div className="bar-row-label"><span>📦 Ocupação de plano</span><span className="bar-row-value">82%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '82%', background: '#7E5BBE' }}></div></div>
              </div>
              <div className="bar-row">
                <div className="bar-row-label"><span>🤖 Tokens IA · 88k de 150k</span><span className="bar-row-value bar-good">59%</span></div>
                <div className="bar-track"><div className="bar-fill bar-fill-good" style={{ width: '59%' }}></div></div>
              </div>
            </div>
            <div className="school-footer">
              <div className="footer-info">
                <span className="footer-item"><strong>6</strong> prof.</span>
                <span className="footer-item"><strong>1</strong> coord.</span>
                <span className="footer-item"><strong>2.140</strong> reg./mês</span>
                <span className="footer-access access-recent"><span className="access-dot"></span>há 1 dia</span>
              </div>
              <div className="footer-actions">
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-003','coord'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Coord.
                </button>
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-003','prof'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
                  Prof.
                </button>
              </div>
            </div>
          </div>

          {/* Centro Pedagógico Girassol */}
          <div className="school-card school-great" onClick={onEscolaClick} style={{ cursor: "pointer" }}>
            <div className="school-card-head">
              <div className="school-avatar">CG</div>
              <div className="school-info">
                <div className="school-name">Centro Pedagógico Girassol</div>
                <div className="school-meta">Caicó · RN · cliente desde Jan/2026</div>
              </div>
              <span className="health-pill" style={{ background: '#E8F5E9', color: '#4CAF50' }}>
                <span className="health-dot" style={{ background: '#4CAF50' }}></span>
                Saudável
              </span>
            </div>
            <div className="school-stats">
              <div className="stat-item"><div className="stat-label">Health Score</div><div className="stat-value" style={{ color: '#4CAF50' }}>86<small>/100</small></div></div>
              <div className="stat-item"><div className="stat-label">Engajamento</div><div className="stat-value" style={{ color: '#4CAF50' }}>81<small>%</small></div></div>
              <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value">198<small>/220</small></div></div>
            </div>
            <div className="school-bars">
              <div className="bar-row">
                <div className="bar-row-label"><span>📦 Ocupação de plano</span><span className="bar-row-value">90%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '90%', background: '#7E5BBE' }}></div></div>
              </div>
              <div className="bar-row">
                <div className="bar-row-label"><span>🤖 Tokens IA · 216k de 350k</span><span className="bar-row-value bar-warn">62%</span></div>
                <div className="bar-track"><div className="bar-fill bar-fill-warn" style={{ width: '62%' }}></div></div>
              </div>
            </div>
            <div className="school-footer">
              <div className="footer-info">
                <span className="footer-item"><strong>16</strong> prof.</span>
                <span className="footer-item"><strong>2</strong> coord.</span>
                <span className="footer-item"><strong>8.120</strong> reg./mês</span>
                <span className="footer-access access-recent"><span className="access-dot"></span>há 4 horas</span>
              </div>
              <div className="footer-actions">
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-004','coord'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Coord.
                </button>
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-004','prof'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
                  Prof.
                </button>
              </div>
            </div>
          </div>

          {/* Escolinha Mãos Que Educam */}
          <div className="school-card school-attention" onClick={onEscolaClick} style={{ cursor: "pointer" }}>
            <div className="school-card-head">
              <div className="school-avatar">ME</div>
              <div className="school-info">
                <div className="school-name">Escolinha Mãos Que Educam</div>
                <div className="school-meta">Mossoró · RN · cliente desde Abr/2026</div>
              </div>
              <span className="health-pill" style={{ background: '#FFF3E0', color: '#FFA726' }}>
                <span className="health-dot" style={{ background: '#FFA726' }}></span>
                Em onboarding
              </span>
            </div>
            <div className="school-stats">
              <div className="stat-item"><div className="stat-label">Health Score</div><div className="stat-value" style={{ color: '#FFA726' }}>48<small>/100</small></div></div>
              <div className="stat-item"><div className="stat-label">Engajamento</div><div className="stat-value" style={{ color: '#EF5350' }}>38<small>%</small></div></div>
              <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value">24<small>/60</small></div></div>
            </div>
            <div className="school-bars">
              <div className="bar-row">
                <div className="bar-row-label"><span>📦 Ocupação de plano</span><span className="bar-row-value">40%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '40%', background: '#7E5BBE' }}></div></div>
              </div>
              <div className="bar-row">
                <div className="bar-row-label"><span>🤖 Tokens IA · 12k de 100k</span><span className="bar-row-value bar-good">12%</span></div>
                <div className="bar-track"><div className="bar-fill bar-fill-good" style={{ width: '12%' }}></div></div>
              </div>
            </div>
            <div className="school-footer">
              <div className="footer-info">
                <span className="footer-item"><strong>3</strong> prof.</span>
                <span className="footer-item"><strong>1</strong> coord.</span>
                <span className="footer-item"><strong>142</strong> reg./mês</span>
                <span className="footer-access access-recent"><span className="access-dot"></span>há 6 horas</span>
              </div>
              <div className="footer-actions">
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-005','coord'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Coord.
                </button>
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-005','prof'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
                  Prof.
                </button>
              </div>
            </div>
          </div>

          {/* Colégio Sementinha */}
          <div className="school-card school-risk" onClick={onEscolaClick} style={{ cursor: "pointer" }}>
            <div className="school-card-head">
              <div className="school-avatar">CS</div>
              <div className="school-info">
                <div className="school-name">Colégio Sementinha</div>
                <div className="school-meta">Parnamirim · RN · cliente desde Mar/2026</div>
              </div>
              <span className="health-pill" style={{ background: '#FFEBEE', color: '#EF5350' }}>
                <span className="health-dot" style={{ background: '#EF5350' }}></span>
                Em risco
              </span>
            </div>
            <div className="school-stats">
              <div className="stat-item"><div className="stat-label">Health Score</div><div className="stat-value" style={{ color: '#EF5350' }}>28<small>/100</small></div></div>
              <div className="stat-item"><div className="stat-label">Engajamento</div><div className="stat-value" style={{ color: '#EF5350' }}>22<small>%</small></div></div>
              <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value">68<small>/120</small></div></div>
            </div>
            <div className="school-bars">
              <div className="bar-row">
                <div className="bar-row-label"><span>📦 Ocupação de plano</span><span className="bar-row-value">57%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '57%', background: '#7E5BBE' }}></div></div>
              </div>
              <div className="bar-row">
                <div className="bar-row-label"><span>🤖 Tokens IA · 8k de 200k</span><span className="bar-row-value bar-good">4%</span></div>
                <div className="bar-track"><div className="bar-fill bar-fill-good" style={{ width: '4%' }}></div></div>
              </div>
            </div>
            <div className="school-footer">
              <div className="footer-info">
                <span className="footer-item"><strong>6</strong> prof.</span>
                <span className="footer-item"><strong>1</strong> coord.</span>
                <span className="footer-item"><strong>89</strong> reg./mês</span>
                <span className="footer-access access-late"><span className="access-dot"></span>há 11 dias</span>
              </div>
              <div className="footer-actions">
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-006','coord'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Coord.
                </button>
                <button className="impersonate-btn" onClick={(e) => { e.preventDefault(); e.stopPropagation(); impersonate('esc-006','prof'); }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
                  Prof.
                </button>
              </div>
            </div>
          </div>

          {/* Escolinha Jardim Encantado — Inativa */}
          <div className="school-card school-inactive">
            <div className="inactive-banner">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
              <span><strong>Inativa</strong> desde 18/02/2026 · login bloqueado</span>
            </div>
            <div className="school-card-head">
              <div className="school-avatar" style={{ filter: 'grayscale(1) opacity(0.6)' }}>EJ</div>
              <div className="school-info">
                <div className="school-name">Escolinha Jardim Encantado</div>
                <div className="school-meta">São Gonçalo do Amarante · RN · cliente desde Out/2025</div>
              </div>
              <span className="health-pill" style={{ background: '#E5E7EB', color: '#6B7280' }}>
                <span className="health-dot" style={{ background: '#6B7280', animation: 'none' }}></span>
                Inativa
              </span>
            </div>
            <div className="school-stats">
              <div className="stat-item"><div className="stat-label">Health Score</div><div className="stat-value" style={{ color: '#9CA3AF' }}>—</div></div>
              <div className="stat-item"><div className="stat-label">Engajamento</div><div className="stat-value" style={{ color: '#9CA3AF' }}>—</div></div>
              <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value" style={{ color: '#9CA3AF' }}>0<small>/80</small></div></div>
            </div>
            <div className="school-bars">
              <div className="bar-row">
                <div className="bar-row-label"><span style={{ opacity: 0.6 }}>📦 Ocupação de plano</span><span className="bar-row-value" style={{ opacity: 0.6 }}>0%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '0%', background: '#E5E7EB' }}></div></div>
              </div>
              <div className="bar-row">
                <div className="bar-row-label"><span style={{ opacity: 0.6 }}>🤖 Tokens IA · 0k de 100k</span><span className="bar-row-value" style={{ opacity: 0.6 }}>0%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: '0%', background: '#E5E7EB' }}></div></div>
              </div>
            </div>
            <div className="school-footer">
              <div className="footer-info" style={{ opacity: 0.7 }}>
                <span className="footer-item"><strong>5</strong> prof.</span>
                <span className="footer-item"><strong>1</strong> coord.</span>
                <span className="footer-item">desativada</span>
                <span className="footer-access" style={{ background: '#E5E7EB', color: '#6B7280' }}>
                  <span className="access-dot" style={{ animation: 'none' }}></span>
                  há 67 dias
                </span>
              </div>
              <div className="footer-actions">
                <button className="impersonate-btn" disabled style={{ opacity: 0.5, cursor: 'not-allowed' }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  Bloqueada
                </button>
                <button
                  className="impersonate-btn"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); ativarEscola('esc-007'); }}
                  style={{ borderColor: '#4CAF50', color: '#4CAF50' }}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="9 12 12 15 16 9"/></svg>
                  Reativar
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}