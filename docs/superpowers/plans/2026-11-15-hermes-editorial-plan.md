# Plano de implementação — curadoria editorial Hermes

> Documento para revisão do Hermes e do proprietário. Não autoriza publicação, reprocessamento real ou alterações na instalação por si só.

**Objetivo:** usar o Hermes como primeira escolha editorial para novos jobs elegíveis, com transcrição e execução locais, fallback local explícito e revisão humana dos resultados.

**Arquitetura:** o Content Factory persiste a solicitação editorial e libera seu único worker. Um cliente do perfil Hermes busca solicitações autorizadas, analisa a transcrição e devolve um plano versionado. O Content Factory valida a resposta, retoma a fila e gera seus próprios artefatos; Telegram é canal de interação, não transporte obrigatório nem fila de estado.

**Tecnologia:** Python, Redis, arquivos atômicos sob `data/`, API Hermes existente, React, Whisper, FFmpeg/Remotion. Referências: `docs/ARCHITECTURE.md`, `docs/PROCESSO.md`, `integrations/hermes/OPERACAO.md` e o contrato proposto pelo Hermes na conversa de 15/11/2026.

## Escopo e estado atual

- O job `5da20658` recebeu resposta local encerrada por limite de saída; o diagnóstico melhorado está implantado. O estado antigo permanece histórico.
- Existem validação de montagem `app/assembly.py`, timelines, QC, artefatos versionados e modo externo para replay. Não existe solicitação editorial assíncrona operacional nem importação geral de propostas do Hermes.
- Há alteração **local, não implantada** em `app/queueing.py`, `app/worker.py` e `tests/test_queueing.py` que preserva `WAITING_EDITORIAL_PLAN` na recuperação. Revisar e incorporar; não confundir com implementação completa.
- O primeiro incremento aceita zero ou mais propostas de **um trecho contínuo por candidato** e direção declarativa limitada. Múltiplos segmentos, mídias novas e efeitos adicionais ficam para incremento posterior; o fluxo já existente de assembly não deve ser reescrito.
- A K4200 não é motor de render integrado: não prometer NVENC. Manter FFmpeg/Remotion, WebM e MP4; `high` não admite fallback simplificado de render.

## Regras de produto

1. Novos jobs elegíveis iniciados pela UI ou Hermes recebem snapshot `editorial_planner=hermes_first`; a mudança não reescreve jobs antigos nem modifica seus retries. Manter escolha explícita local para novas entradas. A habilitação como padrão só acontece após os testes e aceite operacional abaixo.
2. A transcrição só é disponibilizada externamente quando o snapshot **e** o registro atual da fonte autorizam o escopo `external`. Sem autorização, não enviar dados; usar política local configurada e registrar `source_scope_forbids_external`.
3. `no_suitable_candidates` com justificativa válida é resultado editorial, não erro técnico e não aciona fallback. Estado proposto `EDITORIAL_NO_CANDIDATES`, visível como resultado para revisão, sem candidatos, aprovação ou publicação. Permitir ao usuário iniciar nova tentativa explícita com nova identidade de solicitação.
4. Falha técnica, expiração, resposta incompleta, schema inválido ou referências objetivamente inválidas acionam fallback local apenas quando o snapshot o permitir. Divergência subjetiva editorial gera sinalização; não rejeitar uma resposta apenas por discordar do modelo. Limitar a uma geração externa e uma tentativa local por tentativa editorial; repetição de transporte não é nova geração. Registrar razões.
5. Registrar separadamente `planner`, `director`, `renderer` e `qc`, incluindo motor solicitado/efetivo e motivo de fallback por tentativa. Nenhuma dessas decisões aprova ou publica.
6. Nenhum plano pode conter comando, URL ou caminho executável; referências de mídia, quando suportadas, devem apontar para `asset_id` cadastrado e autorizado. O modelo não cria metadados de direitos nem pode autorizar reordenação humana.
7. Preservar identidade, revisão, direitos, solicitações e histórico; nunca executar instruções em transcrição, imagem ou saída do modelo. Não registrar transcrição, prompts, respostas integrais, tokens, caminhos sensíveis ou mídia em logs operacionais ou Git. IDs, hashes e códigos mínimos podem ser registrados com acesso e retenção definidos.

