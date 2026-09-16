import React from 'react';
import { Link } from 'react-router-dom';
import { Mic, PenLine, ClipboardList } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

/**
 * Passo "como quer registrar" dentro do SpecialistRegistrationPage.
 * Voz/Texto trocam o passo local (sem navegação); PAEE navega de
 * verdade, porque é outro destino/fluxo (wizard próprio).
 *
 * Este componente só é alcançado a partir do perfil de uma criança
 * específica (botão "+" em SpecialistChildProfilePage) — por isso
 * `criancaId` sempre vem preenchido aqui, e o link do PAEE usa a rota
 * específica dessa criança.
 *
 * Estilização espelha o card "O que quer fazer agora?" da home
 * (SpecialistHomePage): fundo roxo, opções em branco translúcido.
 */
export default function RegistrationChoice({ criancaId, onEscolherVoz, onEscolherTexto }) {
  return (
    <Card className="bg-roxo-principal border-none rounded-2xl overflow-hidden">
      <CardContent className="p-5">
        <p className="text-sm font-medium text-white/80 mb-3">Como você quer registrar?</p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <button
            onClick={onEscolherVoz}
            className="rounded-xl bg-white/15 hover:bg-white/25 border border-white/20 transition-colors p-3 text-center"
          >
            <Mic className="h-6 w-6 mx-auto mb-1 text-white" />
            <div className="text-xs font-medium text-white mb-0.5">Por voz</div>
            <div className="text-[10px] text-white/65">IA transcreve e interpreta</div>
          </button>

          <button
            onClick={onEscolherTexto}
            className="rounded-xl bg-white/15 hover:bg-white/25 border border-white/20 transition-colors p-3 text-center"
          >
            <PenLine className="h-6 w-6 mx-auto mb-1 text-white" />
            <div className="text-xs font-medium text-white mb-0.5">Digitando</div>
            <div className="text-[10px] text-white/65">Escreva a observação</div>
          </button>

          <Link
            to={`/especialistas/crianca/${criancaId}/paee/criar`}
            className="rounded-xl bg-white/15 hover:bg-white/25 border border-white/20 transition-colors p-3 text-center"
          >
            <ClipboardList className="h-6 w-6 mx-auto mb-1 text-white" />
            <div className="text-xs font-medium text-white mb-0.5">Criar PAEE</div>
            <div className="text-[10px] text-white/65">IA gera as metas</div>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}