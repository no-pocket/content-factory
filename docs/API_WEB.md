# API da interface React

O nginx serve `frontend/dist` em `127.0.0.1:8501` e encaminha `/api/` para
`web-api:8000` (FastAPI). O token privado é gerado no volume `web_auth` e só é
lido pelo backend e pelo entrypoint nginx. Não há token em JS, VITE_* ou
localStorage. `data/` não é servida como diretório estático.

O contrato OpenAPI autenticado está em `/api/openapi.json`, acessível pela mesma
origem da UI. A API opcional de integrações (`compose.api.yaml`, porta 8510)
continua com os contratos e Bearers existentes, sem usar a credencial web.

## Rotas

| Rota | Uso |
| --- | --- |
| GET `/api/bootstrap` | Jobs/candidatos, fontes, assets, agenda, rascunhos e capacidades |
| GET `/api/settings` | Defaults, ranges, modelos, dimensões, direitos/limites de ingestão |
| GET `/api/jobs/{job_id}` | Job e projeção editorial atual |
| POST `/api/jobs` | JSON para YouTube; multipart `metadata` JSON + `file` para upload |
| POST `/api/jobs/{job_id}/retry-editorial` | Nova análise explícita de resultado editorial sem candidatos, com `request_id` e `expected_run_id` |
| POST `/api/jobs/{job_id}/candidates/{candidate_id}/confirm-boundary` | Confirmação humana do início e final do render identificado por `artifact`; não aprova o candidato |
| POST `/api/youtube/metadata` | `{source_url}` individual: título, criador, ID canônico e duração públicos; não cria job |
| POST `/api/jobs/{job_id}/candidates/{candidate_id}/review` | `{seen:{artifact,n,revision},p:{dec,comment,reasons,adjust,rating,grade},request_id}` |
| GET/HEAD `/api/jobs/{job_id}/candidates/{candidate_id}/media/{kind}` | MP4/WebM/timeline; `artifact` congela identidade; `download=true` para baixar; vídeos aceitam Range |
| POST `/api/jobs/{job_id}/verify` | QC completo de MP4/WebM existentes, sem renderizar |
| POST `/api/jobs/{job_id}/retry-enqueue` | Reenvio de QUEUE_FAILED |
| POST `/api/jobs/{job_id}/reject` | Recusa total legada com `reason` |
| POST `/api/jobs/{job_id}/candidates/{candidate_id}/retry` | Retry direcionado, respeitando limite salvo |
| POST `/api/jobs/{job_id}/candidates/{candidate_id}/captions` | Sugestões locais, com `artifact` esperado |
| POST `/api/jobs/{job_id}/candidates/{candidate_id}/frames` | Contact sheet de até 8 quadros com OCR local e classificação visual local opcional; não altera a timeline |
| POST `/api/jobs/{job_id}/candidates/{candidate_id}/edit` | Revisão humana de timeline com limites de artefato, versão, revisão editorial e `request_id`; enfileira novo render |
| PUT `/api/sources/{channel_id}` | `{r,expectedRev}`; cadastro não inicia jobs |
| POST `/api/assets` | Multipart com descrição, licença, confirmação e arquivo |
| GET `/api/groups` e `/api/groups/{group_id}` | Comparação por fonte/modelo |
| POST `/api/groups/{group_id}/finals` | Seleção de finais com revisão e identidades exatas |
| GET `/api/doctor` e `/api/metrics` | Saúde/fila/release e métricas humanas/readiness |
| POST `/api/publications/drafts` | Rascunho local vinculado ao aprovado atual |
| POST `/api/publications/schedule` | Um item completo por envio, com confirmação humana na UI |
| POST `/api/publications/{id}/reschedule` | `{at}` em milissegundos, futuro |
| POST `/api/publications/{id}/cancel` | Cancelamento somente de item pendente |

POST/PUT sem dados adicionais usa `{}`. Datas do cliente são epoch em milissegundos;
a persistência dos serviços conserva segundos e timezone America/Sao_Paulo.
Erros: 401 autenticação do proxy; 403 origem/direitos; 404 ausente; 409 conflito;
413 limite; 422 contrato inválido; 503 indisponível. Nunca há fallback para demo.

## Ingestão e settings

`metadata`: creator, video_title, license_note, rights_confirmed, platform_permission,
settings, qc_settings e assembly_plan opcional. Para URL, source_url individual.

