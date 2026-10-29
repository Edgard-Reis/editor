# Melhoria contínua (todo vídeo)

A skill fica melhor a cada edição. Depois de entregar um vídeo:

1. **Colete o feedback** do que a pessoa achou: o que incomodou, o que faltou, o que ficou bom.
2. **Classifique** cada ponto:
   - regra de estilo (ex.: "sem som agudo");
   - defeito técnico (ex.: "câmera aparece duas vezes");
   - componente novo (ex.: "cursor clicando num print").
3. **Registre** antes de esquecer:
   - na lista de aprendizados da skill (o que pediu, a regra e o estado ✅/⏳);
   - na memória, se for preferência da pessoa.
4. **Corrija na fonte**, não só no vídeo:
   - regra vira código no modelo (`build.py`, `ilustra.py`, `gerar_sons.py`);
   - defeito vira trava (ex.: teste de tom dos sons, +1 ms no início da mídia).
5. **Teste:**
   - `lint` com 0 erros;
   - `snapshot` dos quadros afetados;
   - render de um trecho;
   - comparação com a versão anterior.
6. **Sincronize:** a cópia da skill no repositório da equipe, na mesma sessão.
7. **Pergunte no próximo vídeo** se a regra nova funcionou. Regra que não funcionou volta pro passo 1.

---

## Aprendizados e Preferências Registradas

### Dr. Gestão (Luiz Roberto Saraiva) — Outubro/2026
- ✅ **B-roll sobre o rosto:** Nunca sobrepor o rosto do speaker com cards de b-roll; preferir tela cheia (`card=False`) ou tela dividida sem sobreposição.
- ✅ **Coerência de B-roll:** Se o speaker falar de "fábrica muito grande", usar imagem/vídeo de parque fabril de grande porte, nunca pequenos ateliês.
- ✅ **Alternância de lados:** Alternar cards entre esquerda e direita, priorizando o lado com maior espaço livre no enquadramento.
- ✅ **Identidade Visual:** Aplicar paleta oficial (Azul `#004aad`, Lilás `#8e7de5`, Ciano `#2f97d4`) em cards de vidro, brilhos e ícones.
- ✅ **Logos oficiais:** Usar logos vetorizados/oficiais de plataformas (Shopee, Mercado Livre, Shein, TikTok, WhatsApp) em vez de emojis.
- ✅ **Lower Third sem cortes:** Garantir largura máxima confortável (`max-width: 1150px`) e entrada rápida para leitura do nome e credencial completos.
- ✅ **Trilha sonora:** Opcional/desativada no render final se a música for inserida na pós-produção externa.

