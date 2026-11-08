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

## Aceitação observada e revisões disponíveis

Código implantado na main: `2e1a293`. Suíte isolada: 513 testes passando; verificações
focadas adicionais de revisão/seleção/render/fila: 38 passando. Os dois workflows
GitHub do commit passaram; Compose config e diff check passaram. Agent-browser
confirmou formulário sem envio a cada alteração, confirmação/avanço com dois jobs
sintéticos e entrada padrão na aplicação real. Nenhuma avaliação real foi criada
pelos testes de navegador.

| Job / candidato no JSON | Nova revisão | Mudança |
|---|---|---|
| `0570af0f` / 2 | versão 2, render 2 | fim 89,54 → 91,95 s; conclui `incredible.` |
| `bde563a3` / 1 | versão 2, render 2 | fim 154,35 → 154,50 s; preserva cauda da fala |
| `af0c5e4a` / 1 | versão 1, render 4 | mesmo plano e intervalo 0,68–43,18 s; correção técnica de frames |

Os seis arquivos MP4/WebM chegaram a ended no Edge sem erro. As três versões
ficaram pendentes de nova avaliação. Os outros candidatos mantiveram suas decisões.
Conferência antes/depois: 40 jobs, 36 eventos humanos idênticos, candidatos irmãos
idênticos e 37 jobs não envolvidos idênticos. Todos os 318 arquivos anteriores
conservaram seus hashes. Apenas uma nota adicional recupera a proveniência literal
da mensagem Telegram 1705; a recusa recuperada já estava no baseline.

Mensagens antigas 1688 e 1704 foram vinculadas aos respectivos artefatos distintos.
O Gameplayrj render 4 foi aceito pelo Telegram na mensagem 1710, com ACK 720×1280,
duração 43 s e envio com streaming habilitado; o vínculo ficou salvo na aplicação.
Mestre novo: áudio com deslocamento medido de 0 ms contra a fonte, quadros com
diferença de até 16,7 ms. Ambos os formatos passaram decodificação completa. Isso
não substitui a conferência visual/auditiva no aparelho do proprietário.

Ainda em aberto: reconhecer conclusão narrativa além de pontuação, melhorar
propostas/títulos dos modelos pequenos, confirmar a apresentação no Telegram móvel
e reunir corpus elegível para treinamento offline. Não houve treino nesta rodada.
