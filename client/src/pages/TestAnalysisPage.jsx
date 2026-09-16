import React from 'react';
import ProductionAnalysisBlock from '@/components/report/ProductionAnalysisBlock';

function TestAnalysisPage() {
  return (
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Teste Análise de Produções</h1>
      
      <div>
        <h2 className="text-lg font-semibold mb-4">Teste 1: Nome exato</h2>
        <ProductionAnalysisBlock nomeAluno="Ana Cecilia de Medeiros Nobre da Silva" />
      </div>
      
      <div>
        <h2 className="text-lg font-semibold mb-4">Teste 2: Nome parcial</h2>
        <ProductionAnalysisBlock nomeAluno="Ana Cecilia" />
      </div>
      
      <div>
        <h2 className="text-lg font-semibold mb-4">Teste 3: Maria Isabela</h2>
        <ProductionAnalysisBlock nomeAluno="Maria Isabela Melo Monteiro do Nascimento" />
      </div>
    </div>
  );
}

export default TestAnalysisPage;
