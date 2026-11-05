# Content Factory: auditoria e opções de integração (04/11/2026)

> Atualização após a auditoria: o worker agora combina propostas do Qwen ancoradas em segmentos da transcrição com os candidatos heurísticos, e a fila usa lista de processamento com recuperação na inicialização. As tabelas abaixo descrevem a linha de base observada antes desse upgrade. O vídeo de teste de 612 s gerou três candidatos; um veio da descoberta por transcrição. Algumas consultas ao Qwen ultrapassaram o prazo experimental de 60 s, e o ranker final usou fallback. A suíte atual passou com 46 testes.

## Veredito

O projeto já é um protótipo funcional e bem delimitado: entrada autorizada, transcrição, três candidatos, timeline validada, render e revisão humana. Ainda não há evidência de que alcance três vídeos publicáveis por dia. O principal gargalo de qualidade é a escolha dos trechos; o principal gargalo de operação contínua é a fila sem recuperação. Antes de adicionar publicação, é preciso medir qualidade e estabilizar execução.

Esta análise foi feita sobre a árvore de trabalho indicada, preservando a alteração preexistente em `README.md`. Os 40 testes passaram no contêiner do worker com `app/` e `tests/` montados da árvore atual. Não foi feito benchmark de ponta a ponta nem teste de qualidade com vídeos reais autorizados.

## Fluxo atual e achados

| Área | Implementação observada | Limite / risco | Prioridade |
|---|---|---|---|
| Ingestão | Streamlit recebe arquivo local ou URL de vídeo único do YouTube; há declaração de direitos, validação de host e download opt-in (`app/ui.py`, `app/submit.py`, `app/youtube.py`). | Autorização é autodeclaração; não há verificação externa nem deduplicação por origem/hash. Upload local fica limitado pela configuração do Streamlit, mas não por um orçamento explícito de duração no worker. | Média |
| Transcrição | `faster-whisper` com VAD, `beam_size=5`, timestamps por palavra e prompt GTA; modelo padrão `base`, CPU `int8` (`app/worker.py`, `compose.yaml`). | Sem medida de WER, confiança, revisão de nomes, seleção explícita PT/EN ou alinhamento forçado. O modelo é recriado por job. O log do worker mostrou falha real de TLS ao buscar o modelo ausente do cache, deixando um job `FAILED`. | Alta |
| Seleção | Janelas de fala de 15–60 s, aproximadamente 40 s, pontuadas por palavras-chave, densidade e duração (`app/core.py`). Qwen apenas reordena até 12 candidatos da lista heurística (`app/ranker.py`). | O LLM não pode descobrir momentos fora dessas janelas; faltam áudio, imagem, estrutura narrativa, diversidade temática e verificação de começo/fim. A sobreposição é limitada, mas não há avaliação objetiva de qualidade. | Máxima |
| Diretor | Qwen sugere título, até três zooms e dois B-rolls; `build_timeline` limita tempos, IDs e termos do título (`app/director.py`, `app/timeline.py`). | O título é comparado por conjunto de palavras, o que não garante equivalência semântica. Não há decisão de enquadramento, cortes internos, mixagem ou trilha. | Média |
| Timeline | JSON v2.0 com vídeo, áudio, palavras, texto, efeitos e B-roll; verificação em Python e esquema em `contracts/timeline.schema.json`. | O validador Python checa apenas parte do contrato: não valida todas as camadas, tipos, limites, ordem e caminhos. O esquema exige `broll.path`, mas o builder só o inclui após staging. O contrato precisa ter estágios explícitos ou um esquema único por estágio. | Alta |
| Render | FFmpeg recorta/reescala para `base.mp4`; Remotion compõe legendas/zoom/B-roll; falha do Remotion aciona render SRT via FFmpeg (`app/edit_render.py`, `app/core.py`, `renderer/src/vertical-clip.tsx`). | Há dupla codificação quando o fallback ou modo FFmpeg é usado; B-roll é recodificado em cada inserção. Fallback perde zoom, banner, B-roll e legenda por palavra. Falta `ffprobe` pós-render, checagem de áudio, quadros pretos, duração e loudness. | Alta |
| Legendas | Tempos por palavra do ASR e grupos de até três palavras no Remotion; fonte DejaVu e animação de palavra ativa. | Sem revisão visual/linguística nem métrica de deriva; quando não há palavras, o Remotion fica sem legenda. O SRT do fallback usa segmentos, com apresentação diferente. Correção automática de `Lucia`/`Rockstar` é restrita, mas ainda pede revisão humana. | Alta |
| Assets | Catálogo local com licença, ID gerado e proteção contra traversal (`app/asset_library.py`, `app/edit_render.py`). | Sem hash, tags visuais, índice pesquisável, versão de licença ou cache de transcode. B-roll escolhido só por texto descritivo. | Média |
| Fila | `LPUSH`/`BRPOP`, estado JSON atômico, um worker e heartbeat em Redis (`app/store.py`, `app/worker.py`, `app/doctor.py`). | `BRPOP` remove antes do processamento; queda do worker pode deixar job preso. Não há lease, retry, estágio idempotente, lock por job, prazo por etapa ou reconciliação. Heartbeat indica processo vivo, não saúde da tarefa. | Máxima |
| Aprovação | Interface permite assistir, baixar timeline e aprovar/rejeitar (`app/ui.py`). | Sem edição de limites/legendas, motivos de rejeição, versão da aprovação ou controle de acesso embutido. Sem publicação automática, corretamente. | Média |
| Docker/GPU | Imagens CPU/GPU, volume de cache HF, GPU NVIDIA opcional (`Dockerfile*`, `compose*.yaml`). | Versões amplas/`latest` dificultam reprodução; GPU, CUDA/cuDNN e VRAM não foram testados nesta máquina. UI e worker compartilham imagem pesada. | Média |
| Observabilidade/testes | Doctor mostra worker/Ollama e atividade do LLM; 40 testes passaram. | Sem métricas por etapa, latência por clip, consumo GPU, contagem de fallbacks, trace/correlation ID, testes de crash/recovery e avaliação editorial com mídia real. | Alta |

