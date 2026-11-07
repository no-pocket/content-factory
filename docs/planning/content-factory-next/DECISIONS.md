# Decisões e pendências

## Aprovado pelo usuário para planejamento

| Decisão | Consequência |
|---|---|
| Separar técnico/editorial/edição | Estado do job não substitui decisão por candidato |
| Aprovar com ajustes, motivos e dimensões | UI/backend/dataset precisam preservar esses sinais separadamente |
| Contexto completo e fechamento semântico | Corrigir corte de 700 caracteres e avaliar demonstração/conclusão antes do fade |
| Relevância GTA VI, sem autopromoção dominante | Briefing versionado; não uma regra universal para todos os futuros projetos |
| Enquadramento por conteúdo | Permitir fit/composição/ROI em vez de exigir crop central |
| Multitrecho 1–2 minutos | Timeline nova e mapa de tempos; preservar v2 antiga |
| Feedback progressivo | Dataset confiável, recuperação de exemplos e avaliação; ML somente após gates |
| Manter stack e aparência aprovada | Sem reescrita, sem degradar mestre ou legendas para acomodar integrações |
| Telegram e Hermes | Planejar capacidades e testes; nada enviado/treinado/publicado nesta execução |
| Ordem | Clareza da revisão → inteligência editorial → visual → multitrecho → aprendizado/integrações |

## Orientação posterior do usuário para o próximo agente

Primeiro consolidar o trabalho acumulado em commit, dar push upstream e abrir PR. Depois criar branch local de produto sincronizada com main e executar todos os marcos de produto, validando e comitando cada um. Pesquisa em fontes primárias, recuperação de exemplos, ranker leve e eventual fine-tuning ficam em `codex/editorial-learning`, separada de `codex/editorial-product`. Nenhuma operação Git remota é executada nesta rodada documental. Não há autorização implícita para merge em main ou treinamento sem os gates.

## Escolhas técnicas propostas por este plano

Estas são escolhas de projeto justificadas, não novos resultados experimentais. Conferir contra o código ao executar cada marco; o desenvolvimento posterior de produto já foi solicitado.

1. JSON existente é a fonte de verdade. Eventos v2 ficam no registro do job sob o lock existente; exportações de dataset são derivadas. Sem banco novo, MLflow ou serviço vetorial.
2. Legacy APPROVED não vira automaticamente APPROVED sem ajustes no novo contrato. Exibir decisão original e condição não confirmada; exportar rótulo absoluto desconhecido até confirmação humana.
3. Coletar identidades/versões em M1. Dataset, extração de features e avaliação começam antes de qualquer treino.
4. Iniciar A com exemplos confirmados e recuperação lexical local. Embeddings multilíngues em CPU são uma alternativa avaliada, não pré-requisito nem download autorizado.
5. Primeiro modelo B, se os gates forem atendidos: regressão logística regularizada para conteúdo ou preferência linear por diferenças de features. Boosting/LambdaMART só se houver limitação medida da alternativa simples.
6. Fine-tuning não faz parte da primeira entrega. K4200/CUDA 10.2 não é pressuposto de infraestrutura de treino moderna. GGUF de inferência não é checkpoint pronto de treinamento.
7. Timeline multitrecho monta base FFmpeg e mantém Remotion para composição. Sem mistura automática de falas; cronologia preservada por padrão.
8. API v1 continua atendendo jobs legados. Novos jobs opt-in no protocolo editorial 2 usam revisão ligada ao artefato; clientes v1 não podem aprovar esses jobs sem atualizar o protocolo. Detalhes em DATA_CONTRACTS; sem mudança silenciosa de significado.
9. Treino, publicação de briefing ativo e promoção de modelo são operações distintas. Promoção só com evidência e aprovação humana, nunca porque houve feedback novo.

## Decisões em aberto, com default que permite planejar

| Ponto | Default proposto | Resolver até |
|---|---|---|
| Escala das dimensões | 1–5 ou null; grau de conteúdo separado 0–3, confirmado | M0/M1, antes de coletar v2 |
| Rubrica “pronto” | APPROVED sem pendências maiores; ajustes explícitos viram outra decisão | M1 com usuário |
| Severidade | MINOR/MAJOR/CRITICAL; nunca inferida como humana sem confirmação | M1 |
| Ativação v2 e compatibilidade de clientes | Opt-in por job novo; v1 legado preservado | M1 |
| Orçamento de recuperação | Até 3 exemplos e 600 tokens, reduzível para preservar corpo/fim/contexto; conferir tokenizer real | M8 |
| Encoder de embeddings | Nenhum por padrão; comparar um multilíngue CPU após autorização de dependência/download | M8 opcional |
| Gates numéricos e margem de regressão | Valores de EVALUATION são guardrails propostos, não leis de amostragem | Antes de M9 |
| Composição visual | Presets por cena e ROI manual primeiro; OCR/visão só após justificar dependência | M5 |
| Hermes | Confirmar endpoint que executa tarefa, modelo/provedor, visão, resposta estruturada e custo | M11 |
| Telegram | Bot dedicado/polling, destino e usuário autorizados; limite de arquivo validado na documentação vigente | M12 |
| Publicação social | Fora do escopo, sem credenciais ou envio automático | Somente novo pedido explícito |

Nenhuma pendência permite alterar avaliações antigas por suposição. Se uma escolha impedir um marco, registrar o bloqueio concreto; executar somente trabalho independente que permaneça autorizado.
