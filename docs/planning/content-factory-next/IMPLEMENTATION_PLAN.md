# Content Factory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (execução nativa) or superpowers:subagent-driven-development (quando escolhido explicitamente) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** entregar revisão clara, seleção editorial relevante e histórias completas, preservando a qualidade visual aprovada; preparar aprendizado humano verificável em uma branch independente.

**Architecture:** evoluir o serviço editorial e JSON existentes, com eventos versionados ligados ao render. Corrigir o pipeline local antes de adicionar montagem e integrações. Dataset, recuperação e modelos opcionais são derivados offline, com promoção explícita.

**Tech Stack:** Python, Streamlit, Redis, JSON, Whisper CPU, Qwen/Ollama ou ponte Kepler, FFmpeg, Remotion. Sem banco/serviço novo; bibliotecas ML somente na trilha de aprendizado, se justificadas.

**Spec:** [DECISIONS](DECISIONS.md), [DATA_CONTRACTS](DATA_CONTRACTS.md), [ARCHITECTURE](ARCHITECTURE.md), [EDITORIAL_LEARNING](EDITORIAL_LEARNING.md), [EVALUATION](EVALUATION.md). Ler também [CURRENT_STATE](CURRENT_STATE.md) e [HANDOFF](HANDOFF.md).

## Global Constraints

- Nesta rodada: documentação apenas. Este plano dirige a execução posterior.
- Começar por G0: commit do trabalho acumulado, push upstream e PR; G1: branch local sincronizada com main. Não há autorização para merge automático em main.
- Produto em `codex/editorial-product`; pesquisa em fontes primárias, recuperação de exemplos, ranker leve e eventual fine-tuning em `codex/editorial-learning`.
- Executar todos os marcos de produto, um por vez; M9/M10 dependem de dados/avaliação/infraestrutura e não obrigam treino.
- Preservar `data/`, `.env`, modelos, volumes e avaliações. Não reinterpretar automaticamente APPROVED legado como aprovação perfeita.
- Preservar MP4 mestre e WebM, resolução aprovada, legendas por palavra, cores e efeitos; preservar timeline v2 e snapshots de jobs existentes.
- Worker único; Qwen na K4200 tem contexto/memória limitados, Whisper continua CPU. Fallback deve registrar motivo, modelo solicitado/resolvido e backend real.
- Ratings 1–5 ou null; relevância graduada 0–3 opcional e humana. Sugestões automáticas nunca se tornam rótulos humanos silenciosamente.
- Sem publicação social, treino em startup, download de modelo ou envio externo por conveniência. Integrações reais exigem capacidade/destino/credenciais autorizados.

## Review Focus

1. Aprovação legada com comentário de ressalva e `rework=false`: preservar a decisão, qualificação UNKNOWN; não contar como positivo limpo (M0).
2. Dois clientes ou callback de render antigo: resposta 409 mesmo sem mudar o tamanho do histórico; reenvio idêntico é idempotente (M1/M12).
3. Reprocessamento/aliases/recusas administrativas: uma família nunca atravessa treino e teste, nem gera exemplos falsamente independentes (M7).
4. Transcrição PT/EN com demonstração prometida depois do caractere 700 ou do limite de contexto: conservar informação de fechamento; reduzir exemplos/chunking, sem truncamento silencioso (M3/M4).
5. Montagem com palavra sobre a fronteira, duração inválida ou ROI de site fora da área: recusar plano, não cortar palavra nem informação importante automaticamente (M5/M6).

## Sequência e limites de branch

| Fase | Marcos / branch | Dependências | Entrega verificável |
|---|---|---|---|
| Git | G0, G1 | Estado real do Git | Baseline publicada em PR; branch produto contém main e baseline |
| 0 | M0 / produto | G1 | Contratos puros e fixtures sintéticas |
| 1 | M1 → M2 / produto | M0 | Eventos atômicos e revisão por candidato |
| 2 | M3 → M4 / produto | M1 | Contexto completo, brief fixo, relevância e conclusão |
| 3 | M5 / produto | M3/M4 | Enquadramento por conteúdo |
| 4 | M6 / produto | M5 | Narrativas multitrecho com sincronismo |
| 5 | M7 → M8 → M9? → M10? / aprendizado | M1/M3; incorpora M6 quando avaliar montagem | Dados, prompting com exemplos, ML somente elegível |
| 6 | M11 → M12 / produto | M1/M3; M5 para inspeção visual | Experimento Hermes e revisão Telegram |
| Operação | M13 / produto | M6; instrumentação pode começar antes | Reprodutibilidade e eficiência medidas |

Revisar cada marco antes do próximo, com commit próprio. A trilha de produto não espera por ML. Não abrir branches concorrentes no mesmo diretório com trabalho não commitado; usar checkout limpo ou worktree isolado. Seguir a skill de isolamento ao iniciar implementação.

## G0 — Consolidar o estado acumulado antes de desenvolver

**Files:** todo o trabalho legítimo do projeto já presente, incluindo este pacote; excluir dados locais e segredos. **Interfaces:** Git working tree → commit de baseline → branch remota com upstream → PR para main.

