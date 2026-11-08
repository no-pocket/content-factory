# Revisão editorial e conectores — 07/11/2026

Comparação com main `463d0b9`.

- Revisar candidatos diferentes do mesmo job deixa de produzir conflito artificial. Alterações concorrentes no mesmo candidato continuam bloqueadas; há opção explícita para atualizar a revisão mantendo o rascunho.
- As métricas globais são calculadas sob demanda. O cache de apresentação não autoriza gravação: aprovação e preflight continuam verificando bytes e QC atuais sob lock.
- Notas opcionais 1–5 usam estrelas; conteúdo 0–3 distingue zero de não avaliado. Ajuda explica critérios, severidade e uso dos dados sem inventar pesos.
- Novas gerações recebem instrução de título com promessa concreta e paráfrase fiel, com validação conservadora. Candidatos existentes preservam seus títulos e arquivos.
- Fechamento autorizado opcional por job, desligado inicialmente. Identidade e licença do asset ficam congeladas na submissão e são conferidas por candidato/retry. O material do proprietário ainda precisa ser cadastrado.
- Instagram/Facebook, YouTube e TikTok têm preflight e outbox local idempotente ligados à aprovação humana do render atual. Não há OAuth nem transporte de upload/publicação nesta entrega; presença de configuração não é conta conectada.
- ML continua offline e sem treino/promoção automática. No início desta atualização havia 2 eventos humanos v2 e nenhuma nota de conteúdo. Ainda falta corpus elegível para os gates documentados (50 famílias, 150 candidatos, 30 positivos/30 negativos, 15 famílias holdout e PT/EN).

Medições somente de leitura no acervo real (39 jobs/104 candidatos): a apresentação de todos os jobs na main levou 6,3403 s; atual fria 6,7629 s e repetida 7,6478 s. O cache de 2 s não acelera varreduras que excedem essa janela. A melhoria principal é remover essa varredura de cada interação. Para um job de 3 candidatos: 0,7040 s fria, 0,2190/0,2153 s repetida. Estes valores medem chamadas Python, não latência ponta a ponta do navegador ou aprovação com decode completo.

Validação observada: teste pelo agent-browser no app completo, com dados e vídeos sintéticos isolados. Primeiro candidato aprovado com 5 estrelas e grau 0; segundo recusado mantendo comentário digitado antes da primeira gravação, sem conflito artificial. Rascunho Instagram persistido em DRY_RUN com remote_id nulo; MP4 e WebM chegaram ao fim no Edge. Nenhum feedback real foi criado pelo teste. Sem teste de conta, upload externo, celular ou adequação editorial do futuro fechamento do proprietário. A validação de títulos é deliberadamente conservadora e pode omitir paráfrases válidas; revisão humana continua necessária.

Suíte final: 385 testes passaram em 72,67 s na imagem candidata existente, com código montado somente leitura, rede bloqueada e temporários isolados em E:. Compose config e git diff --check passaram. Revisões independentes de UX/publicação e do conjunto não apontaram regressão importante adicional. Testes não demonstram qualidade editorial dos futuros títulos nem integração externa real.

Implantação: main atualizada com 4272005, UI/API/worker reiniciados com fila vazia, health da UI OK e worker ocioso. A comparação antes/depois confirmou 39 JSONs de jobs idênticos, 104 candidatos e as 2 avaliações v2 preservadas. Não houve regeneração nem avaliações artificiais nos vídeos reais.