## Fluxo e identidades

```text
URL autorizada → download/fingerprint → Whisper/transcrição + hash
→ solicitação persistida → WAITING_EDITORIAL_PLAN + liberar worker
→ Hermes busca solicitação autorizada e envia resposta idempotente
→ validação objetiva → propostas / zero cortes / fallback técnico
→ worker retoma → timeline validada → MP4 + WebM → QC → revisão humana
```

Cada solicitação congela `request_id` UUID, `editorial_attempt_id`, `job_id`, `run_id`, SHA-256 da fonte, digest e versão de canonização da transcrição, duração, idioma, política e limites do snapshot, versão do protocolo, criação e expiração. O identificador da execução não muda durante espera e retomada. Uma nova análise explicitamente solicitada após o resultado cria um novo `editorial_attempt_id` e `request_id` no mesmo `job_id` e um novo `run_id` de processamento, ligado ao anterior; o histórico nunca é sobrescrito. Repetição de transporte preserva as identidades e os bytes da submissão.

A API fornece a transcrição apenas a cliente autenticado e autorizado para a solicitação, mediante autorização atual e do snapshot. A credencial existente não comprova isolamento de permissões: criar e testar escopo editorial mínimo, distinto dos poderes de avaliação/publicação. Não imprimir credenciais; manter a ponte em loopback/túnel privado. O proxy Hermes observado aceita qualquer bearer token: **não expô-lo diretamente** nem tratar esse token como autenticação. Preferir cliente Hermes que faz polling na API autenticada; limites de frequência e expiração devem ser configuráveis e finitos.

### Identidade canônica e âncoras

O código atual calcula `source_fingerprint` como SHA-256 do arquivo, **64 caracteres hexadecimais minúsculos sem prefixo**; o identificador de artefato usa formato diferente. Manter esse formato de fonte no contrato v1 e verificar os bytes antes do render. A tolerância de um frame serve somente para comparar duração declarada e medida; jamais permite `source_out_ms` exceder a fonte. Intervalos são `[in, out)`; a conversão para frames deve usar o relógio existente do executor e ser testada nas bordas.

O digest de transcrição v1 é `sha256:` mais o hexadecimal produzido por `app.artifacts.digest` sobre o objeto congelado inteiro `{language, segments}`: JSON UTF-8 com `sort_keys=True`, `ensure_ascii=False`, separadores `(',', ':')`, `allow_nan=False`, sem normalização Unicode adicional. Array e ordem dos segmentos/palavras, textos e timestamps nativos fazem parte da identidade; alterações de metadados nesse objeto também alteram o digest. Fixar fixtures de bytes Unicode, números e ordem; versionar como `cf-transcript-v1`. Não sobrescrever sidecars antigos nem presumir que esse cálculo já forneça IDs de segmento.

Os IDs v1 são `seg-` mais índice decimal de seis dígitos (base zero) na ordem do array congelado; sua unicidade é relativa ao digest e não depende do timestamp, que pode se repetir ou sobrepor. A API apresenta o índice/ID junto com a transcrição sem modificar seu arquivo. Uma âncora deve nomear um ID existente e conter citação não vazia dentro desse único segmento. A correspondência aplica apenas Unicode NFC, normalização de espaços consecutivos e remoção de espaços nas extremidades; preserva pontuação e letras maiúsculas/minúsculas, sem fuzzy matching ou citação entre segmentos. O trecho temporal do segmento da âncora deve intersectar o intervalo proposto; a posição exata da palavra não é inferida.

### Processo de planejamento e máquina de estados

