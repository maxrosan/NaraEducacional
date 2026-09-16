import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

/**
 * Ligações inteligentes encontradas pela NARA depois de salvar um
 * registro por voz. Componente puro — "Enviar estratégia" abre o
 * RecadoForm inline (via onAbrirRecado), "Voltar ao perfil" navega de
 * verdade para outra página (via onVoltarPerfil).
 */
export default function RegistrationInsights({ onAbrirRecado, onVoltarPerfil }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-[#9FE1CB] bg-[#E1F5EE] p-4 text-center">
        <div className="flex items-center justify-center gap-1.5 text-[#085041] font-medium text-sm mb-1">
          <CheckCircle2 className="h-4 w-4" /> Registro salvo
        </div>
        <p className="text-xs text-[#0F6E56]">NARA cruzou com 8 registros da escola e 3 do bimestre</p>
      </div>

      <Card className="rounded-2xl border-[#AFA9EC] overflow-hidden">
        <div className="bg-[#EEEDFE] px-4 py-3 flex items-center gap-2">
          <span className="text-xs font-medium text-[#534AB7] flex-1">3 padrões identificados</span>
          <span className="text-[10px] font-medium bg-roxo-principal text-white px-2 py-0.5 rounded-full">IA</span>
        </div>
        <CardContent className="p-0 divide-y divide-gray-100">
          <div className="px-4 py-3.5">
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#FCEBEB] text-[#791F1F] inline-block mb-1.5">Padrão crítico</span>
            <div className="text-sm font-medium text-gray-800 mb-1">Hesitação verbal — 4 contextos confirmados</div>
            <p className="text-xs text-gray-600 leading-relaxed">
              A professora registrou hesitação verbal em 4 contextos não estruturados este mês. <strong className="text-gray-800 font-medium">Não é timidez situacional</strong> — o ambiente previsível é fator determinante.
            </p>
            <button onClick={onAbrirRecado} className="text-xs text-roxo-principal font-medium mt-1.5 inline-block">
              → Enviar estratégia para a professora
            </button>
          </div>
          <div className="px-4 py-3.5">
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#FAEEDA] text-[#633806] inline-block mb-1.5">Oportunidade</span>
            <div className="text-sm font-medium text-gray-800 mb-1">Interesse tátil como facilitador</div>
            <p className="text-xs text-gray-600 leading-relaxed">
              Engajamento tátil em <strong className="text-gray-800 font-medium">3 momentos com atenção acima de 10 min</strong>. Canal para atividades fonológicas com materiais texturizados.
            </p>
          </div>
          <div className="px-4 py-3.5">
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#E1F5EE] text-[#085041] inline-block mb-1.5">Marco</span>
            <div className="text-sm font-medium text-gray-800 mb-1">Primeira frase SVO — avanço consistente</div>
            <p className="text-xs text-gray-600 leading-relaxed">
              Frase SVO de hoje é a <strong className="text-gray-800 font-medium">primeira nos seus registros</strong>. Alinhado com avanço em vocabulário — base lexical sustentando a sintaxe.
            </p>
          </div>
        </CardContent>
      </Card>

      <Button className="bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl max-w-sm" onClick={onVoltarPerfil}>
        Voltar ao perfil
      </Button>
    </div>
  );
}