- [ ] Registrar `git status --short`, branch, HEAD, upstream, remotos e PR já existente. Conferir `AGENTS.md`, `.gitignore`, diff e arquivos novos. Não assumir que HEAD reproduz o código atual.
- [ ] Inspecionar segredos/artefatos antes de stage; incluir o código, testes, documentação e AGENTS do projeto. Nunca `git add -f`, nem adicionar mídia/modelos/data/.env. Fazer stage por caminhos auditados, revisar `git diff --cached --stat`, `--check` e conteúdo.
- [ ] Executar a suíte segura do HANDOFF e verificações aplicáveis ao conteúdo acumulado. Se houver falha preexistente, diagnosticar e registrar; não declarar baseline verde sem observar.
- [ ] Criar commit `chore: consolidate content factory editorial baseline`, usando a branch atual se ela continuar adequada. Preservar commits anteriores; nada de reset ou squash destrutivo.
- [ ] `git push --set-upstream origin <branch-observada>`; confirmar upstream aponta para esse commit. Criar ou atualizar o PR dessa branch para main com problema/resultado, validação e limitações. Via ferramenta GitHub disponível; `gh pr create --base main --head <branch> --title ... --body-file <arquivo>` é fallback. Conferir URL e base/head do PR. Não abrir duplicata.

**Aceite:** commit/PR/HEAD/upstream registrados; working tree limpo para iniciar nova trilha. **Falha externa:** autenticação/remoto indisponível deve ser reportada; não fingir push/PR nem prosseguir como se G0 estivesse concluído. **Rollback:** não desfazer o trabalho; corrigir por novo commit. Não fechar PR ou reescrever histórico sem razão autorizada.

## G1 — Sincronizar main e separar trilhas

- [ ] Com tree limpo, `git fetch origin`; verificar `origin/main`. Atualizar `main` por `git switch main` e `git merge --ff-only origin/main`. Se main local divergir, preservar e usar nova branch diretamente de `origin/main`, sem reset.
- [ ] Criar `git switch -c codex/editorial-product origin/main` (se existir, inspecionar antes; não sobrescrever). Se o PR G0 ainda não foi integrado, fazer merge da branch baseline nessa branch de produto. Resolver conflitos preservando os contratos atuais e testar. Não fazer merge do PR em main por conta própria.
- [ ] Confirmar `git merge-base --is-ancestor origin/main HEAD` e que o commit G0 também é ancestral. Resultado esperado 0 para ambos. No PR de produto, documentar dependência do PR baseline enquanto estiver pendente; atualizar com merge de origin/main, sem force push.
- [ ] Antes de M7, criar `codex/editorial-learning` sobre o commit de produto que fornece M1/M3. Usar outro worktree se produto continuar em execução. PR aprendizado contra produto enquanto dependente; depois retarget para main quando a base necessária for integrada. Auditar diff exclusivo de aprendizado. Não mesclar aprendizado na branch de produto automaticamente.

**Aceite:** branches e base/HEAD documentados; produto contém main atualizado e baseline. “Sincronizado” não significa fingir que o PR baseline foi integrado. Nenhuma integração ML precisa existir para concluir produto.

## Convenção RED / GREEN e commits

Os comandos `python -m pytest ...` abaixo podem ser executados no container efêmero do HANDOFF, substituindo apenas os argumentos após pytest. RED exige falha pela nova regra ausente, não falta de dependência ou indisponibilidade de Redis. Fixtures sintéticas ficam em `tests/fixtures/editorial/`; nenhum teste grava decisões reais. Cada GREEN executa arquivo focado, testes existentes afetados e `git diff --check`. Antes de push/PR, executar a suíte completa adequada.

Depois de cada marco: `git add <somente os arquivos do marco listados em Files>` e `git commit -m '<mensagem indicada>'`. Revisar o staging; não repetir stage global de G0. Atualizar documentação operacional/contratos quando mudar comportamento. Interromper apenas a parte realmente bloqueada e continuar marcos independentes autorizados.

## M0 — Contratos puros e baseline de regressão

**Files:** criar `app/editorial_contracts.py`, `contracts/editorial-feedback-v2.schema.json`, `tests/test_editorial_contracts.py`, `tests/fixtures/editorial/legacy_reviews.json`; ler `app/editorial.py`, sem ligar v2 ao runtime ainda.

**Interfaces:** consome forma legada `current_decisions(job: dict) -> dict`; produz `candidate_key(job_id: str, original_index: int) -> str`, `project_legacy_review(job: dict, index: int) -> dict`, `validate_feedback_event(event: dict) -> dict`. Formas exatas em DATA_CONTRACTS.

- [ ] RED: criar `test_legacy_qualified_approval_is_unknown`: fixture sintética APPROVED, comentário de encerramento ruim, `rework=false`; assert decisão original preservada, `normalized_decision is None`, `qualification_status == 'UNCONFIRMED_LEGACY'`, bytes do input inalterados. Criar `test_mixed_job_keeps_candidate_rejection`: job aprovado, candidato recusado continua REJECTED.
- [ ] Rodar `python -m pytest tests/test_editorial_contracts.py -q`; esperado falhar porque projeção/contrato não existem.
- [ ] Implementar as três funções puras. UUIDv5 estável pelo índice original, não posição filtrada. Validar enums, inteiros (rejeitar bool como rating), null, comentário até 4.000 caracteres, severidades e campos obrigatórios. `APPROVED_WITH_ADJUSTMENTS` sem ajuste é inválido; nenhuma nota nasce preenchida.
- [ ] GREEN: mesmo comando; incluir `test_feedback_bounds_and_id_stability`, limites 0/1/5/6, grau 0/3/4, ID inválido e evento automático não humano. Rodar também `tests/test_editorial.py`.
- [ ] Commit `feat: define versioned editorial feedback contracts`.