Um serviço supervisionado no Pi, dedicado ao perfil `nopocket-content`, consulta a API e invoca um único processo Hermes não interativo por lease. Ele usa perfil explícito, concorrência inicial 1, orçamento de tempo e tamanho limitados e backoff; não depende de sessão Telegram nem recebe permissões para aprovar, publicar ou administrar fontes. A execução e instalação desse serviço não são autorizadas por este documento. Antes de ativá-lo, medir `--format stream-json`/`--query-file`, extração de resposta e metadados efetivos, limites e tempos com amostras curtas, longas e ruidosas. Verificar isolamento e retenção real dos arquivos de sessão, prompts e provedor; documentar e aplicar política explícita antes do tráfego real. A autorização `external` deve cobrir processamento pelo provedor, não apenas exibição.

Estado durável da tentativa editorial, separado do estado de exibição do job:

| Estado | Transição vencedora sob lock do job | Resultado |
| --- | --- | --- |
| `REQUESTED` | cliente obtém claim ou expira | `CLAIMED` ou `EXPIRED` |
| `CLAIMED` | submissão válida/inválida, expiração, revogação ou cancelamento | `ACCEPTED`, `NO_CANDIDATES`, `INVALID`, `EXPIRED`, `REVOKED` ou `CANCELLED` |
| `ACCEPTED` | intenção de retomada persistida e reconciliada | job volta à fila uma vez |
| `NO_CANDIDATES` | nenhuma transição automática para fallback | job `EDITORIAL_NO_CANDIDATES` |
| `EXPIRED` ou `INVALID` | snapshot permite fallback e direitos ainda permitem processamento local | uma intenção de fallback persistida e reconciliada |
| `REVOKED` ou `CANCELLED` | nenhuma resposta/render futuro autorizado | bloquear, registrar motivo e não iniciar fallback automaticamente |

Enquanto a solicitação estiver em `REQUESTED`/`CLAIMED`, o job permanece `WAITING_EDITORIAL_PLAN`, com run preservado e worker livre. Claim inclui token aleatório, `lease_version` monotônica, prazo e ator. Renovação é limitada ao prazo total da solicitação. Antes de invocar o provedor, registrar `generation_started` duravelmente sob lock, validando lease e autorização. Se a lease vencer antes desse registro, outro cliente pode assumir; após o registro, não iniciar outra geração na mesma tentativa: recuperar resposta já persistida ou registrar resultado desconhecido/falha técnica e aplicar fallback permitido. Não há garantia de exatamente uma chamada se o processo cair entre gravar a intenção e chamar o provedor. Nova geração exige nova tentativa explicitamente autorizada. Resposta, expiração, revogação e cancelamento competem sob o mesmo lock/fence; apenas uma vence. A autorização é revalidada imediatamente antes da leitura e do envio ao provedor quando possível, e novamente antes de aceitar e renderizar; registrar hora e base dessa verificação. Uma transcrição já enviada não pode ser recuperada do provedor por revogação posterior.

Cada resposta inclui `submission_id` UUID distinto do `request_id`; o backend calcula digest canônico do payload. A primeira aceitação exige lease atual, estado, prazo, direitos e hashes válidos. Consulta ou replay de recibo persistido autentica o mesmo ator e verifica `submission_id` e digest, sem exigir lease ativa ou modificar o resultado; após revogação, retorna apenas recibo mínimo, sem plano ou transcrição. Mesmo ID com digest diferente e nova submissão após decisão aceita retornam conflito. O recibo não prova publicação nem qualidade editorial. Plano inválido não dispara segunda geração externa silenciosa: registra `INVALID` e, somente se configurado, inicia uma tentativa local. Reconciliação baseada em intenção durável precisa cobrir gravação antes de `WAITING`, `WAITING` antes do ACK, aceite/fallback antes de enqueue e entrega duplicada após enqueue; testar que não há nova execução, render duplicado ou perda. O lock existente é entre processos; provar a interação com o worker e arquivos/Redis em testes de falha, sem pressupor transação distribuída.

### Contrato mínimo proposto para revisão

Arquivo a criar: `contracts/editorial-plan-v1.schema.json`; validador runtime em `app/editorial_plan.py`. Um envelope por solicitação, limitado a 256 KiB; strings editoriais até 1.000 caracteres e no máximo seis propostas. Os campos obrigatórios são:

