# Configuração por job e por instalação

## Ajustes na interface

Montagem multitrecho é opt-in: `settings.timeline_v3=true` exige protocolo editorial
2. O plano opcional do editor entra como `assembly_plan` na criação do job (também
no campo avançado do formulário), com `schema_version=3.0`, `source_duration` e
`segments` contendo `segment_id`, `source_in`, `source_out`, `purpose` e framing
opcional. Os tempos são segundos da mesma fonte autorizada; `output_start`,
`duration` e `frame_count` são derivados e conferidos pelo backend. Não se aceitam
paths nem comandos no plano. Sem plano de montagem, a seleção existente permanece.

O máximo v3 é 120 segundos de fala montada, mais a cauda explícita. Não há padding
para atingir um minuto; cada junção pode arredondar até um frame para acomodar o
relógio de saída. Fronteira sobre palavra e timestamp sem duração dentro dos trechos
selecionados são recusados. Problemas em palavras fora da montagem ficam registrados
no contexto e não são inseridos nas legendas. A timeline v2 conserva teto de 60 s.
Rollback desativa criação v3, sem remover suporte de leitura ou arquivos antigos.

Novos jobs guardam snapshots de política e componentes (`editorial_policy`,
`component_snapshot`, `processing_snapshot`), com hashes do código/prompts disponíveis,
Git/patch local, modelos solicitados e dependências conhecidas. Dados indisponíveis
continuam `UNKNOWN`; nenhuma configuração atual é atribuída retrospectivamente ao
legado. A transcrição integral e seu hash ficam ligados ao contexto temporal de cada
candidato. O renderer mantém a aparência aprovada.

O brief inicial de `app.editorial_policy.initial_brief()` é **DRAFT**, sem ativação.
`save_policy_draft()` grava um ID novo; `approve_policy(id, expected_revision, actor)`
é a operação humana explícita que ativa/reverte o ponteiro. Arquivos ficam em
`data/editorial/briefs` e `active_policy.json`. Não execute aprovação para testes no
diretório real. IDs aprovados são imutáveis; uma alteração exige outro ID/parent.
Novos jobs resolvem a política uma vez; jobs existentes preservam seu snapshot.

Contexto não usa prefixos de 700/900/2200 caracteres. O pré-check local conserva o
texto completo e usa um limite superior por bytes UTF-8, com reserva de geração e
template, claramente identificado como estimativa conservadora. O bridge GPU ainda
valida o prompt com tokenizer/contexto reais antes da inferência. Pools grandes são
comparados em blocos sem alegar ordenação global pelo modelo; a direção que não cabe
usa fallback explícito, com motivo. Esta opção pode recusar prompts que caberiam no
tokenizer; não indica melhoria editorial comprovada ou ganho de desempenho.

Abra **Adicionar um vídeo autorizado → Ajustes de processamento**. Todos os campos abaixo são salvos no JSON do job e validados em `app/job_settings.py`. O valor salvo prevalece sobre mudanças futuras dos padrões do worker.

| Campo (`settings`) | Padrão | Limite / efeito |
| --- | ---: | --- |
| `clip_count` | 3 | 1–6 candidatos |
| `target_seconds` | 40 | 8–60 s, entre mínimo e máximo |
| `min_seconds` | 15 | 8–60 s |
| `max_seconds` | 60 | 15–60 s |
| `proposal_max_chunks` | 12 | 1–32 blocos de transcrição consultados pelo Qwen |
| `shortlist` | 12 | 3–32 candidatos para a classificação final; pelo menos `clip_count` |
| `ollama_timeout` | 180 | 15–600 s por consulta ao modelo |
| `whisper_model` | `base` | `tiny`, `base`, `small`, `medium`, `large-v3-turbo`, `large-v3` |
| `whisper_beam_size` | 5 | 1–10; busca maior tende a custar mais tempo |
| `ranker_mode` | `ollama` | `ollama` usa Qwen; `heuristic` dispensa análise por modelo |
| `llm_backend` | `ollama` | `ollama` ou `kepler_gpu` para as chamadas Qwen |
| `llm_model` | `qwen2.5:3b` | `qwen2.5:3b` ou `qwen2.5:1.5b`, salvo por job; precisa estar instalado no backend |
| `director_mode` | `ollama` | `ollama` pede sugestões de edição; `heuristic` usa timeline padrão |
| `render_engine` | `remotion` | `remotion` animado ou `ffmpeg` com legendas simplificadas |

O mesmo objeto `settings` pode ser incluído na entrada JSON de URL autorizada em `app/submit.py`. Para um frontend novo, use `normalize_job_settings` como contrato de validação; a UI atual não contém a lógica de processamento. A chamada de submissão exige URL, criador, nota de licença e confirmações de direitos/plataforma.

## Ajustes da instalação

