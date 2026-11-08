# Rascunhos de publicação

A interface oferece Instagram Reels, Facebook Reels, YouTube e TikTok no painel
**Publicação**. A ação disponível valida e grava um rascunho **local** em
`data/publishing/`; não conecta contas, não transmite vídeo e não publica.
`DRY_RUN` e `remote_id: null` significam exatamente isso. Não existe worker
consumindo esta outbox, agendamento nem botão de publicação real nesta etapa.

O preflight recarrega o job sob o lock existente. Exige revisão editorial v2,
decisão humana `APPROVED` do artefato atual, nenhum ajuste MAJOR/CRITICAL aberto,
QC atual aprovado e hashes atuais de MP4, WebM e timeline. Aprovação legada e
`APPROVED_WITH_ADJUSTMENTS` não qualificam. O rascunho congela candidato, versão,
render, artefato/manifesto e evento de revisão, título e descrição. Não altera o
job. Repetir o mesmo preflight retorna o mesmo registro; uma mudança cria outro.
O rascunho antigo é histórico: não constitui autorização futura de envio.
Qualquer futura implementação de transporte precisará repetir os gates antes de
transferir os bytes e obter consentimento explícito para aquele destino.

## Configuração e próximos passos

As chaves vazias estão em `.env.example`; valores reais pertencem somente ao
ambiente secreto do processo. Não são copiados para rascunhos, planos ou jobs.
Sem todas as chaves: `NOT_CONFIGURED`. Com todas: `CONFIGURED_UNVERIFIED`.
Presença de token não comprova validade, escopo, titularidade ou conexão.
Não há consulta remota implícita ao abrir a interface.

| Destino | Configuração futura necessária |
| --- | --- |
| Instagram | `META_INSTAGRAM_ACCOUNT_ID`, `META_INSTAGRAM_ACCESS_TOKEN`, `META_GRAPH_VERSION`; conta profissional, Instagram Login e permissões `instagram_business_basic`/`instagram_business_content_publish`. Plano usa container Reels com URL pública autorizada, status de processamento e `media_publish`. Hospedagem não provisionada: disponibilizar mídia publicamente exigiria autorização específica. |
| Facebook | `META_FACEBOOK_PAGE_ID`, `META_FACEBOOK_PAGE_TOKEN`, `META_GRAPH_VERSION`; OAuth e Page token com permissões aplicáveis, incluindo `pages_manage_posts`. Plano usa sessão `video_reels`, upload, processamento e finalização `DRAFT`. Não publica em perfil pessoal. |
| YouTube | `YOUTUBE_CHANNEL_ID`, `YOUTUBE_ACCESS_TOKEN`; projeto com Data API e OAuth `youtube.upload` do canal. Inicialização resumível seguida de PUT. Plano fixa `privacyStatus: private` e não notifica inscritos. Verificar quotas e requisitos atuais de conta/projeto antes de habilitar envio. |
| TikTok | `TIKTOK_OPEN_ID`, `TIKTOK_ACCESS_TOKEN`; app Content Posting e OAuth `video.publish`. Antes do init, consultar e exibir `creator_info`, opções de privacidade e limite de duração; obter escolha explícita/consentimento. Clientes sem auditoria têm restrição privada. App/auditoria pode ser recusado; uma ferramenta interna não deve presumir elegibilidade. |

`app/publishing_adapters.py` contém os planos específicos de cada protocolo,
sem cabeçalhos de autenticação ou URLs executáveis de upload. Campos entre
`<...>` dependem da resposta real do provedor. TikTok não inventa privacidade nem
tamanho dos chunks sem verificar as regras e a conta. Os planos não são clientes
HTTP completos. Transportes, OAuth com renovação, validação de hosts de upload,
retentativas sem duplicação, acompanhamento remoto e consentimento de publicação
permanecem para a próxima etapa, após configurar e validar as contas.

Opções atuais: preparar e inspecionar o rascunho local; ou configurar primeiro
as contas de desenvolvimento de cada plataforma. Credenciais não habilitam
publicação nesta versão.

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
