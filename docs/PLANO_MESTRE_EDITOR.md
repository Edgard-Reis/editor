# PLANO MESTRE DO EDITOR — VERSÃO 0.2

**Documento:** Visão de produto, princípios editoriais, arquitetura de referência e planejamento evolutivo  
**Status:** Documento mestre vigente — versão 0.2; visão e princípios aprovados conceitualmente pelo proprietário do projeto  
**Data da versão inicial:** 07/11/2026  
**Última atualização:** 07/11/2026  
**Versão vigente:** 0.2  
**Nome do produto:** Editor (nome de trabalho; identidade comercial ainda não definida)  
**Diretório de produção atual:** `D:\Drifit\Editor\`

> **Finalidade deste documento**  
> Registrar de forma durável a visão, as decisões aprovadas, os princípios de qualidade, a arquitetura de referência, o estado conhecido e a direção evolutiva do Editor. Este documento deve reduzir a dependência da memória de conversas e de agentes de IA. Deve ser atualizado de forma controlada quando novas decisões forem aprovadas.

---

## 0. Como interpretar este documento

Este documento é a referência principal para **visão de produto e planejamento**. Ele não substitui evidências técnicas específicas.

A documentação especializada continua sendo a fonte primária para seus respectivos assuntos:

- Relatórios de auditoria e inventários: evidências do que foi encontrado em determinada data.
- Manifestos SHA-256: integridade de arquivos e pacotes específicos.
- Matrizes de compatibilidade: versões homologadas de ferramentas.
- Relatórios de PoC: resultados efetivamente medidos em experimentos.
- ADRs (Architecture Decision Records): decisões arquiteturais específicas, seus motivos e consequências.
- Documentação de implementação: comportamento real do código.

### 0.1 Classificação das informações

Ao atualizar este documento, distinguir sempre:

- **Aprovado:** decisão explicitamente aceita pelo proprietário do projeto.
- **Validado experimentalmente:** comportamento demonstrado em uma PoC, com evidências e limitações registradas.
- **Estado reportado:** informação de auditoria ou execução relatada por um agente, ainda sem verificação independente nesta documentação.
- **Proposto:** recomendação ainda não aprovada.
- **Futuro:** objetivo ou capacidade desejada, ainda não implementada.
- **Pendente:** informação que precisa ser investigada.

Não apresentar metas futuras como capacidades existentes. Não transformar hipóteses em fatos.

### 0.2 Regra de atualização

Este é um documento vivo, mas não deve ser reescrito livremente por agentes. Alterações devem:

1. preservar decisões já aprovadas;
2. indicar o que mudou e por quê;
3. distinguir decisão nova de sugestão;
4. atualizar a data e o histórico de revisões;
5. referenciar evidências, relatórios ou ADRs pertinentes;
6. evitar duplicar relatórios técnicos extensos.

---

# 1. Visão e identidade do produto

## 1.1 Visão central

O Editor é um sistema autônomo de pós-produção audiovisual assistido por IA. Seu objetivo é receber gravações brutas, compreender o conteúdo falado e visual, planejar uma abordagem editorial adequada, executar a edição e entregar um vídeo profissional o mais próximo possível da versão final de publicação.

O usuário deve precisar **direcionar, aprovar e refinar**, e não executar manualmente cada corte, efeito ou inserção visual.

A ambição é que o usuário forneça o vídeo, escolha um perfil editorial e informe suas prioridades. O Editor deverá assumir o trabalho de análise, planejamento, montagem, tratamento audiovisual e controle de qualidade, mantendo a possibilidade de intervenção humana quando necessária.

**Princípio central:** edição autônoma como ponto de partida; edição manual como possibilidade de refinamento.

## 1.2 O que o Editor pretende resolver

Editores visuais com assistência de IA podem facilitar tarefas, mas ainda podem exigir que o usuário conduza a edição continuamente, trecho a trecho. O Editor busca uma experiência diferente: um fluxo de ponta a ponta no qual a IA tome decisões editoriais coerentes e apresente um resultado muito próximo do vídeo pronto.

O produto não deve depender de instruções humanas a cada pequeno trecho. A intervenção humana acontece principalmente nos pontos de direção criativa, aprovação do briefing, revisão e refinamento.

## 1.3 Resultado desejado

O resultado esperado é um vídeo que:

- preserve a mensagem, a intenção e a naturalidade do apresentador;
- tenha ritmo adequado ao tipo de conteúdo;
- remova erros, redundâncias e pausas sem valor editorial, com critério;
- mantenha demonstrações e ações visuais relevantes mesmo sem fala;
- tenha áudio inteligível, equilibrado e agradável;
- utilize motion graphics, imagens e B-roll quando agregarem significado;
- respeite a identidade visual do projeto;
- tenha continuidade audiovisual e qualidade técnica;
- esteja próximo de ser publicado, exigindo poucos ajustes manuais.

O Editor não deve prometer perfeição automática. Quando houver ambiguidade ou baixa confiança, deverá preservar conteúdo potencialmente relevante e pedir revisão em vez de realizar um corte destrutivo.

## 1.4 Independência de produto

O Editor deve possuir identidade, arquitetura e evolução próprias.

Drift e AlaukCut foram ferramentas de edição visual voltadas ao usuário, nas quais, conforme a experiência relatada, era possível combinar intervenções manuais na interface com solicitações de tarefas à IA. O usuário não confirmou toda a extensão de suas funcionalidades. Os testes anteriores não atenderam às expectativas e ele optou por seguir outro caminho. Elas podem ser referências históricas para refletir sobre experiências híbridas entre usuário e IA, mas **não são bases arquiteturais aprovadas, dependências ativas ou produtos a serem copiados ou integrados**. O objetivo do Editor é diferente: automatizar a pós-produção de ponta a ponta, reduzindo a necessidade de conduzir manualmente a edição trecho a trecho.

O Editor também não deve ser confundido com o Vortex: o Vortex é uma base/orquestrador herdado que pode ser aproveitado, modificado ou substituído conforme justificativa técnica. Nenhuma tecnologia tem lugar garantido apenas por já ter sido utilizada.

O diretório `D:\Drifit\Editor\` é um caminho herdado. “Drifit” ou “Drift” não é o nome comercial aprovado do produto. Não usar “Drifit Studio”.

---

# 2. Experiência do usuário e fluxo de trabalho

## 2.1 Seleção de perfil editorial

Antes da análise, o usuário deverá escolher um **perfil editorial** que indique a intenção e o tratamento esperado. Esses perfis são presets de comportamento editorial, não modelos técnicos de IA.

Perfis iniciais possíveis (lista aberta, ainda sujeita a detalhamento):

| Perfil | Direção editorial esperada |
|---|---|
| Podcast | Conversação natural; cortes de falhas e redundâncias; ritmo coerente; possibilidade de episódio integral e cortes curtos. |
| Live | Preservar a sequência dos acontecimentos; remover apenas problemas relevantes; evitar excesso de cortes. |
| Informacional | Ritmo dinâmico; conceitos em destaque; motion graphics, imagens e B-roll que expliquem o conteúdo. |
| Prático / tutorial | Priorizar clareza das etapas, demonstrações, ações e continuidade do procedimento. |
| Teórico / aula | Organização didática; gráficos, diagramas, exemplos e ritmo que respeite o raciocínio. |
| Demonstração de processo | Preservar operações e sequências visuais importantes, mesmo sem fala; evitar animações que concorram com a demonstração. |

Os perfis deverão controlar, entre outros aspectos:

- densidade e frequência de cortes;
- tolerância a pausas e hesitações;
- intensidade de motion graphics;
- frequência e função de B-roll e imagens;
- preservação de tomadas contínuas;
- ritmo, transições e duração de planos;
- quantidade de intervenções visuais;
- nível de espontaneidade a preservar.

O usuário poderá escolher uma intensidade (por exemplo, discreta, equilibrada ou dinâmica) e, futuramente, salvar perfis personalizados por projeto.

A seleção do perfil não substitui as instruções específicas do usuário. O fluxo deverá combinar: (a) perfil editorial escolhido; (b) instruções em linguagem natural; e (c) análise audiovisual do material. A IA deve usar os três elementos em conjunto, explicando no briefing como resolveu eventuais conflitos. Se uma instrução específica pedir para preservar uma demonstração, por exemplo, essa prioridade deve ser refletida no plano editorial.

Perfis editoriais são configurações de comportamento e critérios de montagem. Não devem ser confundidos com a seleção de um modelo técnico de IA, que deverá permanecer uma decisão de implementação do sistema.

## 2.2 Envio do material e instruções do usuário

O usuário fornecerá o vídeo bruto e poderá incluir instruções opcionais, em linguagem natural, como:

- pontos a enfatizar;
- trechos ou demonstrações que devem ser preservados;
- público-alvo e objetivo do vídeo;
- informações que precisam receber destaque;
- elementos visuais desejados ou indesejados;
- restrições de marca e conteúdo;
- formato e destino de publicação.

Exemplo: “Preserve a demonstração da mesa de corte e dê destaque à explicação sobre balanceamento da produção”.

Essas instruções devem orientar a análise e aparecer refletidas no briefing. A IA não deve obrigar o usuário a escrever um roteiro ou uma especificação técnica completa.

## 2.3 Análise e briefing prévio

Depois de receber o perfil, o vídeo e as instruções, a IA deverá analisar o material e elaborar um briefing antes de editar.

O briefing deverá apresentar, conforme aplicável:

- compreensão do tema, objetivo e mensagem principal;
- estrutura narrativa sugerida;
- momentos fortes e pontos que precisam de contexto;
- cortes propostos e justificativas;
- pausas, repetições, falsos começos e erros detectados;
- trechos visuais importantes que devem ser preservados;
- propostas de motion graphics e o que cada uma pretende explicar;
- sugestões de imagens e B-roll, com função editorial;
- ritmo e tratamento de áudio;
- dúvidas, ambiguidades e decisões de baixa confiança;
- duração aproximada e formato de entrega.

O briefing deve explicar **o que a IA pretende fazer e por que**. Não deve ser uma lista genérica de efeitos.

## 2.4 Aprovação antes da edição

A edição principal só começa depois de o usuário revisar e aprovar o briefing.

O usuário poderá:

- aprovar;
- corrigir instruções;
- pedir substituição ou retirada de uma proposta;
- destacar conteúdo que precisa ser preservado;
- solicitar nova versão do briefing.

A aprovação do briefing é um checkpoint humano deliberado. Não contradiz a autonomia do Editor; evita que uma interpretação equivocada gere uma edição extensa e cara.

## 2.5 Edição autônoma

Após a aprovação, o Editor deverá executar o plano de forma autônoma, incluindo, conforme o perfil e o conteúdo:

- cortes e montagem;
- tratamento e masterização de áudio;
- títulos, legendas e elementos gráficos;
- motion graphics contextualizados;
- gráficos, diagramas e visualizações;
- seleção e inserção de imagens e B-roll;
- identidade visual e ritmo;
- composição e renderização.

O sistema não deve inserir animação, efeito, transição ou B-roll apenas para preencher espaço. Cada elemento deve cumprir uma função narrativa, didática ou estética.

## 2.6 Revisão de qualidade e refinamentos

Após a primeira edição, a IA deverá avaliar o resultado renderizado e procurar problemas, como:

- cortes abruptos ou junções pouco naturais;
- fala cortada ou palavra comprometida;
- dessincronização;
- B-roll sem relação clara com a fala;
- texto ilegível ou fora de quadro;
- motion graphics excessivos ou insuficientes;
- inconsistências de identidade visual;
- problemas de áudio, clipping, picos ou loudness;
- quadros pretos, congelamentos ou falhas de renderização.

O usuário poderá solicitar rodadas de refinamento. O Editor deverá manter histórico de versões e identificar quais componentes precisam ser refeitos, evitando renderizar tudo novamente quando uma alteração localizada for suficiente.

Cada rodada deverá registrar o pedido do usuário, as decisões alteradas, os segmentos/cenas afetados e o resultado da validação. Quando possível, o sistema deverá preservar o que já foi aprovado e regenerar apenas as partes afetadas. O usuário poderá comparar versões e retornar a uma versão anterior.

É aceitável que o usuário faça pequenos ajustes em outro editor, se desejar. Isso não significa fracasso do produto. A meta é reduzir progressivamente essa necessidade.

---

# 3. Inteligência editorial e decisões de conteúdo

## 3.1 Compreensão audiovisual conjunta

O Editor deverá analisar áudio e imagem em conjunto. A ausência de fala não significa ausência de conteúdo.

**Regra editorial aprovada:** nenhum trecho deverá ser eliminado exclusivamente por apresentar silêncio.

Antes de remover uma pausa, a IA deverá avaliar se há ação visual, demonstração, expressão, operação, contexto ou continuidade relevantes.

Exemplo: um profissional cortando tecido em uma mesa de corte pode permanecer em silêncio enquanto demonstra uma etapa importante. Esse trecho deve ser preservado quando tiver valor didático ou documental.

Quando aplicável, a IA poderá:

- preservar a tomada;
- encurtar apenas partes redundantes;
- acelerar suavemente uma etapa longa, se isso não prejudicar a compreensão;
- acrescentar uma identificação ou explicação visual;
- sinalizar a dúvida no briefing.

Na incerteza, a preferência é preservar e pedir revisão, não excluir.

O usuário poderá antecipar, já no envio do vídeo, quais ações visuais são importantes: por exemplo, preservar o corte de tecido na mesa de corte, o funcionamento de uma máquina ou uma sequência operacional. A análise deverá relacionar essas instruções à imagem e à fala, e o briefing deverá mostrar os trechos que serão preservados e a justificativa.

A detecção de silêncio deverá ser tratada como um sinal para análise, não como uma ordem de corte. O sistema precisa distinguir pelo menos: pausa sem valor aparente; silêncio com demonstração ou ação visual; silêncio necessário à compreensão/ritmo; e situação ambígua.

## 3.2 Detecção de problemas de fala

A inteligência editorial deverá reconhecer, com atenção ao contexto:

- gaguejos e repetições involuntárias;
- falsos começos;
- frases interrompidas;
- reformulações e recomeços de frase ou parágrafo;
- palavras duplicadas sem intenção;
- hesitações e preenchimentos;
- vícios de linguagem sem função comunicativa;
- pausas excessivas;
- erros que o apresentador corrige espontaneamente.

Exemplos de preenchimentos que podem aparecer: “né”, “hã”, “é...”, “tipo”, “assim” e “então”. Não remover mecanicamente todas as ocorrências: algumas têm função semântica, ritmo, ênfase ou naturalidade.

O perfil editorial deverá influenciar o grau de limpeza. Um podcast pode preservar mais espontaneidade que uma aula formal.

A IA deverá manter o significado e a intenção do apresentador. Não reescrever ou substituir conteúdo técnico por inferência sem evidência. Erro de fala, erro factual e preferência estilística são categorias diferentes.

## 3.3 Confiança e segurança dos cortes

Classificação proposta:

- **Confiança alta:** corte automático quando o trecho é claramente descartável e a junção é segura.
- **Confiança média:** sugerir o corte no briefing ou na revisão.
- **Confiança baixa:** preservar e sinalizar.

A IA deverá avaliar a continuidade sintática, semântica, temporal e audiovisual após cada corte. Nenhum algoritmo deve simplesmente remover todas as pausas acima de uma duração fixa.

O nível de confiança deverá levar em conta tanto a certeza de que o trecho é um erro quanto a segurança da junção resultante. Mesmo quando a fala parecer descartável, a operação não deverá ser automática se o corte puder comprometer uma ação visual, a compreensão, a sincronização ou a continuidade.

## 3.4 Marcadores falados de erro

O usuário propôs um mecanismo de marcadores verbais raros para comunicar falhas de gravação:

- marcador curto (exemplo de referência: “pato amarelo”): sinaliza que a fala anterior em uma janela curta deve ser invalidada;
- marcador longo (exemplo de referência: “pato vermelho”): sinaliza que um trecho maior, como uma frase ou parágrafo reiniciado, deve ser descartado.

Os nomes são exemplos de conceito, não uma escolha definitiva de nomenclatura.

Requisitos futuros:

- marcadores configuráveis por usuário/projeto;
- expressões improváveis na fala cotidiana e acusticamente distinguíveis;
- detecção da expressão completa;
- identificação contextual dos limites do trecho inválido;
- remoção do marcador e do trecho sinalizado;
- preservação da versão corrigida;
- prevenção de falsos positivos se o marcador for citado no conteúdo;
- possibilidade de revisão quando a extensão do corte não for clara.

## 3.5 Referência de erro de segmentação

Foi relatado um caso de transcrição em que a fala “que atrapalha demais as vendas” foi segmentada como “que é pra palha de mais as vendas”. O trecho foi identificado como referência para testes futuros, desde que o áudio original correspondente esteja disponível.

A correção desse caso deve ser avaliada mantendo o modelo e o contexto atuais do Whisper. Não usar esse exemplo como autorização para alterar o vocabulário aprovado.

---

# 4. Áudio, transcrição e masterização

## 4.1 Transcrição atual

A auditoria de 07/11/2026 relatou como transcrição principal local:

- `mobiuslabsgmbh/faster-whisper-large-v3-turbo`;
- `faster-whisper` com CTranslate2;
- execução em CPU, com `int8` e oito threads na configuração auditada;
- Silero VAD integrado;
- fallback local `openai-whisper` em caso de exceção;
- opção de ElevenLabs Scribe quando a variável `ELEVENLABS_API_KEY` está configurada.

**Decisão aprovada:** preservar o modelo Whisper large-v3-turbo, o `initial_prompt`, o vocabulário atual do Dr. Gestão e a configuração de transcrição que o usuário considera assertiva. Não modificar esses elementos sem autorização específica e evidência comparativa.

A auditoria apontou uma possível inadequação no vocabulário configurado, mas o usuário relatou bons resultados práticos com a configuração atual. Portanto, não alterar o `lexicon_transcricao` por inferência. O teste de áudio deverá manter o Whisper e seu contexto fixos para isolar o efeito do tratamento sonoro.

## 4.2 Tratamento de áudio existente — perfil de gravação no carro

A auditoria de recuperação relatou que existe um script próprio:

`D:\Drifit\Editor\projetos\dr-gestao\branding\scripts\clean_car_audio.py`

O script foi formalizado em `projetos/dr-gestao/branding/PREFERENCIAS.md` em 27/10/2026 e consta no Git, commit `77cfff1`.

A cadeia relatada contém:

1. amostra de ruído dos primeiros 0,5 segundo (`y_noise = data[0.05*sr : 0.55*sr]`);
2. `noisereduce` com `prop_decrease=0.82`, `n_fft=2048` e `stationary=True`;
3. FFmpeg `highpass=f=80`;
4. equalização em 320 Hz com ganho de -2,5 dB;
5. realce de presença em 3 kHz com +2 dB;
6. compressor com threshold -18 dB, ratio 2,5, attack 10 e release 120;
7. normalização final `loudnorm=I=-14:TP=-1.0:LRA=7`.

Um WAV tratado foi localizado pela auditoria:

`D:\Drifit\Editor\projetos\dr-gestao\episodios\teste-piloto\workspace\temp_cleaned.wav`

SHA-256 informado: `893132AE5937D9A3CF899330FBE8A9FAD4F65663748AA3B7BC6E087349C4B325`.

Arquivos de vídeo originais do cenário no carro também foram reportados:

- `D:\Drifit\Editor\20260823_203211.mp4`
- `D:\Drifit\Editor\20260823_203326.mp4`

Essa cadeia é uma solução de processamento digital tradicional, não um modelo neural de restauração. Ela foi avaliada positivamente pelo usuário e deve ser preservada como baseline experimental específico para gravação no carro.

**Atenção:** os parâmetros e a existência dos arquivos foram relatados pela auditoria. Antes de reutilizar ou modificar o script, verificar o estado atual e trabalhar em cópia na sandbox. Não afirmar determinismo de ponta a ponta sem teste de repetição e comparação de hashes.

## 4.3 Restauração neural

Até a auditoria de recuperação, não foi comprovada a instalação de um modelo neural de restauração de áudio. DeepFilterNet 3, VoiceFixer, ClearerVoice e Demucs foram identificados como sugestões ou candidatos, sem pesos locais comprovadamente instalados.

A existência, instalação ou execução de um modelo não deve ser inferida apenas por menção em conversas ou relatórios de planejamento.

A futura PoC poderá comparar candidatos, sem obrigação de utilizar qualquer um deles. A escolha deverá avaliar:

- ruído estacionário e variável;
- trânsito, motores, latidos e obras;
- reverberação;
- ganho excessivo e clipping;
- inteligibilidade;
- preservação do timbre e da identidade vocal;
- artefatos e distorções introduzidos;
- velocidade, RAM, CPU e compatibilidade;
- licenças do código e dos pesos.

Não encadear vários restauradores automaticamente. Cada candidato deve processar uma cópia independente do mesmo original.

## 4.4 Princípios de processamento

Separar conceitualmente:

- restauração e redução de ruído;
- equalização corretiva;
- compressão e controle dinâmico;
- de-esser, quando necessário;
- limitação de pico;
- normalização de loudness e masterização.

Normalização de volume não é restauração de voz. Compressor não recupera automaticamente informação perdida por clipping. Modelos neurais podem melhorar sinais degradados, mas não garantem recuperação perfeita.

Preservar sempre o áudio original e gerar versões processadas independentes para A/B e aprovação.

## 4.5 Loudness de entrega

O usuário verificou diretamente na interface do CapCut que a função “Normalizar nível de volume” apresenta alvo de -14 LUFS, tanto para vídeos longos quanto para vídeos curtos. Registrar isso como observação da interface utilizada pelo usuário; não inferir, sem documentação adicional, todos os detalhes internos do algoritmo do CapCut.

**Decisão inicial aprovada:** utilizar -14 LUFS integrados como preset de normalização para os formatos de entrega, incluindo YouTube longo, Shorts, Reels e TikTok. Não adotar -16 LUFS para vídeos curtos sem teste e aprovação posteriores.

O script de áudio recuperado também usa `TP=-1.0` e `LRA=7`. O limite de -1 dBTP é uma referência técnica inicial para avaliação, não uma informação confirmada sobre os detalhes internos do CapCut.

A medição deverá ser feita no programa completo final, incluindo voz, música e efeitos, não apenas na voz isolada. Validar loudness integrado, true peak e qualidade auditiva. O alvo é uma decisão de masterização, não uma obrigação universal imposta por todas as plataformas.

---

# 5. Arquitetura e tecnologias

## 5.1 Princípios arquiteturais

- Independência de modelo e fornecedor de IA sempre que viável.
- Separação entre análise editorial, plano de edição, composição visual, renderização e QA.
- Componentes reutilizáveis, com identidade visual específica por projeto.
- Renderização previsível, cache granular e invalidação seletiva.
- Reprodutibilidade, logs estruturados, testes e validação visual/auditiva.
- Segurança por isolamento de experimentos e preservação da produção.
- Portabilidade futura, estabilizando primeiro o ambiente Windows.

## 5.2 Base técnica de referência

A base de produção relatada na homologação da Fase 5.6 contém:

- Python para orquestração e utilitários;
- Vortex como orquestrador herdado, sujeito a evolução ou substituição;
- HyperFrames 0.9.5;
- GSAP 3.14.2;
- Chromium Headless / Headless Shell;
- FFmpeg e FFprobe Gyan 9.0.2;
- Node.js 22.18.0.

A matriz completa de compatibilidade e o manifesto da toolchain são as referências técnicas para versões e hashes. Não alterar versões homologadas sem uma PoC e aprovação.

## 5.3 Vortex

Vortex é tratado como orquestrador/editorial pipeline, não como o renderizador visual propriamente dito. O projeto pode manter, refatorar, substituir ou descartar partes do Vortex caso uma alternativa demonstre superioridade técnica.

A integração de Vortex com a Motion Library foi validada experimentalmente em sandbox, mas a integração ainda não foi promovida à produção.

## 5.4 Motion Library

A Motion Library é uma biblioteca compartilhada de componentes visuais/motion graphics, separada da identidade de cada projeto.

Princípios:

- componentes reutilizáveis;
- estilos e temas por projeto;
- movimento com intenção editorial;
- evitar slides estáticos como substituto de motion graphics quando o briefing pedir movimento;
- evitar movimento gratuito ou excessivo;
- preservar legibilidade e acessibilidade;
- composição definida por plano editorial declarativo, quando possível.

A PoC2 demonstrou integração editorial e cache seletivo, mas identificou ressalvas: densidade de movimento insuficiente em determinadas cenas, grid estático e ausência de prova de determinismo completo de renderização a frio.

## 5.5 Vídeo, áudio e composição

O sistema deverá manter separadas as responsabilidades:

- leitura e análise do vídeo bruto;
- análise/transcrição do áudio;
- decisão editorial e timeline;
- seleção e tratamento de mídia;
- motion graphics e composição;
- renderização e mixagem;
- QA final.

O plano de edição deverá ser estruturado e editável, com referências temporais, decisões e justificativas. O original nunca deve ser sobrescrito.

## 5.6 Referências históricas

- `video-motion`: PoC visual independente que o usuário avaliou positivamente por movimento orgânico e composição. Deve ser mantido como referência visual/experimental, não presumido como componente integrado.
- `claude-video`: repositório estudado como referência de metodologia HyperFrames/GSAP, sujeito a licenças e limitações.
- Drift e AlaukCut: editores visuais com interação manual e assistência de IA testados anteriormente; não integrar nem adotar como arquitetura do Editor.

---

# 6. Infraestrutura, armazenamento e desempenho

## 6.1 Hardware atual informado

- CPU: Intel Xeon E5-2680 v4, 2,40 GHz;
- 14 núcleos físicos / 28 threads;
- 32 GB DDR4;
- GPU AMD Radeon RX 6600M, 8 GB VRAM.

O relatório de auditoria indicou execução atual do Whisper em CPU, sem CUDA. Qualquer rota de aceleração pela GPU AMD (DirectML, ONNX Runtime, Windows ML ou outra) precisa ser prototipada e medida; não presumir compatibilidade ou ganhos.

## 6.2 Limites de processamento

Houve congelamento do computador quando um processamento utilizou threads demais. Portanto:

- iniciar PoCs pesadas com teto de quatro threads;
- testar limites maiores somente de forma gradual e monitorada;
- limitar também threads de bibliotecas numéricas e subprocessos;
- medir o processo inteiro, não apenas o processo pai;
- interromper em caso de instabilidade ou pressão crítica de memória;
- não executar vários modelos pesados simultaneamente sem justificativa e teste.

O limite inicial de quatro threads é uma salvaguarda experimental, não uma configuração final obrigatória.

## 6.3 Armazenamento

Preferência aprovada do usuário:

- unidade D: para projetos, modelos, pesos, caches, dependências, temporários, logs, downloads, renders, assets e backups, sempre que tecnicamente apropriado;
- unidade C: reservada ao Windows e aos componentes que precisem permanecer nela.

Sempre que fizer sentido, recursos pertencentes ao Editor devem ficar organizados dentro da estrutura do projeto em D:, com caminhos documentados e configuráveis.

A auditoria informou aproximadamente 14,32 GB de caches/modelos no C: e pouco espaço livre na unidade. Também identificou a transferência de aproximadamente 1,51 GB do cache Hugging Face do projeto para `%LOCALAPPDATA%\huggingface`, contendo pesos do Whisper, não um restaurador neural.

**Não migrar, remover ou reorganizar caches existentes sem:**

1. auditoria somente leitura;
2. inventário de dependências e caminhos;
3. plano de migração;
4. backup;
5. validação por SHA-256;
6. teste sem novo download, quando aplicável;
7. autorização explícita do usuário.

Caminhos propostos para organização futura (ainda não autorizados para criação/migração):

```text
D:\Drifit\Editor\
├── resources\audio\
├── models\audio\
├── cache\audio\
└── tools\audio\
```

Os caminhos finais deverão considerar a arquitetura e os padrões já existentes no repositório, evitando duplicações e estruturas paralelas desnecessárias.

---

# 7. Estado do projeto e evidências conhecidas

## 7.1 PoC2 — integração editorial Vortex + Motion Library

Status reportado: formalmente congelada em 07/11/2026.

Classificação oficial: **REFERÊNCIA EXPERIMENTAL VALIDADA COM RESSALVAS TÉCNICAS**.

Pacote congelado reportado em:

`D:\Drifit\Experimentos_Sandbox\claude_video_official_audit\referencias_congeladas\PoC2_Vortex_MotionLibrary_2026-11-07\`

A auditoria de congelamento reportou 103 arquivos, todos com SHA-256 correspondente ao manifesto, sem divergências ou arquivos ausentes.

Demonstrado segundo os relatórios:

- integração editorial Vortex + Motion Library em sandbox;
- vídeo 16 segundos, 480 frames, 1920×1080, 30 fps;
- segmentos de vídeo base e janelas de motion;
- mixagem multifaixa;
- cache granular e invalidação seletiva;
- toolchain compatível com a base homologada.

Ressalvas registradas:

1. determinismo de renderização completa a frio não comprovado;
2. densidade de movimento visual insuficiente em algumas partes e grid estático;
3. áudio de voz sintética, sem validação de voz humana restaurada;
4. licenças do pipeline completo ainda exigem análise para distribuição comercial;
5. PoC experimental, sem aprovação para produção.

O arquivo `final_rodada1.mp4` é a referência principal do pacote; os demais renders mantêm suas finalidades específicas documentadas no pacote. Não modificar o pacote congelado.

## 7.2 Auditoria técnica de áudio

Diretório reportado:

`D:\Drifit\Experimentos_Sandbox\auditoria_audio_local_2026-11-07\`

A auditoria identificou o Whisper large-v3-turbo, Silero VAD, fallback Whisper base/small, integração opcional com ElevenLabs Scribe e `noisereduce` no pipeline genérico. Identificou também que o pipeline genérico usa redução espectral e normalização, enquanto a solução específica `clean_car_audio.py` possui cadeia acústica diferente.

Os relatórios e seus hashes são a referência documental dessa auditoria.

## 7.3 Recuperação do pipeline anterior de áudio

Diretório reportado:

`D:\Drifit\Experimentos_Sandbox\recuperacao_audio_anterior_2026-11-07\`

A investigação concluiu que o script `clean_car_audio.py` permanece no projeto e foi versionado. O cache Hugging Face migrado pelo OpenCode continha pesos do Whisper. Não foi comprovada a instalação de um modelo neural de restauração sugerido anteriormente.

A solução de áudio do carro e o WAV correspondente devem ser tratados como baseline experimental recuperado, sujeitos a reprodução controlada e avaliação antes de qualquer alteração.

## 7.4 Fase seguinte proposta — PoC de áudio

Ainda não iniciada/aprovada para execução no momento da criação deste documento.

Direção proposta:

1. reproduzir o `clean_car_audio.py` em sandbox;
2. preservar os originais e comparar com o WAV anterior;
3. verificar qualidade e repetibilidade;
4. avaliar o perfil de ruído e parâmetros;
5. comparar, em execuções independentes, candidatos neurais como DeepFilterNet3, VoiceFixer ou um modelo selecionado do ClearerVoice-Studio, após verificação de licença e viabilidade;
6. manter Whisper large-v3-turbo e seu contexto fixos durante as comparações de áudio;
7. iniciar com quatro threads e medir CPU, RAM e tempo;
8. produzir relatório comparativo e recomendação, sem integrar à produção.

---

# 8. Roadmap evolutivo

O roadmap abaixo é uma direção de planejamento, não autorização automática para executar as etapas.

| Fase | Objetivo | Estado conhecido |
|---|---|---|
| Base técnica e auditorias | Conhecer e estabilizar ferramentas, versões e arquitetura | Parcialmente concluído; consultar relatórios. |
| PoCs de composição visual | Avaliar qualidade de motion e integração | PoC2 congelada como referência experimental com ressalvas. |
| Áudio e transcrição | Estabelecer pipeline confiável de restauração, transcrição e masterização | Baseline recuperado; PoC comparativa futura. |
| Inteligência audiovisual | Analisar conteúdo visual e sonoro conjuntamente | Futuro. |
| Inteligência editorial | Detectar erros de fala, reformulações, vícios, silêncios e conteúdo relevante | Futuro. |
| Briefing e aprovação | Gerar plano editorial explicável antes da edição | Futuro. |
| Montagem autônoma | Executar cortes, motion, B-roll, imagens, áudio e timeline | Evolução futura em etapas. |
| QA e refinamento | Revisar render, corrigir problemas e manter versões | Futuro. |
| Piloto real Dr. Gestão | Produzir um vídeo bruto até uma versão próxima de publicação | Meta futura, após validações necessárias. |
| Distribuição | Tornar o Editor portável e distribuível | Objetivo de longo prazo; exige análise de licenças e empacotamento. |

## 8.1 Capacidades futuras de inteligência editorial

- análise semântica e narrativa do vídeo;
- identificação de tópicos, argumentos, exemplos e conclusões;
- detecção de pausas sem valor e preservação de silêncio com ação visual relevante;
- identificação de erros, falsos começos, repetições, reformulações e vícios de linguagem;
- reconhecimento de marcadores verbais de erro;
- geração de briefing e plano de edição;
- associação entre fala, ação visual, motion graphics, imagens e B-roll;
- verificação da coerência editorial do vídeo final;
- decisões com graus de confiança e revisão humana para ambiguidades.

## 8.2 B-roll e imagens

B-roll e imagens devem ter finalidade editorial e relação verificável com o conteúdo. Evitar imagens genéricas apenas para preencher tempo. Registrar fonte, licença, atribuição e restrições de uso de cada mídia externa. Quando não houver material adequado, o Editor deve preferir uma composição gráfica original ou preservar a imagem existente em vez de inserir mídia enganosa.

## 8.3 Estratégia indicativa para piloto e beta interno

A primeira validação audiovisual de ponta a ponta deverá priorizar material real do Dr. Gestão, porque há conhecimento do contexto editorial, exemplos de gravação e referências de qualidade disponíveis. O primeiro piloto não precisa aguardar a implementação de todos os perfis, mas deve exercitar o fluxo completo que estiver tecnicamente disponível e registrar claramente o que ainda for manual ou experimental.

Direção de evolução proposta:

1. produzir um primeiro teste real com vídeo do Dr. Gestão, após validar o pipeline de áudio e os componentes necessários;
2. evoluir para um beta interno capaz de receber vídeo bruto, perfil editorial e instruções, gerar briefing, aguardar aprovação, executar a edição, avaliar o resultado e permitir refinamentos;
3. ampliar gradualmente os perfis editoriais, a robustez, a interface e a capacidade de reutilização em outros projetos.

A seleção inicial de perfis para o beta (por exemplo, informacional/didático, demonstração de processo e apresentação com motion graphics) é uma proposta de escopo e deverá ser confirmada antes da implementação. Não presumir suporte completo a todos os perfis apenas porque aparecem neste plano.

### Cadência e estimativas de planejamento

O usuário estima disponibilidade média de aproximadamente **2 a 3 horas por dia**, com variação: alguns dias podem não ter sessão de trabalho e outros podem ter sessões mais longas. Essa é uma referência de planejamento, não uma obrigação diária nem uma garantia de capacidade.

Estimativas discutidas em 07/11/2026:

- primeiro teste real com vídeo do Dr. Gestão: aproximadamente 1 a 3 semanas;
- beta interno funcional: aproximadamente 6 a 10 semanas;
- beta mais abrangente: aproximadamente 3 a 5 meses.

Essas faixas são projeções preliminares, não prazos prometidos. Devem ser reavaliadas conforme os resultados das PoCs, riscos encontrados, disponibilidade efetiva e escopo aprovado. O objetivo é produzir evidências audiovisuais em etapas, evitando tanto a pressa sem validação quanto um ciclo prolongado de planejamento sem entregas visíveis.

---

# 9. Governança, segurança e método de desenvolvimento

## 9.1 Método de trabalho

Fluxo preferencial:

1. discutir objetivo e critérios;
2. analisar estado atual e evidências;
3. preparar prompt técnico preciso para o agente executor (por exemplo, Antigravity/Gemini);
4. executar em sandbox isolada;
5. coletar logs, artefatos, testes e relatórios;
6. revisar criticamente resultados e contrapontos;
7. decidir explicitamente sobre promoção ou próxima fase.

O assistente atua como parceiro crítico de produto e tecnologia: deve apresentar sugestões, contrapontos, riscos, inviabilidades e alternativas, não apenas concordar. O proprietário mantém a aprovação das decisões de produto e das mudanças na produção.

## 9.2 Produção e sandboxes

- Experimentação nova deve ocorrer em sandbox independente.
- Não modificar produção sem autorização específica.
- Não alterar pacotes congelados ou referências históricas.
- Criar backup antes de operações autorizadas de risco.
- Validar resultados com testes e evidências.
- Documentar reversão e impacto.
- Não sobrescrever arquivos originais de vídeo/áudio.

Ao copiar árvores Windows, tratar junctions/reparse points com cuidado. Usar estratégias que não sigam junctions inadvertidamente (por exemplo, Robocopy `/XJ` quando adequado). Não assumir que `os.walk(followlinks=False)` protege de todos os tipos de junctions do Windows.

## 9.3 Testes e evidência

- Não declarar sucesso com base apenas em mensagem de agente.
- Diferenciar teste unitário, teste de integração, teste visual, teste auditivo, benchmark e validação de produção.
- Registrar condições, versões, hardware, parâmetros e hashes.
- Usar telemetria estruturada (JSON) em vez de depender de parsing frágil de mensagens formatadas.
- Relatar limitações e testes não executados.
- Preservar os relatórios e amostras que sustentam decisões.

## 9.4 Modelos, ferramentas e licenças

Para cada modelo, biblioteca ou mídia, registrar:

- nome e versão;
- origem/repositório oficial;
- finalidade;
- caminho e tamanho;
- licença do código;
- licença dos pesos/modelo;
- restrições de uso comercial e redistribuição;
- dependências;
- parâmetros aprovados;
- testes e resultados;
- status: sugerido, baixado, instalado, executado, integrado ou removido.

Não presumir que a licença do código cubra pesos, dados ou dependências. Não afirmar que o pipeline inteiro está liberado para distribuição comercial sem auditoria de licenças completa.

## 9.5 Autonomia e aprovação

O assistente tem autonomia para recomendar soluções, levantar contrapontos e planejar alternativas. Essa autonomia não autoriza modificar produção, migrar caches, remover arquivos, alterar configurações globais ou promover código sem aprovação explícita do usuário.

A aprovação do usuário é necessária para mudanças com impacto na produção, dados, ambientes, cache compartilhado ou arquitetura homologada.

---

# 10. Decisões aprovadas, propostas e pendências

## 10.1 Decisões aprovadas

- O Editor deve ser um sistema de pós-produção autônomo, não apenas um assistente de edição manual.
- O usuário escolhe perfis editoriais antes da análise.
- O usuário pode fornecer instruções e ênfases junto com o vídeo bruto.
- A IA produz briefing explicável e aguarda aprovação antes da edição principal.
- Após editar, a IA realiza QA e permite refinamentos iterativos.
- Silêncio não é motivo suficiente para corte: analisar ação visual e contexto.
- Preservar demonstrações e processos importantes, mesmo sem fala.
- Detectar erros, falsos começos, reformulações, repetições e vícios de linguagem com sensibilidade contextual.
- Marcadores verbais raros de erro são uma capacidade futura desejada.
- Manter o Whisper large-v3-turbo e o `initial_prompt` atual preservados.
- Preservar `clean_car_audio.py` como baseline experimental recuperado.
- Utilizar -14 LUFS como preset inicial de normalização para todos os formatos, sujeito à medição e validação final.
- Priorizar recursos do projeto na unidade D:.
- Drift e AlaukCut são referências históricas, não bases do Editor.
- A arquitetura e a seleção de ferramentas devem permanecer independentes de fornecedor sempre que viável.
- Não promover mudanças à produção sem aprovação específica.

## 10.2 Propostas de implementação técnica ainda não aprovadas

Os objetivos e princípios editoriais descritos nas decisões aprovadas acima estão conceitualmente aprovados. A lista a seguir se refere à escolha de soluções técnicas, ao escopo exato de cada entrega ou à autorização para iniciar implementações específicas; não é uma retirada da aprovação da visão do produto.

- Perfis editoriais personalizados e controle de intensidade (discreto/equilibrado/dinâmico).
- Aceleração de transcrição na GPU AMD por uma implementação compatível.
- Adoção de modelo neural para restauração de áudio.
- Perfis específicos de tratamento acústico por cenário.
- Organização final de modelos, cache e ferramentas sob diretórios internos do projeto em D:.
- Implementação de briefing, timeline editorial e refinamento seletivo.

## 10.3 Pendências

- Concluir PoC comparativa de áudio.
- Confirmar comportamento real e repetibilidade do script de áudio recuperado.
- Medir a precisão do Whisper em trechos de referência mantendo o prompt atual.
- Verificar clipping e possibilidade de recuperação em gravações reais.
- Validar limites de threads e consumo de memória.
- Investigar viabilidade de aceleração por GPU AMD sem assumir ganhos.
- Completar revisão de licenças para distribuição comercial.
- Definir PRD e critérios de aceitação por capacidade antes de cada implementação relevante.

---

# 11. Histórico de revisões

| Data | Revisão | Alteração |
|---|---|---|
| 07/11/2026 | 0.1 | Documento mestre inicial: visão autônoma, perfis editoriais, briefing/aprovação, inteligência audiovisual, áudio, arquitetura, estado das PoCs e governança. |
| 07/11/2026 | 0.2 | Consolidação das decisões aprovadas em conversa: distinção explícita entre perfil editorial e modelo técnico; instruções do usuário combinadas à análise; preservação de silêncios com ação visual; histórico de refinamentos; esclarecimento da independência em relação a Drift/AlaukCut; observação do CapCut sobre -14 LUFS em todos os formatos; estratégia e estimativas preliminares de piloto/beta e cadência média de trabalho. |

---

## Nota final

O Editor deve compreender o conteúdo antes de editá-lo. Deve saber quando cortar e quando preservar, quando usar movimento e quando deixar a demonstração falar por si, quando tratar o áudio e quando evitar processamento desnecessário. Seu valor não está na quantidade de efeitos, mas na qualidade das decisões editoriais e na capacidade de entregar um vídeo coerente, profissional e próximo da publicação.
