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

Novos formulários começam com Qwen/GPU K4200, Remotion e `render_quality=high`; CPU e perfil standard continuam selecionáveis. A API conserva suas escolhas explícitas e os snapshots dos jobs existentes. Jobs antigos sem `render_quality` são processados como standard.

High mantém mestre 720×1280, usa CRF 16 na base e 18 no mestre; prévia WebM 720×1280, CRF 10/4 Mbit/s. Standard conserva a prévia 540×960. High exige Remotion sem troca silenciosa para FFmpeg se falhar. A UI limita o player a 340 px e oferece MP4 mestre. Fonte horizontal 1280×720 perde detalhe ao recortar para vertical; aumentar resolução de saída não recupera detalhe ausente.

Legendas FFmpeg agora usam frases de até três palavras com timestamps de palavras; sem esses timestamps, a estimativa é diagnosticada. O Remotion mantém o componente de legendas animadas e zooms do exemplo aprovado.

Novas timelines também registram `finishing`: cauda de 0,35 s depois da fala, com último frame congelado e fade visual de 0,25 s. O áudio original termina inteiro, seguido de silêncio; não há música nova nem fade por cima da última palavra. QC considera a cauda na duração final (até 60,35 s para 60 s de fonte). Timeline antiga sem esse campo não ganha cauda. Há uma codificação adicional para esse acabamento, incluída no tempo de render.

O título automático não deve copiar a frase inicial. Resposta inválida ou repetida é omitida; não há fallback que repita transcrição. Novos títulos têm estilo compacto de até três linhas. Um título fornecido explicitamente pelo editor pode ter até 80 caracteres/12 palavras, registra origem humana e não é atribuído ao modelo. A revisão humana continua responsável por sua fidelidade editorial.
