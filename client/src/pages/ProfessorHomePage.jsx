import React, { useState, useEffect } from 'react';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';
import { BookText, BarChart3, CalendarDays, Backpack, HelpCircle, Plus, Sparkles, Mic2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import AlertsAndMessagesCenter from '@/components/dashboard/AlertsAndMessagesCenter';
import ProfessorNavbar from '@/components/teacher/ProfessorNavBar';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/apiClient';

const ActionCard = ({ icon, title, delay, path }) => {
  const navigate = useNavigate();
  const handleClick = () => {
    navigate(path);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      whileHover={{ scale: 1.05, y: -5 }}
      className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100 flex flex-col items-center justify-center text-center space-y-4 cursor-pointer card-hover"
      onClick={handleClick}
    >
      <div className="bg-[#F5F3FA] p-4 rounded-full">
        {icon}
      </div>
      <span className="font-semibold text-gray-700">{title}</span>
    </motion.div>
  );
};

function ProfessorHomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [perfilUsuario, setPerfilUsuario] = useState(null);
  const nomeUsuario = user?.user_metadata?.nome?.split(' ')[0] || 'Professor(a)';

  useEffect(() => {
    const fetchPerfilUsuario = async () => {
      if (!user?.id) return;
      const { data, error } = await apiClient
        .from('usuarios')
        .select('perfil')
        .eq('id', user.id)
        .single();
      if (error) {
        console.error('Erro ao buscar perfil do usuário:', error);
        return;
      }
      setPerfilUsuario(data?.perfil || null);
    };

    fetchPerfilUsuario();
  }, [user?.id]);

  const cards = [
    { icon: <BookText className="h-8 w-8 text-[#8A63D2]" />, title: "Registros", path: "/registro" },
    { icon: <Mic2 className="h-8 w-8 text-[#8A63D2]" />, title: "Gravar", path: "/gravacao" },
    { icon: <BarChart3 className="h-8 w-8 text-[#8A63D2]" />, title: "Relatórios", path: "/relatorios" },
    { icon: <CalendarDays className="h-8 w-8 text-[#8A63D2]" />, title: "Planejamentos", path: "/planejamento/semanal" },
    { icon: <Backpack className="h-8 w-8 text-[#8A63D2]" />, title: "Portfólios", path: "/portfolios" },
  ];
  if (perfilUsuario === 'professor_especialista') {
    cards.push({
      icon: <Sparkles className="h-8 w-8 text-[#8A63D2]" />,
      title: "Contribuições do Especialista",
      path: "/especialistas",
    });
  }

  const handleSupport = () => {
    // Implementar lógica de suporte
  };

  return (
    <>
      <Helmet>
        <title>NARA - Home do Professor</title>
        <meta name="description" content="Página inicial do professor no NARA. Acesse registros, relatórios, planejamentos e mais." />
      </Helmet>

      <div className="bg-white min-h-screen flex flex-col">
        <ProfessorNavbar />

        <main className="flex-1 container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-8"
          >
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-800">Oi, {nomeUsuario}!</h1>
            <p className="text-md sm:text-lg text-gray-600 mt-1">Vamos registrar o que viveu hoje com sua turma?</p>
          </motion.div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 sm:gap-6">
            {cards.map((card, index) => (
              <ActionCard key={card.title} {...card} delay={0.1 * (index + 1)} />
            ))}
          </div>

          <AlertsAndMessagesCenter />
        </main>

        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.5 }}
          className="fixed bottom-6 right-6 z-20"
        >
          <Button
            onClick={() => navigate('/registro')}
            className="bg-[#C3ECD4] hover:bg-[#B0E4C1] text-gray-800 font-bold rounded-full h-16 w-auto px-6 shadow-xl flex items-center space-x-2 text-lg btn-hover"
          >
            <Plus className="h-6 w-6" />
            <span>Novo Registro</span>
          </Button>
        </motion.div>

        <footer className="py-6 text-center mt-8">
          <div className="flex items-center justify-center space-x-4">
            <button onClick={handleSupport} className="flex items-center space-x-1 text-sm text-gray-500 hover:text-gray-800 transition-colors">
              <HelpCircle className="h-4 w-4" />
              <span>Suporte</span>
            </button>
            <span className="text-sm text-gray-400">|</span>
            <p className="text-sm text-gray-500">NARA v1.0 – Professor</p>
          </div>
        </footer>
      </div>
    </>
  );
}

export default ProfessorHomePage;