**Aceite:** nenhum job alterado; legado nunca ganha rótulo limpo automaticamente; schema e validador concordam. **Rollback:** remover import/flag futuro; contratos puros não mudam produção.

## M1 — Persistência atômica, identidade e API v2

**Files:** modificar `app/service.py`, `app/store.py`, `app/editorial.py`, `app/api.py`, `app/candidates.py`, `app/job_settings.py`; criar `contracts/api-v2.openapi.json`, `tests/test_editorial_service_v2.py`, `tests/test_api_v2.py`; ampliar `tests/test_review_actions.py`, `tests/test_store.py`; documentar `docs/API.md`, `docs/PROTOCOLO_EDITORIAL.md`.

**Interfaces:** consome contratos M0 e `job_lock(jid: str)`, `load(jid: str) -> dict`, `save(job: dict) -> None`; produz `review_candidate_v2(jid: str, candidate_id: str, request: dict) -> dict`, `get_editorial_view(job: dict) -> dict`. GET/POST v2 em DATA_CONTRACTS; v1 legado preservado.

- [ ] RED: `test_stale_artifact_rejected_without_new_human_event`: trocar render/hash mantendo tamanho do histórico; request anterior deve gerar Conflict/HTTP409 e nenhum evento. `test_duplicate_request_is_idempotent`: mesmo request ID e payload retorna mesmo evento, sem duplicação; mesmo ID com payload diferente dá409.
- [ ] Rodar `python -m pytest tests/test_editorial_service_v2.py tests/test_api_v2.py -q`; esperado falhar por endpoint/função ausentes.
- [ ] Implementar identidade de candidato, versão de proposta, revisão de render e manifest MP4/WebM/timeline antes da revisão. Usar caminhos versionados sem sobrescrever aprovados. Sob um único lock, comparar revisão/artefato, anexar evento e atualizar projeção numa única escrita JSON atômica. Autor/proveniência vêm do servidor, não de campos livres do cliente. Falha de save não registra decisão parcial.
- [ ] Implementar opt-in `editorial_protocol=2` no snapshot de jobs novos. V1 retorna409 `editorial_protocol_required` ao tentar aprovar v2; não quebrar jobs v1. Recusa técnica permitida mesmo com mídia inválida; aprovação exige QC apropriado. Especificar resposta de conflito e recarregamento.
- [ ] GREEN: adicionar `test_concurrent_reviews_one_wins`, `test_legacy_v1_still_works`, `test_write_failure_preserves_previous_record`, `test_new_render_preserves_history_and_revokes_current_decision`; executar arquivos novos, API/review/store atuais e teste de recuperação. Fazer dry-run de migração em cópia temporária, hash antes/depois igual.
- [ ] Commit `feat: persist artifact-bound editorial reviews`.

**Aceite:** duplicação zero, conflito observado, histórico preservado, v1 operacional e nenhum dado legado convertido. **Rollback:** desligar criação v2 e manter leitor/eventos; não mapear aprovação com ajustes para aprovação limpa ao reverter.

## M2 — Revisão compacta e coleta humana clara

**Files:** modificar `app/ui.py`, `app/editorial.py`; criar `app/editorial_ui.py`, `tests/test_editorial_ui.py`; ampliar `tests/test_ui_smoke.py`, `tests/test_review_actions.py`.

**Interfaces:** consome `get_editorial_view` e `review_candidate_v2`; produz `filter_candidates(rows: list[dict], filters: dict) -> list[dict]` em `editorial_ui.py`, e `summarize_v2(jobs: list[dict]) -> dict` em `editorial.py`. Métricas usam denominadores de EVALUATION, separadas do resumo legado.

- [ ] RED: `test_filter_finds_rejected_inside_approved_job`: exibir recusa candidata apesar do job aprovado; `test_conditional_is_not_clean_approval`: contagens exclusivas e legado desconhecido separado; `test_unreviewed_slot_keeps_metric_coverage_explicit`.
- [ ] Rodar `python -m pytest tests/test_editorial_ui.py -q`; esperado funções/estados ausentes.
- [ ] Implementar filtros por candidato e estado, badges técnico/editorial/pendências separados. Preview compacto com limite de largura, painel de informação/revisão lado a lado no desktop, empilhamento no celular; detalhes e dez ratings opcionais em expansor. Motivos multi-select, comentário e botão explícito “Aprovar com ajustes”. Mostrar candidato/versão, estado salvo e histórico; conflito pede recarregar sem perder rascunho. Comentário obrigatório nos casos previstos, sem exigir dez notas para cada clique.
- [ ] GREEN: testes novos + AppTest/ações existentes. Com `agent-browser` CLI, testar fixture isolada a 390px e desktop: aprovar, aprovar com ajustes, recusar com comentário, filtrar e recarregar. Confirmar persistência e vídeo reproduzível; screenshots não incluem dados sensíveis. Não clicar em candidatos reais como teste. Ver procedimento HANDOFF se CLI ausente.
- [ ] Commit `feat: clarify candidate review and structured feedback`.

**Aceite:** recusa visível dentro de job aprovado; três ações inequívocas; sem rolagem horizontal a 390px; player cabe em painel de revisão e não ocupa a largura toda. **Rollback:** UI antiga para jobs legados; preservar leitura v2 e eventos.

