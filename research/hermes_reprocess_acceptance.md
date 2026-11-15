# Hermes: reprocessamento explícito e diagnóstico — 11/11/2026

## Causa do job d27316c7-6a8e-41f9-bf0e-9cbbefdfcfd7

Vídeo IQt6ObvQ_Y4: transcrição em português com 75 segmentos e 1.344 palavras. O erro persistido `No usable speech windows found; try a longer video with speech` é genérico e não demonstra ausência de fala. No modo flexible, cinco propostas foram recusadas por story_evidence, duas por índices e uma resposta terminou por length. A heurística também retornou zero: exige marcador PAYOFF e pontuação final no mesmo segmento; nenhum dos 75 atende às duas condições. Seis segmentos têm marcador e seis têm pontuação final, mas não coincidem. Não houve falha de conexão Kepler observada; health retornou ok e os eventos mostram oito inferências. `kepler_gpu_pending` é residual: só completed/fallback substituem o marcador, mas candidatos vazios retornam antes desses eventos.

## Implementação

- Serviço `reprocess_failed_job`: somente FAILED sem candidatos, configurações e histórico preservados; requisição UUID idempotente, instrução do proprietário, ator da ponte e expected_run_id. Recuperação Redis existente evita duplicação/perda de resposta.
- Recusa 409 enquanto a execução terminal ainda estiver na lista PROCESSING; regressão reproduzida antes da correção. Evita aceitar retry entre o salvamento de FAILED e o acknowledgment do worker.
- POST /v2/hermes/jobs/<id>/reprocess e comando CLI reprocess. Fontes sem escopo externo vigente continuam bloqueadas.
- Status Hermes retorna latest_run_id, reprocess_available e diagnóstico seguro, sem expor mensagens arbitrárias de exceção/caminhos.
- Cliente e skill instalados no perfil nopocket-content do Pi. Versões anteriores preservadas em backups .pre-reprocess-20261111. Apenas o serviço API foi reiniciado; worker e gateway não foram reiniciados.
- Nenhum ajuste nos filtros editoriais nem nos snapshots existentes.

## Aprovação com ajustes

APPROVED_WITH_ADJUSTMENTS registra comentário, pedidos e histórico; não aplica edição automaticamente nem libera publicação. O resultado corrigido exige QC e nova revisão/aprovação humana. Retry técnico não interpreta instruções editoriais em texto livre. O teste existente test_adjustments_and_legacy_approvals_never_qualify passou na suíte focada.

## Validação observada

- 65 testes focados passaram (108,96 s), cobrindo API/CLI, concorrência, snapshot/histórico, resposta perdida, acknowledgment, escopo e publicação com ajustes.
- Revisão independente encontrou a corrida de acknowledgment; correção coberta por regressão que falhou antes do ajuste.
- Pi→API real via cliente instalado: GET status do job confirmou FAILED, reprocess_available=true e diagnóstico 5 story_evidence / 2 indices / 1 incomplete response. CLI reprocess --help disponível.
- agent-browser CLI abriu a revisão real do job em modo somente leitura: FAILED, zero players, sem erros JavaScript.
- Config Compose base+Kepler+API e git diff --check passaram (avisos LF/CRLF).
- Suíte completa: 634 passaram em 385,56 s. Não foi executado reprocessamento real: reservado ao teste solicitado pelo usuário através do Hermes.

Arquivo do job permanece com SHA256 51D3A4EDF14306FE337FF13C7D7C2BB386CD70F6FA4AE625BED7B7F1E6449565, igual ao início. Nenhum POST reprocess foi enviado ao job real; mídia, transcrição, settings e filas não foram alterados por esta validação.

