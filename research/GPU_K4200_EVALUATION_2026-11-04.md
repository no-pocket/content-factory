# Quadro K4200 no Content Factory: avaliação corrigida

Atualização de 2026-11-05: a [auditoria REA e sua seção de medições pareadas](AUDITORIA_REA_K4200_2026-11-05.md) registram o contrato de contexto, os testes CPU/GPU de três repetições e os limites que permanecem. A versão 4.1.0 rejeita pedidos que excedem o contexto GPU antes da geração.

Atualizado em 2026-11-04, fuso America/Sao_Paulo. A conclusão inicial de que a GPU não executaria inferência no Docker estava errada. O Ollama atual e o CTranslate2 atual não a usam, mas um `llama.cpp` legado compilado para `sm_30` com CUDA 10.2 executou Qwen 2.5 na K4200 dentro do Docker Desktop/WSL 2.

## Pistas pesquisadas

- A [tabela legada da NVIDIA](https://developer.nvidia.com/cuda/gpus/legacy) identifica a K4200 como compute capability 3.0; a [matriz CUDA/arquitetura](https://docs.nvidia.com/datacenter/tesla/drivers/cuda-toolkit-driver-and-architecture-matrix.html) aponta CUDA 10.2 como última versão com suporte a `sm_30`.
- No [Reddit, um caso com a mesma K4200](https://www.reddit.com/r/comfyui/comments/17gpoyp) descreve o aplicativo deixando de reconhecer a placa ao usar CUDA 12.2. Isso motivou testar o toolkit antigo, sem presumir que a placa falhou.
- O [fork Kepler discutido no r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/comments/1xeicw2/highperformance_llamacpp_fork_for_legacy_gpus/) concentra-se em `sm_35` e posteriores; a K4200 exige `sm_30`. Por isso, compilamos o [llama.cpp b4300](https://github.com/ggml-org/llama.cpp/tree/b4300) diretamente com CUDA 10.2 e Clang 14.
- Nos [relatos sobre NVENC antigo](https://www.reddit.com/r/ffmpeg/comments/19f4sgh) e [Kepler](https://www.reddit.com/r/ffmpeg/comments/1ikhh43), FFmpeg 5.1.2 é indicado para a API NVENC 11.1. A tentativa com FFmpeg 9.0.2 e driver 475.14 falhou por exigir API 13.1; o FFmpeg 5.1.2 nativo do Windows codificou um vídeo real da pasta `_videos_test` em H.264, 720×1280, 5 s, 150 quadros. NVENC dentro do container ainda falha com `unsupported device (2)`.

## Evidência local

| Teste | Resultado |
| --- | --- |
| CUDA Driver API e kernel CUDA Runtime 10.2 em Docker | O kernel `sm_30` retornou 42 em ambas as sondas. |
| Ollama atual, Qwen 2.5 3B | Respondeu somente por CPU (`gpu_count=0`). |
| CTranslate2 atual | Não detectou CUDA utilizável. Whisper continua por CPU. |
| `llama.cpp` b4300, CUDA 10.2, Qwen 2.5 3B Q4_K_M | 37/37 camadas descarregadas na K4200; `/health` e `/v1/chat/completions` responderam. |
| API adaptadora `/api/generate` | Resposta JSON válida com contagens e tempos, compatível com o classificador e o editor atuais. |
| Vídeo de teste de 65 s | Job `05eb97a2-c0c7-4d88-80aa-0e7cec1f12b0` terminou `NEEDS_REVIEW`, um corte renderizado, `ranker_used=kepler_gpu`, `director_used=kepler_gpu`. |

Benchmarks, mesmos parâmetros (`p128 n32`, 4 threads, lote 128):

| Modelo | Pré-processamento GPU / CPU | Geração GPU / CPU |
| --- | --- | --- |
| Qwen 2.5 1.5B Q4_K_M | 223,31 / 141,04 tokens/s | 14,73 / 23,22 tokens/s |
| Qwen 2.5 3B Q4_K_M | 107,87 / 75,88 tokens/s | 7,84 / 12,07 tokens/s |

No prompt real de 3.000 tokens usado para propor cortes, a chamada pela GPU levou aproximadamente 42,6 s com formato de chat, ante 95,9 s pelo Ollama na CPU em medição anterior. A GPU melhora a leitura de prompts longos, mas a geração token a token foi mais lenta nos benchmarks; a vantagem total depende do tamanho da resposta e do prompt. Não há garantia de suporte oficial da NVIDIA para Kepler no WSL 2.

## Como executar

1. Na primeira instalação, execute `research/build-kepler.ps1` na raiz do projeto. Ele obtém `llama.cpp` b4300, prepara a imagem CUDA 10.2 se necessário e compila `llama-server` no volume `cf_kepler_b4300`.
2. Tenha o modelo `qwen2.5:3b` no volume Ollama. Ajuste `OLLAMA_MODEL`, `KEPLER_CTX_SIZE`, `KEPLER_BATCH_SIZE`, `KEPLER_UBATCH_SIZE`, `KEPLER_GPU_LAYERS`, `KEPLER_THREADS` e `KEPLER_REQUEST_TIMEOUT` pelo ambiente conforme a memória disponível.
3. Execute `docker compose -f compose.yaml -f compose.kepler.yaml up -d worker ui kepler-engine kepler-bridge`. O override monta o código Python da árvore atual nos serviços e expõe a ponte apenas em `127.0.0.1:11436` para diagnóstico.
4. Na interface, selecione `kepler_gpu` em **Processamento do Qwen** e escolha análise e/ou direção com Qwen para o job. Sem o override, mantenha `ollama`.

O Docker Desktop esgotou a unidade C: durante uma tentativa de reconstrução de imagem com contexto grande. `.dockerignore` agora exclui vídeos, caches e repositórios de pesquisa; o cache pip foi limpo, o Docker recuperado e o espaço livre ao final dos testes era cerca de 1,7 GB. Evite reconstruir imagens grandes nessa unidade antes de ampliar espaço. A integração usa os binários já compilados no volume externo e a imagem existente do worker para a ponte.