## M3 — Contexto completo, títulos e brief versionado

**Files:** criar `app/editorial_context.py`, `app/editorial_policy.py`, `tests/test_editorial_context.py`, `tests/test_editorial_policy.py`; modificar `app/core.py`, `app/ranker.py`, `app/director.py`, `app/timeline.py`, `app/submit.py`, `app/service.py`, `app/job_settings.py`; ampliar testes de ranker/timeline/model snapshot.

**Interfaces:** `build_candidate_context(job: dict, index: int, transcript: dict, *, before_seconds: float = 12, after_seconds: float = 15) -> dict`; `resolve_policy(policy_id: str | None) -> dict`; `approve_policy(policy_candidate_id: str, expected_revision: int, actor: str) -> dict`. `policy_candidate_id` identifica uma proposta de política, separada de um candidato de vídeo. Produzir contexto com trecho integral, antes/depois, offsets/hashes e decisão explícita de orçamento; brief DRAFT/APPROVED/RETIRED e snapshot por job. Adicionar `validate_title(title: str, evidence: dict) -> dict` em `editorial_context.py` (válido/reason/normalized).

- [ ] RED: `test_late_payoff_survives_context_budget_pt_en`: fonte PT/EN longa contém promessa depois de700 caracteres; contexto contém fechamento e referência ao original, sem perder palavras por prefix slice. `test_title_zero_and_transcript_echo_rejected`: `"0"`, branco, eco da fala e alegação sem evidência falham; título humano aprovado com evidência passa.
- [ ] Rodar `python -m pytest tests/test_editorial_context.py tests/test_editorial_policy.py -q`; esperado módulo ausente.
- [ ] Remover limites cegos `[:700]`, `[:900]` e `[:2200]` nos caminhos relevantes, sem simplesmente despejar transcrição ilimitada em4096 tokens. Armazenar texto completo; montar janelas temporalmente localizadas, chunking e reserva de geração conforme tokenizer real. Se não couber, reduzir contexto opcional/chunking, registrar cobertura e falhar explicitamente quando não houver fechamento avaliável. Modelo não inventa timestamps sem conferir fonte.
- [ ] Implementar brief versionado estático inicial e proposta com diff/feedback; aprovação humana ativa ponteiro atômico com revisão. Job resolve uma vez e salva brief/prompts/modelo solicitado/resolvido/digests/backend/ranker/regras/renderer e Git+dirty patch hash. Legados UNKNOWN. Mudança de ambiente não altera snapshot antigo. Nenhuma recuperação dinâmica/ML neste marco de produto.
- [ ] GREEN: testar orçamento realista, falha explícita, versão antiga imutável, rollback de brief, conflito de revisão e título baseado em prova. Rodar testes de ranker/timeline/job settings/model snapshot e API.
- [ ] Commit `feat: preserve editorial context and version policy snapshots`.

**Aceite:** referência700982a4 preservada; título não repete legenda; fechamento consultável além do prefixo; nenhum fallback oculto ou novo modelo baixado. **Rollback:** feature flag para novos jobs e ponteiro para brief aprovado anterior; não reprocessar existentes.

## M4 — Relevância e fechamento semântico

**Files:** criar `app/editorial_story.py`, `tests/test_editorial_story.py`, fixtures PT/EN sintéticas; modificar `app/ranker.py`, `app/director.py`, `app/signals.py`, `app/timeline.py`, `app/job_settings.py` e seus testes.

**Interfaces:** consome contexto/brief M3; produz `assess_story(context: dict, policy: dict, model_result: dict | None) -> dict` e `validate_story_boundary(plan: dict, context: dict) -> dict` em `editorial_story.py`. Resultado: promessa, evidências/offsets, payoff, último pensamento, ponto de término proposto, incerteza e motivo de fallback. Não preencher ratings humanos.

- [ ] RED: `test_live_promotion_is_not_game_discovery`: fala sobre live do criador não ganha relevância de descoberta; `test_pause_before_demonstration_is_not_closure`: pausa seguida de “vou mostrar”/“ele é” permanece incompleta; `test_extend_to_payoff_without_cutting_word` inclui demonstração/última palavra quando fonte permite.
- [ ] Rodar `python -m pytest tests/test_editorial_story.py -q`; esperado função/regra ausente.
- [ ] Implementar plano hook/setup/proof/payoff com evidência temporal. Distinguir assunto GTA de valor informativo; o brief penaliza autopromoção dominante, sem proibir citar o criador quando necessário ao contexto. Limite de duração não justifica truncar payoff: buscar outro intervalo ou emitir insuficiência antes de M6. Fade é acabamento após a conclusão, não sua prova. Manter0,35s cauda/0,25s fade aprovados até evidência de mudança.
- [ ] GREEN: arquivos novos + ranker/signals/timeline atuais; teste de resposta inválida/incompleta do Qwen com fallback explícito e marca de qualidade incerta. Experimento controlado com fontes já autorizadas, configurações iguais e apenas este eixo alterado; a revisão humana decide ganho, GPU sem erro não prova qualidade.
- [ ] Commit `feat: rank complete relevant stories and validate endings`.

