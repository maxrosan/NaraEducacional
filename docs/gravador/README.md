# Kit de testes — API do gravador NARA

Material para a equipe que desenvolve o microfone. Tudo aqui roda **sem
instalar bibliotecas**: só `curl` ou Python 3 puro (biblioteca padrão).

| Arquivo | Para quê |
|---|---|
| `testar_gravador.py` | Bateria completa em Python 3 (stdlib apenas). Mostra o multipart montado à mão — é a referência de bytes para o firmware |
| `testar_gravador.sh` | Mesmos testes só com `curl` (Git Bash, WSL ou Linux/macOS) |
| `esp32_exemplo.ino` | Sketch Arduino/ESP32 usando só `WiFi.h`, `HTTPClient.h` e `Preferences.h` |

A referência completa dos endpoints está na seção **"Gravador de áudio"** do
[README principal](../../README.md).

---

## O essencial em 1 minuto

O aparelho envia **apenas o áudio**. Professora, turma e escola vêm do vínculo
criado no pareamento — não existe campo de identidade no upload.

```
1. A escola gera um CÓDIGO na plataforma (admin → Cadastros → Dispositivos)
2. O aparelho troca esse código por um TOKEN permanente   → /api/dispositivos/parear/
3. A cada gravação, envia o WAV com o token no header      → /api/dispositivos/audio/
4. Consulta o desfecho e acende o LED                      → /api/dispositivos/audio/<upload_id>/
```

**WAV recomendado:** PCM 16 bits, **mono**, **16 kHz** — ideal para a
transcrição e ~10× menor que 44.1 kHz estéreo. Limite: **25 MB** (~13 min).

**Uma gravação por relato.** A professora fala tudo de uma vez:

> *"Estou na turma Nível 3A. Alice Marreiro brincou muito hoje."*

O servidor transcreve, tira a **turma** da própria fala, confere se ela está
liberada para este gravador e só então procura a criança entre os alunos dessa
turma. Se a professora atende mais de uma sala, ela não configura nada — só
anuncia. A turma anunciada continua valendo nas gravações seguintes até ela
anunciar outra.

**O firmware não entende nada disso.** Ele não transcreve, não conhece turmas e
não consulta nada antes de gravar: só manda o WAV e lê o `sinal` do feedback.
Toda a inteligência fica no servidor.

---

## Passo 1 — Obter um código de pareamento

Peça a quem administra a plataforma (ou faça você, se tiver acesso admin):

**Cadastros → Dispositivos → "Gerar código de pareamento"** → escolher a
professora e as turmas → aparece um código de 6 caracteres.

O código **vale 10 minutos e só pode ser usado uma vez**. Se expirar, gere outro.

---

## Passo 2 — Rodar os testes

### Opção A — Python (recomendada para a primeira integração)

```bash
# bateria completa: pareia, envia, testa retry e os erros previstos
python testar_gravador.py tudo --url http://IP_DO_SERVIDOR:8001 --codigo RHFF89

# ou passo a passo
python testar_gravador.py parear --url http://IP_DO_SERVIDOR:8001 \
    --codigo RHFF89 --device-id AA:BB:CC:11:22:33
python testar_gravador.py enviar --url http://IP_DO_SERVIDOR:8001
python testar_gravador.py enviar --url http://IP_DO_SERVIDOR:8001 --arquivo gravacao.wav
python testar_gravador.py feedback --url http://IP_DO_SERVIDOR:8001 --upload-id <uuid>
python testar_gravador.py status --url http://IP_DO_SERVIDOR:8001
```

O token fica salvo em `token.txt` na pasta do script. Sem `--arquivo`, ele gera
um WAV de teste de 3 s no formato recomendado — **grave um áudio de verdade**
(`--arquivo`) se quiser ver a turma e a criança sendo reconhecidas, porque o WAV
sintético é silêncio e não tem fala nenhuma.

Depois do envio, o script já consulta o feedback sozinho (`--sem-feedback`
desliga).

### Opção B — curl

```bash
./testar_gravador.sh parear   http://IP_DO_SERVIDOR:8001 RHFF89 AA:BB:CC:11:22:33
./testar_gravador.sh enviar   http://IP_DO_SERVIDOR:8001 gravacao.wav
./testar_gravador.sh feedback http://IP_DO_SERVIDOR:8001 <upload_id>
./testar_gravador.sh status   http://IP_DO_SERVIDOR:8001
```

### Opção C — direto no ESP32

Abra `esp32_exemplo.ino`, preencha `WIFI_SSID`, `WIFI_SENHA`, `API_BASE`,
`DEVICE_ID` e `CODIGO_PAREAMENTO`, e grave. O sketch pareia no primeiro boot,
guarda o token na NVS e envia 1 s de áudio de exemplo.

---

## Feedback: o que a professora precisa saber

O aparelho não tem tela, e **turma e criança só existem depois da transcrição**,
que é assíncrona. Por isso o `201` do upload significa apenas *"o arquivo
chegou"* — não *"o relato foi registrado"*.

