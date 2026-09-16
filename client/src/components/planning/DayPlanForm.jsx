import React, { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Calendar,
  CheckSquare,
  FileUp,
  Loader2,
  Paperclip,
  Sparkles,
  StickyNote,
  Trash2,
  X,
} from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';

/**
 * Encurta o nome do arquivo preservando a extensão. Ex.:
 *   "Planejamento Quinzenal- 1603 a 27-03- Silvana .docx" (>35)
 *   → "Planejamento Quinzenal- 1603 a …docx"
 *
 * Se não houver extensão reconhecível (sem ponto, ponto no início, ou
 * "extensão" maior que 10 chars), trunca o nome inteiro com reticências.
 */
function shortenFilename(name, maxLength = 35) {
  if (!name) return '';
  if (name.length <= maxLength) return name;

  const lastDot = name.lastIndexOf('.');
  if (lastDot <= 0 || lastDot === name.length - 1 || name.length - lastDot > 10) {
    return name.slice(0, maxLength - 1) + '…';
  }

  const ext = name.slice(lastDot);
  const base = name.slice(0, lastDot);
  const disponivel = maxLength - ext.length - 1;
  if (disponivel <= 0) {
    return name.slice(0, maxLength - 1) + '…';
  }
  return base.slice(0, disponivel) + '…' + ext;
}

/**
 * Formulário simplificado de planejamento por dia.
 *
 * Quatro seções, na ordem:
 *  1. Anexar planejamento (PDF/DOC/DOCX, opcional)
 *  2. Assistente de IA (prompt livre)
 *  3. Atividades Propostas (textarea canônico)
 *  4. Habilidades BNCC (chips, geradas pela IA a partir das atividades)
 */
