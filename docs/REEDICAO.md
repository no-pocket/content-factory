# Reedição após avaliação humana

Quando todos os candidatos de um job v2 têm decisão atual e existe APPROVED_WITH_ADJUSTMENTS, a aplicação solicita um job filho com um candidato. Comentários, notas do artefato atual, dimensões, grau e comparação entre candidatos compõem um snapshot. Originais, avaliações, entrada e ASR são preservados. Repetições idênticas não duplicam a solicitação; novas avaliações diferentes podem gerar outra proposta. Não há execução retroativa dos ajustes históricos nem loop sem nova ação humana.

O backend prepara alternativas validadas de corte, extensão e combinação cronológica; Qwen escolhe uma usando as avaliações e o texto integral do contexto observado. Não inventa IDs ou comandos. Contexto/resposta inválidos falham explicitamente, sem truncamento silencioso. Montagem limitada a 120 s e aos limites herdados. O resultado exige QC e nova revisão humana; nunca é aprovado ou publicado automaticamente.

CONTENT_FACTORY_AUTO_REWORK=true é o padrão Compose. false desliga novos pedidos automáticos. A intenção é persistida junto com a avaliação e entregue à fila existente, com reconciliação a cada 30 s no loop do worker. A interface e o status Hermes mostram pai/filho e pendências. Fontes revogadas/entradas indisponíveis bloqueiam a entrega.

Novos jobs React/Hermes habilitam auto_pace; a opção pode ser desmarcada. Snapshots antigos sem o campo continuam com ritmo original. Fala observadamente lenta pode receber 1,10x ou 1,15x (limite 1,15), respeitando a duração mínima; o modelo pode manter ritmo natural. Áudio usa atempo para preservar o tom; vídeo, legendas e enquadramento compartilham o relógio de frames. Clipes contíguos acima de 120 s mantêm ritmo original para preservar compatibilidade com o caminho flexível de 180 s.

Tokens Whisper com duração zero são agrupados com fala adjacente usando somente limites nativos observados, sem interpolação ou alteração do cache. Isso é indicado na timeline e na UI para conferência. Dados sem intervalo positivo utilizável continuam sendo recusados na montagem; o ritmo opcional inicial mantém o original com diagnóstico quando não há tempos seguros.

A tentativa não garante qualidade editorial nem aplica qualquer instrução arbitrária em texto livre. Ajustes fora das operações suportadas podem exigir o editor manual e nova conferência.

Validação: [ensaio técnico](../research/editorial_rework_acceptance.md).