Na ingestão YouTube, título e criador são confirmados pelos metadados públicos;
a referência da autorização continua separada e exige confirmação humana.
O ID do vídeo é persistido em `youtube_video_id`. Reenvios do mesmo vídeo
reutilizam o job existente, preservando seu snapshot de ajustes.

A preparação da publicação mostra a prévia WebM e o link do MP4 mestre.
Título e legenda recebem sugestões locais editáveis (legenda já salva ou fala
do candidato com crédito), sem inferência nem envio externo. Edições manuais
permanecem durante a atualização da tela.

O acesso HTTP privado pelo Tailscale usa UUID v4 com `getRandomValues` quando
`randomUUID` não está disponível fora de contexto seguro. Uma falha de interface
oferece recarregar ou voltar ao Painel, em vez de deixar a tela vazia.
Uploads são limitados a 2 GiB e assets a 300 MB, com spool em disco. IDs/caminhos
são resolvidos pelo backend. Settings/QC são normalizados antes da criação e
congelados no job. Novos jobs web usam protocolo 2; o protocolo 1 continua explícito.
O fallback FFmpeg de jobs web novos é salvo como `settings.render_fallback_ffmpeg`;
high o proíbe, mesmo que configurado. Jobs antigos sem esse campo preservam a
resolução anterior pela configuração de instalação.

O editor visual permite ajustar cortes v2, título, palavras das legendas e janelas
de enquadramento; timelines v3 preservam a montagem e aceitam correções de título,
legenda e enquadramento. Cada envio cria uma revisão imutável, invalida a aprovação
atual e exige nova revisão humana. A análise extrai no máximo oito quadros do trecho,
executa OCR local e, se `FRAME_VISION_MODEL` apontar para um modelo de visão instalado
no Ollama local, classifica rosto do criador, gameplay, tela/documento ou incerteza.
As imagens e transcrições não são enviadas a serviços externos. Classificação,
regiões e texto OCR são sugestões; somente a seleção explícita e o salvamento humano
alteram a timeline.

## Concorrência e mídia

`seen.artifact` e `seen.n` são o render e o tamanho do histórico ao abrir o
candidato; `revision` mantém a revisão global do protocolo. Todos são conferidos
sob o lock do serviço. Protocolo 2 mantém receipt por request_id; o mesmo pedido
repetido não duplica eventos. Alterações de outro candidato também podem invalidar
a revisão global. O navegador mantém rascunhos de sessão e exige ação explícita
para conferir a versão atual antes de reutilizá-los.

O cache de apresentação invalida quando JSON ou identidade/tamanho/mtime/ctime
de qualquer arquivo muda. Gravações de revisão verificam os bytes novamente;
cache visual não concede aprovação. Legados não ganham notas/graus inventados.

## Publicação

O web-api não lê `.env.meta`. `CONTENT_FACTORY_META_ENABLED=auto` (padrão) reconhece a configuração declarada
pelo publisher separado e reutiliza a integração existente. `false` desabilita
o envio web; `true` é override explícito de instalação. É uma declaração local de configuração, não autenticação
remota verificada. Sem isso, a UI mostra Não configurado e permite rascunhos.
YouTube/TikTok permanecem rascunhos locais conforme os adaptadores existentes.
O executor reconfirma aprovação, artefato, destino e limites antes do envio.
Uma intenção imediata também passa pelo executor; o web-api não faz upload/login.

## Desenvolvimento e demonstração

Instale as dependências web do Python e use um DATA_DIR de teste isolado. Crie
um token fora do Git e passe `CONTENT_FACTORY_WEB_TOKEN` aos processos FastAPI e
Vite; `CONTENT_FACTORY_WEB_HOSTS` deve incluir `127.0.0.1:5173`/`localhost:5173`.
Não use prefixo VITE_ para esse segredo. `CONTENT_FACTORY_WEB_API` define o alvo
do proxy Vite, padrão `http://127.0.0.1:8000`.

```powershell
python -m pip install -r requirements.txt -r requirements.web.lock
python -m uvicorn app.web_api:app --host 127.0.0.1 --port 8000 --no-access-log
# Em outro terminal com a mesma configuração privada:
npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend run dev
```

`VITE_DEMO=true` é opt-in de build/dev, com banner permanente. Dados simulados
nunca escrevem no backend; `simulateExternal` só funciona nesse modo. O build
normal não inclui o módulo demo. Não testar agenda contra publisher real.

Referências de implementação: [respostas de arquivo FastAPI](https://fastapi.tiangolo.com/reference/responses/)
e [build estático Vite](https://vite.dev/guide/build).