```json
{
  "schema_version": "1.0", "request_id": "UUID", "submission_id": "UUID", "editorial_attempt_id": "UUID", "job_id": "UUID", "run_id": "UUID",
  "source": {"source_fingerprint": "64 caracteres hexadecimais", "duration_ms": 200040},
  "transcript": {"digest": "sha256:...", "canonicalization": "cf-transcript-v1", "language": "pt", "timebase": "source_ms"},
  "planner": {"engine": "hermes", "provider": "metadado do executor", "model": "metadado do executor", "prompt_version": "versão", "invocation_id": "identidade observável"},
  "outcome": "candidates_proposed",
  "candidates": [{"proposal_id": "UUID", "editorial_title": "Título", "intent": "Justificativa",
    "segments": [{"source_in_ms": 0, "source_out_ms": 56480,
      "start_anchor": {"segment_id": "seg-000000", "quote": "fala literal"},
      "end_anchor": {"segment_id": "seg-000008", "quote": "no Brasil. Em breve, teremos."},
      "boundary_status": "requires_audio_review"}],
    "direction": {"layout_preset_id": "preset suportado", "subtitle_preset_id": "preset suportado", "pacing": "natural", "word_highlight": "only_if_word_timing_reliable"},
    "risks": [{"type": "boundary", "detail": "Conferir áudio"}]}]
}
```

`no_suitable_candidates` exige `candidates: []` e `reason` não vazia; `candidates_proposed` exige 1–6 candidatos. UUIDs canônicos e únicos, tempos inteiros não booleanos, `0 <= in < out <= duration_ms`, duração dentro do snapshot, âncoras e citações reais no segmento informado. Não proibir sobreposição entre candidatos alternativos por padrão. Rejeitar campos desconhecidos, versões não suportadas, IDs vazios, texto excessivo, referências divergentes e instruções não suportadas. Em v1, rejeitar múltiplos segmentos ou assets/overlays não vazios com erro explícito; não descartá-los silenciosamente. `requires_audio_review` permite preview e master com WARNING, mas não comprova a borda; impedir liberação/aprovação até ação humana explícita, com job, candidato e versão, render_revision, artifact_id, trecho/borda, ator e horário. Confirmar borda não aprova editorialmente. Alteração/re-render invalida a confirmação. A âncora final corresponde ao índice 8 no arquivo atual; confirmar de novo contra o objeto congelado e digest da fixture antes de usá-la em testes.

Texto literal no exemplo é apenas ilustrativo, não prova de áudio. O backend anuncia capacidades de presets versionadas e aceita apenas valores realmente implementados. Provider, modelo e invocation ID são coletados pelo executor confiável, não autodeclarados pelo texto gerado; quando não verificáveis registrar `UNKNOWN` e sinalizar, sem rejeitar automaticamente um plano válido. Word highlight só quando os timestamps nativos passarem pelos critérios existentes; caso contrário usar legenda por frase e registrar motivo.

## Tarefas e critérios de aceitação

### 1. Contrato e validação objetiva

**Arquivos:** criar `contracts/editorial-plan-v1.schema.json`, `app/editorial_plan.py`, `tests/test_editorial_plan.py`; consultar `app/assembly.py`, `app/timeline.py` e `app/artifacts.py`.

- [ ] Limitar os bytes HTTP a 256 KiB antes de ler/interpretar; parser JSON estrito rejeita chaves duplicadas e JSON inválido. Testar separadamente transporte, parser e função pura que recebe o dict.
- [ ] Escrever testes que falhem para envelopes válidos de zero e múltiplos candidatos, limites de duração, UUID duplicado, `bool` como tempo, âncora/citação inexistente, hash alterado, campo extra e payload acima do limite.
- [ ] Implementar `validate_editorial_plan(plan: dict, request: dict, transcript: dict) -> dict`, com validação estrutural e semântica, sem I/O nem efeitos. Retornar cópia normalizada e erros objetivos estáveis; nunca retornar código executável ou caminhos.
- [ ] Executar testes focados e testes de assembly/timeline; provar que `no_suitable_candidates` é aceito sem invocar fallback.

