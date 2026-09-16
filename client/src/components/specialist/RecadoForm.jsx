import React, { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';

const SUGESTOES = [
  'Antes da roda de conversa, fazer uma conversa rápida em dupla com o Vini sobre o tema — reduz a ansiedade de falar no grupo grande.',
  'Dar ao Vini um objeto tátil relacionado ao tema da roda — pode ser âncora para iniciar a fala espontânea.',
  'Avisar antes que será chamado na roda de conversa — a previsibilidade reduz a hesitação significativamente.',
];

/**
 * Formulário de recado/estratégia da especialista para a professora.
 * Componente puro — não navega sozinho. É embutido inline (sem modal)
 * tanto no fluxo de registro (depois de ver as ligações) quanto na aba
 * "Da escola" do perfil da criança.
 *
 * @param {() => void} [onEnviado] - chamado depois da confirmação de envio
 * @param {() => void} [onCancelar]
 */
export default function RecadoForm({ onEnviado, onCancelar }) {
  const { toast } = useToast();
  const [sugestaoAtiva, setSugestaoAtiva] = useState(null);
  const [texto, setTexto] = useState('');
  const [enviado, setEnviado] = useState(false);

  function usarSugestao(i) {
    setSugestaoAtiva(i);
    setTexto(SUGESTOES[i]);
  }

  function enviar() {
    toast({
      title: '🚧 Funcionalidade em construção!',
      description: 'O envio de recados para a professora ainda será implementado.',
    });
    setEnviado(true);
    setTimeout(() => onEnviado?.(), 1400);
  }

  if (enviado) {
    return (
      <div className="text-center py-8">
        <div className="w-14 h-14 rounded-full bg-[#E1F5EE] flex items-center justify-center mx-auto mb-3">
          <CheckCircle2 className="h-6 w-6 text-[#1D9E75]" />
        </div>
        <div className="text-base font-medium text-gray-800 mb-1">Recado enviado</div>
        <p className="text-xs text-gray-500">A professora Myrna receberá uma notificação agora</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-[#AFA9EC] bg-[#EEEDFE] p-3 text-xs text-[#3C3489] leading-relaxed flex gap-2">
        <CheckCircle2 className="h-4 w-4 flex-shrink-0 mt-0.5" />
        <span>A professora vê este recado no perfil da criança. <strong className="font-medium">A família não tem acesso.</strong></span>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-4 space-y-3">
          <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Sugestões da NARA</Label>
          <div className="space-y-1.5">
            {SUGESTOES.map((s, i) => (
              <button
                key={s}
                onClick={() => usarSugestao(i)}
                className={`w-full text-left text-xs leading-relaxed rounded-lg border px-3.5 py-2.5 transition-colors ${
                  sugestaoAtiva === i ? 'border-roxo-principal bg-[#EEEDFE] text-[#3C3489]' : 'border-gray-200 bg-[#F8F7FF] text-gray-600 hover:border-roxo-principal'
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <div className="pt-2">
            <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Seu recado</Label>
            <Textarea
              rows={4}
              placeholder="Escreva uma estratégia ou observação para a professora..."
              value={texto}
              onChange={(e) => { setTexto(e.target.value); setSugestaoAtiva(null); }}
              className="mt-1.5 text-sm bg-[#F8F7FF]"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
        {onCancelar && <Button variant="outline" className="order-2 sm:order-1 w-full sm:w-auto sm:px-8 rounded-xl" onClick={onCancelar}>Cancelar</Button>}
        <Button className="order-1 sm:order-2 w-full sm:w-auto sm:px-8 bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl" onClick={enviar}>Enviar para a professora</Button>
      </div>
    </div>
  );
}