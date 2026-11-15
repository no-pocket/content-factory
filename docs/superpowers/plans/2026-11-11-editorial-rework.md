# Reedição orientada por avaliação humana

Decisão do usuário: iniciar automaticamente após avaliar todos os candidatos. Objetivo: tentar produzir um candidato melhor com o conjunto das avaliações, combinando/encurtando/estendendo trechos da mesma fonte. Nunca aprovar ou publicar automaticamente. O job d27316c7-6a8e-41f9-bf0e-9cbbefdfcfd7 continua reservado ao teste do Hermes, sem reprocessamento pelo agente.

## Contrato

- Uma decisão ADJUSTED junto com todas as decisões atuais concluídas cria uma solicitação persistida no job. Hash das avaliações/artefatos evita duplicação por replay; job filho conserva o original e herda seus limites/autorizações. Novas avaliações diferentes podem gerar outra proposta explícita; não há loop automático de melhoria.
- Worker existente e fila Redis existentes. Outbox pequeno no próprio job resolve a lacuna entre gravar a avaliação e enfileirar o filho; reconciliação a cada 30 s quando o worker volta ao loop. Não haverá serviço novo.
- Filho recebe snapshot de todas as avaliações, source_parent_job, settings próprios (um candidato, montagem v3 e ajuste leve de ritmo), reaproveita entrada e transcrição. Não altera snapshots originais.
- Planejador local recebe avaliações completas e texto integral dos segmentos dos candidatos, com contexto adjacente. Seleciona alternativas de intervalos pré-validados por IDs existentes, em ordem cronológica, sem sobreposição, dentro do limite salvo e do teto atual de montagem de 120 s. Contexto/JSON incompletos ou inválidos falham explicitamente; sem truncamento silencioso ou substituição heurística do pedido.
- Ritmo: medir palavras/minuto nos timestamps Whisper; só acelerar fala observadamente lenta, entre 1 e 1,15x. Modelo pode manter ritmo natural. Remapear vídeo, áudio (atempo preserva pitch), legendas e enquadramento para o mesmo relógio de frames. Novos jobs têm opção auto_pace; jobs antigos sem esse campo continuam com ritmo original.
- UI e Hermes mostram ligação pai/filho e ritmo aplicado. Qualquer saída volta a NEEDS_REVIEW com decisão PENDING. Pedidos anteriores à implantação não disparam um lote retroativo.

## Execução e aceitação

1. Testes primeiro: gatilho após última avaliação, idempotência/recovery, todas as notas no snapshot, preservação de originais e direitos; contratos de intervalos/ritmo e relógio de legendas.
2. Implementar serviço/outbox/planejador e integração no worker sem novo serviço. Estender montagem v3 com rate opcional e defaults compatíveis.
3. Expor configuração e acompanhamento no React/Hermes, atualizar contratos/docs e skill instalada.
4. Testes focados, render sintético com áudio/legendas e decodificação completa, fluxo real agent-browser em ambiente isolado, suíte adequada, config e diff check. Inspecionar fila/dados/disco antes de implantação; não interromper jobs ativos.
