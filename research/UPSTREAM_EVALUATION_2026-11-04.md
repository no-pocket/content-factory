# Content Factory: análise dos projetos clonados e do timeout

Data da análise: 04/11/2026 (horário de São Paulo). Clones rasos em `research/upstream/`, ignorados pelo Git da aplicação. Nenhum código desses clones foi copiado para `app/` nesta análise.

## Por que houve timeout

O ensaio anterior definiu `OLLAMA_TIMEOUT=60` apenas para o contêiner temporário. O valor atual por job é ajustável na interface e seu padrão é 180 segundos. No vídeo de 612,2 s, duas chamadas de descoberta e a classificação final foram canceladas exatamente aos 60 s; outra chamada de descoberta terminou em 44,48 s. O serviço registrou respostas 500 para as chamadas canceladas pelo cliente. A origem foi processamento acima do limite, não indisponibilidade do endpoint.

Medição adicional: reenviei a primeira consulta da transcrição com prazo de 240 s. Ela terminou em **95,9 s**: 9,6 s para carregar o modelo, 73,6 s para avaliar **3.029 tokens de entrada**, 12,6 s para gerar 144 tokens. O prompt tinha 7.433 caracteres e 50 segmentos. O log do Ollama identifica `inference compute id=cpu library=cpu`; a configuração Docker atual não atribui GPU ao contêiner. Portanto, o limite de 60 s era curto para essa entrada nessa CPU. Isso não demonstra que todas as entradas terminarão em 180 s; faltam percentis por duração e concorrência.

As falhas TLS de consulta a `ollama.com` presentes nos logs são independentes das chamadas locais `/api/generate`; o modelo Qwen já estava instalado e gerou resposta. Não usá-las para explicar o timeout.

## Clones e avaliação

| Projeto e commit | O que existe e encaixe real | Decisão |
|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) `2a3a857`, MIT | **Já é dependência da aplicação**. O clone confirma `BatchedInferencePipeline`, VAD, timestamps por palavra e `hotwords` em `faster_whisper/transcribe.py`. O worker atual cria o modelo a cada job, usa `base` por padrão e não mede WER. | Manter. Pilotar modelo `small`/`large-v3-turbo` e vocabulário GTA em conjunto rotulado; reutilizar instância por worker quando seguro. Medir custo CPU/VRAM. |
| [WhisperX](https://github.com/m-bain/whisperX) `5d3678b`, BSD-2 | `whisperx/alignment.py` oferece `load_align_model` e `align`; há modelo PT mapeado. Depende também de Torch, pyannote, transformers e modelos extras. O clone aponta versão pré-release `3.8.7rc1`. | Piloto **apenas nos finalistas** para alinhamento forçado; não trocar toda a transcrição agora. Rodar em contêiner separado e comparar erro de legenda. |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) `c5ce29c`, BSD-3 | API `detect(path, AdaptiveDetector())`, backend OpenCV. Instalei o clone em imagem de laboratório e testei o vídeo autorizado de 612 s: **2 cenas**, corte em 245,77 s, execução em ~18 s. | Integrar como sinal de cortes de cena e para evitar transições ruins. Neste vídeo talking-head estático, não deve pesar muito no score de highlight. |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) `0332274`, Apache-2 | `FaceDetectorOptions` tem modo vídeo; `detect_for_video` recebe timestamps. Requer asset de modelo TFLite e adaptação de trajetória/suavização. Frames aos 60, 300 e 500 s mostram apresentador com rosto deslocando-se; o crop central atual pode cortar expressões/mãos. | Piloto de autoenquadramento para talking head, com fallback ao centro; testar visualmente em múltiplos layouts antes de integrar. |
| [auto-editor](https://github.com/WyattBlue/auto-editor) `5ad05f9`, domínio público/Unlicense | Código atual é principalmente **Nim** (`src/analyze/audio.nim`, `motion.nim`); CLI detecta silêncio e movimento. Não é módulo Python pronto para o worker. | Usar CLI em laboratório para comparar sinais de energia/movimento; para integração permanente, FFmpeg/Python provavelmente encaixam melhor na timeline JSON existente. Não entregar cortes automáticos do auto-editor diretamente. |
| [RQ](https://github.com/rq/rq) `e672abe`, BSD-2 | Usa Redis já presente. `StartedJobRegistry.cleanup` trata jobs abandonados e retries. O projeto atual tem recuperação básica apenas quando o worker reinicia; não tem leases/retry por etapa. | Melhor candidato se houver vários workers ou filas com prioridades. Antes, criar idempotência por etapa e benchmark de migração. |
| [Celery](https://github.com/celery/celery) `2fe0ead`, BSD-3 | Mais recursos, mas mais configuração. A documentação do Redis alerta que tarefa acima do `visibility_timeout` pode ser redeliverada repetidamente; timeout longo atrasa recuperação após morte abrupta. | Não adotar agora para um worker; reavaliar com múltiplos nós, escalonamento e agendas. |

## Reuso real até aqui

- Dependências já presentes antes desta análise: faster-whisper, FFmpeg, Remotion, Redis, Ollama/Qwen, yt-dlp e Streamlit.
- Implementações recentes em `app/ranker.py` e `app/queueing.py` foram escritas no projeto e **não** importam código de RQ, PySceneDetect, WhisperX, MediaPipe, auto-editor ou Celery.
- PySceneDetect foi instalado **somente numa imagem descartável de teste** (`content-factory-scene-probe`); não foi adicionado ao worker de produção.

## Ordem recomendada

1. **Medição editorial**: conjunto de vídeos autorizados com marcação humana de trechos publicáveis; comparar precisão de seleção, início/fim, diversidade e tempo por vídeo. O trecho descoberto no ensaio anterior termina com referência ao próximo vídeo, portanto a validação de payoff ainda é fraca.
2. **Inferência**: registrar `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, carga de modelo, timeout e taxa de fallback por bloco. Reduzir texto/segmentos por consulta e comparar qualidade/latência. Usar GPU compatível para Ollama se disponível; a GPU presente não foi validada para este contêiner.
3. **Reenquadramento**: testar MediaPipe em source talking-head, emitir keyframes de crop na timeline; revisar casos sem rosto, múltiplos rostos e gameplay.
4. **Legendas**: benchmark de Whisper `base` versus modelos maiores e alinhamento WhisperX somente dos candidatos; revisar nomes GTA/Rockstar sem reescrever a fala.
5. **Sinais multimodais**: áudio (energia, silêncio, riso) e cenas/movimento como evidências separadas, nunca como score único sem explicação. PySceneDetect é barato, mas o piloto mostrou pouco poder discriminativo neste material.
6. **Confiabilidade/QC**: leases/retry por etapa, validação de MP4 final com `ffprobe`, loudness e falhas visuais. RQ só quando a orquestração atual deixar de ser suficiente.

## Limites da análise

O piloto real foi feito com um vídeo talking-head e um modelo Qwen 2.5 3B em CPU. Não executei benchmarking de WhisperX, MediaPipe ou auto-editor no vídeo, nem avaliei licenças de modelos específicos além das licenças dos repositórios. As escolhas acima são prioridades de pilotos, não garantias de ganho editorial.
