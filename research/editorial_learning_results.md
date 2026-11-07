# Aprendizado editorial — execução offline

Execução de07/11/2026, branch `codex/editorial-learning`. Sem treino, inferência
nova, download de modelo ou envio externo nesta etapa.

## M7: população e integridade

A coorte autorizada contém cinco fontes/15 candidatos:11APPROVED legados e4REJECTED.
As18 recusas administrativas têm47 candidatos e ficam em auditoria separada.
Há zero evento v2 confirmado e zero grau0–3 elegível; aprovações com ressalvas e
comentários “bom” continuam sem alvo absoluto. Os comentários legados completos
permanecem no export local, não neste relatório nem no Git.

Export verificado localmente: dataset
`7fd4efa33fbd1ba122a29ad430624e8ce03762cecd7375996fa5366ddfe26fe4`, cutoff
`2026-11-07T00:00:00Z`. Hashes dos JSON de entrada, conteúdo canônico, registros,
critérios e famílias estão no manifest imutável. O export bruto está somente em
diretório ignorado pelo Git. Nenhuma fonte/decisão foi alterada.

Famílias unem proveniência/parent/hash/aliases confirmados transitivamente antes
do split; holdout explícito pode ser fixado por job de origem. Novos datasets não
herdam automaticamente um holdout: deve-se conservar a lista aprovada de origens.
A semente estável serve para desenvolvimento descritivo, não para abrir e ajustar
contra o mesmo teste repetidamente.

Métricas ficam null sem revisão/grade confirmada e mostram cobertura. Precision@3
usa três slots, NDCG usa ganho linear e média de empates, IDCG0 é excluído. Pedidos
de edição são deduplicados por fonte/edit_id. Recusas administrativas não entram
no denominador editorial. Preferências registram “todas abaixo do padrão” sem criar
positivo; o contrato v2 atual não registra empate A/B, então esse resultado aparece
como NOT_RECORDED_BY_V2_CONTRACT, nunca como empate inventado.

Features pré-decisão são <=12, com valores ausentes explícitos; decisão, ratings e
pedidos atuais não entram como features. Não há resultado causal de melhoria do
ranker, nem comparação estatística a partir das cinco fontes.

## Fontes primárias verificadas

Consultadas07/11/2026. Versões rolling de documentação são referências conceituais,
não dependências instaladas.

- [GroupKFold e grupos não sobrepostos](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html): justifica particionar por família, não por candidato.
- [Vazamento e pipelines](https://scikit-learn.org/stable/common_pitfalls.html): preprocessamento deve ser ajustado exclusivamente em treino.
- [NDCG e empates](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html): referência para tratamento de ties; ganhos/denominadores são decisões deste projeto.
- [LoRA, Hu et al., v2](https://arxiv.org/abs/2106.09685v2): adapters treináveis sobre uma base congelada; não prova suporte da workstation.
- [DPO, Rafailov et al., v3](https://arxiv.org/abs/2305.18290v3): aprendizado de preferências entre saídas comparáveis; não transforma aprovação legada em par elegível.
