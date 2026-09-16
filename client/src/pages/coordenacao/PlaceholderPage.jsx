import React from 'react';

/* Placeholder temporário para telas da coordenação ainda em migração.
 * Vai sendo substituído tela a tela pelos componentes definitivos. */
export default function PlaceholderPage({ titulo = 'Em construção' }) {
  return (
    <main className="content">
      <div className="greeting">
        <h1 className="greeting-title">{titulo}</h1>
        <p className="greeting-sub">Esta tela está sendo migrada para o novo layout. Em breve.</p>
      </div>
      <div className="empty-hint" style={{ marginTop: 8 }}>
        Conteúdo desta seção será portado do mockup correspondente.
      </div>
    </main>
  );
}