**Aceite:** fixtures de b824 / f6 / 589 reproduzidas anonimamente; não aceitar promessa sem payoff silenciosamente. Resultado real permanece NEEDS_REVIEW. **Rollback:** regras anteriores identificadas, manter rastreabilidade das duas propostas.

## M5 — Enquadramento por conteúdo e área segura

**Files:** criar `app/framing.py`, `tests/test_framing.py`; modificar `app/director.py`, `app/timeline.py`, `app/edit_render.py`, `contracts/timeline.schema.json`, `renderer/src/vertical-clip.tsx`; ampliar `tests/test_timeline.py`, `tests/test_edit_render.py`.

**Interfaces:** `validate_framing(scene: dict, source_size: tuple[int, int], output_size: tuple[int, int]) -> dict` em `framing.py`; timeline fornece preset `face|gameplay|web|tweet|document`, ROI normalizada e caption safe area. V2 sem preset conserva aparência atual.

- [ ] RED: `test_web_roi_survives_vertical_output`: página larga com informação nas bordas exige fit/composição, não crop central; `test_invalid_roi_is_rejected`: coordenadas fora0..1 ou área nula falham; `test_captions_avoid_important_region` preserva ROI/legibilidade.
- [ ] Rodar `python -m pytest tests/test_framing.py -q`; esperado módulo ausente.
- [ ] Implementar presets determinísticos e ajuste manual de ROI primeiro. Fit sobre fundo/composição quando crop perde prova; rosto e gameplay preservam foco validado. Remotion deve respeitar preset em vez de `objectFit: cover` global. Legenda continua karaoke, cores/fontes/efeitos aprovados; área segura varia sem cobrir documento. Não adicionar OCR/visão sem limitação concreta e autorização de dependência.
- [ ] GREEN: novos testes e render de fixture com página/tweet e rosto; inspecionar frames no começo/meio/fim e MP4/WebM reais. Reproduzir caso4cbC3/8bC3 somente como nova variante, sem substituir aprovados.
- [ ] Commit `feat: preserve visual evidence with content-aware framing`.

**Aceite:** evidência visual legível, fora de corte e não coberta; resolução original aprovada mantida. **Rollback:** preset antigo por flag nos novos jobs; timelines v2 idênticas.

## M6 — Montagem multitrecho e sincronismo

**Files:** criar `app/assembly.py`, `contracts/timeline-v3.schema.json`, `tests/test_assembly.py`, `tests/test_multisegment_render.py`; modificar `app/core.py`, `app/timeline.py`, `app/edit_render.py`, `app/candidates.py`, `app/job_settings.py`, `renderer/src/vertical-clip.tsx`; atualizar documentação de configuração/testes.

**Interfaces:** `validate_assembly(plan: dict, source_duration: float) -> dict`; `map_words(plan: dict, words: list[dict]) -> list[dict]`. Consome framing M5, contexto M3 e história M4. V3 uma fonte, trechos temporais/ordem/purpose, output_start derivado validado, somatório e acabamento explícitos.

- [ ] RED: `test_maps_second_segment_words_to_output`: segmento fonte[30,40] em output10 mapeia palavra[31,32] para[11,12]. `test_rejects_partial_word_and_out_of_source`: limite31,5 para palavra[31,32] falha; `test_v2_single_segment_is_unchanged`. Incluir trecho vazio, duração negativa, sobreposição indesejada, ordem invertida sem aprovação e concat não contínuo.
- [ ] Rodar `python -m pytest tests/test_assembly.py -q`; esperado módulos ausentes.
- [ ] Implementar validação e remapeamento puro antes de render. Permitir histórias de 60–120 s quando houver conteúdo, sem padding para cumprir duração. Remover teto60 do caminho v3 apenas, preservar limites v2. Fonte e palavras mantêm IDs para auditoria. Timestamp usa segundos e quantização por frame, nunca acumulando drift por arredondamento independente.
- [ ] GREEN: suíte pura e fixtures de mapeamento. Commit `feat: validate multisegment narrative timelines` antes de ligar o render.
- [ ] RED integração: fixture audiovisual sintética com marcadores/palavras conhecidos em 2 trechos; assert duração montada e offset de cada marcador com tolerância de um frame. Mesmo plano inválido deve falhar antes de chamar FFmpeg. Rodar `tests/test_multisegment_render.py`, esperado fluxo v3 ausente.
- [ ] Renderizar base concatenada FFmpeg por segmentos validados; Remotion usa relógio final para palavras, zoom/overlays/ROI e cauda. Não concatenar binários, não usar shell gerado por modelo. Gerar MP4 mestre e WebM por render_revision com QC existentes.
- [ ] GREEN integração: decode integral, áudio presente e sincronizado em ambas as junções/início/fim, sem frame preto indevido ou palavra interrompida. Inspeção humana de variante real autorizada1–2min. Sem orçamento/infra de render, marcar integração pendente, não reivindicar sucesso só com unitários.
- [ ] Commit `feat: render synchronized multisegment stories`.

**Aceite:** sync dentro de um frame no fixture, história com conclusão e informação visual preservada na revisão real; nenhum aprovado sobrescrito. **Rollback:** flag `timeline_v3` off para novos jobs; renderizador v2 permanece disponível e artefatos imutáveis.

## M7 — Branch aprendizado: dataset confiável e avaliação reproduzível

