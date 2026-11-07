# Editorial Learning System

**Branch de implementação: `codex/editorial-learning`.** Toda pesquisa adicional em fontes primárias, dataset, recuperação, ranker e eventual fine-tuning ficam separados do produto. Contratos de feedback humano e briefing estático são fundações comuns implementadas na branch de produto. Este documento registra a investigação para planejamento; não ativa aprendizado.

## Recomendação

Começar com feedback confirmado + briefing versionado + recuperação de exemplos. Isso adapta o contexto do Qwen sem treinar pesos. Preparar interfaces/dataset desde cedo para testar um reranker leve depois. Não treinar LLM, recompensa neural ou fine-tuning com os dados atuais.

Há cinco fontes na rodada detalhada, não 15 fontes; clones, diagnósticos e recortes não aumentam independência. Há 11 aprovações legadas, oito com ressalvas, e zero rótulos no novo contrato. Nem mesmo os três comentários apenas “bom” são convertidos silenciosamente em novos positivos.

## Alvos distintos

| Sinal | Uso permitido | Uso proibido |
|---|---|---|
| `content_grade` humano 0–3 | Relevância/utilidade e ranking de conteúdo: 0 irrelevante, 1 fraco/incompleto, 2 útil, 3 conteúdo completo alinhado ao brief | Inferir grade 3 de um APPROVED legado |
| `release_ready` derivado de avaliação v2 confirmada | Qualidade pronta, em conjunto com QC e ausência de pendências | Treinar relevância com toda falha de render/enquadramento como negativo |
| APPROVED_WITH_ADJUSTMENTS | Aprender risco/tipo de edição; conteúdo pode ter grade alta, baixa ou desconhecida | Tratar como exemplo ideal ou recusa automática de conteúdo |
| Preferência relativa confirmada | Comparar opções daquele conjunto, inclusive todas ruins | Deduzir qualidade absoluta ou multiplicar pares como fontes independentes |
| Recusa editorial | Negativo de conteúdo apenas quando alvo/motivo humano sustentam esse uso | Usar motivo técnico, administrativo ou desconhecido como irrelevância |
| Qwen/Hermes sugere motivo/score | Feature versionada ou sugestão a confirmar | Ground truth, aprovação ou autorreforço com pseudorrótulos |

`release_ready=1` somente com decisão v2 APPROVED no artefato atual, QC permitido e sem pendência bloqueante; APPROVED_WITH_ADJUSTMENTS não conta como pronto. Pendente, legado não confirmado e alvo ausente são desconhecidos, não zeros de conteúdo. Para o primeiro classificador B, usar `content_grade>=2` como alvo binário **somente quando grade humana existir**; manter readiness e risco de edição como saídas separadas.

## Comparação dos estágios

As quantidades abaixo são **guardrails de engenharia propostos**, não mínimos universais publicados ou garantia de ganho. Aprovar antes de iniciar treino e rever com curvas de aprendizado/intervalos de confiança.