Depois de enviar, consulte `GET /api/dispositivos/audio/<upload_id>/` a cada
~3 s. A resposta traz um bloco `feedback`, e **`sinal` é o único campo que o
firmware precisa ler**:

```json
{
  "status": "processado",
  "feedback": { "sinal": "ok", "mensagem": "Nível 3A · 1 criança registrada" },
  "turma": { "id": "...", "nome": "Nível 3A" },
  "turma_resultado": "anunciada",
  "alunos_identificados": ["Alice Marreiro"],
  "nomes_nao_identificados": []
}
```

| `sinal` | Significa | Sugestão de hardware |
|---|---|---|
| `aguardando` | Ainda processando | LED azul piscando; consultar de novo |
| `ok` | Turma resolvida e criança(s) registrada(s) | LED verde + bipe curto |
| `atencao` | Entrou, mas incompleto (ver abaixo) | LED amarelo + dois bipes |
| `erro` | Nada foi registrado | LED vermelho |

Os três casos de `atencao` — todos culpa do que foi falado, não do firmware:

| `turma_resultado` / `erro_codigo` | O que aconteceu | O que a professora faz |
|---|---|---|
| `nao_autorizada` | Ela anunciou uma turma que existe na escola mas **não está liberada** para este gravador | Falar a turma certa, ou pedir liberação na plataforma |
| `indefinida` | O gravador atende várias turmas e **nenhuma foi anunciada** | Repetir dizendo *"estou na turma Nível 3A"* |
| `nenhum_aluno` | A turma foi resolvida, mas nenhum nome bateu com as crianças dela | Repetir falando o nome com mais clareza |

Nesses casos **nada é gravado de propósito**: registrar na sala errada é pior do
que não registrar. O WAV continua no servidor e pode ser reprocessado.

`mensagem` é texto pronto em português, caso o aparelho ganhe display ou
alto-falante mais tarde. Se o firmware perder o `upload_id` (reboot no meio do
envio), `GET /api/dispositivos/status/` devolve o mesmo bloco em `ultimo_audio`.

## O que observar nas respostas do upload

| Situação | Resposta | O que o firmware faz |
|---|---|---|
| Áudio novo aceito | `201` + `"recebido": true` | Apagar o arquivo local e consultar o feedback |
| Retry do mesmo áudio | `200` + `"duplicado": true` | Idem — o servidor **não** duplicou |
| Token revogado/errado | `401 token_invalido` | Apagar o token salvo e parear de novo |
| Arquivo não é WAV | `400 wav_invalido` | Erro de firmware — não adianta repetir |
| Hash não confere | `400 hash_divergente` | Arquivo corrompido no envio — regravar |
| `upload_id` não é UUID | `400 upload_id_invalido` | Corrigir o gerador de UUID |
| Arquivo > 25 MB | `413 arquivo_grande` | Fatiar a gravação |
| Muitas requisições | `429` | Aguardar e repetir (upload: 10/min) |

### Regra de ouro do retry

Gere **um `upload_id` por gravação** e reutilize-o em **todas** as tentativas
daquele mesmo áudio. Assim:

- perdeu a resposta por timeout? reenvie — o servidor devolve `200` com
  `duplicado: true` e nada é duplicado no relatório da professora;
- gravação nova? `upload_id` novo.

Só **timeout** e erros **5xx** justificam retry. Os `4xx` da tabela acima são
definitivos: repetir sem corrigir a causa dá o mesmo erro.

---

## Perguntas frequentes

**Preciso enviar a data/hora da gravação?**
Não. O servidor carimba o horário de recebimento — o aparelho não precisa de RTC
nem de sincronizar relógio.

**E se a professora trocar de turma ou de sala?**
Ela fala a turma no microfone, na mesma gravação do relato. Se a mudança for
definitiva, a escola ajusta o vínculo na plataforma — **sem** mexer no aparelho
e **sem** trocar o token.

**O aparelho precisa reconhecer a fala "estou na turma X"?**
Não. Ele não transcreve nada e não sabe o que é uma turma. Quem reconhece é o
servidor, sobre o mesmo WAV que já foi enviado — não existe (nem é necessário)
um endpoint de "trocar de sala" para o firmware chamar.

**Quanto tempo até o feedback ficar pronto?**
Depende da fila de transcrição, tipicamente alguns segundos. Consulte a cada
~3 s; se passar do limite, não trave o aparelho: o relato entra do mesmo jeito e
a professora pode conferir na plataforma.

**Posso testar sem um código novo a cada vez?**
Sim: o token é permanente. Pareie uma vez e use `enviar`/`status` à vontade. Só
precisa de código novo se o token for perdido ou o dispositivo, revogado.

**O `device_id` precisa ser o MAC?**
Não obrigatoriamente — qualquer identificador estável e único do aparelho serve
(MAC ou serial do chip são as escolhas naturais). Ele é a chave que liga o
hardware ao cadastro: parear de novo com o mesmo `device_id` atualiza o mesmo
registro em vez de criar outro.
