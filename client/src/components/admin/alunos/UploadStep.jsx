import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { UploadCloud, FileText, Download, Loader2 } from 'lucide-react';

const UploadStep = ({ onProcessFile, onDownloadTemplate, processing }) => {
    const [file, setFile] = useState(null);
    const [fileName, setFileName] = useState('');

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setFileName(selectedFile.name);
        }
    };

    const handleProcess = () => {
        if (file) {
            onProcessFile(file);
        }
    };

    return (
        <div className="text-center p-6 space-y-6">
            <div className="flex flex-col items-center justify-center w-full">
                <label
                    htmlFor="dropzone-file"
                    className="flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors"
                >
                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                        {fileName ? (
                            <>
                                <FileText className="w-10 h-10 mb-3 text-green-500" />
                                <p className="mb-2 text-sm text-gray-700 font-semibold">{fileName}</p>
                                <p className="text-xs text-gray-500">Clique para selecionar outro arquivo</p>
                            </>
                        ) : (
                            <>
                                <UploadCloud className="w-10 h-10 mb-3 text-gray-400" />
                                <p className="mb-2 text-sm text-gray-500"><span className="font-semibold">Clique para fazer upload</span> ou arraste e solte</p>
                                <p className="text-xs text-gray-500">Arquivo .xlsx</p>
                            </>
                        )}
                    </div>
                    <input id="dropzone-file" type="file" className="hidden" onChange={handleFileChange} accept=".xlsx, .xls" />
                </label>
            </div>
            
            <div className="flex flex-col sm:flex-row justify-center items-center gap-4">
                <Button onClick={onDownloadTemplate} variant="outline">
                    <Download className="mr-2 h-4 w-4" />
                    Baixar Modelo
                </Button>
                <Button onClick={handleProcess} disabled={!file || processing}>
                    {processing ? (
                        <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Processando...
                        </>
                    ) : 'Verificar e Continuar'}
                </Button>
            </div>
        </div>
    );
};

export default UploadStep;