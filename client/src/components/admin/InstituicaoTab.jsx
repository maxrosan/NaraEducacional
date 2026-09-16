import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Edit, UploadCloud, Image as ImageIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { listarInstituicoes, criarInstituicao, atualizarInstituicao, uploadLogoInstituicao } from '@/services/api';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';

const InstituicaoView = ({ institution }) => {
    if (!institution) {
        return <p className="p-6 text-center text-gray-500">Nenhuma instituição cadastrada. Clique em 'Editar' para começar.</p>;
    }

    const reportTypeMap = {
        'texto_e_evidencia': 'Texto + Evidência',
        'apenas_texto': 'Apenas Texto',
        'observacao_guiada': 'Observação Guiada'
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 p-4">
            <div className="md:col-span-1 flex flex-col items-center">
                <div className="w-32 h-32 sm:w-40 sm:h-40 bg-gray-100 rounded-full flex items-center justify-center border-4 border-white shadow-md mb-4">
                    {institution.logo_url ? (
                        <img src={institution.logo_url} alt="Logo da instituição" className="w-full h-full object-cover rounded-full" />
                    ) : (
                        <ImageIcon className="w-16 h-16 sm:w-20 sm:h-20 text-gray-400" />
                    )}
                </div>
            </div>
            <div className="md:col-span-2 space-y-4">
                <h2 className="text-xl sm:text-2xl font-bold text-gray-800">{institution.nome}</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4 text-gray-600 text-sm sm:text-base">
                    <div><span className="font-semibold">CNPJ:</span> {institution.cnpj || 'Não informado'}</div>
                    <div><span className="font-semibold">Telefone:</span> {institution.telefone || 'Não informado'}</div>
                    <div><span className="font-semibold">E-mail:</span> {institution.email_institucional}</div>
                    <div><span className="font-semibold">Localização:</span> {institution.cidade} - {institution.uf}</div>
                    <div className="sm:col-span-2"><span className="font-semibold">Tipo de Relatório Padrão:</span> {reportTypeMap[institution.tipo_relatorio] || 'Não definido'}</div>
                </div>
            </div>
        </div>
    );
};

const InstituicaoForm = ({ institution, onSave, onCancel }) => {
    const [formData, setFormData] = useState(institution || {
        nome: '',
        cnpj: '',
        email_institucional: '',
        telefone: '',
        cidade: '',
        uf: '',
        logo_url: '',
        tipo_relatorio: ''
    });
    const [logoFile, setLogoFile] = useState(null);
    const [logoPreview, setLogoPreview] = useState(formData.logo_url);
    const fileInputRef = useRef(null);

    const ufs = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };
    
    const handleSelectChange = (name, value) => {
        setFormData(p => ({...p, [name]: value}));
    };

    const handleLogoChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            setLogoFile(file);
            const reader = new FileReader();
            reader.onloadend = () => setLogoPreview(reader.result);
            reader.readAsDataURL(file);
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        onSave(formData, logoFile);
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6 pt-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-1 flex flex-col items-center justify-center">
                    <input type="file" ref={fileInputRef} onChange={handleLogoChange} accept="image/png, image/jpeg, image/svg+xml" className="hidden" />
                    <div 
                        className="w-32 h-32 sm:w-40 sm:h-40 bg-gray-100 rounded-full flex items-center justify-center border-2 border-dashed border-gray-300 cursor-pointer hover:bg-gray-200 transition-colors"
                        onClick={() => fileInputRef.current.click()}
                    >
                        {logoPreview ? (
                            <img src={logoPreview} alt="Prévia da logo" className="w-full h-full object-cover rounded-full" />
                        ) : (
                            <div className="text-center text-gray-500">
                                <UploadCloud className="w-8 h-8 sm:w-10 sm:h-10 mx-auto" />
                                <p className="text-xs mt-1">Clique para enviar</p>
                            </div>
                        )}
                    </div>
                </div>
                <div className="md:col-span-2 space-y-4">
                    <div>
                        <Label htmlFor="nome">Nome da Instituição</Label>
                        <Input id="nome" name="nome" value={formData.nome} onChange={handleChange} required />
                    </div>
                    <div>
                        <Label htmlFor="email_institucional">E-mail Institucional</Label>
                        <Input id="email_institucional" name="email_institucional" type="email" value={formData.email_institucional} onChange={handleChange} required />
                    </div>
                </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <Label htmlFor="cnpj">CNPJ</Label>
                    <Input id="cnpj" name="cnpj" value={formData.cnpj} onChange={handleChange} />
                </div>
                <div>
                    <Label htmlFor="telefone">Telefone</Label>
                    <Input id="telefone" name="telefone" value={formData.telefone} onChange={handleChange} />
                </div>
                <div>
                    <Label htmlFor="cidade">Cidade</Label>
                    <Input id="cidade" name="cidade" value={formData.cidade} onChange={handleChange} required />
                </div>
                <div>
                    <Label htmlFor="uf">UF</Label>
                    <Select name="uf" value={formData.uf} onValueChange={(value) => handleSelectChange('uf', value)}>
                        <SelectTrigger id="uf"><SelectValue placeholder="Selecione" /></SelectTrigger>
                        <SelectContent>
                            {ufs.map(uf => <SelectItem key={uf} value={uf}>{uf}</SelectItem>)}
                        </SelectContent>
                    </Select>
                </div>
            </div>
            <div>
                <Label htmlFor="tipo_relatorio">Tipo de Relatório Padrão</Label>
                <Select name="tipo_relatorio" value={formData.tipo_relatorio} onValueChange={(value) => handleSelectChange('tipo_relatorio', value)}>
                    <SelectTrigger id="tipo_relatorio"><SelectValue placeholder="Selecione o tipo de relatório" /></SelectTrigger>
                    <SelectContent>
                        <SelectItem value="texto_e_evidencia">Texto + Evidência</SelectItem>
                        <SelectItem value="apenas_texto">Apenas Texto</SelectItem>
                        <SelectItem value="observacao_guiada">Observação Guiada</SelectItem>
                    </SelectContent>
                </Select>
            </div>
            <CardFooter className="px-0 pt-6">
                <div className="flex justify-end w-full gap-2">
                    {institution && <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>}
                    <Button type="submit">Salvar Alterações</Button>
                </div>
            </CardFooter>
        </form>
    );
};

