# Sprint de qualidade: implementação, evidências e pendências

Data: 06/11/2026, São Paulo. **Qualidade editorial ainda não validada.** O objetivo
completo depende de corpus e decisões reais; nenhum benchmark técnico substitui isso.
Código na branch `codex/quality-editorial-api`; sem merge, push ou publicação.

Conferência requisito por requisito: [auditoria de aceitação](AUDITORIA_ACEITACAO_SPRINT.md).

Continuação solicitada: [cinco fontes com GPU/Qwen 2.5](TESTES_GPU_5_VIDEOS_2026-11-06.md),
[acesso Tailscale pelo celular](../docs/OPERACAO.md#acessar-pelo-celular-via-tailscale)
e [planejamento das próximas sprints](../docs/PROXIMAS_SPRINTS.md).

## Entregas

- QC completo MP4/WebM: decode, duração, resolução, áudio esperado, silêncio/preto,
  limites por job, medições e diagnósticos por candidato/tentativa.
- Retry direcionado limitado, checkpoints de transcrição/seleção/timeline/resultados,
  recuperação de processing e registros QUEUED órfãos, estado parcial explícito.
- Decisões com notas de gancho/contexto/fechamento/legendas, razão, retrabalho, ajustes,
  histórico, snapshots e controle de revisão concorrente. Sem aprendizado automático.
- Métricas por fonte/configuração, comparação pareada e médias de dimensões para
  orientar hipóteses; falta avaliação real suficiente para propor regra geral.
- Serviço compartilhado Streamlit/CLI/HTTP, API v1 autenticada em localhost, contrato
  OpenAPI e documentação de erros/estados. Nenhuma dependência Python adicionada.
- Instrumentos offline de inventário, sinais audiovisuais e comparação de modelos.

Referências: [plano](../docs/SPRINT_QUALIDADE_PLANO.md), [QC](../docs/CONTROLE_QUALIDADE.md),
[editorial](../docs/PROTOCOLO_EDITORIAL.md), [API](../docs/API.md).

## Corpus e decisões

O usuário autorizou **12 vídeos**, com português e inglês, e definiu esse conjunto
como suficiente para a rodada atual. O [inventário](sprint/inventory.json) registra
**12 hashes distintos, 112,49 minutos e 1,93 GiB**. A meta original de 20–30 permanece
apenas como referência futura; não bloqueia este piloto. A confirmação explícita do
usuário foi registrada nos jobs; a presença de um arquivo na pasta, isoladamente,
não é comprovação de autorização.
`corpus-manifest.json` identifica os 12 jobs baseline; `corpus-results.json` é produzido
quando o lote terminar. O worker detecta o idioma, preserva a fala sem tradução e as
métricas incluem `by_language`. Ainda é necessário revisar trocas de idioma e detecções
erradas. O lote começou com Whisper base/CPU/int8, três candidatos de duração alvo 40 s,
seleção/direção heurísticas e FFmpeg. O usuário recusou editorialmente esse lote. O perfil inicial da UI agora usa Qwen/GPU + Remotion; snapshots existentes são preservados.

O usuário aprovou explicitamente o job `7cb2fb21` e solicitou recusar todos os demais existentes: **18 jobs recusados**, com comentário real, sem notas inventadas. O registro e os seis arquivos do job aprovado mantiveram os hashes. Evidência: [recusas](sprint/user-rejections.json). A aprovação técnica do lote não demonstrou qualidade editorial.

As correções e o novo teste controlado estão em [correções após revisão](CORRECOES_REVISAO_USUARIO.md). Os novos ensaios permanecem para revisão humana.

## Sinais de áudio e cenas — mesmo vídeo de 612,217 s

`python -m research.evaluate_sprint signals --job 530ade0e-7027-46ff-8173-5da8e5166ef4 ...`
gerou [signals.json](sprint/signals.json): FFmpeg levou **22,070 s**, incluindo
**5,179 s** de áudio, detectando 152 pausas e 1.225 janelas RMS de 0,5 s. A regra
experimental deslocou três inícios em menos de 0,75 s; manteve os fins. A energia
fica disponível como evidência, sem peso editorial calibrado.

FFmpeg `scene > 0.3`, reduzido a largura 320, não detectou cenas. A imagem de laboratório
PySceneDetect já instalada (`sha256:a3c87af81ff5eff182dc6d383f7fdabc6929a340a629d603ca17f0a2d150e602`)
com AdaptiveDetector levou **15,065 s** e encontrou duas cenas, fronteira em
**245,766667 s**. O resultado demonstra que parâmetros/detectores não são equivalentes;
não demonstra qual transição melhora um corte. Os ensaios não isolam clocks/cache e o
FFmpeg começou enquanto havia inferência local; tempos são observações, sem ranking
conclusivo de performance. Não houve instalação de PySceneDetect no worker nem mudança
de seleção padrão. Compare variantes nos mesmos vídeos com revisão humana antes de integrar.

## Modelos locais

Modelos já instalados: Qwen2.5 1.5B (~986 MB) e 3B (~1,93 GB), Q4_K_M. Sem download,
build ou troca de padrão. Recursos antes do trabalho: C: ~13,7 GB livres, E: ~1,80 TB;
containers com limite de memória agregado de 15,58 GiB. Uma amostra durante inferência
mostrou Ollama em 592% de CPU e 3,328 GiB de RAM; não é pico nem medição por modelo.
Snapshots `/api/ps` por execução estão no relatório e registram CPU (`size_vram=0`).

Nos [prompts reais do pipeline](sprint/pipeline-models.json), mesmos 12 segmentos e
mesmos parâmetros por tarefa, duas repetições por modelo, sem alterar jobs:

| Modelo | Descoberta, s (execuções 1 / 2) | Direção, s (1 / 2) | Resultado técnico |
|---|---|---|---|
| Qwen 1.5B | 22,717 / 17,157 | 7,789 / 7,798 | 1 proposta aceita por execução; direção válida |
| Qwen 3B | 36,241 / 34,443 | 19,726 / 19,707 | 1 proposta aceita por execução; direção válida |

Ambos terminaram por `stop`, sem fallback observado nessas oito chamadas. Descoberta:
767 tokens de entrada; direção: 379. Os hashes dos prompts iguais entre modelos,
opções, contagens, durações internas, outputs e recursos estão no JSON. Primeira
execução pode incluir carga; não confundir com steady state. São apenas um vídeo e
duas repetições: não estimam confiabilidade geral nem qualidade aprovada pelo usuário.
Esse ensaio inicial foi complementado pelas comparações v2 PT/EN e ASR descritas abaixo. A avaliação editorial dos efeitos continua dependente do usuário.

Ensaios exploratórios anteriores também foram preservados: [inicial](sprint/models-initial.json)
incluía timestamps de palavras desnecessários; [prompt reduzido](sprint/models.json)
gerou JSON, mas ambos modelos confundiram índices com tempos (0/3 respostas aceitas
por modelo). Esses contratos de teste não são o prompt de produção e não devem ser
usados para concluir que o ranker real falhou. Motivaram o ensaio com prompts reais.

Os [benchmarks anteriores CPU/GPU](AUDITORIA_REA_K4200_2026-11-05.md) continuam válidos
no seu escopo: mesma implementação/modelo, CPU mais rápida em geração, GPU em prefill.
Nenhum desses números prova vantagem editorial nem justifica trocar padrão. GPU K4200
continua opcional; Whisper permanece CPU e não houve alteração do servidor legado.

## Clones existentes e licenças

[clones.json](sprint/clones.json) registra commit completo e SHA-256 dos LICENSE locais,
reinspecionados nesta sprint. Nenhum código copiado ou dependência incorporada.

| Clone | Licença inspecionada | Aproveitamento e custo |
|---|---|---|
| faster-whisper `2a3a857` | MIT | Dependência existente; manter VAD/word timestamps; trocar modelo exige avaliação de legenda/custo. |
| WhisperX `5d3678b` | BSD-2 | Alinhamento de finalistas é hipótese; Torch/pyannote/modelos extras e RAM tornam integração maior. |
| PySceneDetect `c5ce29c` | BSD-3 | Detector adaptativo mostrou transição ausente na regra FFmpeg; manter piloto isolado até comparação editorial. |
| MediaPipe `0332274` | Apache-2 | Enquadramento facial é hipótese futura; requer modelo, suavização e testes de múltiplos rostos/gameplay. |
| auto-editor `5ad05f9` | Unlicense | Análise de áudio/movimento em Nim; sem módulo Python direto. FFmpeg já cobre sinais desta sprint. |
| RQ `e672abe` | BSD-2 | Registros de jobs abandonados são referência; migração desnecessária para worker único com checkpoints. |
| Celery `2fe0ead` | BSD-3 | Recursos distribuídos com custo operacional maior; não adotar nesta sprint. |
| llama-b4300 `dafae66cc` | MIT | Backend Kepler existente preservado. |
| llama-cuda102 `c16c35b81` | MIT | Alternativa de laboratório, sem build/adoção nova. |
| llama-jetson-cuda102 `cba793e` | MIT | Orientado a plataforma distinta; não assumir compatibilidade com K4200/WSL. |
| llamacpp-kepler `b367989` | MIT | Referência legada; atualizar binários sem medições ameaçaria ambiente funcional. |

Licenças de repositório não substituem as de modelos/assets. Manter avisos MIT/BSD
e obrigações Apache quando houver futura incorporação; reavaliar dependências transitivas.

## Evidência funcional e limites operacionais

Última suíte completa observada: **136 testes passaram**, em 16,33 s, após as correções de título/encerramento e registro da origem da decisão. Compose base/Kepler/API e `git diff --check` passaram. O lote terminou: **12 vídeos, 36 candidatos, 26 VALID/10 WARNING**, 48,08 min de processamento e 9,10 min de sinais; **editorialmente recusado pelo usuário**. [Resultados completos](CORPUS_PILOTO_12_RESULTADOS.md).

- Via **agent-browser CLI** no Edge: botão de QC verificou os três candidatos do job
  `7cb2fb21`; todos `VALID`. Três WebM chegaram a `ended`, sem erro: 25,309 s,
  15,307 s e 41,107 s. Cada MP4 também passou pelo decode completo e dimensões/áudio.
- Upload pela UI do trecho autorizado `gpu_fixture_65.mp4`, Whisper tiny, heurística,
  diretor heurístico e FFmpeg, 1 candidato: job `27e1ff51-6607-4586-b192-f45eabec7aa0`,
  `NEEDS_REVIEW`, `VALID`, tentativa 1, **56,068 s** registrados. Não aprovado editorialmente.
  A prévia de **43,307 s** também chegou a `ended` no Edge sem erro de mídia.
- API local 8510 iniciada com segredo em `data/api.token` (ignorado): consulta real
  autenticada respondeu v1 e sete jobs; consulta sem token respondeu HTTP 401.
- No corpus novo, os três WebM do primeiro vídeo inglês (`a5f108ff`) chegaram a
  `ended` no Edge: 43,073 s, 44,673 s e 42,384 s, sem erro. A transcrição e o SRT
  permaneceram em inglês. [Evidência técnica](sprint/browser-english.json); não é
  avaliação de fidelidade da transcrição nem aprovação editorial.
- Fluxo de revisão pelo agent-browser em Streamlit **isolado**, com mídia sintética:
  aprovação → reload → rejeição com retrabalho → reload preservou duas revisões e
  os snapshots. O candidato falho continuou bloqueado e o estado parcial visível.
  [Histórico sintético](sprint/review-ui-synthetic.json). Essas duas decisões foram sintéticas; as recusas reais posteriores foram executadas somente por instrução explícita do usuário. O container de UI de teste foi removido.
- Worker reiniciado somente com pending/processing zerados; resultados e aprovação
  legada preservados. Sem rebuild, download de modelos ou remoção de volumes/dados.
- Testes incluem decode real de mídia sintética, corrupção, áudio ausente, estados
  parciais, limite de tentativa, checkpoint antes do render, interrupção sintética
  durante render com arquivos persistidos, recuperação de fila/transcrição/seleção,
  histórico/revisão concorrente, invalidação de aprovação, métricas e HTTP real efêmero.
- Revisão independente encontrou quatro bugs (alvo do retry, aprovação ligada a
  artefato invalidado, denominador entre configurações e tempo interrompido): corrigidos
  com regressões observadas falhando antes de passar. Tempo interrompido é limite inferior.

Foi feito SIGKILL/restart **real** de um worker e Redis isolados, com mídia sintética:
[recovery-real.json](sprint/recovery-real.json). Após kill: primeiro candidato VALID,
segundo RENDERING, ambos tentativa 1, processing=1. Após restart: ambos VALID,
tentativas [1,2], processing=0, hash do primeiro MP4 idêntico. Corrupção intencional
do segundo gerou PARTIAL_FAILED e o limite bloqueou nova tentativa. Nenhum dado da
produção foi montado nesse teste; containers temporários foram removidos sem volumes.

O primeiro ensaio expôs PermissionError intermitente no rename atômico quando um leitor
Windows acessava o JSON no bind mount. [Registro inicial](sprint/recovery-real-initial.json).
Foi corrigido com retry exponencial limitado e aviso; testes comprovam também que
negação persistente preserva o registro anterior e continua falhando explicitamente.
A correção foi validada no worker isolado e carregada no worker de produção depois que o lote terminou, com as filas vazias.

Ainda não foi interrompido o host nem cada estágio com mídia real. Não há lease
multiworker, Range HTTP nem idempotency key de criação. JSON/base64 continua limitado
a ~48 MiB de mídia; a rota nova de streaming suporta até 2 GiB, como o Streamlit.
O maior arquivo real do corpus (457,2 MiB) passou pela API isolada, HTTP 201, hash
idêntico e fila isolada com um job; nenhum render ou decisão adicional em produção.
Tempo observado: 9,495 s. RAM após envio: 19,18 MiB (não é pico).
[Registro do teste](sprint/api-stream-real.json).

## Comparações adicionais concluídas

Os ensaios [PT v2](sprint/pipeline-models-pt-v2.json) e [EN v2](sprint/pipeline-models-en-v2.json) usaram os prompts completos de proposta, reranking e direção, mesmos segmentos/opções por idioma, Qwen1.5B/3B CPU, duas repetições. Em português ambos aceitaram uma proposta por repetição; em inglês ambos aceitaram zero propostas, embora reranking e direção respondessem. As [respostas inglesas diagnosticadas](sprint/english-proposal-diagnostics.json) mostram índices inválidos/confusão com tempos e durações fora do limite. As validações não foram relaxadas; as rejeições agora têm contadores e motivos. Nenhuma superioridade editorial foi inferida.

Whisper [tiny](sprint/asr-tiny.json) e [base](sprint/asr-base.json), ambos CPU/int8, quatro threads, beam5, VAD e palavras, usaram os mesmos 60 s PT/EN, duas repetições, modelos em cache e sem rede. Tiny: PT 3,663/3,387 s, EN 2,945/3,092 s; base: PT 5,621/5,876 s, EN 6,184/6,496 s. RSS máximo por processo: 608,375/760,852 MiB. Ambos detectaram os idiomas esperados. Não há transcrição humana de referência nem WER: velocidade não prova fidelidade de legendas.

A comparação posterior na K4200 usou dois GGUFs locais sobre o mesmo minuto em português e gerou dois candidatos Remotion de alta fidelidade. 1.5B concluiu seleção/direção GPU; 3B teve fallback na direção por limite de resposta. Detalhes e limitações: [correções após revisão](CORRECOES_REVISAO_USUARIO.md).

## Gates pendentes

1. **Resolvido nesta amostra:** o usuário avaliou os dois candidatos como idênticos, com imagem/legendas/efeitos bons e final seco. Esse feedback orientou a variante `700982a4`, com título humano e final suave, posteriormente aprovada com “Ficou bom; manter os dois ajustes”. Decisão registrada sem notas inventadas. O job aprovado `7cb2fb21` foi preservado. [Detalhes e testes](CORRECOES_REVISAO_USUARIO.md).
2. Medir ganhos/perdas editoriais por fonte em pares comparáveis após essas decisões; os dois novos ensaios cobrem somente uma fonte PT. Não atribuir ao modelo um ganho decorrente de trocar FFmpeg por Remotion.
3. Só incorporar regras de pausas/energia/cenas após comparação humana dos mesmos vídeos. As 21/36 janelas alteradas pelo experimento são evidência de mudança, não de melhoria.
4. Se houver expansão de teste, repetir a comparação GPU em uma fonte inglesa; o piloto bilíngue completo e os benchmarks CPU já existem, mas o novo perfil GPU foi renderizado apenas em PT.

A implementação e as evidências técnicas estão disponíveis; a sprint **não está totalmente validada editorialmente**. Os 12 vídeos aceitos pelo usuário bastam para esta rodada. Não é necessário reenviar mídia nem preencher o corpus original de 20–30 para revisar as amostras atuais.
