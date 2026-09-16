import { useState } from 'react';
import EscolasTab from './EscolasTab';
import EscolaDetalhe from './EscolaDetalhe';

export default function EscolasSection() {
  const [view, setView] = useState('lista'); // 'lista' | 'detalhe'

  if (view === 'detalhe') {
    return <EscolaDetalhe onVoltar={() => setView('lista')} />;
  }

  return <EscolasTab onEscolaClick={() => setView('detalhe')} />;
}