| Estágio | Dados e gate | Benefício esperado, custo e localidade | Risco/manutenção |
|---|---|---|---|
| A: brief + exemplos | Pode começar com poucos casos confirmados, positivos/negativos/condicionais diversos; reportar cobertura. Piloto de cinco fontes é descritivo | Sem treino; Qwen existente, recuperação lexical CPU/stdlib. Mais tokens/latência medidos. Exatidão do contexto é pré-requisito | Seleção enviesada de exemplos, overfitting ao criador e injeção em comentários. Manter brief, filtros e dataset versionados |
| A opcional: embeddings | Testar recuperação contra consultas/casos julgados; aprovar encoder/licença/download/recursos antes | Busca multilíngue exata em cache local, sem banco vetorial; CPU, sem disputar a K4200. Embeddings representam similaridade, não preferência aprendida | Exemplos semelhantes porém editorialmente opostos; idioma, truncamento e versão do encoder |
| B1: regressão logística | Proposta: >=50 famílias de origem e >=150 candidatos com grade confirmada; >=30 positivos e >=30 negativos distribuídos em >=10 famílias por classe. Holdout >=15 famílias; treino com classes representadas nos folds | Regularização, poucas features, inferência/treino CPU leves; explicável. Adicionar scikit-learn como extra offline somente neste marco | Alto risco com pouco dado/feature demais; calibrar fora do treino, imputer/scaler ajustados somente no treino |
| B2: preferência linear | Além do gate B, >=100 pares humanos não empatados, em >=30 famílias; não contar pares combinatórios como dados novos | Bradley–Terry/logística sobre diferença de features; ensina ordem mesmo sem aprovação absoluta | Comparações contraditórias/ties; restringir ao mesmo conjunto/objetivo e normalizar peso por família |
| B3: boosting / LambdaMART | Só após B1/B2, com curva de aprendizado e erro residual mostrando limitação; proposta >=100 famílias/300 candidatos graduados | Árvores capturam interações; learning-to-rank organiza por qid. CPU inicialmente; XGBoost é dependência adicional apenas se ganho justificar | Mais tuning/overfitting e artefatos. Não adicionar XGBoost para replicar o que o modelo linear já resolve |
| C: SFT/LoRA/DPO | Opcional; proposta para estudo: >=500 famílias/2.000 exemplos de planos finais humanos para SFT; DPO precisa >=1.000 pares válidos em >=200 famílias, de mesmo contexto, e holdout separado. Investigar apenas se A/B atingirem limite mensurável | Pode adaptar geração de planos, não só ordenação. Custo de curadoria/treino/conversão/serving muito maior; infraestrutura compatível e orçamento explícitos | Overfitting, regressões PT/EN, direitos e manutenção de adapters/base/quantização. Não assumir suporte de treino na K4200; não obrigatório |

SFT requer entrada→plano editorial correto, revisado e ligado a render aceito. DPO requer entrada e saídas escolhida/rejeitada comparáveis; comentário livre ou dois clipes de objetivos distintos não constituem automaticamente esse dataset.

## Estágio A executável, sem dependência inicial