`qc_settings` é um snapshot separado aceito na criação via API. Limites e faixas estão
em [Controle de qualidade](CONTROLE_QUALIDADE.md). O servidor opcional usa
`CONTENT_FACTORY_API_TOKEN` (mínimo 24 caracteres) e porta local 8510; veja [API](API.md).

`.env.example` documenta parâmetros dos serviços. Eles não são todos opções por job:

| Grupo | Variáveis principais | Quando alterar |
| --- | --- | --- |
| Ingestão | `ENABLE_YOUTUBE_DOWNLOAD`, `YOUTUBE_MAX_DURATION`, `YOUTUBE_MAX_BYTES` | Habilitar e limitar downloads autorizados |
| Whisper | `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `WHISPER_INITIAL_PROMPT` | Mudar execução ASR e vocabulário inicial |
| Qwen/Ollama | `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_PROPOSAL_MAX_CHUNKS` | Padrões do backend; ajustes por job prevalecem onde houver campo correspondente |
| Render | `RENDER_FALLBACK_FFMPEG`, `RENDER_TIMEOUT` | Controlar fallback e prazo do Remotion |
| K4200 | `KEPLER_CTX_SIZE`, `KEPLER_BATCH_SIZE`, `KEPLER_UBATCH_SIZE`, `KEPLER_GPU_LAYERS`, `KEPLER_THREADS`, `KEPLER_REQUEST_TIMEOUT`, `KEPLER_CONTEXT_MARGIN` | Ajustar o servidor legado, com teste de VRAM/contexto |

O backend GPU exige `compose.kepler.yaml`. Alterações de ambiente do Compose exigem recriação do serviço, não apenas reinício do processo. Veja [Operação diária](OPERACAO.md) para os comandos e [GPU K4200](GPU_K4200.md) para limites medidos.

## Perfil de fidelidade e revisão compacta

O padrão `legacy` mantém o vertical aprovado. Para `web`, `tweet` ou `document`,
novos jobs exigem `framing_windows`: intervalos em segundos da **fonte**, por exemplo
`[{"start":12.5,"end":18}]`. O formulário aceita `12.5-18; 40-47.2`.
Só durante esses intervalos a página fica inteira (ou na ROI manual), sobre fundo
desfocado da própria fonte, com legenda próxima. Fora deles volta o vertical.
Em montagens v3 os intervalos são convertidos para o relógio de cada trecho.
Não há detecção visual/OCR automática: o editor informa e confere os intervalos.

`framing_roi` opcional usa `x`, `y`, `width`, `height` normalizados dentro da fonte.
`face` e `gameplay` continuam disponíveis como foco manual. Timelines antigas e
snapshots existentes mantêm sua geometria; a composição compacta nova é
versionada como `proof_compact_v2`, sem sobrescrever renders anteriores.

Somente efeitos punch zoom/B-roll que cobririam os intervalos protegidos são
suprimidos. Karaoke, tipografia e cores permanecem no Remotion. Preservar a
página não garante leitura de letras pequenas: confira o mestre e a prévia antes
de aprovar; ROI manual pode ser necessária.

Novos formulários começam com Qwen/GPU K4200, Remotion e `render_quality=high`; CPU e perfil standard continuam selecionáveis. A API conserva suas escolhas explícitas e os snapshots dos jobs existentes. Jobs antigos sem `render_quality` são processados como standard.

High mantém mestre 720×1280, usa CRF 16 na base e 18 no mestre; prévia WebM 720×1280, CRF 10/4 Mbit/s. Standard conserva a prévia 540×960. High exige Remotion sem troca silenciosa para FFmpeg se falhar. A UI limita o player a 340 px e oferece MP4 mestre. Fonte horizontal 1280×720 perde detalhe ao recortar para vertical; aumentar resolução de saída não recupera detalhe ausente.

Legendas FFmpeg agora usam frases de até três palavras com timestamps de palavras; sem esses timestamps, a estimativa é diagnosticada. O Remotion mantém o componente de legendas animadas e zooms do exemplo aprovado.

Novas timelines também registram `finishing`: cauda de 0,35 s depois da fala, com último frame congelado e fade visual de 0,25 s. O áudio original termina inteiro, seguido de silêncio; não há música nova nem fade por cima da última palavra. QC considera a cauda na duração final (até 60,35 s para 60 s de fonte). Timeline antiga sem esse campo não ganha cauda. Há uma codificação adicional para esse acabamento, incluída no tempo de render.

O título automático não deve copiar a frase inicial. Resposta inválida ou repetida é omitida; não há fallback que repita transcrição. Novos títulos têm estilo compacto de até três linhas. Um título fornecido explicitamente pelo editor pode ter até 80 caracteres/12 palavras, registra origem humana e não é atribuído ao modelo. A revisão humana continua responsável por sua fidelidade editorial.