function DayPlanForm({
  dayName,
  date,
  data,
  onDataChange,
  onUploadFile,
  onSugerirAtividades,
  onSugerirBncc,
  onRemoverArquivo,
  uploading = false,
  gerandoAtividades = false,
  gerandoBncc = false,
  bnccError = null,
  bnccOrigem = null,
  bnccMensagem = null,
  atividadesSugeridas = '',
  onAplicarAtividadesSugeridas, // (modo: 'substituir' | 'anexar')
}) {
  const inputArquivoRef = useRef(null);
  const [promptError, setPromptError] = useState('');

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      await onUploadFile?.(file);
    } finally {
      // Permite selecionar o mesmo arquivo de novo se a professora quiser.
      if (inputArquivoRef.current) {
        inputArquivoRef.current.value = '';
      }
    }
  };

  const handleSugerirAtividades = async () => {
    const prompt = (data.prompt_ia || '').trim();
    if (prompt.length < 10) {
      setPromptError('Descreva o objetivo/tema com pelo menos 10 caracteres.');
      return;
    }
    setPromptError('');
    await onSugerirAtividades?.(prompt);
  };

  const habilidades = data.habilidades || [];

  const handleRemoverHabilidade = (codigo) => {
    onDataChange('habilidades', habilidades.filter((h) => h.codigo !== codigo));
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      <div className="flex items-center gap-3 mb-6">
        <Calendar className="h-6 w-6 text-roxo-principal" />
        <div>
          <h3 className="text-xl font-semibold text-texto-escuro">{dayName}</h3>
          <p className="text-sm text-texto-medio">{date}</p>
        </div>
      </div>

      <div className="grid gap-6">
        {/* 1. Upload de arquivo */}
        <div className="space-y-2">
          <Label className="text-base font-semibold text-gray-700 flex items-center gap-2">
            <Paperclip className="h-4 w-4" />
            Anexar planejamento (opcional)
          </Label>
          <p className="text-xs text-gray-500">
            Envie um PDF ou Word com o planejamento que você já preparou — a NARA lê o
            arquivo e preenche as Atividades Propostas pra você.
          </p>

          <input
            ref={inputArquivoRef}
            type="file"
            accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="hidden"
            onChange={handleFileChange}
            disabled={uploading}
          />

          {data.arquivo_storage_key ? (
            <div className="flex items-center justify-between gap-3 p-3 bg-purple-50 border border-purple-100 rounded-lg">
              <div className="flex items-center gap-2 min-w-0">
                <Paperclip className="h-4 w-4 text-roxo-principal shrink-0" />
                {data.arquivo_url ? (
                  <a
                    href={data.arquivo_url}
                    target="_blank"
                    rel="noreferrer"
                    title={data.arquivo_nome_original || 'Arquivo anexado'}
                    className="text-sm text-roxo-principal underline"
                  >
                    {shortenFilename(data.arquivo_nome_original) || 'Arquivo anexado'}
                  </a>
                ) : (
                  <span
                    title={data.arquivo_nome_original || 'Arquivo anexado'}
                    className="text-sm text-roxo-principal"
                  >
                    {shortenFilename(data.arquivo_nome_original) || 'Arquivo anexado'}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => inputArquivoRef.current?.click()}
                  disabled={uploading}
                >
                  Trocar
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-red-600 hover:text-red-700"
                  onClick={() => onRemoverArquivo?.()}
                  disabled={uploading}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ) : (
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start"
              onClick={() => inputArquivoRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processando arquivo...
                </>
              ) : (
                <>
                  <FileUp className="h-4 w-4 mr-2" />
                  Selecionar arquivo (PDF, DOC ou DOCX)
                </>
              )}
            </Button>
          )}
        </div>

        {/* 2. Assistente de IA */}
        <div className="space-y-2 rounded-lg border bg-white p-4">
          <Label className="text-base font-semibold text-gray-700 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-500" />
            Assistente de IA
          </Label>
          <p className="text-xs text-gray-500">
            Descreva brevemente o objetivo da aula, o tema ou a atividade. A NARA sugere
            uma sequência de atividades pra você revisar.
          </p>

          <Textarea
            placeholder="Ex.: Vou trabalhar contação de histórias com fantoches focando em escuta atenta..."
            className="min-h-[90px] resize-none"
            value={data.prompt_ia || ''}
            onChange={(event) => onDataChange('prompt_ia', event.target.value)}
          />
          {promptError && <p className="text-xs text-red-600">{promptError}</p>}

          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleSugerirAtividades}
              disabled={gerandoAtividades}
            >
              {gerandoAtividades ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Gerando...
                </>
              ) : (
                'Gerar atividades'
              )}
            </Button>
          </div>

          {atividadesSugeridas && (
            <div className="mt-2 rounded-lg border border-purple-100 bg-purple-50/40 p-3 space-y-2">
              <p className="text-xs font-medium text-roxo-principal">
                Sugestão pronta — revise e aplique:
              </p>
              <p className="whitespace-pre-wrap text-sm text-gray-700">
                {atividadesSugeridas}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => onAplicarAtividadesSugeridas?.('substituir')}
                >
                  Substituir Atividades
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onAplicarAtividadesSugeridas?.('anexar')}
                >
                  Anexar ao final
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* 3. Atividades Propostas */}
        <div className="space-y-2">
          <Label className="text-base font-semibold text-gray-700 flex items-center gap-2">
            <StickyNote className="h-4 w-4" />
            Atividades Propostas
          </Label>
          <Textarea
            placeholder="Descreva as atividades planejadas para este dia..."
            className="min-h-[160px] resize-none"
            value={data.atividades_propostas || ''}
            onChange={(event) => onDataChange('atividades_propostas', event.target.value)}
          />
        </div>

        {/* 4. Habilidades da BNCC */}
        <div className="space-y-2 rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <Label className="text-base font-semibold text-gray-700 flex items-center gap-2">
              <CheckSquare className="h-4 w-4" />
              Habilidades da BNCC
            </Label>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onSugerirBncc?.()}
              disabled={gerandoBncc}
            >
              {gerandoBncc ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Gerando...
                </>
              ) : (
                'Gerar BNCC'
              )}
            </Button>
          </div>

          <p className="text-xs text-gray-500">
            Geradas pela IA com base no texto de "Atividades Propostas".
          </p>

          {bnccError && <p className="text-xs text-red-600">{bnccError}</p>}
          {bnccMensagem && (
            <p className="text-xs text-gray-500">
              {bnccOrigem === 'fallback' ? '⚠️ ' : ''}
              {bnccMensagem}
            </p>
          )}

          {habilidades.length > 0 ? (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                {habilidades.map((skill) => (
                  <span
                    key={skill.codigo}
                    title={skill.descricao || ''}
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-purple-100 text-purple-800 rounded-full text-sm"
                  >
                    <span className="font-medium">{skill.codigo}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoverHabilidade(skill.codigo)}
                      className="hover:bg-purple-200 rounded-full p-0.5"
                      aria-label={`Remover ${skill.codigo}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {habilidades.map((skill) => (
                  <div key={`detail-${skill.codigo}`} className="p-3 bg-gray-50 border rounded-lg text-sm">
                    <div className="font-medium text-roxo-principal">{skill.codigo}</div>
                    {skill.descricao && (
                      <p className="text-gray-600 mt-1">{skill.descricao}</p>
                    )}
                    {skill.justificativa && (
                      <p className="text-blue-600 mt-1 text-xs italic">
                        {skill.justificativa}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">
              Nenhuma habilidade ainda. Preencha as atividades acima e clique em
              "Gerar habilidades BNCC".
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default DayPlanForm;
