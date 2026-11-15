# Follow-up: ingestão, preparação e acesso móvel — 11/11/2026

## Mudanças

- Metadados públicos preenchem título e criador, sem reutilizar o campo de autorização. Confirmações de direitos/plataforma continuam explícitas.
- Ingestão persiste `youtube_video_id`, título e provenance; URL equivalente reutiliza o job e seu snapshot.
- Hermes recebe status enriquecido com grupo, modelo, transcrição, candidatos e referências de render; revisão aguarda `pipeline.ready`.
- Preparação de publicação exibe WebM/MP4 e sugestões locais editáveis de título/legenda. Nenhum novo envio externo foi realizado.
- Correção da tela vazia no HTTP Tailscale: UUID v4 CSPRNG quando `crypto.randomUUID` não existe. Boundary oferece recuperação de erros.
- Links antigos `?job=` e `?group=` continuam abrindo a revisão React (ambos verificados pelo navegador).

## Evidências observadas

O erro `crypto.randomUUID is not a function` foi reproduzido no endereço HTTP privado com `isSecureContext=false`. Após o build/deploy do frontend, a Revisão abriu com dois candidatos, sem novos erros, em 375 px e 430 px; nos dois tamanhos não houve overflow. Teste pelo agent-browser CLI em Chromium, sem iPhone/Safari físico.

No formulário Novo, a URL `HmVHy3ttq0Q` trouxe título e criador públicos; autorização ficou vazia e as duas confirmações desmarcadas. Publicação preencheu título/legenda do candidato aprovado existente, reproduziu a prévia de 42,888 s e preservou edição manual após alternar Facebook/Instagram e atualizar dados. Sem publicação ou agendamento adicional.

O túnel privado do Hermes estava parado (tarefa Windows encerrada). A tarefa existente foi iniciada, mantendo execução oculta/keepalive. Pi→API autenticado voltou a responder HTTP 200. Uma reingestão real de `HmVHy3ttq0Q` retornou `duplicate=true` e o mesmo job. GET da transcrição retornou segmentos; GET do MP4 retornou HTTP 200, `video/mp4`, assinatura MP4 e 6.205.698 bytes. O primeiro candidato WebM foi reproduzido no frontend (41,074 s).

## Lote autorizado

| Vídeo | Canal confirmado | Job |
| --- | --- | --- |
| HmVHy3ttq0Q | Cortes do Davy Jones [OFICIAL] | cc3baa3a-844d-4e3b-803d-b451221cdbb5 |
| cvY_q2BhZhg | Gutz | a2a84a09-4e2f-40e3-b2df-8548c5a890d5 |
| J1EMr_2SnRo | Grove Street Brasil | f364031b-079c-44c4-a26a-d948505686f2 |
| H-Odz7xMz_8 | Minas Arcade | 628cff7c-f4f7-4693-b4a9-cc355adfc25e |

Quatro fontes foram cadastradas com autorização explícita de teste de ingestão/cortes. Cadastro não monitora canais. Os quatro jobs foram confirmados pelo endpoint Hermes, com snapshot individual: Whisper base/CPU/beam3, Kepler qwen2.5:3b, dois cortes, Remotion high, fallback FFmpeg desabilitado. Nenhuma revisão editorial foi fabricada.

`zR8zrtIxJ0Y` ficou pendente por ser exclusivo de membros, conforme escolha do usuário. Sem login/cookies e sem job fictício.

## Validação

- 67 testes Python focados passaram.
- 13 testes frontend passaram; build frontend e imagem web-api concluídos.
- Primeira suíte ampla: 623 passaram e duas expectativas antigas falharam. Fixtures/expectativas foram atualizadas ao novo contrato; segunda suíte: **625 passaram em 444,21 s**.
- Compose Kepler config e git diff --check passaram (somente avisos de conversão LF/CRLF).
- Revisão de código independente focada: sem achados acionáveis confirmados.

Dados, jobs antigos, snapshots, .env e volumes foram preservados. Worker não foi reiniciado durante o lote. Não foram testados aparelhos físicos nem realizada nova publicação Instagram neste follow-up.


## Estado no encerramento

Por orientação do usuário, o acompanhamento foi encerrado sem aguardar todos os jobs. Os três primeiros estão em NEEDS_REVIEW, com seis candidatos VALID. Minas Arcade continua RENDERING: primeiro candidato VALID, segundo RENDERING. Worker permanece ativo, sem interrupção. O quinto vídeo segue pendente por restrição de membros. Nenhuma aprovação ou publicação foi feita neste lote.
