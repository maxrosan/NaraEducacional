import React from 'react';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';
import LoginForm from '@/components/LoginForm';
import { Navigate, Link } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

function getHomeRoute(perfil) {
  switch ((perfil || '').toLowerCase()) {
    case 'admin': return '/admin';
    case 'coordenador': return '/coordenacao';
    case 'professor':
    case 'professor_infantil':
    case 'professor_fundamental':
      return '/home-professor';
    case 'professor_especialista':
    case 'especialista':
      return '/especialistas';
    default: return null;
  }
}

function LoginPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-roxo-principal"></div>
      </div>
    );
  }

  const homeRoute = user ? getHomeRoute(user.perfil) : null;
  if (homeRoute) {
    return <Navigate to={homeRoute} replace />;
  }

  return <>
      <Helmet>
        <title>NARA - Login</title>
        <meta name="description" content="Acesse o NARA - Núcleo de Acompanhamento e Registro da Aprendizagem. Faça login para acompanhar o desenvolvimento educacional." />
      </Helmet>
      
      <div className="min-h-screen flex flex-col bg-white">
        <div className="flex-1 flex flex-col items-center justify-center px-4 py-8">
          <div className="w-full max-w-md space-y-8">
            
            <motion.div initial={{
            opacity: 0,
            y: -30
          }} animate={{
            opacity: 1,
            y: 0
          }} transition={{
            duration: 0.8,
            ease: 'easeOut'
          }} className="text-center space-y-6">
              <div className="flex justify-center">
                <motion.div whileHover={{
                scale: 1.05
              }} transition={{
                type: "spring",
                stiffness: 300,
                damping: 10
              }}>
                  <img alt="NARA - Núcleo de Acompanhamento e Registro da Aprendizagem" className="h-40 w-auto object-contain sm:h-44" src="/nara-logo.png" />
                </motion.div>
              </div>
              
              <motion.div initial={{
              opacity: 0
            }} animate={{
              opacity: 1
            }} transition={{
              duration: 0.6,
              delay: 0.4
            }} className="space-y-2">
                <h1 className="text-2xl font-bold text-gray-800 leading-relaxed">NARA tá aqui.</h1>
                <p className="text-xl text-gray-600 font-medium">
                  Pode contar como foi seu dia.
                </p>
              </motion.div>
            </motion.div>

            <LoginForm />
            <p className="text-center text-sm mt-2">
              <Link to="/esqueci-senha" className="text-purple-600 hover:underline">Esqueceu a senha?</Link>
            </p>
          </div>
        </div>

        <motion.footer initial={{
        opacity: 0
      }} animate={{
        opacity: 1
      }} transition={{
        duration: 0.6,
        delay: 0.8
      }} className="py-6 text-center">
          <p className="text-sm text-gray-500">
            Versão 1.0 – Núcleo de Acompanhamento e Registro da Aprendizagem
          </p>
        </motion.footer>

        <div className="fixed top-0 left-0 w-full h-full pointer-events-none overflow-hidden -z-10">
          <motion.div animate={{
          x: [0, 100, 0],
          y: [0, -50, 0]
        }} transition={{
          duration: 20,
          repeat: Infinity,
          ease: "linear"
        }} className="absolute top-10 left-10 w-20 h-20 rounded-full bg-gradient-to-br from-[#D7CDEB] to-[#C3ECD4] opacity-20" />
          <motion.div animate={{
          x: [0, -80, 0],
          y: [0, 60, 0]
        }} transition={{
          duration: 25,
          repeat: Infinity,
          ease: "linear"
        }} className="absolute top-1/3 right-10 w-16 h-16 rounded-full bg-gradient-to-br from-[#C3ECD4] to-[#D7CDEB] opacity-15" />
          <motion.div animate={{
          x: [0, 60, 0],
          y: [0, -40, 0]
        }} transition={{
          duration: 18,
          repeat: Infinity,
          ease: "linear"
        }} className="absolute bottom-1/4 left-1/4 w-12 h-12 rounded-full bg-gradient-to-br from-[#D7CDEB] to-[#C3ECD4] opacity-25" />
        </div>
      </div>
    </>;
}
export default LoginPage;
