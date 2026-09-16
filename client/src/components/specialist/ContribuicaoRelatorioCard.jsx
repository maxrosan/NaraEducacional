import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Mic, MicOff, Sparkles, Send, Save, Loader2, History } from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';

const ContribuicaoRelatorioCard = ({ especialista }) => {
    const { toast } = useToast();
    const [criancas, setCriancas] = useState([]);
    const [selectedTurma, setSelectedTurma] = useState('');
    const [selectedCrianca, setSelectedCrianca] = useState('');
    const [observacao, setObservacao] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [previousObservations, setPreviousObservations] = useState([]);
    
    const { transcript, listening, browserSupportsSpeechRecognition, resetTranscript } = useSpeechRecognition();

    const turmasUnicas = [...new Set(criancas.map(c => c.nome_turma).filter(Boolean))];

    const fetchPreviousObservations = useCallback(async () => {
        if (!especialista?.id) return;
        const { data, error } = await apiClient
            .from('observacoes_especialistas')
            .select('id, area, texto, data_hora, rascunho, criancas(nome_completo)')
            .eq('especialista_id', especialista.id)
            .order('data_hora', { ascending: false })
            .limit(5);

        if (error) {
            toast({ variant: 'destructive', title: 'Erro ao buscar histórico', description: error.message });
        } else {
            setPreviousObservations(data);
        }
    }, [especialista?.id, toast]);

    useEffect(() => {
        if (transcript) {
            setObservacao(prev => prev ? `${prev} ${transcript}` : transcript);
            resetTranscript();
        }
    }, [transcript, resetTranscript]);

    const fetchCriancas = useCallback(async () => {
        if (!especialista.instituicao_id) return;
        setIsLoading(true);
        const { data, error } = await apiClient
            .from('criancas')
            .select('id, nome_completo, turmas(nome)')
            .eq('instituicao_id', especialista.instituicao_id);
        
        if (error) {
            toast({ variant: 'destructive', title: 'Erro ao buscar crianças', description: error.message });
        } else {
            setCriancas(data.map(c => ({...c, nome_turma: c.turmas?.nome || 'Sem turma'})));
        }
        setIsLoading(false);
    }, [especialista.instituicao_id, toast]);

    useEffect(() => {
        fetchCriancas();
        fetchPreviousObservations();
    }, [fetchCriancas, fetchPreviousObservations]);

    const handleIaSuggestion = () => {
        if (!observacao) {
            toast({ title: "Atenção", description: "Digite ou grave algo antes de pedir uma sugestão." });
            return;
        }
        toast({ title: '🪄 Gerando sugestão com IA...', description: 'Aguarde um momento.' });
        const iaText = `Durante os atendimentos, observou-se que a criança demonstra ${observacao.toLowerCase()}. É notável seu desenvolvimento, apresentando comportamentos como...`;
        setObservacao(iaText);
    };

    const handleSave = async (rascunho = false) => {
        if (!selectedCrianca || !observacao) {
            toast({ variant: 'destructive', title: 'Campos obrigatórios', description: 'Por favor, selecione a turma, a criança e preencha a observação.' });
            return;
        }
        
        setIsSaving(true);
        const payload = {
            especialista_id: especialista.id,
            crianca_id: selectedCrianca,
            texto: observacao,
            rascunho: rascunho,
            area: especialista.tipo_especialista || 'Geral',
        };

        const { error } = await apiClient.from('observacoes_especialistas').insert(payload);
        
        if (error) {
            toast({ variant: 'destructive', title: 'Erro ao salvar', description: error.message });
        } else {
            toast({ title: `Contribuição ${rascunho ? 'salva como rascunho' : 'enviada'}!`, description: 'Sua observação foi registrada com sucesso.' });
            setSelectedTurma('');
            setSelectedCrianca('');
            setObservacao('');
            fetchPreviousObservations();
        }
        setIsSaving(false);
    };

    const startListening = () => SpeechRecognition.startListening({ continuous: true, language: 'pt-BR' });
    const stopListening = () => SpeechRecognition.stopListening();

    if (!browserSupportsSpeechRecognition) {
        return <p>Seu navegador não suporta reconhecimento de voz.</p>;
    }

    if (!especialista?.instituicao_id) {
        return (
            <Card className="mt-6">
                <CardContent className="pt-6">
                    <p className="text-gray-600">Instituição não vinculada ao especialista. Não é possível carregar as crianças.</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="bg-white shadow-lg border border-gray-100 overflow-hidden">
                <CardHeader className="bg-fundo-solido">
                    <CardTitle className="text-roxo-principal">💜 Contribuição para o Relatório Pedagógico</CardTitle>
                </CardHeader>
                <CardContent className="p-6 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <Label htmlFor="turma-select">Selecionar turma</Label>
                            <Select onValueChange={(value) => { setSelectedTurma(value); setSelectedCrianca(''); }} value={selectedTurma}>
                                <SelectTrigger id="turma-select" disabled={isLoading}>
                                    <SelectValue placeholder={isLoading ? "Carregando turmas..." : "Selecione uma turma"} />
                                </SelectTrigger>
                                <SelectContent>
                                    {turmasUnicas.map(turma => (
                                        <SelectItem key={turma} value={turma}>{turma}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        {selectedTurma && (
                            <div>
                                <Label htmlFor="crianca-select">Selecionar criança</Label>
                                <Select onValueChange={setSelectedCrianca} value={selectedCrianca}>
                                    <SelectTrigger id="crianca-select">
                                        <SelectValue placeholder="Selecione uma criança" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {criancas.filter(c => c.nome_turma === selectedTurma).map(c => (
                                            <SelectItem key={c.id} value={c.id}>{c.nome_completo}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                    </div>
                    
                    <div>
                        <Label>Forma de contribuição</Label>
                        <div className="relative">
                            <Textarea
                                value={observacao}
                                onChange={(e) => setObservacao(e.target.value)}
                                placeholder="Digite sua observação ou grave um áudio..."
                                className="min-h-[120px] pr-28"
                                rows={5}
                            />
                            <div className="absolute top-2 right-2">
                                <Button
                                    type="button"
                                    size="icon"
                                    variant={listening ? 'destructive' : 'outline'}
                                    onClick={listening ? stopListening : startListening}
                                >
                                    {listening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                                </Button>
                            </div>
                        </div>
                    </div>

                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                        <Button type="button" onClick={handleIaSuggestion} variant="outline">
                            <Sparkles className="h-4 w-4 mr-2 text-yellow-500" />
                            Sugerir versão final com IA
                        </Button>
                        <div className="flex items-center gap-2">
                            <Button type="button" onClick={() => handleSave(true)} disabled={isSaving} variant="secondary">
                                {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                                <span>Salvar Rascunho</span>
                            </Button>
                            <Button type="button" onClick={() => handleSave(false)} disabled={isSaving}>
                                {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                                <span>Enviar Observação</span>
                            </Button>
                        </div>
                    </div>
                </CardContent>
                <CardFooter className="bg-gray-50 p-6">
                    <div>
                        <h3 className="text-lg font-medium text-gray-800 flex items-center mb-4">
                            <History className="h-5 w-5 mr-2 text-roxo-principal" />
                            Últimas Contribuições
                        </h3>
                        <div className="space-y-4">
                            {previousObservations.length > 0 ? (
                                previousObservations.map(obs => (
                                    <div key={obs.id} className="p-3 bg-white rounded-lg border border-gray-200 text-sm">
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <p className="font-semibold text-gray-700">{obs.criancas.nome_completo}</p>
                                                <p className="text-gray-500 truncate max-w-xs">{obs.texto}</p>
                                            </div>
                                            <div className="text-right flex-shrink-0 ml-4">
                                                <span className={`inline-block px-2 py-1 text-xs font-semibold rounded-full ${obs.rascunho ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}`}>
                                                    {obs.rascunho ? 'Rascunho' : 'Enviado'}
                                                </span>
                                                <p className="text-xs text-gray-400 mt-1">{safeFormatDate(obs.data_hora, "dd/MM/yy 'às' HH:mm", { locale: ptBR })}</p>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <p className="text-sm text-gray-500">Nenhuma contribuição registrada ainda.</p>
                            )}
                        </div>
                    </div>
                </CardFooter>
            </Card>
        </motion.div>
    );
};

export default ContribuicaoRelatorioCard;