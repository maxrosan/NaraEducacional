import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

/**
 * Componente que protege rotas, redirecionando para login se não autenticado.
 */
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Enquanto carrega, mostrar nada (ou um spinner)
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-roxo-principal"></div>
      </div>
    );
  }

  // Se não está autenticado, redirecionar para login
  if (!user) {
    // Salvar a URL atual para redirecionar de volta após o login
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  // Se está autenticado, verificar se o usuário tem o perfil permitido
  if (allowedRoles && !allowedRoles.includes(user.perfil)) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  // Se está autenticado e tem o perfil permitido, renderizar o conteúdo
  return children;
};

export default ProtectedRoute;