**Files novos na branch aprendizado:** `app/editorial_dataset.py`, `app/editorial_features.py`, `research/build_editorial_dataset.py`, `research/evaluate_editorial.py`, `tests/test_editorial_dataset.py`, `tests/test_editorial_features.py`, `tests/test_editorial_evaluation.py`, fixtures sintéticas.

**Interfaces:** `build_dataset(jobs: list[dict], config: dict, output_dir: Path) -> dict`; `extract_features(context: dict, plan: dict, signals: dict, versions: dict) -> dict`; `evaluate_pool(records: list[dict], config: dict) -> dict` em `editorial_dataset.py`. CLIs chamam biblioteca; não importam worker para treinar.

- [ ] Confirmar G1: branch separada e dependências de produto presentes. Manter registro de fontes primárias com data, versão e conclusão; nenhuma referência vira prova de ganho neste corpus.
- [ ] RED: `test_aliases_and_retries_never_cross_split`: todos descendentes/aliases/hash de uma fonte têm mesmo split; `test_admin_and_unconfirmed_legacy_have_no_absolute_target`:18 recusas administrativas/11 aprovações legadas não viram classes; `test_duplicate_request_counts_once` e `test_snapshot_change_aborts_export`.
- [ ] Rodar `python -m pytest tests/test_editorial_dataset.py tests/test_editorial_features.py tests/test_editorial_evaluation.py -q`; esperado módulos ausentes.
- [ ] Implementar manifest imutável com cutoff/hash, staging+rename, elegibilidade por alvo, dedup transitiva de origem e root group antes de split. Exportar somente feedback autorizado/confirmado, sem mídia, tokens, caminhos pessoais ou dados externos desnecessários. Comentários completos permanecem locais; se futuro compartilhamento, produzir cópia redigida com proveniência, não reescrever fonte humana. Features <=12 iniciais, pré-decisão, com missingness e versão; nenhuma coluna de decisão atual/futura como entrada.
- [ ] Implementar métricas de EVALUATION com coverage/unknown, Prec@3/NDCG sem inventar graus, ganho linear0..3, ties e IDCG0 explicitados. Separar qualidade editorial de QC/operacional e de mudanças de renderer.
- [ ] GREEN: testar pool incompleto, sem notas, todas as notas 0, empate, render corrigido parent-linked, caminhos de saída inseguros e exportação determinística; mesmo input/config produz mesmo conteúdo/hash. Dataset bruto atual permanece baseline descritiva, não treino. Saída default dry-run; escrita somente local e fora de Git.
- [ ] Commit `feat: export versioned editorial evaluation datasets`.

**Aceite:** zero fonte cruzada entre splits, zero rótulo humano inventado, contagens reconciliadas15/11/4 e 18 administrativas. **Rollback:** apagar somente exportação derivada explicitamente selecionada, nunca job/evento; nenhuma ativação em produto.

## M8 — Branch aprendizado: exemplos recuperados para Qwen

**Files:** criar `app/editorial_retrieval.py`, `tests/test_editorial_retrieval.py`; alterar somente nesta branch `app/ranker.py`, `app/director.py`, `app/job_settings.py` e testes de snapshot. Encoder opcional tem requirements separado, sem dependência no produto padrão.

**Interfaces:** `select_examples(query: dict, dataset: dict, policy: dict, budget: dict) -> list[dict]`, consumindo M7 e contexto M3. Retorna IDs/hashes, categoria, relevância e custo; snapshot inclui retrieval/dataset/query/version.

- [ ] RED: `test_retrieval_excludes_same_source_and_holdout`: jamais recuperar família atual, teste ou exemplo não confirmado; `test_three_examples_diverse_within_budget`: <=3, <=1 por família, <=600 tokens e reserva de geração mantida. `test_no_eligible_examples_uses_brief_only` retorna[] e motivo.
- [ ] Rodar `python -m pytest tests/test_editorial_retrieval.py -q`; esperado módulo ausente.
- [ ] Implementar lexical local primeiro, categoria positivo/negativo/condicional quando disponível, sem forçar exemplos ruins para preencher3. Comentário/exemplo são dados delimitados, não instruções executáveis. Preservar contexto de prova/fechamento antes de exemplos; usar tokenizer/capacidade reais. Consulta reproduzível e congelada por job.
- [ ] GREEN: ablação brief/contexto fixos com/sem exemplos, leave-one-source-out descritivo das cinco fontes. Sem v2 confirmado elegível, retornar sem exemplos e relatório de falta de dados. Encoder multilíngue CPU/cache/cosseno exato só como variante após benefício medido e autorização para download/dependência; sem serviço vetorial.
- [ ] Commit `feat: retrieve confirmed editorial examples behind opt-in`.

**Aceite:** nenhum vazamento ou truncamento silencioso, comparação humana cega e custos registrados. Poucas fontes permitem piloto humano, não alegar significância. **Rollback:** retrieval off/brief aprovado anterior para novos jobs, snapshots preservados.

## M9 — Branch aprendizado: ranker leve condicional

**Files:** criar `app/editorial_models.py`, `research/train_editorial_ranker.py`, `requirements-editorial-ml.txt`, `tests/test_editorial_models.py`; ampliar `research/evaluate_editorial.py`. Só instalar dependências em ambiente isolado depois de justificar sua necessidade.

**Interfaces:** `score_candidates(features: list[dict], artifact: dict) -> list[dict]`; `check_training_eligibility(manifest: dict, config: dict) -> dict`; `train_ranker(dataset: dict, config: dict, output_dir: Path) -> dict` (últimas em `editorial_models.py`). Config fixa alvos/versões/split/seed/hiperparâmetros antes de abrir holdout.

