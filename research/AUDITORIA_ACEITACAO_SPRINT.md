# Auditoria de aceitação da sprint — 06/11/2026

Conferência contra o pedido original, sem tratar QC como aprovação editorial. Estado consultado diretamente no worktree e nos registros de produção: [snapshot](sprint/acceptance-current-state.json).

| Requisito | Evidência verificável | Situação |
|---|---|---|
| QC MP4/WebM: decode, duração, resolução, áudio, silêncio e preto | `app/quality.py`, `tests/test_quality.py`, relatórios por candidato nos 12 jobs do `corpus-manifest.json` | Implementado; 36 candidatos tecnicamente verificáveis no lote |
| Limites configuráveis e diagnóstico; distinguir aviso contextual de falha | `docs/CONTROLE_QUALIDADE.md`, snapshot `qc_settings`, QC de cada tentativa | Implementado; silêncio/preto não significam rejeição automática |
| Retry de candidato com limite e preservação dos irmãos | `app/candidates.py`, `tests/test_interruptions.py`, `tests/test_candidates.py`, `sprint/recovery-real.json` | Teste automatizado e SIGKILL real isolado; hash do irmão preservado |
| Estados verificáveis e falha parcial | QC, worker, serviço de revisão e testes de aprovação bloqueada | NEEDS_REVIEW/PARTIAL_FAILED/FAILED explícitos; UI só reproduz candidatos verificáveis |
| Inventário e corpus autorizado | `inventory.json`, `corpus-manifest.json`, `corpus-summary.json` | 12 fontes aceitas explicitamente pelo usuário, 9 PT/3 EN; não faltam vídeos para esta rodada |
| Dimensões, decisão, motivo, retrabalho e ajustes | `app/editorial.py`, UI e API compartilhando `app/service.py`; testes HTTP/serviço e navegador sintético | Implementado; notas opcionais sem inventar avaliação; histórico preservado |
| Métricas, denominadores, tempo e comparação por fonte/configuração | `docs/PROTOCOLO_EDITORIAL.md`, `tests/test_editorial.py`, painel e GET /v1/metrics | Implementado; não inferir efeito causal de poucas decisões |
| Refinar usando decisões reais e separar sinais da seleção | Recusas reais em `user-rejections.json`; correções de legenda/UI/render; `app/signals.py` e `app/editorial.py` | Preferência do usuário aplicada ao perfil inicial; nenhuma regra editorial aprendida automaticamente |
| Investigar pausas, energia, cenas e PySceneDetect | `signals.json`, doze relatórios `signals-*.json`, relatório principal e corpus | Comparação offline nas mesmas fontes; 21/36 janelas alteradas, melhoria editorial não comprovada; não incorporada à seleção |
| Recuperação de persistência, fila, render e revisão | testes store/recovery/interruption/editorial, `recovery-real.json`, revisão sintética após reload | Cobertura por processo/checkpoint; sem alegação de proteção contra perda de energia do host ou coordenação multiworker |
| API estável para outro frontend, lógica no backend, auth/local | `app/api.py`, `app/service.py`, OpenAPI, `docs/API.md`, `compose.api.yaml`, testes HTTP e upload real isolado | Implementado; UI usa mesmo serviço; sem publicação externa; sem idempotency key/Range HTTP |
| Comparar modelos: latência, recursos, respostas, compatibilidade | ensaios Qwen PT/EN v2, ASR tiny/base, piloto K4200, inventário GGUF e relatórios anteriores | Concluídos ensaios delimitados; 3B GPU tem fallback na direção. Usuário considerou os dois modelos idênticos; variante posterior com título humano e cauda foi aprovada |
| Inventário dos clones, licenças e custo | `sprint/clones.json`, tabela do relatório principal | Concluído; nenhuma cópia de código ou dependência introduzida |
| Testes, mídia autorizada, fluxo real e documentação | 136 testes; teste HTTP ampliado passou; agent-browser e mídia real; Compose/diff check | Validação técnica observada; não significa sprint editorialmente aprovada |
| Preservar job aprovado e recusar demais existentes | 18 REJECTED, 2 APPROVED, 2 ensaios NEEDS_REVIEW; sete hashes da referência novamente idênticos | Instrução executada; arquivos e histórico preservados |

## Decisão humana recebida

O usuário avaliou `77b79d5e` e `90dda26b` como idênticos: boa imagem, legendas/efeitos e fechamento, mas fim seco e título repetido. A variante `700982a4` aplica o título fornecido e um encerramento suave. O usuário aprovou explicitamente ambos os ajustes: “Ficou bom; manter os dois ajustes”. A decisão foi registrada no backend após QC, sem inventar notas. O lote original foi rejeitado, não validado.

Entrega implementada e verificada; a avaliação real orientou as correções e aprovou a variante. Não há bloqueio na aprovação desse ajuste. Uma futura ampliação para pares adicionais em português e inglês continua uma opção, sem alegação de validação editorial geral do corpus. Não há processamento pendente nem motivo para recriar o lote inteiro agora.

## Continuação solicitada: cinco fontes, Tailscale e planejamento

- Cinco fontes distintas, 3 PT/2 EN, agora têm 15 candidatos em NEEDS_REVIEW com classificação e direção Qwen2.5 1.5B na K4200 e render Remotion. QC: 9 VALID/6 WARNING contextuais, zero FAILED; 30 arquivos decodificados. Um teste com fallback foi preservado como diagnóstico; uma variante com shortlist menor completou o caminho GPU. [Resultados e IDs para avaliação](TESTES_GPU_5_VIDEOS_2026-11-06.md).
- As 15 prévias terminaram no Edge pelo endereço Tailscale, durações conferidas contra cada job. A automação foi ajustada para esperar todos os players atualizarem ao trocar de job. [Evidência de reprodução](sprint/browser-gpu-five.json).
- Tailscale Serve TCP 8501 encaminha para localhost, sem Funnel e com Docker ainda restrito a loopback. IP/nome privados responderam HTTP 200 e a UI funcionou com viewport de 390 px, sem rolagem horizontal. O aparelho físico ainda depende de confirmação do usuário. [Configuração e limites](sprint/tailnet-access.json).
- [Plano das próximas sprints](../docs/PROXIMAS_SPRINTS.md) entregue com prioridades, dependências, critérios de aceite e pontos abertos, baseado no estado atual.
- 140 testes passaram; Compose e diff check passaram. GPU/worker normais restaurados, saúde CUDA10.2 ok, filas vazias. Nenhum novo candidato foi aprovado automaticamente. A entrega de engenharia está concluída; revisão humana dos novos cortes e generalização editorial permanecem explícitas, conforme o pedido original.
