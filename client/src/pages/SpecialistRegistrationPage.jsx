import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useEspecialistaLogado } from '@/hooks/useEspecialistaLogado';
import { capitalizarPalavras } from '@/lib/textFormat';
import SpecialistNavbar from '@/components/specialist/SpecialistNavbar';
import RegistrationChoice from '@/components/specialist/RegistrationChoice';
import VoiceRegistrationForm from '@/components/specialist/VoiceRegistrationForm';
import TextRegistrationForm from '@/components/specialist/TextRegistrationForm';
import RegistrationInsights from '@/components/specialist/RegistrationInsights';
import RecadoForm from '@/components/specialist/RecadoForm';
// TODO: confirme o nome real do helper de fetch autenticado usado no projeto
import { authFetch } from '@/services/api';

/**
 * Página única que concentra todo o fluxo de registro do especialista:
 * escolha do tipo → voz OU texto → ligações da IA → (opcional) recado.
 *
 * Usa o SpecialistNavbar padrão (fixo) — o "voltar" e o título do passo
 * atual vivem dentro do próprio conteúdo da página, não num header
 * compartilhado à parte. O botão de voltar aqui é "inteligente": sabe
 * se deve trocar de passo (dentro desta mesma página) ou navegar de
 * verdade para o perfil da criança, dependendo do passo atual.
 *
 * Nome da criança e especialidade agora vêm de dados reais
 * (GET /api/criancas/{criancaId}/) em vez de "Vini Natan" fixo.
 *
 * Rota: /especialistas/crianca/:criancaId/registrar
 * Pode receber `location.state = { step: 'voz' }` para abrir direto
 * num passo específico (ex: o botão "Atualizar" de uma meta do PAEE).
 */
export default function SpecialistRegistrationPage() {
  const { criancaId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { especialista } = useEspecialistaLogado();
  const [step, setStep] = useState(location.state?.step || 'escolha');
  // Se a página abriu direto num passo (ex: card "Por voz" da home, que
  // pula a tela de escolha), guardamos isso pra saber que "voltar" deve
  // sair da página de verdade, não tentar mostrar uma tela que o
  // usuário nunca viu.
  const [entradaDireta] = useState(Boolean(location.state?.step));

  const [nomeCrianca, setNomeCrianca] = useState('');
  // Só relevante no passo 'texto': o aluno é escolhido dentro do próprio
  // formulário via select (não vem do criancaId da URL, que aqui é só um
  // placeholder para permitir abrir a tela sem uma criança pré-definida).
  const [alunoSelecionadoTexto, setAlunoSelecionadoTexto] = useState(null);
  // Idem para o passo 'voz'.
  const [alunoSelecionadoVoz, setAlunoSelecionadoVoz] = useState(null);

  useEffect(() => {
    if (!criancaId) return;

    let cancelado = false;

    authFetch(`/api/criancas/${criancaId}/`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar dados da criança');
        return res.json();
      })
      .then((data) => {
        if (!cancelado) setNomeCrianca(data.nome_completo || '');
      })
      .catch((err) => {
        console.error(err);
      });

    return () => {
      cancelado = true;
    };
  }, [criancaId]);

  const especialidade = especialista?.tipo_especialista
    ? capitalizarPalavras(especialista.tipo_especialista)
    : 'Fonoaudiologia';
  const nomeExibido = nomeCrianca || 'Carregando…';

  const TITULOS = {
    escolha: { title: 'Novo registro', subtitle: `${nomeExibido} · ${especialidade}` },
    voz: {
      title: 'Registro por voz',
      subtitle: alunoSelecionadoVoz ? `${alunoSelecionadoVoz.nome_completo} · hoje` : 'Selecione o aluno · hoje',
    },
    texto: {
      title: 'Registro da sessão',
      subtitle: alunoSelecionadoTexto ? `${alunoSelecionadoTexto.nome_completo} · hoje` : 'Selecione o aluno · hoje',
    },
    insights: { title: 'Ligações encontradas', subtitle: `${nomeExibido} · registro de hoje` },
    recado: { title: 'Recado para a professora', subtitle: `${nomeExibido} · estratégia terapêutica` },
  };

  function voltar() {
    if (step === 'voz' || step === 'texto') {
      return entradaDireta ? navigate(-1) : setStep('escolha');
    }
    if (step === 'recado') return setStep('insights');
    // 'escolha' e 'insights' voltam pra página anterior de verdade (histórico do navegador)
    navigate(-1);
  }

  const { title, subtitle } = TITULOS[step];

  return (
    <>
      <Helmet><title>NARA - {title}</title></Helmet>
      <div className="bg-[#F5F3FA] min-h-screen">
        <SpecialistNavbar />

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Voltar + título do passo atual — sempre na largura total do container */}
          <div className="flex items-center gap-3 mb-4">
            <Button variant="ghost" size="icon" onClick={voltar}>
              <ArrowLeft className="h-5 w-5 text-gray-600" />
            </Button>
            <div className="min-w-0">
              <h1 className="text-lg font-semibold text-gray-800 truncate">{title}</h1>
              <p className="text-xs text-gray-500 truncate">{subtitle}</p>
            </div>
          </div>

          {/* Conteúdo do passo — largura própria, não afeta a posição do voltar acima */}
          <div className="max-w-2xl lg:max-w-5xl mx-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.2 }}
            >
              {step === 'escolha' && (
                <RegistrationChoice
                  criancaId={criancaId}
                  onEscolherVoz={() => setStep('voz')}
                  onEscolherTexto={() => setStep('texto')}
                />
              )}

              {step === 'voz' && (
                <VoiceRegistrationForm onSalvar={() => setStep('insights')} onAlunoSelecionado={setAlunoSelecionadoVoz} />
              )}

              {step === 'texto' && (
                <TextRegistrationForm
                  onSalvar={() => navigate(-1)}
                  onCancelar={() => (entradaDireta ? navigate(-1) : setStep('escolha'))}
                  onAlunoSelecionado={setAlunoSelecionadoTexto}
                />
              )}

              {step === 'insights' && (
                <RegistrationInsights
                  onAbrirRecado={() => setStep('recado')}
                  onVoltarPerfil={() => navigate(-1)}
                />
              )}

              {step === 'recado' && (
                <RecadoForm
                  onEnviado={() => navigate(-1)}
                  onCancelar={() => setStep('insights')}
                />
              )}
            </motion.div>
          </AnimatePresence>
          </div>
        </main>
      </div>
    </>
  );
}