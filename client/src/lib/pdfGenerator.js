import jsPDF from 'jspdf';
import 'jspdf-autotable';
import html2canvas from 'html2canvas';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { NARA_LOGO_URL } from '@/lib/branding';
import { authFetch, API_BASE_URL } from '@/services/api';

async function addImageWithCors(doc, url, x, y, w, h, options = {}) {
    if (!url) return;
    try {
        const response = await fetch(url);
        const blob = await response.blob();
        const inferredFormat = blob.type && blob.type.toLowerCase().includes('png') ? 'PNG' : 'JPEG';
        const { format = inferredFormat, compression = 'FAST' } = options;
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = function() {
                const dataUrl = reader.result;
                const img = new Image();
                img.src = dataUrl;
                img.onload = () => {
                    const aspectRatio = img.width / img.height;
                    let finalW = w;
                    let finalH = h;
                    if (w && !h) {
                        finalH = w / aspectRatio;
                    } else if (!w && h) {
                        finalW = h * aspectRatio;
                    }
                    doc.addImage(dataUrl, format, x, y, finalW, finalH, undefined, compression);
                    resolve();
                };
            };
            reader.readAsDataURL(blob);
        });
    } catch (error) {
        console.error("Error fetching image for PDF:", error);
    }
}

async function addHeader(doc, title, _institutionLogoUrl) {
  const logoUrl = NARA_LOGO_URL;
  await addImageWithCors(doc, logoUrl, 15, 10, 31.75, 0); // 120px converted to mm

  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor('#374151');
  doc.text(title, 50, 25);
  doc.setDrawColor('#E5E7EB');
  doc.line(15, 40, 195, 40);
}

function addFooter(doc) {
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor('#9CA3AF');
    doc.text(`Gerado por NARA em ${format(new Date(), 'dd/MM/yyyy HH:mm')}`, 15, 285);
    doc.text(`Página ${i} de ${pageCount}`, 180, 285);
  }
}

export const addNaraHeader = async (doc, title) => {
  await addHeader(doc, title);
};

/**
 * Replace external image `src` attributes in HTML with proxied data URLs.
 * Uses the backend `/api/proxy-imagem/` endpoint which also refreshes
 * expired S3 pre-signed URLs.
 *
 * @param {string} html - The HTML string containing <img> tags
 * @returns {Promise<string>} HTML with external image srcs replaced by data URLs
 */
