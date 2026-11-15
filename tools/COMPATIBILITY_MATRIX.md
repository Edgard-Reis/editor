# DRIFIT EDITOR — MATRIZ DE COMPATIBILIDADE E GOVERNANÇA DE FERRAMENTAS
# `tools/COMPATIBILITY_MATRIX.md`

**Data de Publicação:** 05 de novembro de 2026  
**Status Oficial:** ATIVO E HOMOLOGADO EM PRODUÇÃO  
**Localização Central:** `D:\Drifit\Editor\tools\`

---

## 1. Visão Geral e Princípio Arquitetural

O Drifit Editor opera com uma arquitetura de renderização **local, determinística, reproduzível e sem dependências externas obrigatórias**. 

Isso assegura que todas as ferramentas essenciais para compilação e renderização de episódios residam diretamente no repositório do projeto ou no ambiente controlado da máquina host, eliminando:
- Invocação de utilitários como `npx` que realizam consultas automáticas à rede;
- Downloads automáticos de pacotes ou navegadores durante o processo de renderização;
- Dependência obrigatória de Content Delivery Networks (CDNs como `cdn.jsdelivr.net`) para bibliotecas de animação essenciais (ex.: GSAP).

A conectividade externa à internet da máquina continua ativa para ferramentas de produtividade, modelos de inteligência artificial (Antigravity, Gemini, OpenCode) e transações convencionais. Contudo, **a cadeia audiovisual não depende de conexão ativa para renderizar**.

---

## 2. Versões Homologadas na Toolchain Oficial (`tools/hyperframes/`)

| Componente | Versão Fixada | Função no Pipeline | Origem / Localização | SHA-256 Registrado |
|---|---|---|---|---|
| **HyperFrames CLI** | `0.9.5` | Motor de composição e renderização | `tools/hyperframes/node_modules/hyperframes/` | `E65ED25C36426B6E...` |
| **FFmpeg** | `9.0.2-essentials` | Transcoder, mixer e muxer master | `tools/hyperframes/bin/windows-x64/ffmpeg.exe` | `3256173F3F8BFFD7...` |
| **FFprobe** | `9.0.2-essentials` | Analisador de metadados e áudio | `tools/hyperframes/bin/windows-x64/ffprobe.exe` | `F0D36ECBBDD3BCFA...` |
| **GSAP** | `3.14.2` | Biblioteca de interpolação e animação | `tools/hyperframes/assets/gsap/3.14.2/gsap.min.js` | `C174BFCE53A72941...` |

---

## 3. Dependências de Ambiente do Sistema Operacional

| Dependência | Versão Mínima / Homologada | Localização Padrão | Observações |
|---|---|---|---|
| **Node.js** | v20+ (Homologado: `v22.18.0`) | `C:\Program Files\nodejs\node.exe` | Utilizado para executar diretamente o `hyperframes.mjs` sem intermediários de pacote. |
| **Python** | 3.11+ (Homologado: `3.11.15`) | PATH do sistema / Ambiente virtual | Executa os scripts de compilação (`build.py`) e renderização (`render_rapido.py`). |
| **Chrome Headless Shell** | `win64-152.0.7977.30` | `~/.cache/hyperframes/chrome/...` | Binário headless gerenciado pelo HyperFrames para extração de quadros no Puppeteer. |

---

## 4. Plataformas Testadas e Suportadas

- **Windows 11 / Windows Server x64:** 100% Homologado e ativo como plataforma primária.
- **Linux x64 / macOS arm64:** Arquiteturalmente suportado (requer disponibilização dos binários nativos equivalentes de FFmpeg e Chrome nas respectivas subpastas da toolchain).

---

## 5. Política de Codificação e Não Regressão

O pipeline canônico utiliza uma arquitetura de codificação em **dois estágios**:

1. **Estágio 1 — Trechos Intermediários com Animação (HyperFrames):**  
   - Argumento: `--crf 8`
   - Objetivo: Geração de arquivos intermediários no cache `.trechos/` com compressão quase sem perdas (near-lossless), preservando nitidez vetorial e tipográfica máxima.
2. **Estágio 2 — Concatenação e Masterização Final (FFmpeg `junta()`):**  
   - Argumentos: `-c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p`
   - Tratamento de Áudio: Mixagem estéreo com normalização EBU R128 (`loudnorm=I=-14:TP=-1:LRA=11`), saída AAC a 320 kbps e 48 kHz.
   - Reúso de Base: Os trechos sem animação são copiados diretamente do vídeo original (`base.mp4`) sem passar pelo navegador, acelerando drasticamente o tempo de entrega.

---

## 6. Limitações Conhecidas e Recomendações Operacionais

1. **Comunicação de Loopback no Windows:**  
   O HyperFrames utiliza sockets TCP em `localhost` para conectar os workers do Chrome headless ao servidor HTTP da composição. Em ambientes de sandbox com isolamento estrito de portas de rede local, a execução deve permitir loopback (ex.: `BypassSandbox: true`).
2. **Gerenciamento de Cache de Quadros:**  
   O HyperFrames extrai quadros temporários em `AppData\Local\Temp\`. O renderizador `render_rapido.py` realiza a limpeza automática desses diretórios temporários a cada trecho processado para evitar saturação de disco.

---

## 7. Política Central de Atualização e Governança

Para garantir estabilidade contínua e prevenir quebras inesperadas no fluxo de edição:

1. **Imutabilidade em Produção:** O ambiente de produção opera exclusivamente com versões fixadas no manifesto `tools/hyperframes/TOOLCHAIN_MANIFEST.json`.
2. **Proibição de Atualização Automática:** É terminantemente proibido o uso de `npm update`, `npm install` sem argumentos ou scripts de auto-update na pasta `tools/`.
3. **Verificação Mensal:** Revisão mensal de notas de versão e correções de segurança das ferramentas base.
4. **Avaliação Trimestral:** Análise trimestral de melhorias de desempenho que justifiquem atualização da toolchain.
5. **Avaliação Extraordinária:** Em caso de vulnerabilidade crítica de segurança que afete o ambiente local.
6. **Rito de Transição Obrigatório:** Qualquer atualização de dependência deve:
   - Ser montada primeiro em workspace experimental isolado;
   - Passar pela suíte de 17 testes unitários;
   - Ter o `hyperframes doctor` aprovado com código 0;
   - Renderizar o episódio piloto com conferência de métricas de áudio e vídeo;
   - Receber aprovação explícita do usuário antes da substituição em produção.
