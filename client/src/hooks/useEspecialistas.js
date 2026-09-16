import { useState, useCallback } from 'react';
import { apiClient } from '@/lib/apiClient';
import { toast } from '@/components/ui/use-toast';

export const useEspecialistas = () => {
    const [especialistas, setEspecialistas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [institutionId, setInstitutionId] = useState(null);

    const tiposEspecialistaPadrao = [
        'Psicólogo',
        'Psicopedagogo',
        'Professor de Música',
        'Professor de Inglês',
        'Professor de Psicomotricidade',
    ];

    const fetchInstitutionAndData = useCallback(async (forceRefetch = false) => {
        setLoading(true);
        try {
            let currentInstitutionId = institutionId;
            if (!currentInstitutionId || forceRefetch) {
                const { data: instData, error: instError } = await apiClient.from('instituicoes').select('id').limit(1).single();
                if (instError && instError.code !== 'PGRST116') throw instError;
                if (!instData) {
                    setLoading(false);
                    return;
                }
                setInstitutionId(instData.id);
                currentInstitutionId = instData.id;
            }

            const { data: especialistasData, error: especialistasError } = await apiClient
                .from('usuarios')
                .select('id, nome, email, tipo_especialista, ativo')
                .eq('instituicao_id', currentInstitutionId)
                .eq('perfil', 'especialista')
                .limit(100);

            if (especialistasError) throw especialistasError;

            setEspecialistas(especialistasData);

        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao carregar dados", description: error.message });
            setEspecialistas([]);
        } finally {
            setLoading(false);
        }
    }, [institutionId]);

    return {
        especialistas,
        loading,
        institutionId,
        fetchInstitutionAndData,
        tiposEspecialistaPadrao
    };
};