## Componentes externos: o que vale reaproveitar

| Projeto | Uso realista aqui | Decisão |
|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Já integrado. Experimentar `small`, `medium` e `large-v3-turbo` em PT e EN com o mesmo conjunto de amostras, medir WER, nomes próprios, tempo e VRAM. Usar `hotwords`/prompt quando apropriado. | **Manter e medir antes de trocar.** |
| [WhisperX](https://github.com/m-bain/whisperX) | Alinhamento forçado nos trechos finalistas e diarização quando houver múltiplos falantes. Rodar como etapa opcional GPU; preservar texto original e sinalizar palavras sem alinhamento. | **Piloto limitado**, porque adiciona modelos, dependências e custo de GPU. |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Detectar cortes/mudanças de cena e anexar eventos temporais ao score e às decisões de B-roll/reframe. | **Piloto prioritário**, simples de integrar em Python; cena não equivale a highlight. |
| [MediaPipe Face Detector](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/FaceDetectorOptions) | Detectar rostos em amostragem de frames, suavizar trajetória e produzir crop keyframes na timeline; centro quando confiança baixa. | **Piloto**, útil para talking head; gameplay exige regras separadas. |
| [auto-editor](https://github.com/WyattBlue/auto-editor) | Extrair sinais de silêncio e movimento; avaliar prévia sem render para reduzir pausas. | **Aproveitar sinais, não substituir a timeline**: o corte automático pode romper setup/payoff. |
| [RQ](https://python-rq.org/docs/workers/) | Registries, retries e workers sobre Redis já existente. | **Candidato preferido para piloto de fila**; checar recuperação de tarefas abandonadas e idempotência dos artefatos. |
| [Celery/Redis](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html) | Retries e redelivery com visibility timeout. | **Alternativa** se houver múltiplas filas/workers e agendamento; mais superfície operacional. Configurar timeout maior que a tarefa longa. |

Não recomendo importar um editor completo de terceiros agora. FFmpeg e Remotion já cobrem o contrato visual atual; a lacuna é a inteligência que alimenta a timeline, a validação e a avaliação de qualidade.

## Desenho recomendado

1. Gerar candidatos por **duas vias**: janelas de fala e propostas do Qwen sobre chunks de transcrição com IDs/tempos fixos. O modelo sugere intervalos, mas Python ancora em palavras reais, impõe 15–60 s e rejeita começo/fim cortados. Unir, deduplicar e diversificar por assunto.
2. Calcular sinais separados: coerência/hook/setup/payoff via modelo local; pausa, energia e riso por áudio; mudança de cena e movimento por vídeo; gaming específico por regras leves; autonomia contextual por pergunta de avaliação. Registrar score e evidências por sinal. O LLM deve justificar decisões, não fornecer pontuação única opaca.
3. Fazer avaliação cega de 30–50 vídeos autorizados: comparar seleção atual, Qwen livre e multissinal; revisores marcam publicável, gancho, fechamento, contexto e erro factual. A métrica principal é vídeos aprovados por hora de processamento e por dia, além de diversidade e taxa de retrabalho.
4. Acrescentar etapas idempotentes: `ingest`, `transcribe`, `analyze`, `propose`, `direct`, `render`, `qc`, `review`. Guardar hash de entrada, versão de modelo/contrato, artefatos e conclusão por etapa; lease/retry/reconciler para recuperar queda.
5. Manter o JSON como contrato central e versioná-lo: `source_range`, cortes internos, crop keyframes, B-roll referenciado por ID, audio gain/ducking, captions revisadas e provenance. Validar com JSON Schema no runtime **e** regras semânticas Python. Uma timeline aprovada deve ser imutável.
6. FFmpeg: ingest/probe, recorte, cache de proxies, crop/scale, normalização EBU R128, mixagem e QC. Python: análise, tracking, seleção, validação e orquestração. Remotion: tipografia, zoom, transições e composição final. Qwen: propostas semânticas estruturadas, sempre ancoradas e revisáveis.
7. QC automático antes de `NEEDS_REVIEW`: arquivo abre, duração/fps/resolução, áudio presente, loudness/true peak, silêncio excessivo, quadros pretos, legendas dentro dos limites e amostra visual. Fallback FFmpeg deve aparecer como candidato degradado, sujeito a revisão explícita.

## Distribuição futura

Criar adaptadores independentes apenas depois de aprovação humana e QC, com `publish_id`, idempotência, estado remoto e reconciliação. [YouTube `videos.insert`](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert) permite upload autorizado; [TikTok Content Posting API](https://developers.tiktok.com/docs/en/content-posting-api-get-started) exige app, escopo e autorização do usuário, e clientes não auditados ficam restritos. A [coleção oficial da Meta para Instagram](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api) documenta publicação de Reels em contas elegíveis. Facebook Reels requer validação específica da API e permissões da conta antes de escolher o fluxo. Não usar automação de navegador como substituto dos adaptadores oficiais.

## Próximo experimento que decide a arquitetura

Primeiro resolver o certificado/obter modelo Whisper no cache de forma confiável. Em seguida, com vídeos licenciados, executar um lote controlado comparando o ranker atual, Qwen propondo timestamps e fusão com áudio/cenas. Sem esse conjunto, qualquer afirmação de superioridade editorial ou meta de três vídeos por dia seria especulativa.
