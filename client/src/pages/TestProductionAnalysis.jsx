import React from 'react';
import ProductionAnalysisBlock from '@/components/report/ProductionAnalysisBlock';

function TestProductionAnalysis() {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Teste - Análise de Produções</h1>
      
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-4">Teste com Ana Cecilia</h2>
          <ProductionAnalysisBlock nomeAluno="Ana Cecilia de Medeiros Nobre da Silva" />
        </div>
        
        <div>
          <h2 className="text-lg font-semibold mb-4">Teste com nome parcial</h2>
          <ProductionAnalysisBlock nomeAluno="Ana Cecilia" />
        </div>
        
        <div>
          <h2 className="text-lg font-semibold mb-4">Teste com nome inexistente</h2>
          <ProductionAnalysisBlock nomeAluno="Nome Inexistente" />
        </div>
      </div>
    </div>
  );
}

export default TestProductionAnalysis;
