import React, { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from '@/lib/apiClient';
import { Loader2 } from 'lucide-react';

const RegistrosTab = () => {
    const { toast } = useToast();
    const [turmas, setTurmas] = useState([]);
    const [configuracoes, setConfiguracoes] = useState({});
    const [loading, setLoading] = useState(true);
    const [institutionId, setInstitutionId] = useState(null);

    const fetchInstitution = useCallback(async () => {
        const { data, error } = await apiClient.from('instituicoes').select('id').limit(1).single();
        if (error && error.code !== 'PGRST116') {
            toast({ variant: "destructive", title: "Erro ao buscar instituição", description: error.message });
            return null;
        }
        if (data) {
            setInstitutionId(data.id);
            return data.id;
        }
        return null;
    }, [toast]);

    const fetchData = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);

        const { data: turmasData, error: turmasError } = await apiClient
            .from('turmas')
            .select('id, nome')
            .eq('instituicao_id', id);

        if (turmasError) {
            toast({ variant: "destructive", title: "Erro ao buscar turmas", description: turmasError.message });
            setLoading(false);
            return;
        }
        setTurmas(turmasData);

        const turmaIds = turmasData.map(t => t.id);
        if (turmaIds.length > 0) {
            const { data: configsData, error: configsError } = await apiClient
                .from('configuracoes_registro')
                .select('*')
                .in('turma_id', turmaIds);
            
            if (configsError) {
                toast({ variant: "destructive", title: "Erro ao buscar configurações", description: configsError.message });
            } else {
                const configsMap = configsData.reduce((acc, config) => {
                    acc[config.turma_id] = config;
                    return acc;
                }, {});
                setConfiguracoes(configsMap);
            }
        }
        
        setLoading(false);
    }, [toast]);

    useEffect(() => {
        fetchInstitution().then(id => {
            if (id) {
                fetchData(id);
            } else {
                setLoading(false);
            }
        });
    }, [fetchInstitution, fetchData]);

    const handleFrequencyChange = async (turmaId, frequencia) => {
        const existingConfig = configuracoes[turmaId];
        const payload = {
            turma_id: turmaId,
            frequencia_registro: frequencia,
            ...(existingConfig?.id ? { id: existingConfig.id } : {}),
        };

        const { data, error } = await apiClient
            .from('configuracoes_registro')
            .upsert(payload)
            .select()
            .single();

        if (error) {
            toast({ variant: "destructive", title: "Erro ao salvar frequência", description: error.message });
        } else {
            toast({ title: "Frequência de registro atualizada!" });
            setConfiguracoes(prev => ({
                ...prev,
                [turmaId]: data,
            }));
        }
    };

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Configurações de Registro</CardTitle>
                    <CardDescription>Defina a frequência de registro esperada para cada turma.</CardDescription>
                </CardHeader>
                <CardContent className="flex justify-center items-center p-8">
                    <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
                </CardContent>
            </Card>
        );
    }

    if (!institutionId) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Configurações de Registro</CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-center text-gray-500">Por favor, cadastre uma instituição primeiro para definir as configurações de registro.</p>
                </CardContent>
            </Card>
        );
    }
    
    return (
        <Card>
            <CardHeader>
                <CardTitle>Configurações de Registro</CardTitle>
                <CardDescription>Defina a frequência de registro esperada para cada turma.</CardDescription>
            </CardHeader>
            <CardContent>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Turma</TableHead>
                            <TableHead className="w-[250px]">Frequência de Registro</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {turmas.length > 0 ? turmas.map(turma => (
                            <TableRow key={turma.id}>
                                <TableCell className="font-medium">{turma.nome}</TableCell>
                                <TableCell>
                                    <Select
                                        value={configuracoes[turma.id]?.frequencia_registro || ''}
                                        onValueChange={(value) => handleFrequencyChange(turma.id, value)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Definir frequência..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="diario">Diário</SelectItem>
                                            <SelectItem value="semanal">Semanal</SelectItem>
                                            <SelectItem value="quinzenal">Quinzenal</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </TableCell>
                            </TableRow>
                        )) : (
                            <TableRow>
                                <TableCell colSpan={2} className="text-center">Nenhuma turma cadastrada. Adicione turmas na aba 'Turmas'.</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
};

export default RegistrosTab;
