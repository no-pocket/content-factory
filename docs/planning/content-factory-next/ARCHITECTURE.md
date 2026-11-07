# Arquitetura incremental

## Atual

`UI/CLI/API → app.service → JSON + Redis → worker → ASR → propostas/shortlist/Qwen → diretor → timeline v2 → FFmpeg/Remotion → QC → revisão humana`.

O estado editorial é binário por candidato, histórico por snapshots de decisões, sem dataset de aprendizado ou personalização automática. O runtime usa um worker e a GPU pode carregar um modelo por sessão. Manter os limites documentados em `docs/GPU_K4200.md`.

## Alvo

```text
UI / API / Telegram
        ↓ serviço editorial, concorrência e identidade de artefato
job JSON: eventos humanos + render revisions + versões resolvidas
        ↓ exportação explícita / somente leitura
dataset imutável + grupos de origem + features e splits
        ↓ avaliação offline / aprovação humana
brief/exemplos (A) → ranker leve opcional (B) → fine-tuning opcional (C)
        ↓ política ativa resolvida na criação do job
Qwen + regra editorial + plano de história + direção visual
        ↓ timeline / fonte→montagem→palavras
FFmpeg + Remotion + QC → novo render → nova decisão humana
```

Não existe seta automática de comentário para promoção em produção. A resposta do Qwen/Hermes pode ser feature ou sugestão, nunca rótulo humano.

## Módulos propostos e interfaces estáveis

Todos os módulos `app/editorial_*.py` abaixo são novos, exceto `app/editorial.py`. Criar apenas no marco que os usa. Tipos são dicionários versionados definidos em DATA_CONTRACTS; validação sem dependência nova inicialmente.

| Módulo | Responsabilidade e interface proposta |
|---|---|
| `app/editorial_contracts.py` | `validate_feedback_event(event: dict) -> dict`; `project_legacy_review(job: dict, index: int) -> dict`; `candidate_key(job_id: str, original_index: int) -> str` |
| `app/service.py` existente | `review_candidate_v2(jid: str, candidate_id: str, request: dict) -> dict`; `get_editorial_view(job: dict) -> dict`; armazenamento/concorrência, não treinamento |
| `app/editorial.py` existente | Projeções/métricas compatíveis; métricas v2 separadas das binárias legadas |
| `app/editorial_context.py` | `build_candidate_context(job: dict, index: int, transcript: dict, *, before_seconds: float = 12, after_seconds: float = 15) -> dict`; texto completo, offsets e hashes |
| `app/editorial_policy.py` | `resolve_policy(policy_id: str | None) -> dict`; `approve_policy(policy_candidate_id: str, expected_revision: int, actor: str) -> dict`; arquivo ativo atômico e snapshot por job |
| `app/editorial_features.py` | `extract_features(context: dict, plan: dict, signals: dict, versions: dict) -> dict`; valores/proveniência/missingness anteriores ao rótulo |
| `app/editorial_dataset.py` | `build_dataset(jobs: list[dict], config: dict, output_dir: Path) -> dict`; exportação explícita, dedup, elegibilidade e manifest |
| `app/editorial_retrieval.py` | `select_examples(query: dict, dataset: dict, policy: dict, budget: dict) -> list[dict]`; filtros de origem, confirmação, diversidade e orçamento |
| `app/editorial_models.py` | `score_candidates(features: list[dict], artifact: dict) -> list[dict]`; inferência B opcional. Treino fica em comando offline, sem imports pesados no worker quando desabilitado |
| `app/assembly.py` | `validate_assembly(plan: dict, source_duration: float) -> dict`; `map_words(plan: dict, words: list[dict]) -> list[dict]`; remapeamento determinístico |
| `app/telegram_review.py` | Adaptador futuro, envio autorizado e callbacks para o serviço; não consome a fila do worker nem decide editorialmente |

`research/build_editorial_dataset.py`, `research/evaluate_editorial.py`, `research/train_editorial_ranker.py` e `research/compare_hermes_direction.py` são CLIs **propostas**. Não existem ainda. Usar a biblioteca comum, sem duplicar regras do backend nos scripts.

## Propriedade por branch

`codex/editorial-product` contém contratos/eventos humanos, serviço/API/UI, contexto completo, briefing estático versionado, relevância/fechamento/enquadramento, montagem, Hermes/Telegram e observabilidade. Não importa módulos de ML ou recuperação dinâmica. Snapshots admitem IDs opcionais de dataset/ranker para compatibilidade futura, sem ativá-los.

`codex/editorial-learning` contém pesquisa primária adicional, `editorial_features`, `editorial_dataset`, `editorial_retrieval`, `editorial_models`, CLIs de dataset/avaliação/treino e dependências opcionais. Nasce sobre as fundações de produto necessárias, com PR inicialmente contra a branch de produto enquanto houver dependência. Sua ativação é uma promoção separada; não fazer merge automático na branch de produto. O script de comparação Hermes pertence à trilha de produto, apesar de estar em `research/`.

## Persistência sem serviço novo

- `data/work/<job>.json`: única transação de revisão, incluindo evento v2 e projeção compatível, protegida pelo lock do job e troca atômica. Não adicionar um segundo arquivo de evento cuja escrita precise ser coordenada com o primeiro.
- `data/editorial/briefs/<id>.json`: brief aprovado imutável. `active_policy.json` guarda referências e revisão; atualização explícita, sob lock e troca atômica. Resolve-se uma vez ao criar cada job.
- `data/editorial/datasets/<version>/`: `manifest.json`, `examples.jsonl`, `preferences.jsonl`, `splits.json`, features e checksums. Diretório preparado em staging e promovido por rename; nunca alterar uma versão publicada.
- `data/editorial/models/<id>/`: artefato B opcional, feature schema, dados/split de treino, parâmetros e relatório. Registro JSON de candidatos/aprovações, sem MLflow.
- Novos renders usam caminhos por versão; mestres, prévias e timelines anteriores permanecem. Modelo não fornece caminhos arbitrários.

Ao exportar, fixar cutoff de eventos e conferir hashes/revisões dos registros lidos; se mudarem no meio, repetir a leitura limitada ou abortar explicitamente. Não produzir dataset parcialmente misturado.

## Fronteiras

- Aprovação humana e QC são independentes; aprovação de publicação não existe neste fluxo.
- Comentários, transcrições, frames/OCR e pareceres de modelo são dados não confiáveis. Nenhum vira shell, caminho ou autorização.
- Dados de feedback atuais nunca entram como feature do próprio exemplo. Referências recuperadas no teste vêm somente do conjunto de treino e de outras famílias de origem.
- Não habilitar treinamento/download em startup do worker. Falta de exemplos retorna contexto sem exemplos e diagnóstico; falta do ranker opcional usa baseline identificado.
- Política/encoder/modelo novos têm feature flags opt-in e rollback para versão anterior. Jobs existentes continuam usando seu snapshot e renderer/timeline originais.