1. Brief aprovado é snapshot por job; não modificar o prompt global em resposta a cada comentário.
2. `select_examples` filtra: confirmação humana, autorização, mesma política/escopo compatível, elegibilidade e disponibilidade na partição permitida. Excluir sempre a família da consulta, duplicatas do candidato e revisões antigas suplantadas.
3. Primeira recuperação usa termos/tema/motivos confirmados e diversidade, com stdlib. No máximo três exemplos, um por família, buscando positivo de conteúdo, negativo relevante e condicional quando existirem. Não forçar categoria ausente com exemplo ruim.
4. Orçamento inicial proposto: 600 tokens para exemplos, subordinado ao contexto real de 4.096 tokens e à reserva de geração. Preservar corpo, fechamento e contexto próximo; reduzir exemplos primeiro. Se não couber, avaliação por blocos com fim preservado ou falha explícita, nunca `[:700]` silencioso. Não enviar timestamps de cada palavra quando bastam IDs de segmentos.
5. Embeddings são uma alternativa ao seletor lexical. Comparar resultados julgados antes de ativar. Cache por hash de texto/esquema/encoder/revisão; busca por cosseno em arquivo/array local. Para este volume, busca exata é suficiente.
6. Uma opção para ensaio é `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, por suporte PT/EN. Não foi baixada nem medida nesta máquina. Biblioteca/weights só entram após justificar recuperação lexical insuficiente, verificar licença/revisão e medir CPU/RAM/latência. Não presumir que Qwen GGUF generativo seja encoder de embeddings.
7. Registrar IDs, scores, ordem, hashes e tokens dos exemplos usados. Se não houver exemplos elegíveis, executar baseline com diagnóstico, sem inventar memória.

## Features e ranking B

Features possíveis: relevância temática, autopromoção, hook/contexto/narrativa/prova/fechamento, promessa entregue, duração/posição, pausas/energia, fronteiras de cena, tipo visual/ROI, repetição de tema e diversidade. Cada feature tem versão, origem (`rule|llm|audio|visual`), confiança quando real e indicador de ausente. Score do Qwen não é rating humano.

Manter três conjuntos: **conteúdo** para ranker; **risco de edição** para priorizar retrabalho; **QC operacional** para bloquear artefatos inválidos. Uma recusa por crop não é negativo do ranker de conteúdo. Features históricas usam apenas eventos anteriores ao cutoff e outros grupos; a avaliação atual, sua decisão e pedidos de edição atuais nunca são inputs do próprio exemplo.

Começar B com <=12 features interpretáveis selecionadas previamente; comparar baseline e logística regularizada antes de árvores. Esse teto inicial é uma escolha conservadora revisável, não propriedade do algoritmo. Avaliar preferência linear com pares confirmados e qid; empates ficam fora da perda de pares. Contradições são reportadas para adjudicação, sem forçar ordem silenciosa.

## Ciclo e proteção contra aprendizado incorreto

`gerar com versões → revisar → preservar comentário → confirmar motivos opcionais → editar em nova versão → revisar versão corrigida → exportar snapshot → avaliar offline → aprovar política/modelo → resolver snapshot em novos jobs`.

- Eventos novos têm alvo explícito; snapshots legados repetem decisões anteriores, portanto exportar uma amostra canônica por candidato/versão/tarefa, sem uma linha por cópia de histórico.
- Uma ação administrativa em lote tem `batch_action_id`/escopo e peso de treino editorial zero por padrão. Preservar sua rastreabilidade.
- Correção de framing/renderer gera vínculo pai→filho e permite medir edição; não atribuir ganho ao ranker se sua seleção não mudou.
- Grupo de origem transitivo inclui recortes, clones, variantes e fontes com mesmo conteúdo identificadas. Split por arquivo isolado é insuficiente.
- Extração de features, exemplos de prompt, seleção de hiperparâmetros e normalização de labels respeitam o split. Retrieval da avaliação só usa treino; não permitir comentário do teste em exemplos.
- Sugestões de motivos e autocríticas ficam separadas. Sem aprendizado online de pseudorrótulos, sem promover alterações de preferências sem humano.
- Treinamento registra dataset/split/feature schema/semente/dependências/métricas; artefatos só de origem interna verificada. Registro ativo é ponteiro reversível, não sobrescrita dos pesos anteriores.

## Promoção e rollback

Estágio não avança por contagem isolada. Exigir qualidade dos rótulos, cobertura PT/EN, benefício em fontes não vistas e critérios de EVALUATION. No conjunto atual, resultados são descritivos; A pode ser ensaiado opt-in após confirmação dos exemplos. B/C estão fechados por falta de dados e, para C, por infraestrutura não demonstrada.

Cada proposta de brief/exemplos/modelo inclui diff e relatório. Humano aprova ativação. Rollback aponta para a versão anterior, preserva dataset/eventos/artefatos e não altera jobs já criados. Se o gate falhar, manter baseline e registrar o motivo; não ajustar indefinidamente contra o holdout.

## Fontes primárias consultadas

Consultadas em 06/11/2026; algoritmos não foram treinados nesta etapa.

- [Regressão logística regularizada — scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html): baseline linear leve; versão da biblioteca será fixada no futuro, sem copiar cegamente assinatura de versão rolling.
- [Gradient boosting — scikit-learn](https://scikit-learn.org/stable/modules/ensemble.html): alternativa para interações; a própria documentação distingue implementações conforme tamanho da amostra.
- [Learning to Rank — XGBoost](https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html): ranking supervisionado por grupos/qid e objetivos pairwise/NDCG.
- [Busca semântica — Sentence Transformers](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html): recuperação por embeddings; não exige um serviço vetorial neste desenho.
- [Encoder multilíngue candidato — model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2): opção a validar, sem adoção atual.
- [LoRA — artigo original](https://arxiv.org/abs/2106.09685): adapters de baixo rank reduzem parâmetros treináveis; não demonstram compatibilidade com a K4200 deste projeto.
- [DPO — artigo original](https://arxiv.org/abs/2305.18290): otimização baseada em pares de preferências; não torna os poucos exemplos atuais suficientes.
