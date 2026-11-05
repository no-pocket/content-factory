# Arquitetura técnica — Content Factory 4.1.0

## Componentes e fluxo

```text
Streamlit :8501 ──> registro JSON em data/work ──> Redis clips:queue
                                                └──> worker único
                                                      ├── ingestão autorizada / yt-dlp opcional
                                                      ├── faster-whisper (CPU, timestamps por palavra)
                                                      ├── heurística + Qwen ranker
                                                      │     ├── Ollama local (CPU nesta máquina)
                                                      │     └── ponte Kepler -> llama.cpp/CUDA 10.2/K4200
                                                      ├── Qwen Editing Director + timeline validada
                                                      ├── FFmpeg + Remotion (fallback FFmpeg)
                                                      └── MP4 mestre + WebM de prévia -> revisão humana
```

`compose.yaml` define UI, worker, Redis e Ollama opcional. `compose.kepler.yaml` acrescenta servidor GPU e ponte Ollama compatível, exposta somente em localhost para diagnóstico. A UI é uma camada de apresentação: `app/job_settings.py`, `app/store.py`, `app/queueing.py` e o worker mantêm a lógica e os dados necessários a outro frontend.

## Dados e contratos

`data/work/<id>.json` é o estado persistido do job; `data/work/<id>.transcript.json` guarda ASR; `data/input/` contém upload/download; `data/output/<id>/` guarda MP4, WebM e timeline por candidato. Escritas do estado usam troca atômica de arquivo. Redis guarda fila pendente, lista em processamento e heartbeat. `recover_inflight` reenvia jobs interrompidos quando o worker reinicia; a implantação suporta um worker, sem lease multiworker.

Cada job salva uma cópia validada de seus ajustes. A UI e `app/submit.py` usam `normalize_job_settings`, portanto mudanças na configuração padrão não alteram a intenção de um job já criado. `contracts/youtube_ingest.schema.json` descreve a entrada de URL para integrações; `contracts/timeline.schema.json` documenta a timeline. `app/timeline.py` é o validador semântico em runtime.

## Fronteiras e tratamento de falhas

- Fonte YouTube restrita a vídeo individual e autorização declarada; download desabilitado por padrão. Assets B-roll exigem registro de direitos e caminho local validado.
- Transcrição, descrições e saída Qwen são dados não confiáveis. O ranker valida IDs, tempos e respostas completas; o diretor só sugere campos limitados. A timeline impõe limites e não aceita comandos shell nem caminhos arbitrários do modelo.
- Na GPU, a ponte consulta contexto e tokenizer reais antes da inferência; rejeita estouro de contexto e opções não implementadas. Ranker e diretor descartam resposta limitada ou prompt truncado. Falhas semânticas acionam heurística, com evento no job.
- Render Remotion pode cair para FFmpeg com legendas simplificadas, se configurado. Cada MP4 recebe prévia VP8/Opus completamente decodificada antes da publicação. O motor efetivo fica registrado por candidato.
- `NEEDS_REVIEW` exige decisão humana. Não há publicação social, autenticação para exposição pública, edição manual de timeline nem verificação externa de licença.

## Limites atuais

Whisper continua em CPU nesta workstation. A K4200 acelera leitura de prompts, mas a geração 3B foi mais lenta nos testes pareados; a escolha de backend permanece por job. NVENC funcionou isoladamente no container com a capacidade `video`, mas não foi integrado nem validado em qualidade no pipeline, que usa `libx264`. A fila não oferece vários workers, leases nem idempotência detalhada por etapa. A UI só deve ficar em localhost, túnel SSH ou VPN.

Leia [Processo de produção](PROCESSO.md) para a sequência operacional, [GPU K4200](GPU_K4200.md) para o caminho legado e [Testes](TESTES.md) para validação.