- [ ] RED: `test_training_refuses_insufficient_independent_groups`: corpus atual não elegível; `test_pairwise_better_but_bad_is_not_positive`: par relativo não vira absoluto; `test_test_labels_never_fit_preprocessing`: imputer/scaler somente treino.
- [ ] Rodar `python -m pytest tests/test_editorial_models.py -q`; esperado módulo ausente.
- [ ] Implementar gate (valores propostos em EDITORIAL_LEARNING), ranker desligado por padrão e schema de artefato. Se dados insuficientes, entregar CLI que recusa treino com diagnóstico e testes sintéticos; não rodar treino real para “concluir” o marco. Regressão logística regularizada CPU primeiro; preferência linear por diferenças separada, com peso por fonte. Boosting/LambdaMART somente com evidência de limitação e dados correspondentes.
- [ ] GREEN: integração com dataset sintético claramente rotulado como teste; inferência sem biblioteca/modelo disponível faz fallback explícito, nunca troca silenciosa. Treino real somente após elegibilidade confirmada e escopo autorizado. Ablação baseline vsB, holdout intocado, bootstrap por fonte e aprovação humana conforme EVALUATION. Salvar artefato, parâmetros, features, dependências, hashes e relatório; nenhum `pickle` remoto não confiável.
- [ ] Commit `feat: gate lightweight editorial ranking experiments`.

**Aceite:** pode terminar como “infra pronta, treino bloqueado por dados”, com causa objetiva; ganho nunca inventado. **Rollback:** ranker off/artefato aprovado anterior, sem retreinar automaticamente.

## M10 — Branch aprendizado: estudo opcional de fine-tuning

**Files:** criar `research/editorial_finetuning_feasibility.md` e, somente se estudo justificar experimento posterior, plano independente com testes. Não adicionar trainer ao worker.

- [ ] Comparar SFT/LoRA/DPO em fontes primárias, dados finais corrigidos vs pares do mesmo contexto, base de treino/licença vs GGUF de inferência, hardware moderno necessário, custo/privacidade/manutenção e baselineA/B.
- [ ] Conferir gates propostos de dados no EDITORIAL_LEARNING e lacunas da K4200; medir consumo só em experimento autorizado, não pressupor PyTorch moderno em compute3.0.
- [ ] Entregar decisão go/no-go com orçamento e aceite mensurável, sem alegar treino ou ganhos. Treino/fine-tuning não é obrigatório e exige outro escopo concreto se elegível.
- [ ] Commit `docs: assess optional editorial fine-tuning feasibility`.

**Aceite:** decisão rastreável e custo explícito. **Rollback:** nenhum runtime alterado.

## M11 — Produto: experimento local versus Hermes

**Files:** criar `research/compare_hermes_direction.py`, `app/editorial_critic.py`, `tests/test_editorial_critic.py`; reutilizar `contracts/clip_proposal.schema.json` se compatível ou adicionar versão nova, sem alterar o significado legado.

**Interfaces:** `validate_critique(payload: dict, context: dict) -> dict` em `editorial_critic.py`; entrada contexto/brief/mesmo plano local, saída crítica com evidência, sugestões temporais/visuais e incerteza. Não cria avaliação humana nem caminho de arquivo livre.

- [ ] Descobrir capacidades MCP sem envio: ponte de mensagens não prova execução de tarefa/visão. Registrar endpoint, retorno, modelo/provedor, timeout, custo e que conteúdo sai da máquina. Não enviar vídeos/transcrições a conversa aleatória para testar.
- [ ] RED: `test_invalid_critic_cannot_override_timeline_or_review`: timestamp fora da fonte, caminho arbitrário, falsa aprovação e recomendação sem evidência são recusados. `test_missing_hermes_capability_keeps_local_direction` preserva baseline.
- [ ] Rodar `python -m pytest tests/test_editorial_critic.py -q`; esperado módulo ausente. Implementar validador/adapter com mock e dry-run sem envio; GREEN.
- [ ] Se capacidade/destino estiverem confirmados e autorizados, comparar1 vídeo da fonte 4cb C3 com dois braços: direção local e mesmo plano com crítica Hermes. Fixar fonte, seleção, brief, Qwen, seed quando suportada, renderer/qualidade; variar somente crítica. Mesmos frames autorizados em ambos quando houver visão; sem visão declarar crítica apenas textual. Revisão humana cega sem assumir superioridade por provedor. Nenhuma mensagem real nesta etapa de planejamento.
- [ ] Commit `feat: add controlled optional editorial critique experiment`.

**Aceite:** relatório pode concluir capacidade indisponível; não fingir experimento realizado. Toda variante termina NEEDS_REVIEW. **Rollback:** desabilitar crítico e manter local.

## M12 — Produto: Telegram ligado ao mesmo backend

**Files:** criar `app/telegram_review.py`, `tests/test_telegram_review.py`, `contracts/telegram-review-v1.schema.json`; atualizar `docs/OPERACAO.md`, configuração de exemplo e integração opt-in em `app/service.py`. Não colocar token em job, log ou Git.