### 2. Solicitação durável e recuperação

**Arquivos:** `app/worker.py`, `app/queueing.py`, `app/store.py`, `app/job_settings.py`; testes em `tests/test_queueing.py`, `tests/test_editorial_requests.py`.

- [ ] Adicionar snapshot de política com padrão compatível para jobs antigos e opção `hermes_first` para novos, com fallback e prazo explícitos. Não reinterpretar o conjunto atual de modos `external` como esse novo fluxo.
- [ ] Ao terminar ASR, salvar hash, identidade, run e solicitação antes de gravar `WAITING_EDITORIAL_PLAN`; confirmar item da fila após persistência. Em reinício, preservar espera e nunca criar outra execução ou solicitação para o mesmo `run_id`.
- [ ] Testar falhas antes/depois da gravação e do ACK, Redis indisponível, worker reiniciado, duplicação de entrada e solicitação vencida. Política de expiração deve ser um evento persistido e limitada a uma transição sob lock; preservar estado sem acesso externo quando a autorização for revogada.
- [ ] O trabalho preliminar local em `WAITING` precisa ser revalidado junto com esse ciclo completo; `WAITING` não é estado terminal de produto.

### 3. Ponte Hermes e aceitação idempotente

**Arquivos:** `app/hermes_api.py`, `app/service.py`, `integrations/hermes/nopocket-content/skills/content-editorial/scripts/cf_editorial.py`, contrato API v2 e testes Hermes.

- [ ] Propor `GET /v2/hermes/editorial-requests` para solicitações elegíveis, `GET /v2/hermes/jobs/{id}/editorial-request` para identidade, `POST /v2/hermes/jobs/{id}/editorial-claim` e `/editorial-claim/renew` para posse e renovação, e `POST /v2/hermes/jobs/{id}/editorial-plan` para resposta. Esses nomes são proposta, não endpoints atuais. Paginar e limitar payload; autenticar, restringir permissões e revalidar escopos em cada leitura e escrita.
- [ ] Na primeira aceitação, verificar sob lock do job estado, token e versão da lease, `request_id`, `submission_id`, `editorial_attempt_id`, `run_id`, hashes e prazo; gravar resposta e intenção de retomada antes de enfileirar. Replay do recibo aceito segue a regra independente de lease acima. Conteúdo diferente, resposta nova tardia ou execução divergente retorna conflito. Usar reconciliação idempotente para a lacuna entre arquivo e Redis, sem presumir atomicidade distribuída; testar resposta perdida, colisões, expiração concorrente, revogação e escrita concorrente.
- [ ] Em `no_suitable_candidates`, persistir justificativa e estado proposto; sem chamada local ou render. Em erro técnico/plano inválido, registrar erro objetivo e aplicar política de fallback do snapshot; nunca converter um plano válido para fallback por gosto editorial.
- [ ] Diferenciar resposta incompleta, timeout/processo encerrado, schema inválido, falha de comunicação e falha interna do validador. Falha interna não é atribuída ao modelo. Testar geração iniciada com lease expirada, recibo após expiração/revogação e colisão de digest.
- [ ] O cliente Hermes usa leitura autenticada e polling limitado; não depende de mensagem Telegram. Testes sem rede real verificam respostas, backoff, limites e ausência de segredos.

### 4. Adaptador para render existente

**Arquivos:** `app/editorial_plan.py`, `app/worker.py`, `app/candidates.py`, `app/timeline.py`; testes em `tests/test_editorial_plan_render.py` e testes existentes de QC.

