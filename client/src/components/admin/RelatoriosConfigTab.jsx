import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';
import { GripVertical, ChevronDown } from 'lucide-react';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const allReportSections = {
    introducao_coletiva: 'Introdução coletiva (baseada no planejamento)',
    texto_descritivo_individual: 'Texto descritivo individual',
    analise_escrita: 'Análise de escrita (IA)',
    analise_leitura: 'Análise de leitura (IA)',
    analise_desenho: 'Análise de desenho (IA)',
    tabela_bncc_percent: 'Tabela de campos da BNCC por porcentagem',
    quadro_habilidades: 'Quadro de habilidades marcadas por nível',
    portfolio: 'Portfólio (fotos e vídeos)',
    texto_especialistas: 'Texto dos especialistas',
};

const defaultOrder = Object.keys(allReportSections);

const MultiSelectDropdown = ({ turmas, selectedTurmaIds, onSelectionChange }) => {
    const handleSelect = (turmaId) => {
        const newSelection = selectedTurmaIds.includes(turmaId)
            ? selectedTurmaIds.filter(id => id !== turmaId)
            : [...selectedTurmaIds, turmaId];
        onSelectionChange(newSelection);
    };

    const selectedTurmasCount = selectedTurmaIds.length;
    const buttonText = selectedTurmasCount > 0 ? `${selectedTurmasCount} turma(s)` : 'Selecionar turmas';

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="outline" className="w-[180px] justify-between text-sm">
                    {buttonText}
                    <ChevronDown className="h-4 w-4 ml-2" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56">
                <DropdownMenuLabel>Atribuir às turmas</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {turmas.map(turma => (
                    <DropdownMenuCheckboxItem
                        key={turma.id}
                        checked={selectedTurmaIds.includes(turma.id)}
                        onSelect={(e) => {
                            e.preventDefault();
                            handleSelect(turma.id);
                        }}
                    >
                        {turma.nome}
                    </DropdownMenuCheckboxItem>
                ))}
            </DropdownMenuContent>
        </DropdownMenu>
    );
};

const SortableItem = ({ id, label, isChecked, onSwitchChange, turmas, selectedTurmas, onTurmasChange }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
    } = useSortable({ id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    const isIaSection = id === 'analise_escrita' || id === 'analise_leitura';

    return (
        <div
            ref={setNodeRef}
            style={style}
            className="flex items-center justify-between p-4 rounded-lg border bg-white shadow-sm hover:bg-gray-50 transition-colors"
        >
            <div className="flex items-center gap-4">
                <button {...attributes} {...listeners} className="cursor-grab p-1">
                    <GripVertical className="h-5 w-5 text-gray-400" />
                </button>
                <div className="flex flex-col gap-1">
                    <Label htmlFor={id} className="text-base font-medium text-gray-700 cursor-pointer">
                        {label}
                    </Label>
                    {isIaSection && isChecked && selectedTurmas.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                            {turmas
                                .filter(t => selectedTurmas.includes(t.id))
                                .map(t => <Badge key={t.id} variant="secondary">{t.nome}</Badge>)
                            }
                        </div>
                    )}
                </div>
            </div>
            <div className="flex items-center gap-4">
                {isIaSection && isChecked && (
                    <MultiSelectDropdown
                        turmas={turmas}
                        selectedTurmaIds={selectedTurmas}
                        onSelectionChange={(newSelectedIds) => onTurmasChange(id, newSelectedIds)}
                    />
                )}
                <Switch
                    id={id}
                    checked={isChecked}
                    onCheckedChange={(checked) => onSwitchChange(id, checked)}
                />
            </div>
        </div>
    );
};

