# Reedição automática — aceitação de 11/11/2026

Decisão do usuário: aguardar todas as avaliações. Quando houver aprovação com ajustes, criar um job filho com uma proposta, usando todas as avaliações/artefatos atuais, notas, preferências e notas por dimensão. Originais preservados, sem reprocessamento retroativo nem publicação automática.

## Implementação

Outbox no próprio job, hash das avaliações e UUID determinístico evitam duplicação. Worker existente reconcilia entrega à fila a cada 30 s. Qwen seleciona uma alternativa pré-validada de corte, extensão ou combinação cronológica da mesma fonte. Não são aceitos IDs/timelines inventados. O resultado exige nova revisão humana. auto_pace mede ritmo por timestamps, limita a 1,15x, preserva tom com atempo e remapeia legendas/enquadramento no mesmo relógio. Snapshots antigos sem o campo mantêm ritmo original. Montagens limitadas a 120 s; clipes contíguos mais longos preservam o caminho original.

Palavras Whisper sem duração são agrupadas com fala adjacente por limites de tempo nativos, sem interpolar ou alterar o ASR salvo. Proveniência e agrupamento ficam na timeline/UI. Trechos sem intervalo utilizável continuam recusados. O ritmo opcional inicial mantém o original com diagnóstico se não houver tempos seguros.

## Verificações observadas

- Suíte final: **668 testes Python passaram em 408,76 s**. Frontend: **13 passaram**. Build frontend/API, Compose base+Kepler+API e git diff --check passaram; somente avisos LF/CRLF.
- Falhas de compatibilidade encontradas na primeira suíte (metadados mínimos de candidatos e orçamento de prompt antigo) foram corrigidas; regressões focadas passaram e a suíte final acima foi executada depois das correções.
- Teste FFmpeg real: intervalo de 2,2 s a 1,1x gerou 2 s; FFT preservou tom de 440 Hz; legenda .55–1.1 foi remapeada para .5–1.0. Decodificação completa passou.
- QA isolado: pai 1ee1eb5f-fe12-4b77-8dc1-e19ab0b68b5a, filho 2f1e56bc-dae1-5d8b-9755-37f8e59b930d. Foram usadas cópias de mídia/transcrição previamente autorizadas, com comentários de ensaio técnico, sem avaliações editoriais reais em produção. Primeiro voto não criou job; após o segundo, a UI criou uma única solicitação/filho.
- Ensaios iniciais revelaram limites do planejador livre e tokens ASR com duração zero. Foram corrigidos com seleção de alternativas pré-validadas e agrupamento explícito por tempos nativos. Retentativas ocorreram somente nesse job de QA e ficaram no histórico.
- Execução final com Qwen 2.5 3B/Kepler + Remotion high: um candidato **VALID**, dois trechos [249.08,267.12] e [392.0,414.14], 146 palavras, NEEDS_REVIEW/PENDING. Ritmo 1x porque a fala tinha 218 palavras/min; cinco tokens agrupados, com aviso visível.
- WebM 720x1280 reproduzido até ended (40,607 s); MP4 iniciou reprodução (40,6 s). FFmpeg decodificou ambos integralmente. agent-browser CLI confirmou ausência de overflow em 375 px e ausência de erros JS; produção HTTP/Tailscale abriu Revisão após implantação. Safari físico não foi testado.
- Revisões independentes identificaram snapshot de encerramento e avaliação comparativa ausentes; ambos corrigidos com regressões. Nova conferência focada de seleção, tempos e proveniência não apontou achados acionáveis.

## Operação final

Fila/processing de produção estavam em zero antes da implantação. Worker, web-api, API e frontend foram recriados sem build do worker/modelos, sem interromper jobs. Publisher e volumes foram preservados. Skill do Hermes foi atualizada com backup. A tarefa privada de túnel estava parada e foi iniciada novamente para a verificação de conectividade. QA foi parado preservando arquivos/volumes; nenhum publisher de QA foi iniciado.

O job reservado d27316c7-6a8e-41f9-bf0e-9cbbefdfcfd7 **não foi reprocessado** pelo agente: SHA256 51D3A4EDF14306FE337FF13C7D7C2BB386CD70F6FA4AE625BED7B7F1E6449565 permaneceu igual, status FAILED. Sua ação real continua reservada ao teste pelo Hermes.

A tentativa não garante qualidade editorial nem executa instruções arbitrárias em texto livre; pedidos fora dos controles disponíveis podem exigir o editor manual. Feedback/contexto acima do limite do modelo falha explicitamente. Não houve publicação nova, treino ou promoção automática.