- [ ] Converter proposta validada em candidato com texto reconstituído da transcrição, direção permitida e identidade/proveniência; não aceitar texto ou caminho do modelo como fonte de legenda. Revalidar fonte, autorização e hash antes do render; novos artefatos seguem a versão e o QC existentes.
- [ ] Aplicar limites de duração e evidências objetivas. Se validações narrativas atuais recusarem uma proposta válida por critério subjetivo, tratá-la como sinalização para revisão, sem alterar silenciosamente sua intenção e sem acionar fallback local.
- [ ] Testar um trecho sintético inspirado no caso 5da20658 com ressalva atravessando a borda, preservação de `requires_audio_review`, fallback de legenda por frase quando não houver alinhamento confiável, plano alterado antes do render, falha de render `high`, MP4/WebM e revisão humana separada. Dados reais exigem autorização e retenção apropriada mesmo que sanitizados; não publicar.

### 5. Observabilidade, interface e documentação

**Arquivos:** `app/web_views.py`, `frontend/src/Review.tsx`, `frontend/src/types.ts`, `integrations/hermes/OPERACAO.md`, `docs/PROCESSO.md`, `docs/CONFIGURACAO.md`, `docs/API_WEB.md`.

- [ ] Exibir espera, prazo, resultado sem candidatos, erro objetivo e opção de nova tentativa explicitamente autorizada. Apresentar motores, fallback e motivo por etapa; preservar distinção de proposta, QC, aprovação, seleção e publicação.
- [ ] Guardar latência, código normalizado, metadados confiáveis do executor e hashes do pedido/resposta, sem logar conteúdo integral, tokens ou caminhos sensíveis. Quando modelo ou provedor efetivo não puder ser verificado, registrar `UNKNOWN` com aviso; não afirmar que Hermes é um modelo único.
- [ ] Definir documentação de operação/retomada, retenção e política padrão, direitos, permissões e limitações; incluir acesso via celular e condições de fallback. Exercitar pelo `agent-browser` em ambiente isolado.

### 6. Aceitação e ativação gradual

- [ ] Rodar primeiro os testes focados, suíte Python descrita em `docs/TESTES.md`, testes/build frontend, typecheck do renderer, Compose config e `git diff --check`.
- [ ] Em ambiente isolado, simular plano válido, plano inválido, ausência de cortes, indisponibilidade, expiração, revogação de direitos, duplicidade, interrupções e reinício; confirmar que fallback ocorre apenas nas condições autorizadas e que nenhum envio é iniciado.
- [ ] Com uma fonte explicitamente autorizada, testar ponta a ponta: Whisper → Hermes → plano → validação → prévia/master → QC → `NEEDS_REVIEW`; conferir reprodução, áudio e legendas manualmente. Verificar também o caso zero candidatos. Não alterar nem reprocessar o job `5da20658` sem necessidade operacional específica.
- [ ] Antes de qualquer deploy: verificar worker, fila, publicação em andamento, espaço, configuração ativa e volumes. Implantar sem interrupção de jobs; validar a versão de cada processo. Só então habilitar Hermes como padrão para **novos** jobs e manter opção de reversão via configuração.

## Questões para o Hermes revisar

1. O cliente do perfil consegue buscar solicitações e produzir JSON estrito usando o modelo efetivo, sem que o tópico seja necessário como fila? Informar limites reais, latência, timeout e tratamento de resposta incompleta.
2. O envelope mínimo permite representar cortes e riscos sem inventar precisão de palavras? Quais campos de direção realmente agregam valor na primeira entrega?
3. O resultado sem candidatos deve terminar em `EDITORIAL_NO_CANDIDATES` como proposto? Como apresentar pedido explícito de nova análise sem duplicar jobs?
4. As condições objetivas de rejeição e as sinalizações de discordância editorial estão separadas corretamente? Há dados ou casos reais que precisem de uma regra diferente?
5. Quais permissões do perfil e da API são necessárias para leitura e retorno, e como evitar que transcrições de fontes sem escopo externo cheguem ao modelo?
6. Existe uma forma segura de testar uma proposta do caso `5da20658` em dados isolados, sem publicação nem alterar o job original?

## Limites do plano

O presente documento é uma proposta para revisão, não uma API implantada. Não prova qualidade editorial, fidelidade de legenda ou desempenho real. Retomada do processamento, a nova política de fallback e o Hermes como padrão continuam pendentes até implementação e validação.