const RelatoriosConfigTab = () => {
    const { toast } = useToast();
    const [settings, setSettings] = useState({});
    const [orderedKeys, setOrderedKeys] = useState(defaultOrder);
    const [institution, setInstitution] = useState(null);
    const [turmas, setTurmas] = useState([]);
    const [loading, setLoading] = useState(true);

    const sensors = useSensors(
        useSensor(PointerSensor, {
          activationConstraint: {
            distance: 8,
          },
        })
    );

    const fetchInstitutionData = useCallback(async () => {
        setLoading(true);
        try {
            const { data, error } = await apiClient.from('instituicoes').select('id, report_settings, ordem_relatorio').limit(1).single();
            if (error && error.code !== 'PGRST116') throw error;
            
            if (data) {
                setInstitution(data);
                const fetchedSettings = data.report_settings || {};
                const initialSettings = {};
                defaultOrder.forEach(key => {
                    initialSettings[key] = fetchedSettings[key] !== false;
                    if (key === 'analise_escrita' || key === 'analise_leitura') {
                        initialSettings[`${key}_turmas`] = fetchedSettings[`${key}_turmas`] || [];
                    }
                });
                setSettings(initialSettings);

                const serverOrder = data.ordem_relatorio;
                const newOrder = serverOrder && serverOrder.length > 0 
                    ? [...new Set([...serverOrder, ...defaultOrder])]
                    : defaultOrder;
                setOrderedKeys(newOrder);

                const { data: turmasData, error: turmasError } = await apiClient
                    .from('turmas')
                    .select('id, nome')
                    .eq('instituicao_id', data.id);
                if (turmasError) throw turmasError;
                setTurmas(turmasData || []);

            } else {
                toast({
                    variant: "destructive",
                    title: "Nenhuma instituição encontrada",
                    description: "Por favor, cadastre primeiro os dados da instituição.",
                });
            }
        } catch (error) {
            toast({
                variant: "destructive",
                title: "Erro ao carregar configurações",
                description: error.message,
            });
        } finally {
            setLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        fetchInstitutionData();
    }, [fetchInstitutionData]);
    
    const saveSettingsToDb = async (settingsToSave) => {
        if (!institution) return false;
        try {
            const { error } = await apiClient
                .from('instituicoes')
                .update({ report_settings: settingsToSave })
                .eq('id', institution.id);
            if (error) throw error;
            setInstitution(prev => ({ ...prev, report_settings: settingsToSave }));
            return true;
        } catch (error) {
            toast({
                variant: "destructive",
                title: "Erro ao salvar",
                description: `Não foi possível salvar a configuração. ${error.message}`,
            });
            return false;
        }
    };

    const handleSwitchChange = async (sectionKey, isChecked) => {
        const oldSettings = { ...settings };
        const newSettings = { ...settings, [sectionKey]: isChecked };
        setSettings(newSettings);

        const success = await saveSettingsToDb(newSettings);
        if (success) {
            toast({
                title: "Configuração atualizada!",
                description: `A seção "${allReportSections[sectionKey]}" foi ${isChecked ? 'ativada' : 'desativada'}.`,
            });
        } else {
            setSettings(oldSettings);
        }
    };

    const handleTurmasChange = async (sectionKey, selectedIds) => {
        const oldSettings = { ...settings };
        const newSettings = { ...settings, [`${sectionKey}_turmas`]: selectedIds };
        setSettings(newSettings);

        const success = await saveSettingsToDb(newSettings);
        if (success) {
            toast({
                title: "Turmas atualizadas!",
                description: `A seleção de turmas para "${allReportSections[sectionKey]}" foi salva.`,
            });
        } else {
            setSettings(oldSettings);
        }
    };

    const handleDragEnd = async (event) => {
        const { active, over } = event;
        if (active.id !== over.id) {
            const oldIndex = orderedKeys.indexOf(active.id);
            const newIndex = orderedKeys.indexOf(over.id);
            const newOrder = arrayMove(orderedKeys, oldIndex, newIndex);
            setOrderedKeys(newOrder);

            try {
                const { error } = await apiClient
                    .from('instituicoes')
                    .update({ ordem_relatorio: newOrder })
                    .eq('id', institution.id);

                if (error) throw error;

                toast({
                    title: "Ordem atualizada!",
                    description: "A nova ordem dos blocos do relatório foi salva.",
                });
            } catch (error) {
                toast({
                    variant: "destructive",
                    title: "Erro ao salvar a ordem",
                    description: error.message,
                });
                setOrderedKeys(orderedKeys);
            }
        }
    };
    
    const sortedSections = useMemo(() => {
        return orderedKeys.map(key => ({
            key,
            label: allReportSections[key]
        })).filter(section => section.label);
    }, [orderedKeys]);


    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Configuração da Geração de Relatórios</CardTitle>
                    <CardDescription>Arraste para reordenar. Ative ou desative os blocos que aparecerão no relatório final.</CardDescription>
                </CardHeader>
                <CardContent className="text-center p-8">Carregando configurações...</CardContent>
            </Card>
        );
    }
    
    if (!institution && !loading) {
         return (
            <Card>
                <CardHeader>
                    <CardTitle>Configuração da Geração de Relatórios</CardTitle>
                </CardHeader>
                <CardContent className="text-center p-8 text-red-500">
                    Nenhuma instituição encontrada. Por favor, cadastre uma instituição na aba 'Instituição' para continuar.
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Configuração da Geração de Relatórios</CardTitle>
                <CardDescription>Arraste para reordenar. Ative ou desative os blocos que aparecerão no relatório final.</CardDescription>
            </CardHeader>
            <CardContent>
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext
                        items={orderedKeys}
                        strategy={verticalListSortingStrategy}
                    >
                        <div className="space-y-4">
                            {sortedSections.map(({ key, label }) => (
                                <SortableItem
                                    key={key}
                                    id={key}
                                    label={label}
                                    isChecked={settings[key] ?? false}
                                    onSwitchChange={handleSwitchChange}
                                    turmas={turmas}
                                    selectedTurmas={settings[`${key}_turmas`] || []}
                                    onTurmasChange={handleTurmasChange}
                                />
                            ))}
                        </div>
                    </SortableContext>
                </DndContext>
            </CardContent>
        </Card>
    );
};

export default RelatoriosConfigTab;