**Interfaces:** `build_review_card(job: dict, candidate_id: str) -> dict`; `handle_review_callback(callback: dict, config: dict) -> dict`; `queue_review_delivery(jid: str, candidate_id: str, *, destination_id: str) -> dict`. Estas funções vivem em `telegram_review.py`; callback chama M1, nunca grava decisão por outro caminho.

- [ ] Confirmar destino/usuário/bot autorizados e documentação vigente do Bot API. Usar polling privado inicialmente; não abrir UI/API pública nem depender de Tailscale no telefone para reproduzir mídia enviada. Autenticar callback/ator e conferir allowlist.
- [ ] RED: `test_old_render_callback_is_rejected`: candidato correto/artefato antigo dá409; `test_unauthorized_actor_cannot_review`; `test_redelivery_does_not_duplicate_event`; `test_adjustment_requires_comment`.
- [ ] Rodar `python -m pytest tests/test_telegram_review.py -q`; esperado módulo ausente.
- [ ] Implementar cartão com identidade/versão, prévia correspondente e três ações; coletar comentário/motivos/ajustes pelo mesmo contrato. Callback curto usa token opaco aleatório persistido → IDs/hash/revisão, não URL ou payload gigante. Outbox JSON local tem chave idempotente, estados PENDING/SENT/FAILED e retries limitados; callback processa independentemente do worker de render. Recuperação após envio com resposta perdida pode reenviar cartão: não prometer exactly-once remoto, mas garantir decisão idempotente.
- [ ] GREEN com transporte fake: expiração, retry/timeouts, bot reiniciado, comentário malicioso, troca de render entre cartão e clique, anexo grande. MP4 de revisão menor, se necessário, precisa mapear ao mestre exato; não reduzir mestre. Teste real somente com destino autorizado, registrar aprovação/recusa de fixture, não de candidato real sem intenção editorial.
- [ ] Commit `feat: review exact candidate renders through telegram`.

**Aceite:** UI e Telegram mostram a mesma decisão/histórico; versões antigas não aprovam versões novas. Nenhuma publicação social. **Rollback:** parar polling/entrega, manter backend/UI e eventos; não remover token/config automaticamente.

## M13 — Produto: reprodutibilidade, observabilidade e eficiência

**Files:** modificar `Dockerfile`, `requirements.txt` e lock de dependências Python novo se adotado, `renderer/package.json`, `renderer/package-lock.json`, `app/edit_render.py`, `app/worker.py`, `app/candidates.py`; ampliar `tests/test_pipeline_benchmark.py`, `tests/test_edit_render.py`; atualizar `docs/TESTES.md`, `docs/OPERACAO.md`, `docs/CONFIGURACAO.md`.

**Interfaces:** preservar `render_edited(...) -> str`, `apply_finishing(target: Path, timeline: dict, *, quality: str = 'standard') -> None`; métricas por etapa associadas a job/candidato/render_revision/config hash. Não trocar renderer para obter redução de tempo.

- [ ] RED: teste de instrumentação exige durações e versão/config para ASR/ranker/diretor/base/Remotion/finishing/QC; teste de fallback exige solicitado/resolvido/motivo. Rodar arquivos focados, esperado ausência dos novos campos.
- [ ] Congelar dependências da imagem e copiar lock npm para `npm ci`, validando compatibilidade de Remotion/Chromium antes de atualizar versões. Não baixar builds grandes/reconstruir serviço ativo sem verificar jobs, volumes e disco. Reprodutibilidade de dependências não significa render bit-a-bit igual em hardware diferente.
- [ ] GREEN: build isolado quando necessário, import/config e render fixture; registrar digest de imagem, locks, versão de FFmpeg/Chromium e recursos reais. Eventos não logam transcrição completa, token ou URL secreta.
- [ ] Medir baseline de 3 repetições do mesmo fixture local, sem concorrência GPU. Otimizar o encode adicional da cauda/fade somente se puder manter acabamento aprovado (ex.: composição na mesma etapa Remotion); medir 3 repetições novas mantendo todas outras opções. QC/decode e comparação visual/áudio com tolerância declarada; só promover se não houver regressão e ganho de tempo/recursos observado. Resultado sem ganho é manter caminho antigo.
- [ ] Commit `build: make editorial processing reproducible and measurable`; otimização de render, se validada, em commit separado `perf: avoid redundant finishing encode`.

**Aceite:** configuração/dependências rastreáveis, métricas reconciliadas, nenhum reinício ou alteração silenciosa de job antigo. Verificar Compose sem subir serviços. **Rollback:** imagem/digest anterior e flag de acabamento anterior; preservar volumes e outputs.

## Encerramento de cada trilha

- [ ] Rever diff, testes completos e `git diff --check`; checar código e contratos contra este plano. Documentar limites editoriais e testes reais não realizados.
- [ ] Produto: push upstream/PR próprio, declarar dependência G0 se ainda existir; não misturar commits de aprendizado.
- [ ] Aprendizado: PR separado e relatório de gates/dados/fontes, mesmo que nenhum treino seja elegível. Não ativar política/modelo sem revisão humana.
- [ ] Reportar links dos PRs e hashes observados. Não declarar merge, aprovação humana, entrega Telegram ou superioridade editorial sem resultado observado.

Auto-revisão documental: requisitos mapeados, interfaces alinhadas, cinco Review Focus ligados a testes, marcos com limites/aceite/rollback. Implementação continua responsável por validar o código real ao assumir; este documento não é um resultado de execução.