export const proxyHtmlImages = async (html) => {
  if (!html) return html;

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  const images = doc.querySelectorAll('img');

  await Promise.all(
    Array.from(images).map(async (img) => {
      const src = img.getAttribute('src') || '';
      if (!src || src.startsWith('data:')) return;
      try {
        const resp = await authFetch(`${API_BASE_URL}/proxy-imagem/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: src }),
        });
        if (resp.ok) {
          const { data_url } = await resp.json();
          if (data_url) img.setAttribute('src', data_url);
        }
      } catch {
        // Leave original src — image may be missing
      }
    })
  );

  return doc.body.innerHTML;
};

export const generateReportPdf = async (student, reportData, institution) => {
  const doc = new jsPDF('p', 'mm', 'a4');
  await addHeader(doc, 'Relatório de Desenvolvimento');

  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.text(`Criança: ${student.nome_completo}`, 15, 50);
  doc.setFont('helvetica', 'normal');
  doc.text(`Turma: ${reportData.turma.nome}`, 15, 57);
  
  doc.setDrawColor('#E5E7EB');
  doc.line(15, 70, 195, 70);

  let yPos = 80;

  Object.entries(reportData.sections).forEach(([sectionTitle, sectionContent]) => {
    if (yPos > 250) {
      addFooter(doc);
      doc.addPage();
      yPos = 20;
    }
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor('#8A63D2');
    doc.text(sectionTitle, 15, yPos);
    yPos += 8;

    doc.setFontSize(11);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor('#374151');
    const splitText = doc.splitTextToSize(sectionContent.text || "Ainda sem informações nesta seção.", 180);
    doc.text(splitText, 15, yPos);
    yPos += splitText.length * 5 + 10;
  });

  if (reportData.portfolio.length > 0) {
    if (yPos > 220) {
      addFooter(doc);
      doc.addPage();
      yPos = 20;
    }
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor('#8A63D2');
    doc.text('Portfólio Visual', 15, yPos);
    yPos += 10;

    let xPos = 15;
    for (const item of reportData.portfolio) {
      if (yPos > 220) {
          addFooter(doc);
          doc.addPage();
          yPos = 20;
          xPos = 15;
      }
      await addImageWithCors(doc, item.url, xPos, yPos, 85, 0); 
      xPos += 95;
      if (xPos > 110) {
        yPos += 60;
        xPos = 15;
      }
    }
  }


  addFooter(doc);
  doc.save(`relatorio_${student.nome_completo.toLowerCase().replace(/ /g, '_')}.pdf`);
};

export const generatePlanningPdf = async (reportData) => {
  const doc = new jsPDF('p', 'mm', 'a4');
  await addHeader(doc, 'Planejamento Semanal');

  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.text(`Turma: ${reportData.turmaName}`, 15, 50);
  doc.setFont('helvetica', 'normal');
  doc.text(`Período: ${reportData.weekPeriod}`, 15, 57);

  doc.setDrawColor('#E5E7EB');
  doc.line(15, 65, 195, 65);

  const body = reportData.dailyPlans.map(plan => {
    const skillsLine = Array.isArray(plan.skills) && plan.skills.length
      ? plan.skills.map(s => s.codigo).filter(Boolean).join(', ')
      : 'N/A';
    const content = [
      { content: `Atividades: ${plan.atividades_propostas || plan.activities || 'N/A'}` },
      { content: `Habilidades BNCC: ${skillsLine}` },
    ];
    return [plan.day, content];
  });

  doc.autoTable({
    startY: 70,
    head: [['Dia da Semana', 'Detalhes do Planejamento']],
    body: body,
    theme: 'grid',
    headStyles: { fillColor: '#8A63D2' },
    didParseCell: function (data) {
        if (data.column.dataKey === 1) {
            data.cell.styles.cellPadding = 3;
        }
    },
  });

  addFooter(doc);
  doc.save(`planejamento_semanal_${reportData.turmaName.toLowerCase().replace(/ /g, '_')}.pdf`);
};

export const generateFamilyPlanningPdf = async (reportData) => {
  const doc = new jsPDF('p', 'mm', 'a4');
  await addHeader(doc, 'CRONOGRAMA SEMANAL');

  doc.setFontSize(11);
  doc.setFont('helvetica', 'bold');
  doc.text(`Turma: ${reportData.turmaName}`, 15, 50);
  doc.setFont('helvetica', 'normal');
  doc.text(`Semana: ${reportData.weekPeriod}`, 15, 56);

  doc.setDrawColor('#E5E7EB');
  doc.line(15, 62, 195, 62);

  const body = reportData.dailyPlans.map(plan => {
    const habilidades = plan.skills && plan.skills.length > 0
      ? plan.skills.map(skill => `${skill.codigo} - ${skill.descricao}`).join('\n')
      : '—';
    const habilidadesComDia = plan.day
      ? `${plan.day}\n${habilidades}`
      : habilidades;

    return [
      habilidadesComDia,
      plan.activities || '—',
      plan.homework || '—',
      plan.observations || '—'
    ];
  });

  doc.autoTable({
    startY: 68,
    head: [['HABILIDADES', 'ATIVIDADE PROPOSTA', 'ATIVIDADE DE CASA', 'OBSERVAÇÕES']],
    body,
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 9,
      textColor: '#374151',
      cellPadding: 2,
      overflow: 'linebreak',
      valign: 'top',
    },
    headStyles: {
      fillColor: '#EDE9FE',
      textColor: '#4C1D95',
      fontStyle: 'bold',
    },
    columnStyles: {
      0: { cellWidth: 50 },
      1: { cellWidth: 60 },
      2: { cellWidth: 40 },
      3: { cellWidth: 40 },
    },
    rowPageBreak: 'avoid',
  });

  addFooter(doc);
  doc.save(`cronograma_semanal_${reportData.turmaName.toLowerCase().replace(/ /g, '_')}.pdf`);
};

export const generateBnccCoveragePdf = async ({
  coverageByField = [],
  pendingSkills = [],
  filters = {},
  reportTitle = 'Cobertura por Campo de Experiência',
}) => {
  const doc = new jsPDF('p', 'mm', 'a4');
  await addHeader(doc, reportTitle);

  let yPos = 50;

  const filterEntries = Object.entries(filters).filter(([, value]) => value);
  if (filterEntries.length > 0) {
    doc.setFontSize(10);
    doc.setTextColor('#4B5563');
    doc.text(
      `Filtros: ${filterEntries.map(([label, value]) => `${label}: ${value}`).join(' | ')}`,
      15,
      yPos
    );
    yPos += 6;
  }

  yPos += 2;

  if (!coverageByField.length) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor('#6B7280');
    doc.text('Sem dados de cobertura disponíveis para os filtros selecionados.', 15, yPos);
    yPos += 8;
  } else {
    const barStartX = 15;
    const barWidth = 140;
    const barHeight = 5;

    coverageByField.forEach((item) => {
      if (yPos > 250) {
        addFooter(doc);
        doc.addPage();
        yPos = 20;
      }

      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor('#374151');
      doc.text(item.campo, 15, yPos);
      yPos += 4;

      doc.setDrawColor('#E5E7EB');
      doc.setFillColor('#F3F4F6');
      doc.rect(barStartX, yPos, barWidth, barHeight, 'F');

      const percentWidth = Math.max(0, Math.min(100, item.percent)) / 100 * barWidth;
      doc.setFillColor('#8A63D2');
      doc.rect(barStartX, yPos, percentWidth, barHeight, 'F');

      doc.setFontSize(9);
      doc.setTextColor('#111827');
      doc.text(`${item.percent}%`, barStartX + barWidth + 4, yPos + 4);

      yPos += 10;
    });
  }

  if (yPos > 230) {
    addFooter(doc);
    doc.addPage();
    yPos = 20;
  }

  doc.setFontSize(13);
  doc.setTextColor('#111827');
  doc.setFont('helvetica', 'bold');
  doc.text('Habilidades Pendentes', 15, yPos);
  yPos += 6;

  if (!pendingSkills.length) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor('#6B7280');
    doc.text('Nenhuma habilidade pendente encontrada para os filtros selecionados.', 15, yPos);
    yPos += 6;
  } else {
    const pendentesPorCampo = pendingSkills.reduce((acc, hab) => {
      const campo = hab.campo_experiencia || 'Outros';
      if (!acc[campo]) acc[campo] = [];
      acc[campo].push(hab);
      return acc;
    }, {});

    const camposOrdenados = Object.entries(pendentesPorCampo).sort((a, b) => b[1].length - a[1].length);

    camposOrdenados.forEach(([campo, habs]) => {
      if (yPos > 250) {
        addFooter(doc);
        doc.addPage();
        yPos = 20;
      }

      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor('#111827');
      doc.text(`${campo} (${habs.length})`, 15, yPos);
      yPos += 5;

      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor('#374151');

      habs.forEach((hab) => {
        const label = hab.pergunta_norma
          ? `${hab.pergunta_norma}: ${hab.pergunta}`
          : hab.pergunta;
        const lines = doc.splitTextToSize(`• ${label}`, 180);
        if (yPos + (lines.length * 4) > 270) {
          addFooter(doc);
          doc.addPage();
          yPos = 20;
        }
        doc.text(lines, 15, yPos);
        yPos += lines.length * 4;
      });

      yPos += 4;
    });
  }

  addFooter(doc);
  doc.save('cobertura_bncc.pdf');
};

export const generateClassReportPdf = async ({
  coverageByField = [],
  pendingSkills = [],
  filters = {},
  bnccCoverage = {},
  sugestoes = [],
  dadosSemanais = [],
  turmas = [],
  languageDevelopment = [],
  reportTitle = 'RELATÓRIO DA TURMA — PERÍODO',
}) => {
  const doc = new jsPDF('p', 'mm', 'a4');
  const marginX = 15;
  const contentWidth = 180;
  const lineColor = '#D1D5DB';

  await addImageWithCors(doc, NARA_LOGO_URL, 150, 12, 40, 0, { compression: 'FAST' });

  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor('#111827');
  doc.text(reportTitle, marginX, 28);

  const filterEntries = Object.entries(filters).filter(([, value]) => value);
  const filtersLabel = filterEntries.length
    ? filterEntries.map(([label, value]) => `${label}: ${value}`).join(' | ')
    : 'Sem filtros aplicados';

  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor('#374151');
  doc.text(`Filtros: ${filtersLabel}`, marginX, 38);
  doc.text(`Gerado em: ${format(new Date(), 'dd/MM/yyyy HH:mm', { locale: ptBR })}`, marginX, 44);

  doc.setDrawColor(lineColor);
  doc.line(marginX, 50, 195, 50);

  let yPos = 58;

  const ensureSpaceLocal = (heightNeeded) => {
    if (yPos + heightNeeded > 270) {
      doc.addPage();
      yPos = 20;
    }
  };

  const drawSectionHeader = (label, color) => {
    doc.setFillColor(color);
    doc.rect(marginX, yPos - 4, 4, 4, 'F');
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor('#111827');
    doc.text(label, marginX + 7, yPos);
    yPos += 6;
  };

  const drawDivider = () => {
    doc.setDrawColor(lineColor);
    doc.line(marginX, yPos, 195, yPos);
    yPos += 6;
  };

  const addTextBlock = (text, width = contentWidth, fontSize = 10) => {
    const safeText = text && text.trim() ? text : '—';
    doc.setFontSize(fontSize);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor('#374151');
    const lines = doc.splitTextToSize(safeText, width);
    ensureSpaceLocal(lines.length * 4.5 + 2);
    doc.text(lines, marginX, yPos);
    yPos += lines.length * 4.5 + 2;
  };

  const addTextSection = (label, color, text) => {
    const safeText = text && text.trim() ? text : '—';
    const lines = doc.splitTextToSize(safeText, contentWidth);
    ensureSpaceLocal(12 + lines.length * 4.5 + 8);
    drawSectionHeader(label, color);
    addTextBlock(safeText, contentWidth, 10);
    drawDivider();
  };

  const totalHabilidades = bnccCoverage?.totalHabilidades || 0;
  const habilidadesUsadas = bnccCoverage?.habilidadesUsadas || 0;
  const coveragePercent = totalHabilidades > 0
    ? Math.round((habilidadesUsadas / totalHabilidades) * 100)
    : 0;

  const sugestoesTexto = sugestoes.length > 0
    ? sugestoes.map((item) => `${item.titulo}: ${item.descricao}`).join(' ')
    : 'Nenhum alerta pedagógico identificado para este período.';

  const sinteseTexto = [
    `A cobertura atual da BNCC está em ${coveragePercent}% (${habilidadesUsadas} de ${totalHabilidades} habilidades).`,
    sugestoesTexto,
  ].join(' ');

  addTextSection('O que vivemos juntos neste bimestre', '#8B5CF6', sinteseTexto);

  const totalRegistros = turmas.reduce((acc, turma) => acc + (turma.registros || 0), 0);
  const mediaCobertura = turmas.length
    ? Math.round(turmas.reduce((acc, turma) => acc + (turma.cobertura || 0), 0) / turmas.length)
    : 0;
  const camposAtivos = bnccCoverage?.camposAtivos || 0;

  const observacoesTexto = [
    `Foram analisadas ${turmas.length || 0} turma(s), totalizando ${totalRegistros} registros.`,
    `A cobertura média por turma está em ${mediaCobertura}%.`,
    `Foram utilizados ${camposAtivos} de ${bnccCoverage?.totalCampos || 6} campos de experiência.`,
  ].join(' ');

  addTextSection('Observações gerais da turma', '#22C55E', observacoesTexto);

  if (languageDevelopment.length > 0) {
    const barWidth = 120;
    const barHeight = 3.5;
    ensureSpaceLocal(16 + languageDevelopment.length * 10);
    drawSectionHeader('Desenvolvimento de Linguagem por Turma', '#F59E0B');

    languageDevelopment.forEach((turma) => {
      ensureSpaceLocal(10);
      const percent = typeof turma.percentual_final === 'number' ? turma.percentual_final : 0;
      const label = turma.turma_nome || 'Turma';

      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor('#111827');
      doc.text(label, marginX, yPos);
      doc.setTextColor('#6B7280');
      doc.text(`${percent}%`, marginX + barWidth + 6, yPos);

      yPos += 3;
      doc.setFillColor('#E5E7EB');
      doc.rect(marginX, yPos, barWidth, barHeight, 'F');
      doc.setFillColor('#F59E0B');
      doc.rect(marginX, yPos, (barWidth * percent) / 100, barHeight, 'F');
      yPos += 7;
    });

    drawDivider();
  }

  if (turmas.length > 0) {
    ensureSpaceLocal(40);
    drawSectionHeader('Turmas analisadas', '#3B82F6');
    doc.autoTable({
      startY: yPos,
      columns: [
        { header: 'Turma', dataKey: 'turma' },
        { header: 'Cobertura', dataKey: 'cobertura' },
        { header: 'Habilidades', dataKey: 'habilidades' },
        { header: 'Registros', dataKey: 'registros' },
      ],
      body: turmas.map((turma) => ({
        turma: turma.nome,
        cobertura: `${turma.cobertura || 0}%`,
        habilidades: `${turma.habilidadesUsadas || 0}/${turma.totalHabilidades || 0}`,
        registros: turma.registros || 0,
      })),
      theme: 'grid',
      styles: {
        font: 'helvetica',
        fontSize: 9,
        textColor: '#111827',
        cellPadding: 2,
        valign: 'top',
      },
      headStyles: {
        fillColor: '#FFFFFF',
        textColor: '#111827',
        fontStyle: 'bold',
      },
      columnStyles: {
        turma: { cellWidth: 70 },
        cobertura: { cellWidth: 30 },
        habilidades: { cellWidth: 40 },
        registros: { cellWidth: 30 },
      },
    });
    yPos = doc.lastAutoTable.finalY + 6;
    drawDivider();
  }

  if (dadosSemanais.length > 0) {
    ensureSpaceLocal(30);
    drawSectionHeader('Engajamento semanal', '#F59E0B');
    doc.autoTable({
      startY: yPos,
      columns: [
        { header: 'Semana', dataKey: 'semana' },
        { header: 'Registros', dataKey: 'registros' },
      ],
      body: dadosSemanais.map((item) => ({
        semana: item.semana,
        registros: item.registros,
      })),
      theme: 'grid',
      styles: {
        font: 'helvetica',
        fontSize: 9,
        textColor: '#111827',
        cellPadding: 2,
        valign: 'top',
      },
      headStyles: {
        fillColor: '#FFFFFF',
        textColor: '#111827',
        fontStyle: 'bold',
      },
      columnStyles: {
        semana: { cellWidth: 60 },
        registros: { cellWidth: 40 },
      },
    });
    yPos = doc.lastAutoTable.finalY + 6;
    drawDivider();
  }

  ensureSpaceLocal(30);
  drawSectionHeader('Cobertura por campo de experiência', '#6366F1');

  if (!coverageByField.length) {
    addTextBlock('Sem dados de cobertura disponíveis para os filtros selecionados.');
  } else {
    const barStartX = marginX;
    const barWidth = 140;
    const barHeight = 5;

    coverageByField.forEach((item) => {
      ensureSpaceLocal(12);
      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor('#374151');
      doc.text(item.campo, marginX, yPos);
      yPos += 4;

      doc.setDrawColor('#E5E7EB');
      doc.setFillColor('#F3F4F6');
      doc.rect(barStartX, yPos, barWidth, barHeight, 'F');

      const percentWidth = Math.max(0, Math.min(100, item.percent)) / 100 * barWidth;
      doc.setFillColor('#8B5CF6');
      doc.rect(barStartX, yPos, percentWidth, barHeight, 'F');

      doc.setFontSize(9);
      doc.setTextColor('#111827');
      doc.text(`${item.percent}%`, barStartX + barWidth + 4, yPos + 4);

      yPos += 10;
    });
  }

  drawDivider();

  ensureSpaceLocal(20);
  drawSectionHeader('Habilidades pendentes', '#EF4444');

  if (!pendingSkills.length) {
    addTextBlock('Nenhuma habilidade pendente encontrada para os filtros selecionados.');
  } else {
    const pendentesPorCampo = pendingSkills.reduce((acc, hab) => {
      const campo = hab.campo_experiencia || 'Outros';
      if (!acc[campo]) acc[campo] = [];
      acc[campo].push(hab);
      return acc;
    }, {});

    const camposOrdenados = Object.entries(pendentesPorCampo).sort((a, b) => b[1].length - a[1].length);

    camposOrdenados.forEach(([campo, habs]) => {
      ensureSpaceLocal(10);
      doc.setFontSize(10);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor('#111827');
      doc.text(`${campo} (${habs.length})`, marginX, yPos);
      yPos += 5;

      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor('#374151');

      habs.forEach((hab) => {
        const label = hab.pergunta_norma
          ? `${hab.pergunta_norma}: ${hab.pergunta}`
          : hab.pergunta;
        const lines = doc.splitTextToSize(`• ${label}`, contentWidth);
        ensureSpaceLocal(lines.length * 4 + 2);
        doc.text(lines, marginX, yPos);
        yPos += lines.length * 4;
      });

      yPos += 3;
    });
  }

  addFooter(doc);
  doc.save('relatorio_turma.pdf');
};

export const generatePortfolioPdf = async (student) => {
    const doc = new jsPDF('p', 'mm', 'a4');
    await addHeader(doc, `Portfólio de ${student.name}`);

    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text(`Turma: ${student.turma}`, 15, 50);
    doc.setFont('helvetica', 'normal');
    doc.text(`Idade: ${student.age}`, 15, 57);
    
    doc.setDrawColor('#E5E7EB');
    doc.line(15, 65, 195, 65);

    let y = 75;
    for (const media of student.portfolioMedia) {
        if (y > 190) {
            addFooter(doc);
            doc.addPage();
            y = 20;
        }
        if (media.type === 'image') {
            await addImageWithCors(doc, media.url, 15, y, 80, 60);
        } else if (media.type === 'video') {
            await addImageWithCors(doc, media.thumbnail, 15, y, 80, 60);
            doc.text('[VÍDEO]', 48, y + 30);
        }
        
        doc.setFontSize(10);
        const captionText = doc.splitTextToSize(media.caption, 85);
        doc.text(captionText, 105, y + 5);

        doc.setFontSize(8);
        doc.setTextColor('#6B7280');
        doc.text(`Data: ${format(new Date(media.date), 'dd/MM/yyyy', { locale: ptBR })}`, 105, y + 10 + (captionText.length * 4));
        if (media.project) {
            doc.text(`Projeto: ${media.project}`, 105, y + 15 + (captionText.length * 4));
        }
        doc.setTextColor('#000000');

        y += 70;
    }

    addFooter(doc);
    doc.save(`portfolio_${student.name.toLowerCase().replace(' ', '_')}.pdf`);
};

const ensureSpace = (doc, yPos, heightNeeded = 10) => {
  if (yPos + heightNeeded > 270) {
    addFooter(doc);
    doc.addPage();
    return 20;
  }
  return yPos;
};

const addSectionTitle = (doc, title, yPos) => {
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor('#4B5563');
  doc.text(title, 15, yPos);
  return yPos + 6;
};

const addParagraph = (doc, text, yPos, fontSize = 10) => {
  const safeText = text && text.trim() ? text : '—';
  doc.setFontSize(fontSize);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor('#374151');
  const lines = doc.splitTextToSize(safeText, 180);
  doc.text(lines, 15, yPos);
  return yPos + (lines.length * 4.5);
};

export const buildBimonthlyReportPdf = async ({
  studentName,
  turmaName,
  periodoLabel,
  reportText,
  planningSummary,
  productionAnalyses = [],
  portfolioItems = [],
  specialistsSummary = '',
  bnccSummary = [],
  professorName = '',
  conclusionText = '',
}) => {
  const doc = new jsPDF('p', 'mm', 'a4');
  const marginX = 15;
  const contentWidth = 180;
  const lineColor = '#D1D5DB';
  const title = `RELATÓRIO BIMESTRAL — ${periodoLabel || 'PERÍODO'}`;

  await addImageWithCors(doc, NARA_LOGO_URL, 150, 12, 40, 0, { compression: 'FAST' });

  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor('#111827');
  doc.text(title, marginX, 28);

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text(`Nome da criança: ${studentName}`, marginX, 38);
  doc.text(`Turma: ${turmaName || 'Não informada'}`, marginX, 44);
  doc.text(`Período: ${periodoLabel || 'Não informado'}`, marginX, 50);
  doc.text(`Professora: ${professorName || '—'}`, marginX, 56);

  doc.setDrawColor(lineColor);
  doc.line(marginX, 62, 195, 62);

  let yPos = 70;

  const ensureSpaceLocal = (heightNeeded) => {
    if (yPos + heightNeeded > 270) {
      doc.addPage();
      yPos = 20;
    }
  };

  const drawSectionHeader = (label, color) => {
    doc.setFillColor(color);
    doc.rect(marginX, yPos - 4, 4, 4, 'F');
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor('#111827');
    doc.text(label, marginX + 7, yPos);
    yPos += 6;
  };

  const drawDivider = () => {
    doc.setDrawColor(lineColor);
    doc.line(marginX, yPos, 195, yPos);
    yPos += 6;
  };

  const addTextBlock = (text, width = contentWidth, fontSize = 10) => {
    const safeText = text && text.trim() ? text : '—';
    doc.setFontSize(fontSize);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor('#374151');
    const lines = doc.splitTextToSize(safeText, width);
    ensureSpaceLocal(lines.length * 4.5 + 2);
    doc.text(lines, marginX, yPos);
    yPos += lines.length * 4.5 + 2;
  };

  const addTextSection = (label, color, text) => {
    const safeText = text && text.trim() ? text : '—';
    const lines = doc.splitTextToSize(safeText, contentWidth);
    ensureSpaceLocal(12 + lines.length * 4.5 + 8);
    drawSectionHeader(label, color);
    addTextBlock(safeText, contentWidth, 10);
    drawDivider();
  };

  const addAnalysisSection = async ({ label, color, text, imageUrl }) => {
    const safeText = text && text.trim() ? text : '—';
    const hasImage = Boolean(imageUrl);
    const imageWidth = 55;
    const imageHeight = 35;
    const textWidth = hasImage ? 115 : contentWidth;
    const lines = doc.splitTextToSize(safeText, textWidth);
    const textHeight = lines.length * 4.5;
    const blockHeight = Math.max(textHeight, hasImage ? imageHeight : 0);

    ensureSpaceLocal(12 + blockHeight + 8);
    drawSectionHeader(label, color);

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor('#374151');
    doc.text(lines, marginX, yPos);

    if (hasImage) {
      await addImageWithCors(doc, imageUrl, 140, yPos - 2, imageWidth, imageHeight, { compression: 'FAST' });
    }

    yPos += blockHeight + 4;
    drawDivider();
  };

  const findAnalysis = (keyword) => {
    const lowered = keyword.toLowerCase();
    return productionAnalyses.find((analysis) => (analysis.tipo || '').toLowerCase().includes(lowered));
  };

  addTextSection('O que vivemos juntos neste bimestre', '#8B5CF6', planningSummary);
  addTextSection(`Observações individuais sobre ${studentName}`, '#22C55E', reportText);

  const analiseEscrita = findAnalysis('escrita');
  const analiseDesenho = findAnalysis('desenho');
  const analiseLeitura = findAnalysis('leitura');

  await addAnalysisSection({
    label: 'Análise da Escrita',
    color: '#F59E0B',
    text: analiseEscrita?.resumo || analiseEscrita?.texto || '',
    imageUrl: analiseEscrita?.url,
  });

  await addAnalysisSection({
    label: 'Análise do Desenho',
    color: '#3B82F6',
    text: analiseDesenho?.resumo || analiseDesenho?.texto || '',
    imageUrl: analiseDesenho?.url,
  });

  await addAnalysisSection({
    label: 'Análise da Leitura (a escola escolhe a partir de que turma terá)',
    color: '#06B6D4',
    text: analiseLeitura?.resumo || analiseLeitura?.texto || '',
    imageUrl: analiseLeitura?.url,
  });

  const portfolioLabel = 'Portfólio (evidências)';
  const portfolioColor = '#F97316';
  const portfolioItemsToShow = portfolioItems.slice(0, 4);
  const captionsToShow = portfolioItems.slice(0, 3);
  const gridHeight = portfolioItemsToShow.length ? 115 : 0;
  const captionHeight = captionsToShow.length ? captionsToShow.length * 12 : 12;

  ensureSpaceLocal(12 + gridHeight + captionHeight + 12);
  drawSectionHeader(portfolioLabel, portfolioColor);

  if (!portfolioItemsToShow.length) {
    addTextBlock('Sem registros de portfólio para este período.');
    drawDivider();
  } else {
    const grid = [
      { x: marginX, y: yPos, w: 85, h: 55 },
      { x: 110, y: yPos, w: 85, h: 55 },
      { x: marginX, y: yPos + 60, w: 85, h: 55 },
      { x: 110, y: yPos + 60, w: 85, h: 55 },
    ];

    for (let i = 0; i < portfolioItemsToShow.length; i += 1) {
      const target = grid[i];
      const item = portfolioItemsToShow[i];
      await addImageWithCors(doc, item.url, target.x, target.y, target.w, target.h, { compression: 'FAST' });
    }

    yPos += gridHeight + 4;

    doc.setFontSize(9);
    doc.setTextColor('#111827');
    captionsToShow.forEach((item, index) => {
      const title = item.tag || 'Registro';
      const description = item.caption || '';
      doc.setFont('helvetica', 'bold');
      doc.text(`${index + 1}. ${title}`, marginX, yPos);
      yPos += 4;
      if (description) {
        doc.setFont('helvetica', 'italic');
        const lines = doc.splitTextToSize(description, contentWidth - 10);
        doc.text(lines, marginX + 5, yPos);
        yPos += lines.length * 4 + 2;
      } else {
        yPos += 2;
      }
    });

    drawDivider();
  }

  addTextSection('Registros dos especialistas', '#6B7280', specialistsSummary);

  if (yPos > 200) {
    doc.addPage();
    yPos = 20;
  }

  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor('#111827');
  doc.text('Acompanhamento das Habilidades e Competências da BNCC', marginX, yPos);
  yPos += 6;

  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor('#374151');
  const bnccIntro = 'Abaixo estão algumas das habilidades observadas durante o período.';
  const introLines = doc.splitTextToSize(bnccIntro, contentWidth);
  doc.text(introLines, marginX, yPos);
  yPos += introLines.length * 4.2 + 4;

  const bnccRows = bnccSummary.flatMap((campo) =>
    campo.habilidades.map((hab) => {
      const baseText = hab.texto || '—';
      const label = hab.codigo ? `${hab.codigo} - ${baseText}` : baseText;
      return {
        habilidade: label,
        status: hab.status?.label || '—',
        statusTone: hab.status?.tone || 'neutral',
      };
    })
  );

  if (!bnccRows.length) {
    addTextBlock('Nenhuma observação BNCC encontrada para este período.', contentWidth, 9);
  } else {
    doc.autoTable({
      startY: yPos,
      columns: [
        { header: 'Habilidade da BNCC', dataKey: 'habilidade' },
        { header: 'Nível observado', dataKey: 'status' },
      ],
      body: bnccRows,
      theme: 'grid',
      styles: {
        font: 'helvetica',
        fontSize: 9,
        textColor: '#111827',
        cellPadding: 2,
        valign: 'top',
      },
      headStyles: {
        fillColor: '#FFFFFF',
        textColor: '#111827',
        fontStyle: 'bold',
      },
      columnStyles: {
        habilidade: { cellWidth: 130 },
        status: { cellWidth: 50 },
      },
      didParseCell: (data) => {
        if (data.column.dataKey === 'status') {
          data.cell.styles.cellPadding = { top: 2, right: 2, bottom: 2, left: 7 };
        }
      },
      didDrawCell: (data) => {
        if (data.section !== 'body' || data.column.dataKey !== 'status') return;
        const tone = data.row.raw.statusTone;
        const colorMap = {
          positive: '#22C55E',
          progress: '#F59E0B',
          negative: '#EF4444',
          neutral: '#9CA3AF',
        };
        const color = colorMap[tone] || colorMap.neutral;
        doc.setFillColor(color);
        doc.rect(data.cell.x + 2, data.cell.y + 2, 3, 3, 'F');
      },
    });

    yPos = doc.lastAutoTable.finalY + 6;
  }

  const conclusion = conclusionText && conclusionText.trim() ? conclusionText : '—';
  const conclusionLines = doc.splitTextToSize(conclusion, contentWidth);
  ensureSpaceLocal(12 + conclusionLines.length * 4.5 + 4);
  drawSectionHeader('Conclusão da professora', '#4B5563');
  addTextBlock(conclusion, contentWidth, 10);

  addFooter(doc);
  return doc.output('blob');
};

/**
 * Generate a PDF from HTML content using html2canvas.
 * Renders the HTML in an off-screen container styled with ProseMirror CSS,
 * captures it at A4 proportions, and paginates intelligently at natural
 * break points (sections, table rows, paragraphs).
 *
 * @param {string} htmlContent - The HTML string (from the rich text editor)
 * @param {string} filename    - Desired filename for the downloaded PDF
 */
export const generatePdfFromHtml = async (htmlContent, filename) => {
  const A4_WIDTH_PX = 794;
  const A4_HEIGHT_PX = 1123;
  const RENDER_SCALE = 2;

  let container;
  try {
    container = document.createElement('div');
    container.className = 'ProseMirror';
    container.style.cssText =
      `position:absolute;left:-9999px;top:0;background:#fff;` +
      `width:${A4_WIDTH_PX}px;`;
    container.innerHTML = htmlContent;
    document.body.appendChild(container);

    // Convert external images to data URLs via backend proxy (avoids CORS)
    const images = container.querySelectorAll('img');
    await Promise.all(
      Array.from(images).map(async (img) => {
        const src = img.getAttribute('src') || '';
        if (!src || src.startsWith('data:')) return;
        try {
          const resp = await authFetch(`${API_BASE_URL}/proxy-imagem/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: src }),
          });
          if (resp.ok) {
            const { data_url } = await resp.json();
            if (data_url) img.src = data_url;
          }
        } catch {
          // Image will be missing in PDF — non-critical
        }
      })
    );

    // Wait for images to render
    await Promise.all(
      Array.from(images).map(
        (img) =>
          new Promise((resolve) => {
            if (img.complete) return resolve();
            img.onload = resolve;
            img.onerror = resolve;
          })
      )
    );

    // Wait for fonts to load
    if (document.fonts?.ready) {
      await document.fonts.ready;
    }

    const pages = container.querySelectorAll('.pagina');
    const pdf = new jsPDF('p', 'mm', 'a4');
    const pageW = 210; // mm
    const pageH = 297; // mm
    const MARGIN_MM = 6;
    let isFirstPdfPage = true;

    const collectBreakPoints = (element) => {
      const elementRect = element.getBoundingClientRect();
      const selectors = [
        '.secao',
        '.secao-header',
        '.secao-body',
        '.rodape',
        '.barra-rodape',
        '.ficha-aluno',
        '.banner-relatorio',
        '.header-escola',
        '.bncc-tabela tbody tr',
        '.secao-body p',
        '.portfolio-item',
        '.producao-bloco',
      ];
      const points = new Set();
      for (const sel of selectors) {
        for (const child of element.querySelectorAll(sel)) {
          const rect = child.getBoundingClientRect();
          points.add(Math.round((rect.bottom - elementRect.top) * RENDER_SCALE));
          points.add(Math.round((rect.top - elementRect.top) * RENDER_SCALE));
        }
      }
      return Array.from(points).sort((a, b) => a - b);
    };

    const renderElementToPages = async (element) => {
      const canvas = await html2canvas(element, {
        scale: RENDER_SCALE,
        useCORS: false,
        logging: false,
        width: A4_WIDTH_PX,
        windowWidth: A4_WIDTH_PX,
      });

      const a4CanvasH = A4_HEIGHT_PX * RENDER_SCALE;
      const pxPerMM = a4CanvasH / pageH;

      if (canvas.height <= a4CanvasH * 1.08) {
        if (!isFirstPdfPage) pdf.addPage();
        isFirstPdfPage = false;
        const imgData = canvas.toDataURL('image/jpeg', 0.95);
        const drawH = Math.min(canvas.height / pxPerMM, pageH);
        pdf.addImage(imgData, 'JPEG', 0, 0, pageW, drawH);
        return;
      }

      const breakPoints = collectBreakPoints(element);
      const marginPx = Math.round(MARGIN_MM * pxPerMM);
      let srcY = 0;
      let sliceIndex = 0;

      while (srcY < canvas.height) {
        if (!isFirstPdfPage) pdf.addPage();
        isFirstPdfPage = false;

        const isFirst = sliceIndex === 0;
        const topMarginPx = isFirst ? 0 : marginPx;
        const bottomMarginPx = marginPx;
        const usableH = a4CanvasH - topMarginPx - bottomMarginPx;
        const idealCutY = srcY + usableH;

        let cutY;
        if (idealCutY >= canvas.height) {
          cutY = canvas.height;
        } else {
          const minCutY = srcY + usableH * 0.6;
          let bestBP = idealCutY;
          for (const bp of breakPoints) {
            if (bp <= srcY) continue;
            if (bp > idealCutY) break;
            if (bp >= minCutY) bestBP = bp;
          }
          cutY = bestBP;
        }

        const srcH = cutY - srcY;
        const sliceCanvas = document.createElement('canvas');
        sliceCanvas.width = canvas.width;
        sliceCanvas.height = srcH;
        const ctx = sliceCanvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
        ctx.drawImage(canvas, 0, srcY, canvas.width, srcH, 0, 0, canvas.width, srcH);

        const imgData = sliceCanvas.toDataURL('image/jpeg', 0.95);
        const drawH = srcH / pxPerMM;
        const topMM = isFirst ? 0 : MARGIN_MM;
        pdf.addImage(imgData, 'JPEG', 0, topMM, pageW, drawH);

        srcY = cutY;
        sliceIndex++;
      }
    };

    if (pages.length > 0) {
      for (const page of pages) {
        await renderElementToPages(page);
      }
    } else {
      await renderElementToPages(container);
    }

    document.body.removeChild(container);
    container = null;

    pdf.save(filename);
  } catch (err) {
    console.error('Erro ao gerar PDF:', err);
    if (container?.parentNode) container.parentNode.removeChild(container);
    throw err;
  }
};
