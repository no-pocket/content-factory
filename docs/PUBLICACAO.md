# Publicação e agenda

A aba **Agenda de publicações** permite escolher um candidato aprovado, Instagram
Reels e/ou Facebook Reels, conta, legenda e envio imediato ou data/hora em
`America/Sao_Paulo`. O executor local transmite o MP4 diretamente à Meta. Um ✅
aparece apenas depois de confirmação remota; `UNCERTAIN` exige reconciliação
manual e nunca é reenviado automaticamente. O histórico inclui o ID remoto da
sessão quando disponível. A publicação continua vinculada à aprovação humana v2,
ao QC e aos hashes atuais, que são revalidados antes do envio.

Para ativar o executor nesta workstation, depois de conferir jobs e configuração:

```powershell
docker compose -f compose.yaml -f compose.kepler.yaml -f compose.publishing.yaml up -d --no-deps --no-build publisher
```

Ele usa a imagem existente, monta `./app` e `./data` e lê `.env.meta` somente
no processo de publicação. `USER_ACCESS_TOKEN` deve ser válido e ter acesso às
contas escolhidas; o Page token é obtido em memória. A interface exige os IDs
da Página e da conta Instagram, que ficam associados ao agendamento. O serviço
usa `META_GRAPH_VERSION` (padrão `v27.0`). Credenciais não são salvas nos
registros. Não expor o arquivo secreto nem montá-lo na UI.

O executor roda enquanto o serviço e a workstation estiverem ligados. Jobs
pendentes com horário vencido são processados quando o serviço volta. Uma
interrupção durante envio, processamento ou publicação é marcada `UNCERTAIN`:
consulte o ID remoto e a plataforma antes de qualquer nova tentativa. Cancele ou
altere somente agendamentos que ainda não começaram. O serviço suporta um único
executor; não usar múltiplos workers de publicação. Verifique vídeo, destino,
legenda e direitos antes de confirmar a publicação.

## Rascunhos locais

A interface também oferece Instagram Reels, Facebook Reels, YouTube e TikTok no painel
**Rascunhos de publicação**. Essa ação valida e grava um rascunho **local** em
`data/publishing/`; não conecta contas, não transmite vídeo e não publica.
`DRY_RUN` e `remote_id: null` significam exatamente isso. Essa outbox de rascunhos
é independente da agenda real; não é consumida pelo executor.

O preflight recarrega o job sob o lock existente. Exige revisão editorial v2,
decisão humana `APPROVED` do artefato atual, nenhum ajuste MAJOR/CRITICAL aberto,
QC atual aprovado e hashes atuais de MP4, WebM e timeline. Aprovação legada e
`APPROVED_WITH_ADJUSTMENTS` não qualificam. O rascunho congela candidato, versão,
render, artefato/manifesto e evento de revisão, título e descrição. Não altera o
job. Repetir o mesmo preflight retorna o mesmo registro; uma mudança cria outro.
O rascunho antigo é histórico: não constitui autorização futura de envio.
O transporte real da agenda repete os gates antes de transferir os bytes.

## Configuração dos rascunhos e outros destinos

As chaves vazias estão em `.env.example`; valores reais pertencem somente ao
ambiente secreto do processo. Não são copiados para rascunhos, planos ou jobs.
Sem todas as chaves: `NOT_CONFIGURED`. Com todas: `CONFIGURED_UNVERIFIED`.
Presença de token não comprova validade, escopo, titularidade ou conexão.
Não há consulta remota implícita ao abrir a interface.

| Destino | Configuração futura necessária |
| --- | --- |
| Instagram | Para a agenda real: conta profissional vinculada à Página, permissões Meta aplicáveis e token de usuário válido. O envio real usa upload direto resumable, status do container e `media_publish`; o plano de rascunho é apenas ilustrativo. |
| Facebook | `META_FACEBOOK_PAGE_ID`, `META_FACEBOOK_PAGE_TOKEN`, `META_GRAPH_VERSION`; OAuth e Page token com permissões aplicáveis, incluindo `pages_manage_posts`. Plano usa sessão `video_reels`, upload, processamento e finalização `DRAFT`. Não publica em perfil pessoal. |
| YouTube | `YOUTUBE_CHANNEL_ID`, `YOUTUBE_ACCESS_TOKEN`; projeto com Data API e OAuth `youtube.upload` do canal. Inicialização resumível seguida de PUT. Plano fixa `privacyStatus: private` e não notifica inscritos. Verificar quotas e requisitos atuais de conta/projeto antes de habilitar envio. |
| TikTok | `TIKTOK_OPEN_ID`, `TIKTOK_ACCESS_TOKEN`; app Content Posting e OAuth `video.publish`. Antes do init, consultar e exibir `creator_info`, opções de privacidade e limite de duração; obter escolha explícita/consentimento. Clientes sem auditoria têm restrição privada. App/auditoria pode ser recusado; uma ferramenta interna não deve presumir elegibilidade. |

`app/publishing_adapters.py` contém os planos de rascunho de cada protocolo,
sem cabeçalhos de autenticação ou URLs executáveis de upload. Campos entre
`<...>` dependem da resposta real do provedor. TikTok não inventa privacidade nem
tamanho dos chunks sem verificar as regras e a conta. Os planos não são clientes
HTTP completos. O transporte real de Instagram e Facebook usa módulos separados;
OAuth interativo, renovação automática, YouTube e TikTok reais e sincronização com
as agendas das plataformas permanecem para etapas futuras.

Credenciais de rascunho não comprovam acesso. A publicação real requer a agenda,
o executor ativo e credenciais Meta válidas no arquivo secreto.

## Fontes oficiais consultadas em 07/11/2026

- [Instagram Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/).
  O acesso automatizado retornou HTTP 429 nesta sessão; confirmar a referência
  da versão Graph escolhida antes de implementar transporte real.
  [Coleção oficial Meta Instagram](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
  e [exemplo oficial de container Reels via Facebook Login](https://www.postman.com/meta/instagram/request/5kkpkh6/upload-a-reel-to-an-ig-container)
  também consultados; o login Facebook exige outros escopos e host.
- [Facebook Reels: coleção oficial Meta](https://www.postman.com/meta/facebook/documentation/r56bjfd/facebook-api),
  [iniciar Reel](https://www.postman.com/meta/facebook/request/rgkn91u/1-create-reel).
- [YouTube: uploads resumíveis](https://developers.google.com/youtube/data/guides/using_resumable_upload_protocol),
  [videos.insert e escopos](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert).
- [TikTok Direct Post](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post),
  [diretrizes e auditoria](https://developers.tiktok.com/docs/en/content-sharing-guidelines),
  [upload para inbox, que exige conclusão no aplicativo](https://developers.tiktok.com/docs/en/content-posting-api-reference-upload-video).

Validação: `tests/test_publishing.py` usa arquivos sintéticos e rede bloqueada;
testa rejeição sem aprovação, render alterado, legado/ajustes, outbox idempotente,
ausência de segredos e planos distintos. Não é evidência de integração ao vivo
ou de aprovação por qualquer plataforma.
