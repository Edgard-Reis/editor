---
name: dr-gestao
description: Automatiza a edição completa dos episódios do canal Dr. Gestão (Luiz Roberto Saraiva) no formato 16:9 (YouTube) e a extração e renderização dos 7 cortes virais no formato 9:16 (Shorts/Reels/TikTok) com split stage, legendas dinâmicas, sound design e vinhetas. Inclui fluxo contínuo de aprendizado e registro de melhorias e preferências a cada novo episódio. Ative em "edita o ep do dr gestao", "gerar cortes dr gestao", "novo episodio dr gestao", "ajustes dr gestao", "/dr-gestao".
---

# Skill de Edição Automatizada — Dr. Gestão

Esta skill padroniza e automatiza a edição dos vídeos do canal **Dr. Gestão (Luiz Roberto Saraiva)** — especialista em alta performance e lucro real em confecções do vestuário.

> **Fonte única das regras de marca:** `projetos/dr-gestao/branding/PREFERENCIAS.md`.
> Esta skill manda no **procedimento** (o que rodar, em que ordem). As **regras** (paleta, lower third, b-roll, split stage, checklist, histórico de melhorias) vivem no `PREFERENCIAS.md` — **leia-o antes de planejar** e nunca duplique as regras aqui. Quando o usuário pedir um ajuste, siga o protocolo de aprendizado (seção 5) e **escreva a regra no `PREFERENCIAS.md`**, não só no episódio.

## Formatos

1. **Episódio Completo 16:9 (YouTube):** gancho + fala no carro com áudio tratado + vinheta oficial + conteúdo principal (lower third, b-rolls tela cheia, motions laterais alternados).
2. **7 Cortes Virais 9:16 (Shorts/Reels/TikTok):** vertical em Duas Zonas (*Split Stage*), legendas cinéticas palavra por palavra, cards animados item a item com sound design e vinheta final.

## 1. Identidade e herança de projeto

A identidade visual, áudio, logos, vinhetas e regras de motion estão **todas** em `projetos/dr-gestao/branding/`:
`PREFERENCIAS.md` (regras vivas), `config.json` (paleta/parâmetros), `logos/`, `overlays/` (vinhetas e transições), `sons/`, `vinhetas/`, `scripts/` (templates reutilizáveis). **Não redefina** essas regras em nenhum outro lugar.

Estrutura de um episódio (`projetos/dr-gestao/episodios/EP-<XX>/`):
```text
brutos\      gravações brutas originais (preservadas, nunca sobrescrever)
workspace\   scripts de render, transcrição e assets (build.py, media/)
renders\     finais 16:9 e cortes_9_16/
```

## 2. Criar o episódio

```bash
python d:\Drifit\Editor\novo_episodio.py dr-gestao EP-01 "caminho\para\gravacao.mp4"
```
Cria `brutos/`, `workspace/`, `renders/` e copia do `branding/`: `PREFERENCIAS.md`, logos, vinhetas, sons, transições e scripts base (`render_todos_cortes.py`, `clean_car_audio.py`, `build_intro_and_merge.py`).

## 3. Episódio 16:9 — passo a passo

### 3.1 Áudio de campo (voz do carro / ambiente)
Gravações externas têm ressonância de cabine e ruído. Rode `clean_car_audio.py`, que aplica a cadeia acústica obrigatória (High-Pass 80 Hz, Spectral Denoise, EQ 320 Hz/3 kHz, compressão suave, normalização −14 LUFS).

### 3.2 Linha do tempo (4 blocos)
Estrutura e minutagens exatas em `PREFERENCIAS.md` §7. Blocos: gancho → fala no carro → vinheta oficial (`Intro-Dr-Gestao.mp4`) → conteúdo principal. O motor de edição é o `vortex-edicao` (`transcrever → cortar → build → render_rapido`); acesse `W("frase")` para ancorar motions na fala.

### 3.3 B-roll
Regras em `PREFERENCIAS.md` §4 (tela cheia `card=False`, Ken Burns `kb=1.06`, zero obstrução de rosto, coerência temática). Busca automatizada:
```bash
python vortex-edicao/scripts/broll_pixabay.py "garment factory" -o media/broll -n 2   # oficial
python vortex-edicao/scripts/broll_pexels.py "textile manufacturing" -o media/broll    # complementar
```

### 3.4 Renderizar e concatenar
```bash
python build_intro_and_merge.py     # → renders/EP<XX>_final_completo.mp4
```

## 4. Cortes 9:16 — passo a passo

### 4.1 Selecionar os 7 ganchos
Mapeie na transcrição (`media/palavras_saida.json`) 7 trechos de alta retenção que cubram os pilares do Dr. Gestão. Os 7 temas-padrão (diagnóstico, oportunidade, escala, realismo, casos, ponto crítico, autoridade) estão em `PREFERENCIAS.md` §8.

### 4.2 Layout Split Stage e legendas
Spec completa (duas zonas, legendas em `y=1020`, sound design sincronizado, logo branca, fechamento com `outro_drgestao_shorts_30fps.mp4`) em `PREFERENCIAS.md` §8 — não duplique aqui.

### 4.3 Renderizar os cortes
```bash
python render_todos_cortes.py            # os 7
python render_todos_cortes.py --cuts 1   # só o corte 1 (teste rápido)
```
Saída: `renders/cortes_9_16/EP<XX>_corte_<YY>_<tema>.mp4` (nomenclatura obrigatória).

## 5. Protocolo de aprendizado contínuo (a cada EP)

**Regra de ouro:** nenhuma correção pedida pelo usuário fica restrita ao episódio local.

```text
[Solicitação do usuário]
        │
        ▼
[1. Ajustar e testar no episódio atual] ──► snapshot/render de validação
        │
        ▼
[2. Promover para PREFERENCIAS.md] ────────► atualiza a regra na seção correspondente
        │
        ▼
[3. Atualizar branding/scripts/] ─────────► próximos episódios já nascem corrigidos
        │
        ▼
[4. Registrar no histórico] ───────────────► data, motivo e regra em PREFERENCIAS.md §9
```

## 6. Checklist de qualidade

O checklist obrigatório pré-renderização (rosto desobstruído, lower third, loudness, safe zone 9:16, identidade, 7 cortes) está em **`PREFERENCIAS.md` §10** — valide contra ele antes de entregar qualquer episódio ou corte. **Não mantenha uma cópia aqui** (é a causa clássica de divergência).
