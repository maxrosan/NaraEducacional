import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/apiClient';

/**
 * Verifica se existe um período avaliativo ativo para a instituição.
 * Retorna { periodoAtivo, loading }.
 */
export function usePeriodoAvaliativo(instituicaoId) {
  const [periodoAtivo, setPeriodoAtivo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!instituicaoId) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    const fetchPeriodo = async () => {
      setLoading(true);
      const hoje = new Date().toISOString().split('T')[0];

      const { data, error } = await apiClient
        .from('periodos_avaliativos')
        .select('id, descricao, data_inicio, data_fim')
        .lte('data_inicio', hoje)
        .gte('data_fim', hoje)
        .eq('instituicao_id', instituicaoId)
        .limit(1);

      if (!cancelled) {
        if (!error && data && data.length > 0) {
          setPeriodoAtivo(data[0]);
        } else {
          setPeriodoAtivo(null);
        }
        setLoading(false);
      }
    };

    fetchPeriodo();
    return () => { cancelled = true; };
  }, [instituicaoId]);

  return { periodoAtivo, loading };
}
