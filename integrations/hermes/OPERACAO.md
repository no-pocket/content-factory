# Hermes / nopocket-content

Pacote do perfil: `nopocket-content/SOUL.md` e `nopocket-content/skills/content-editorial/`.
A skill usa Python padrão, sem instalar bibliotecas ou modelos.

Instalado e validado por SSH em 08/11/2026. Perfil em
`/srv/nopocket/data/hermes/profiles/nopocket-content`, tópico
[nopocket-content](https://t.me/c/4410866638/1687), roteado pelo gateway existente.
Personalidade e skill próprias; modelo/provedor existente, sem duplicar OAuth.
O gateway confirmou o perfil servido e Telegram conectado após reload sem turnos ativos.

Ponte privada: tarefa Windows `Content Factory Hermes Private API`, iniciada no login
do Machado, mantém SSH reverso para loopback do Pi18510→workstation8510. Credencial
Hermes distinta e ator autorizado configurados somente em ambientes secretos.
Reconexão configurada; reboot/logout não foram testados fisicamente.
Cliente remoto consultou19 fontes e baixou MP4 com SHA conferido. Teste real do agente,
somente leitura, terminou com exit0 e identificou Qwen/DeepSeek/Hermes na fonte correta.
Não foram criadas avaliações, notas ou seleções artificiais.
## Instalação com o host disponível

1. Pelo SSH existente, ler `hermes --version`, `hermes profile --help`, diretório
   efetivo HERMES_HOME, serviço gateway e configuração de perfis/tópicos atuais.
   Não imprimir tokens, auth.json ou conteúdo integral de .env. Confirmar que a
   versão instalada suporta o mesmo padrão usado pelos outros tópicos do dono.
2. Fazer backup privado dos arquivos que serão alterados. Criar `nopocket-content`
   pelo mecanismo nativo suportado, sem clonar canais/tokens nem banco de sessões.
   Usar o provedor já autorizado do Hermes sem duplicar refresh tokens OAuth.
3. Instalar SOUL.md apenas no novo perfil e a pasta content-editorial no diretório
   de skills efetivamente descoberto desse perfil. Preservar os outros SOULs/skills.
4. Criar/vincular o tópico nopocket-content no bot atual com o mecanismo de roteamento
   já usado no gateway. Não iniciar outro getUpdates/webhook com o mesmo token.
   Confirmar autorização apenas do Telegram owner que será atribuído pela ponte.
5. Configurar canal privado Pi→workstation para API8510, por túnel SSH autenticado
   limitado a loopback ou endereço privado já protegido. Não publicar8510 na LAN/Internet.
   A UI deve usar CONTENT_FACTORY_PUBLIC_URL com URL privada acessível no celular,
   nunca localhost do Pi. Não enviar token em querystring ou no chat.
6. Gerar credencial própria para CONTENT_FACTORY_HERMES_TOKEN (mínimo24 caracteres,
   diferente de CONTENT_FACTORY_API_TOKEN), armazenada só nos ambientes secretos da
   API e do novo perfil. Configurar CONTENT_FACTORY_HERMES_ACTOR_ID com ID Telegram
   confirmado do dono; não inferir identidade de transcrição ou texto recebido.
   No perfil: CONTENT_FACTORY_HERMES_URL aponta para a entrada privada/túnel.
7. Validar `cf_editorial.py groups`, leitura de uma rodada real e do candidato, e
   abertura do link privado. Fazer escrita apenas em fixture isolada ou após uma
   instrução editorial real do dono. Confirmar identidade do perfil no tópico e
   envio de uma prévia autorizada; download local não é evidência de entrega Telegram.

## API e contratos

Apenas `/v2/hermes/*` aceita a credencial Hermes. Credenciais iguais fazem ambas
as superfícies falharem fechadas (503); credencial curta/ausente não ativa a ponte.
A API geral conserva sua credencial própria e contratos existentes.

- GET `groups`, `groups/<source:id>`: fontes, modelos, candidatos e seleção.
- POST `ingest`: URL autorizada com fonte ativa; preserva o ID YouTube e deduplica.
  A resposta confirma o job persistido; falha de conexão não confirma criação.
- GET `jobs/<job>`: status e handoff com grupo, modelo solicitado/resolvido,
  referência da transcrição, candidatos e referências autenticadas de render.
  Só iniciar revisão editorial quando `pipeline.ready=true`; enquanto houver
  `pipeline.missing`, aguardar ou diagnosticar a falha indicada em `pipeline.next`.
  Fontes sem escopo externo não expõem esse conteúdo ao Hermes.
- POST `jobs/<job>/reprocess`: `{owner_message,reprocess:{request_id,expected_run_id}}`.
  Só aceita FAILED sem candidatos e fonte com acesso externo vigente. Mantém o
  snapshot, entrada, transcrição e histórico; reconcilia fila atomicamente.
  `expected_run_id` vem de `latest_run_id` do status. Repetir request_id/conteúdo
  recupera resposta perdida; nunca inicia outra tentativa após uma nova falha.
  ID com conteúdo diferente ou execução desatualizada retorna 409. Enquanto o
  worker não confirmar o encerramento da execução, também é preciso aguardar (409).
  Candidatos existentes usam retry individual; ajustes editoriais não são aplicados por retry.
  `status` também expõe diagnóstico seguro `failure` e `reprocess_available`,
  sem mensagens arbitrárias de exceção, caminhos ou conteúdo de prompts.
- GET `jobs/<job>/candidates/<candidate>`: texto/revisão/identidade/link e comentários.
- GET `jobs/<job>/transcript`: transcrição da fonte, limitada a 4 MiB e sujeita ao escopo externo da fonte.
- POST `jobs/<job>/candidates/<candidate>/captions`: salva sugestão editorial Hermes para Instagram ou Facebook, com instrução do proprietário, request_id e identidade do artefato. Não aprova nem publica; reenvios idênticos são idempotentes.
- GET `jobs/<job>/candidates/<candidate>/media?artifact_id=sha256:...`: MP4 privado,
  identidade/QC atuais, até50MB; cliente valida SHA e não segue redirecionamento.
- POST `.../notes`: `{owner_message,note:{request_id,expected_artifact_id}}`.
  Comentário literal sem decisão/rating/seleção. Visível na UI e preservado por render.
  `source_message:{chat_id,thread_id,message_id,sent_at}` é opcional; preserva IDs e
  horário original ISO8601 com fuso, distinto do horário de gravação. Um artefato
  histórico conhecido pode receber nota sem alterar o render atual. A leitura
  separa `notes` atuais de `historical_notes`.
- POST `.../reviews`: `{owner_message,review:<contrato v2 existente>}`. Guarda
  comentário literal e atribui ator Telegram configurado; não inventa notas.
  Recusa sem classificação usa `rejection_domain: UNSPECIFIED`. Nova decisão
  explícita pode substituir avaliação anterior do mesmo artefato; o histórico
  anterior permanece. Uma avaliação existente nunca deduplica mensagem nova.
- POST `.../deliveries`: `{delivery:{artifact_id,master_sha256,chat_id,thread_id,
  message_id}}`, somente após aceite real do gateway. A identidade e SHA do
  mestre devem corresponder ao render registrado. O vínculo é persistido em
  `data/telegram-deliveries/`; o mesmo chat/mensagem não pode ser reassociado.
  Campo opcional `sent_media:{width,height,duration,supports_streaming}` registra
  somente os metadados confirmados pelo aceite Telegram: dimensões inteiras
  1..8192, duração inteira 1..86400 segundos e streaming booleano. Sem evidência
  do aceite, mantenha `sent_media:null`; não derive esse campo do ffprobe. Assim,
  divergências entre geometria do arquivo e do aceite permanecem diagnosticáveis.
- GET `deliveries/<chat_id>/<message_id>` resolve o vídeo realmente entregue.
  A leitura do candidato inclui `deliveries` e `delivery_media` com largura,
  altura, duração e suporte a streaming medidos no MP4. Quando os metadados não
  forem verificáveis, use o link privado e diagnostique `delivery_media_error`;
  não invente largura/altura nem confunda SHA idêntico com prova de sincronia.
- POST `groups/<id>/selection`: `{owner_message,selection:{request_id,
  expected_revision,selected:[identidades completas]}}`. Zero/um/vários finais;
  render/rodada alterados exigem nova conferência. Não aprova nem publica.

Toda ação tem request_id UUID idempotente. Reutilizar ID com outro conteúdo é conflito.
Grupos mantêm histórico próprio em data/source-review.json. Comentários sem decisão
ficam em editorial_notes no job; não viram rótulos de ML. Decisões v2 anteriores continuam
em feedback_events. Mesclar grupos previamente selecionados pede reconciliação explícita.

A interface abre comparação por fonte; `?group=...` abre rodada e `?job=UUID` abre
revisão individual. Nenhum grupo é unido por título, idioma ou similaridade textual.

Se o Pi retornar `URLError`, verificar a tarefa Windows existente
`Content Factory Hermes Private API` e o túnel privado antes de repetir ingestão.
Confirmar conectividade autenticada e consultar o ID do vídeo para evitar duplicação.
Não imprimir tokens nem reiniciar o worker durante processamento.

### Planejamento editorial assíncrono

O código da integração oferece `editorial_planner=hermes_first` por job. A API
do Telegram e a interface web aceitam `CONTENT_FACTORY_HERMES_EDITORIAL_DEFAULT=true`
para aplicar esse padrão apenas a novos jobs; o padrão da configuração é `false`.
Na interface, URLs de canais registrados passam pela ingestão autorizada e
congelam o cadastro da fonte; uploads e URLs sem cadastro não concedem acesso
externo e seguem a política local ou falham se o fallback estiver desativado.
Para canais registrados isso também vale no modo local: cadastro desativado,
idioma não autorizado ou metadados insuficientes bloqueiam a ingestão, em vez
de contornar a política pelo formulário manual. Montagem manual requer a escolha
explícita de planejamento local.
Uma escolha explícita `local` prevalece e jobs existentes mantêm seu snapshot.
A transcrição só é entregue ao planejador quando o snapshot e o cadastro atual
autorizam `external`. Fallback local depende da política salva e da autorização
local vigente. Um plano válido sem candidatos é resultado editorial e não inicia
fallback; uma nova análise depende de ação explícita.

Uma nova rodada explicitamente solicitada pelo tópico usa `editorial-attempt`
com instrução literal e UUID idempotente. O job filho é reservado ao ator do
tópico antes de entrar na fila; o executor automático não o lista nem pode
adquirir sua lease. A reserva expira após duas horas e não ativa fallback local.
O tópico deve adquirir a lease, iniciar a geração e enviar o plano versionado.

Após iniciar uma geração, o executor pode registrar uma falha técnica pela rota
privada `editorial-failure`, protegida pela lease e pela credencial editorial.
Os códigos distinguem, por exemplo, prazo excedido, saída grande, resposta
incompleta, JSON inválido e executor indisponível. O recibo pode ser reenviado
sem iniciar outra geração; a política do job decide se o worker tenta o modelo
local. A falha não guarda o prompt ou a resposta bruta nos logs operacionais.

O executor usa uma credencial distinta `CONTENT_FACTORY_EDITORIAL_TOKEN`,
restrita às rotas de solicitações editoriais. Credenciais Content Factory não
são repassadas ao processo do modelo; o executor ainda roda com as permissões do
usuário do Pi e não constitui isolamento de sistema operacional. O modelo é invocado em perfil temporário privado com
toolset limitado; o perfil e o banco temporário são removidos na saída normal.
Interrupção abrupta pode deixar um diretório `.cf-editorial-invocation-*` com
dados sensíveis: verifique processos e origem antes da remoção. A retenção pelo
provedor externo é independente dessa limpeza. O serviço de exemplo acompanha o
repositório, mas sua presença não indica que esteja instalado ou ativo.

Documentação oficial consultada em07/11/2026: [perfis](https://hermes-agent.nousresearch.com/docs/user-guide/profiles),
[Telegram/tópicos](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram),
[skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/).
Os detalhes da instalação efetiva têm precedência sobre exemplos atuais do upstream.

Entrega real confirmada: uma prévia de5.244.486bytes enviada ao tópico1687, mensagem1688, aceite BotAPI com tamanho igual. A legenda informa REJECTED/QCWARNING existentes e não registra aprovação/seleção. Recibos privados em operations/nopocket-content-install-report-20261108.json e nopocket-content-telegram-delivery-20261108.json no Pi.
