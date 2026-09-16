import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/apiClient';

/**
 * Busca os dados do especialista logado (mesmo padrão já usado em
 * SpecialistHomePage / SpecialistObservationPage / SpecialistReportPage),
 * centralizado aqui para não repetir o fetch em cada página nova.
 *
 * @returns {{ especialista: object|null, loading: boolean }}
 */
export function useEspecialistaLogado() {
  const { user } = useAuth();
  const [especialista, setEspecialista] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEspecialista = async () => {
      if (!user) return;
      setLoading(true);
      const { data, error } = await apiClient
        .from('usuarios')
        .select('id, nome, email, perfil, tipo_especialista, instituicao_id, permissoes_esp')
        .eq('id', user.id)
        .single();

      if (error) {
        console.error('Erro ao buscar dados do especialista:', error);
      } else {
        setEspecialista(data);
      }
      setLoading(false);
    };

    fetchEspecialista();
  }, [user]);

  return { especialista, loading };
}