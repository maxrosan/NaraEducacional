import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, Key, Download } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/apiClient';
import { usePwaInstall } from '@/hooks/usePwaInstall';
import NotificationsBell from '@/components/notifications/NotificationsBell';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import ChangePasswordModal from '@/components/auth/ChangePasswordModal';
import { toast } from '@/components/ui/use-toast';

function abreviarBimestre(texto) {
  if (!texto) return '';
  const match = texto.match(/(\d+º?)\s*([A-Za-zÀ-ÿ])/);
  if (match) {
    return `${match[1]} ${match[2].toUpperCase()}`;
  }
  const iniciais = texto
    .split(' ')
    .filter(Boolean)
    .map((palavra) => palavra[0]?.toUpperCase())
    .join('. ');
  return iniciais || texto;
}

function ProfessorNavbar() {
  const navigate = useNavigate();
  const { user, signOut, turmas, turmaAtiva, setTurmaAtiva } = useAuth();
  const [bimestreAtual, setBimestreAtual] = useState('');
  const [nomeProfessor, setNomeProfessor] = useState('');
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const { shouldOfferInstall, isIOS, canInstall, install, markInstalledManually } = usePwaInstall();

  useEffect(() => {
    const buscarNome = async () => {
      const { data } = await apiClient.from('usuarios').select('nome').eq('id', user.id).single();
      if (data) {
        setNomeProfessor(data.nome);
      }
    };
    if (user) {
      buscarNome();
    }
  }, [user]);

  useEffect(() => {
    const fetchBimestreAtual = async () => {
      const hoje = new Date().toISOString().split('T')[0];
      const instituicaoId = user?.user_metadata?.instituicao_id || user?.instituicao_id;

      const query = apiClient
        .from('periodos_avaliativos')
        .select('descricao')
        .lte('data_inicio', hoje)
        .gte('data_fim', hoje)
        .limit(1);

      if (instituicaoId) {
        query.eq('instituicao_id', instituicaoId);
      }

      const { data, error } = await query;

      if (error) {
        console.error('Erro ao buscar bimestre:', error);
        setBimestreAtual('Bimestre');
      } else if (data && data.length > 0) {
        setBimestreAtual(data[0].descricao);
      } else {
        setBimestreAtual('Período de Férias');
      }
    };

    if (user) {
      fetchBimestreAtual();
    }
  }, [user]);

  async function handleInstallClick() {
    if (isIOS) {
      toast({
        title: 'Instale o app NARA no seu iPhone',
        description: 'Toque em Compartilhar (ícone com seta ↑) e depois em "Adicionar à Tela de Início".',
      });
      markInstalledManually();
      return;
    }

    if (canInstall) {
      const result = await install();
      if (result.outcome === 'accepted') {
        toast({ title: 'App instalado com sucesso!' });
      }
    }
  }

  return (
    <>
      <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-20 shadow-sm">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <img
            src="/nara-logo.png"
            alt="Logo NARA"
            className="h-12 w-auto sm:h-14 cursor-pointer"
            onClick={() => navigate('/home-professor')}
          />

          <div className="flex items-center gap-1.5 sm:gap-3">
            {turmas?.length > 1 && (
              <div className="relative">
                <select
                  value={turmaAtiva?.id || ''}
                  onChange={(e) => {
                    const selecionada = turmas.find((t) => t.id === e.target.value);
                    if (selecionada) setTurmaAtiva(selecionada);
                  }}
                  className="appearance-none bg-white border border-gray-200 text-gray-700 font-semibold text-xs sm:text-sm rounded-full pl-3 pr-7 py-1.5 sm:px-4 sm:py-2 sm:pr-8 shadow-sm cursor-pointer hover:border-roxo-principal focus:outline-none focus:ring-2 focus:ring-roxo-principal transition-colors"
                >
                  {turmas.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.nome}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 sm:h-4 sm:w-4 text-gray-500" />
              </div>
            )}

            {bimestreAtual && (
              <div className="bg-roxo-claro text-roxo-principal font-semibold px-2.5 py-1.5 sm:px-4 sm:py-2 rounded-full text-xs sm:text-sm whitespace-nowrap">
                <span className="hidden sm:inline">{bimestreAtual}</span>
                <span className="sm:hidden">{abreviarBimestre(bimestreAtual)}</span>
              </div>
            )}

            <NotificationsBell />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <span className="font-semibold text-gray-600 rounded-md px-3 py-1 cursor-pointer hover:bg-gray-100 transition-colors flex items-center gap-2">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                    <path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0" />
                    <path d="M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2" />
                  </svg>
                </span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Olá, {nomeProfessor || 'Professor'}!</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onSelect={(e) => {
                    e.preventDefault();
                    setChangePasswordOpen(true);
                  }}
                >
                  <Key className="mr-2 h-4 w-4" />
                  Trocar senha
                </DropdownMenuItem>
                {shouldOfferInstall && (
                  <DropdownMenuItem
                    onSelect={(e) => {
                      e.preventDefault();
                      handleInstallClick();
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Instalar app
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onSelect={(e) => {
                    e.preventDefault();
                    signOut();
                  }}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="mr-2 h-4 w-4"
                  >
                    <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                    <path d="M14 8v-2a2 2 0 0 0 -2 -2h-7a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2 -2v-2" />
                    <path d="M9 12h12l-3 -3" />
                    <path d="M18 15l3 -3" />
                  </svg>
                  Sair
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <ChangePasswordModal open={changePasswordOpen} onOpenChange={setChangePasswordOpen} />
    </>
  );
}

export default ProfessorNavbar;