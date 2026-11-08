# Fila de revisão e correções — 08/11/2026

A entrada padrão abre **Job individual → Para revisar**, considerando decisões
salvas para os renders atuais, inclusive aprovação com ajustes e decisões legadas.
**Revisados** e **Todos** permitem consultar ou complementar avaliações anteriores.
Um link direto para um job continua abrindo esse job.

Os campos de comentário, descrição de ajustes e estrelas continuam em formulário:
editar não grava nem reexecuta a revisão. O botão de decisão salva o conjunto.
Ao salvar o último candidato ainda pendente, aparece a confirmação com a quantidade
real de candidatos e abre o próximo job pendente. Sem outro job, aparece a conclusão
da fila. Editar um job já concluído não dispara esse avanço. Um render substituído
durante o salvamento cancela a transição; não se presume revisão da nova versão.

Novas seleções procuram o fim de frase nas palavras da fonte e preservam até
150 ms de intervalo observado após a fala, dentro do limite salvo. O contexto
textual não inclui palavras que ficariam além do corte. Isso evita palavra/frase
truncada; pontuação não prova conclusão narrativa. Sem evidência suficiente, o
diagnóstico permanece explícito. Retrabalho de candidato avaliado exige nova
revisão, sem apagar arquivos, comentários ou aprovações anteriores.

O Telegram usa vínculo persistente entre mensagem, candidato, render e hashes do
artefato/mestre. Comentários novos são aceitos mesmo após avaliação na aplicação.
Recusa sem classificação explícita usa UNSPECIFIED, sem inventar notas. Observação
sobre render antigo fica no histórico desse render e não decide uma versão nova.
O cliente deve confirmar o recibo antes de dizer que salvou.

Dimensões e duração do envio vêm do MP4 medido; metadados desconhecidos de um ACK
antigo permanecem desconhecidos. A normalização de frames agora seleciona 30 fps
no relógio da fonte. A investigação e suas limitações estão no
[relatório audiovisual](../research/TELEGRAM_AV_MEDIDAS_2026-11-08.md); o levantamento
editorial está no [diagnóstico de feedback](../research/FEEDBACK_CLOSURE_DIAGNOSIS_2026-11-08.md).
Não há publicação, aprovação ou treinamento automático por causa dessas mudanças.