const InstituicaoTab = () => {
    const { toast } = useToast();
    const [institution, setInstitution] = useState(null);
    const [loading, setLoading] = useState(true);
    const [isEditing, setIsEditing] = useState(false);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const instituicoes = await listarInstituicoes();
            const data = instituicoes?.[0] || null;
            setInstitution(data);
            if (!data) setIsEditing(true);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao buscar dados da instituição", description: error.message });
        } finally {
            setLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleSave = async (formData, logoFile) => {
        try {
            let result = institution?.id
                ? await atualizarInstituicao(institution.id, formData)
                : await criarInstituicao(formData);

            if (logoFile) {
                const { data: { session: currentSession } } = await apiClient.auth.getSession();
                if (!currentSession) {
                    toast({ variant: "destructive", title: "Erro de autenticação", description: "Sua sessão expirou. Faça login novamente." });
                    return;
                }
                const uploadResult = await uploadLogoInstituicao(result.id, logoFile);
                result = { ...result, logo_url: uploadResult.logo_url };
            }

            toast({ title: `Instituição ${institution?.id ? 'atualizada' : 'criada'} com sucesso!` });
            setInstitution(result);
            setIsEditing(false);
            fetchData();
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao salvar instituição", description: error.message });
        }
    };

    if (loading) {
        return <Card><CardContent><p className="p-6 text-center">Carregando dados da instituição...</p></CardContent></Card>;
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div className="min-w-0">
                    <CardTitle>Dados da Instituição</CardTitle>
                    <CardDescription className="mt-1">Gerencie as informações e configurações da sua escola.</CardDescription>
                </div>
                {!isEditing && institution && (
                    <Button onClick={() => setIsEditing(true)} className="shrink-0">
                        <Edit className="mr-2 h-4 w-4" /> Editar
                    </Button>
                )}
            </CardHeader>
            <CardContent>
                {isEditing ? (
                    <InstituicaoForm 
                        institution={institution} 
                        onSave={handleSave} 
                        onCancel={() => { if(institution) setIsEditing(false); }}
                    />
                ) : (
                    <InstituicaoView institution={institution} />
                )}
            </CardContent>
        </Card>
    );
};

export default InstituicaoTab;