import * as XLSX from 'xlsx';

function formatarData(dataExcel) {
  if (!dataExcel) return '';
  
  // Tenta converter diretamente. `raw: false` geralmente retorna a data formatada como string.
  const date = new Date(dataExcel);
  if (!isNaN(date.getTime()) && String(dataExcel).includes('/')) {
      const parts = String(dataExcel).split('/');
      if(parts.length === 3) {
          // Assuming dd/mm/yyyy or mm/dd/yyyy from sheet
          return String(dataExcel);
      }
  }

  // Se for um número (data serial do Excel)
  if (typeof dataExcel === 'number') {
      const excelEpoch = new Date(1899, 11, 30);
      const excelDate = new Date(excelEpoch.getTime() + dataExcel * 86400000);
      if (!isNaN(excelDate.getTime())) {
          return excelDate.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
      }
  }
  
  return String(dataExcel); // Retorna como string se não puder formatar
}


export const processUploadedFile = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        const worksheet = workbook.Sheets[workbook.SheetNames[0]];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { raw: false });

        const headerMapping = {
            'nome_aluno': ['nome_aluno', 'nome', 'aluno', 'Nome do Aluno'],
            'data_nascimento': ['data_nascimento', 'nascimento', 'Data de Nascimento', 'data_nasc', 'Data de Nasc.'],
            'nome_responsavel': ['nome_responsavel', 'responsavel', 'Nome do Responsável', 'Responsável'],
            'telefone_responsavel': ['telefone_responsavel', 'telefone', 'Telefone do Responsável', 'contato', 'Telefone']
        };

        const getColumnValue = (row, field) => {
            for (const key of headerMapping[field]) {
                if (row[key] !== undefined) return row[key];
            }
            return '';
        };

        const alunosFormatados = jsonData.map((aluno, index) => ({
          id: index,
          nome_aluno: String(getColumnValue(aluno, 'nome_aluno')).trim(),
          data_nascimento: formatarData(getColumnValue(aluno, 'data_nascimento')),
          nome_responsavel: String(getColumnValue(aluno, 'nome_responsavel')).trim(),
          telefone_responsavel: String(getColumnValue(aluno, 'telefone_responsavel')).trim(),
        }));

        resolve(alunosFormatados);
      } catch (error) {
        console.error("Erro ao processar planilha:", error);
        reject(new Error("Erro ao processar o arquivo. Verifique se o formato e os dados estão corretos."));
      }
    };
    reader.onerror = (error) => {
        reject(new Error("Não foi possível ler o arquivo."));
    };
    reader.readAsArrayBuffer(file);
  });
};