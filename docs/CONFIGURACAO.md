# Configuração por job e por instalação

## Ajustes na interface

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
| `director_mode` | `ollama` | `ollama` pede sugestões de edição; `heuristic` usa timeline padrão |
| `render_engine` | `remotion` | `remotion` animado ou `ffmpeg` com legendas simplificadas |

O mesmo objeto `settings` pode ser incluído na entrada JSON de URL autorizada em `app/submit.py`. Para um frontend novo, use `normalize_job_settings` como contrato de validação; a UI atual não contém a lógica de processamento. A chamada de submissão exige URL, criador, nota de licença e confirmações de direitos/plataforma.

## Ajustes da instalação

`.env.example` documenta parâmetros dos serviços. Eles não são todos opções por job:

| Grupo | Variáveis principais | Quando alterar |
| --- | --- | --- |
| Ingestão | `ENABLE_YOUTUBE_DOWNLOAD`, `YOUTUBE_MAX_DURATION`, `YOUTUBE_MAX_BYTES` | Habilitar e limitar downloads autorizados |
| Whisper | `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `WHISPER_INITIAL_PROMPT` | Mudar execução ASR e vocabulário inicial |
| Qwen/Ollama | `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_PROPOSAL_MAX_CHUNKS` | Padrões do backend; ajustes por job prevalecem onde houver campo correspondente |
| Render | `RENDER_FALLBACK_FFMPEG`, `RENDER_TIMEOUT` | Controlar fallback e prazo do Remotion |
| K4200 | `KEPLER_CTX_SIZE`, `KEPLER_BATCH_SIZE`, `KEPLER_UBATCH_SIZE`, `KEPLER_GPU_LAYERS`, `KEPLER_THREADS`, `KEPLER_REQUEST_TIMEOUT`, `KEPLER_CONTEXT_MARGIN` | Ajustar o servidor legado, com teste de VRAM/contexto |

O backend GPU exige `compose.kepler.yaml`. Alterações de ambiente do Compose exigem recriação do serviço, não apenas reinício do processo. Veja [Operação diária](OPERACAO.md) para os comandos e [GPU K4200](GPU_K4200.md) para limites medidos.
