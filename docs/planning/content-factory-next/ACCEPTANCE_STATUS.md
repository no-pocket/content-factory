# Aceitação da execução editorial — 07/11/2026

Código consolidado na main por autorização explícita do proprietário; registro
e validações em [consolidação de07/11](../../CONSOLIDACAO_MAIN_2026-11-07.md).
Produto: [PR3](https://github.com/no-pocket/content-factory/pull/3).
Aprendizado independente: [PR4](https://github.com/no-pocket/content-factory/pull/4), contra a branch de produto.
Baseline: [PR2](https://github.com/no-pocket/content-factory/pull/2). Originais, eventos,
volumes, modelos e serviços de produção foram preservados.

| Marco | Resultado observado | Limite / gate restante |
|---|---|---|
| G0/G1 | Baseline033a2d9, main619efee incorporada e branches separadas | Nenhum merge em main |
| M0/M1 | Contratos/eventos v2, artefatos e revisões imutáveis, conflito/idempotência | Legado permanece não confirmado |
| M2 | Três decisões, filtros por candidato, métricas com cobertura; dois clientes Streamlit testados | Não inventa nota/tempo de revisão legado |
| M3 | Contexto integral e chunks, budget explícito, brief e snapshots por job | Brief inicial DRAFT/inativo; bytes são teto conservador, não tokenizer exato |
| M4 | Fixtures PT/EN e controle em cinco fontes/15 janelas fixas; guard indicou bloqueio em2 casos | Estudo de regras sem inferência/render novo; ganho editorial humano NOT_EVALUATED |
| M5 | Vertical aprovado fora de janelas; ROI/página protegidas e legenda próxima; sintético e variante95s reais | 4cb/8b renderizados e inspecionados; anotação manual, sem detector/OCR |
| M6 | V3 uma fonte/1..12 trechos, teste AV440→880Hz, palavras na fonte e relógio por frames; real95s QC válido | Revisão humana de áudio/narrativa e timestamp legado suspeito continuam pendentes |
| M7 | Dataset local imutável:5fontes/15candidatos,11aprovações legadas/4recusas,18jobs administrativos separados | Zero grau v2 elegível; nenhuma classe humana inferida |
| M8 | Recuperação lexical opt-in, famílias/holdout excluídos, contexto prioritário, snapshot congelado |0 exemplos no corpus;0 chamadas; sem inferência/ganho de ablação demonstrado |
| M9 | CLI recusou treino com exit2, gates e preprocessamento/JSON testados | Dados insuficientes, aprovação ausente, dependência extra não instalada; fit não executado |
| M10 | Estudo documentado NO-GO com fontes primárias | Nenhum treino neural, modelo ou serviço adquirido |
| M11/M12 | Crítica/outbox/callbacks validados localmente/fakes/dry-run | Mantidos dry-run por escolha do proprietário; sem transporte/destino real usado |
| M13 | Dependências e imagem fixadas; métricas por etapa; build final e render curto da imagem observados | Acabamento integrado NÃO promovido: ganho2,70% ficou dentro da variação |

## Verificações

Produto:265 testes passaram (99,37s). Aprendizado:294 testes passaram (39,24s),
com revisão independente por branch e correções verificadas RED→GREEN. TypeScript,
Compose sem subir serviços e diff checks passaram. Não usar suíte como prova de
qualidade editorial.

Imagem candidata final, sem trocar o tag de produção:
`content-factory-editorial-candidate:20261107-final`, digest
`sha256:3bd96ce31e8237f5cbb1f6d151e639683760001e8720f9c6650c640115ddb247`.
Código de runtime no commit305f0b0, sourcehash
`af358563c18bb251d5e2bf1d6f306960413b4e7fd830b048ce7b605561448945`.
Commits posteriores de produto são documentação/evidência, sem alterar esse runtime.
Python3.11.18, Node22.23.4, FFmpeg5.1.9, Chromium158.0.8127.2; pip check passou.

A variante adaptativa de95s terminou no Edge390px nos dois formatos:
MP495,368s e WebM95,389s, erro null, player340px e sem overflow. Reprodução4x/muda
foi teste técnico; escuta e aprovação editorial humana não foram alegadas.
Job `2a8c9983-b78a-4006-b500-073e56ce15f9`, artifact
`sha256:b71503369197de4ae183542b726b5a38a5c88ce7a002e207e95d964c057dc6f5`.
Mídia local de demonstração fica no diretório ignorado
`research/pytest_temp_editorial/real-adaptive/`; não foi adicionada ao Git.

Controle de M4: [relatório de janelas fixas](../../../research/editorial_story_control_2026-11-07.json).
Ele registra fontes/ASR/config/contexto fixos e apenas a mudança do guard; não
compara modelos nem transforma ausência de guard em julgamento de qualidade.
A evidência de execução completa está em [EXECUTION](EXECUTION.md). O relatório
de aprendizado e o estudo de fine-tuning estão exclusivamente na branch/PR4.

## Antes de promover

Revisar os PRs e reproduzir as variantes com áudio para decidir narrativa, ASR,
legibilidade e estilo. Nenhum candidato foi aprovado automaticamente nesta execução.
Brief concreto para revisão: [EDITORIAL_BRIEF_DRAFT.json](EDITORIAL_BRIEF_DRAFT.json), DRAFT/approval=null; não gravado no ponteiro de produção.
Aprovar um briefing/modelo ou integrar/deployar uma branch são decisões separadas;
este plano não autoriza publicação social. Telegram/Hermes continuam dry-run.

## Controles reais de enquadramento

4cbC3: variante22f7c36c-3001-4b94-92d5-2af83367b8db, artifact
`sha256:3f21c793f232fc6b715ce9796456a86ae4e46a2966a36bcc219db9a5adb63e8d`,
fonte344,4–375,66s. Vertical até349s, tweet com ROI manual até371,833s,
artigo com outra ROI depois. A ROI única do primeiro rascunho não servia à troca
de página; esse rascunho foi preservado e não promovido. A nova variante mantém o
fim original: não corrige nem aprova o problema narrativo de cortar antes da
exibição completa da demonstração. Mestre31,634s e WebM31,645s, QC VALID.

8bC3: varianteb967cded-57f1-4099-b1a5-4ac91d7f515d, artifact
`sha256:6679b4a269fa63b7b4095b6b11d92fce17b1aad29d8b09cdae4a7c229f603a4e`,
fonte120,76–165,74s, tweet durante todo esse intervalo, ROI manual preserva a
coluna da publicação. Mestre45,367s e WebM45,384s, QC VALID; ambos terminaram no
Edge390px sem erro. Os dois controles usam as mesmas palavras/intervalos/timeline
arquivados; não há nova inferência ou rótulo humano. Frames inicial/meio/fim e a
troca de página foram inspecionados. Os dois formatos de4cb também terminaram no Edge390px com ended=true/error=null, player340px e sem overflow.

A UI de aprendizado foi conferida via agent-browser CLI em instalação efêmera:
recuperação desativada por padrão, ID de dataset vazio, vertical aprovado e
intervalos explícitos. Nenhum job foi submetido nessa UI; o container efêmero foi
parado após a conferência.
