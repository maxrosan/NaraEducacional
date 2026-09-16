/**
 * Vazamento de object URL no preview de mídias.
 *
 * O preview criava a URL do blob direto no `src` da <img> e de novo no clique
 * de visualizar, sem nunca chamar revokeObjectURL. Cada re-render prendia mais
 * um blob — uma foto ou vídeo inteiro — na aba até a página ser recarregada.
 *
 * O que estes testes travam: uma URL por arquivo (não por render), e toda URL
 * criada é revogada quando o preview sai de cena.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MediaAnalysisModal } from '@/components/observations/MediaAnalysisModal';

const ALUNOS = [{ id: '1', name: 'Ana Silva' }];

/**
 * Registra as URLs criadas e revogadas para poder comparar os dois conjuntos.
 *
 * Atribui as funções em vez de usar vi.spyOn: o jsdom não implementa
 * createObjectURL/revokeObjectURL, então não há nada para espionar.
 */
function espionarObjectUrl() {
  const criadas = [];
  const revogadas = [];
  let contador = 0;

  const originais = {
    create: URL.createObjectURL,
    revoke: URL.revokeObjectURL,
  };

  URL.createObjectURL = () => {
    const url = `blob:teste/${++contador}`;
    criadas.push(url);
    return url;
  };
  URL.revokeObjectURL = (url) => {
    revogadas.push(url);
  };

  return {
    criadas,
    revogadas,
    /** URLs criadas que nunca foram revogadas — o vazamento em si. */
    vazadas: () => criadas.filter((u) => !revogadas.includes(u)),
    restaurar: () => {
      URL.createObjectURL = originais.create;
      URL.revokeObjectURL = originais.revoke;
    },
  };
}

function imagem(nome) {
  return new File(['conteudo-binario-da-foto'], nome, { type: 'image/jpeg' });
}

async function abrirModalComArquivos(user, arquivos) {
  const { container, unmount } = render(
    <MediaAnalysisModal
      students={ALUNOS}
      analysisType="media"
      onSave={() => {}}
      triggerButton={<button type="button">Abrir</button>}
    />
  );

  await user.click(screen.getByRole('button', { name: 'Abrir' }));

  // O input de arquivo fica no DOM independentemente do <Select> de criança,
  // então dá para anexar sem passar pelo Radix Select (que não funciona bem
  // sob jsdom por depender de pointer events).
  const input = document.querySelector('input[type="file"]');
  await user.upload(input, arquivos);

  return { container, unmount, input };
}

describe('FilePreview — object URLs', () => {
  let espiao;
  let user;

  beforeEach(() => {
    espiao = espionarObjectUrl();
    user = userEvent.setup();
  });

  afterEach(() => {
    espiao.restaurar();
    vi.restoreAllMocks();
  });

  it('cria uma única URL por arquivo, não uma por render', async () => {
    const { unmount } = await abrirModalComArquivos(user, [imagem('foto1.jpg')]);

    await waitFor(() => expect(espiao.criadas.length).toBe(1));

    // Anexar um segundo arquivo re-renderiza o preview do primeiro. Com o
    // código antigo, o src inline geraria outra URL para 'foto1' aqui.
    const input = document.querySelector('input[type="file"]');
    await user.upload(input, [imagem('foto2.jpg')]);

    await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(2));
    expect(espiao.criadas).toHaveLength(2);

    unmount();
  });

  it('usa a URL criada como src da imagem', async () => {
    const { unmount } = await abrirModalComArquivos(user, [imagem('foto.jpg')]);

    await waitFor(() => {
      expect(screen.getByRole('img')).toHaveAttribute('src', espiao.criadas[0]);
    });

    unmount();
  });

  it('revoga todas as URLs ao desmontar', async () => {
    const { unmount } = await abrirModalComArquivos(user, [
      imagem('foto1.jpg'),
      imagem('foto2.jpg'),
    ]);

    await waitFor(() => expect(espiao.criadas).toHaveLength(2));

    unmount();

    await waitFor(() => expect(espiao.vazadas()).toEqual([]));
  });

  it('revoga a URL do arquivo removido pelo X', async () => {
    const { unmount } = await abrirModalComArquivos(user, [
      imagem('foto1.jpg'),
      imagem('foto2.jpg'),
    ]);

    await waitFor(() => expect(espiao.criadas).toHaveLength(2));

    // A lista usa key={index}: remover o primeiro faz o React reaproveitar a
    // instância com outro `file`. O efeito precisa revogar a URL antiga e criar
    // a do novo arquivo — senão sobra um blob preso sem nenhum preview na tela.
    const remover = screen
      .getAllByRole('button')
      .filter((b) => b.className.includes('destructive'));
    await user.click(remover[0]);

    await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(1));

    const visivel = screen.getByRole('img').getAttribute('src');
    await waitFor(() => {
      // Tudo que não está na tela foi revogado.
      expect(espiao.vazadas()).toEqual([visivel]);
    });

    unmount();
    await waitFor(() => expect(espiao.vazadas()).toEqual([]));
  });

  it('não deixa URL pendurada ao fechar o modal', async () => {
    const { unmount } = await abrirModalComArquivos(user, [imagem('foto.jpg')]);

    await waitFor(() => expect(espiao.criadas).toHaveLength(1));

    await user.keyboard('{Escape}');

    await waitFor(() => expect(espiao.vazadas()).toEqual([]));

    unmount();
  });
});
