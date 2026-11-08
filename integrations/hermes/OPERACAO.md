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
- GET `jobs/<job>/candidates/<candidate>`: texto/revisão/identidade/link e comentários.
- GET `jobs/<job>/candidates/<candidate>/media?artifact_id=sha256:...`: MP4 privado,
  identidade/QC atuais, até50MB; cliente valida SHA e não segue redirecionamento.
- POST `.../notes`: `{owner_message,note:{request_id,expected_artifact_id}}`.
  Comentário literal sem decisão/rating/seleção. Visível na UI e preservado por render.
- POST `.../reviews`: `{owner_message,review:<contrato v2 existente>}`. Guarda
  comentário literal e atribui ator Telegram configurado; não inventa notas.
- POST `groups/<id>/selection`: `{owner_message,selection:{request_id,
  expected_revision,selected:[identidades completas]}}`. Zero/um/vários finais;
  render/rodada alterados exigem nova conferência. Não aprova nem publica.

Toda ação tem request_id UUID idempotente. Reutilizar ID com outro conteúdo é conflito.
Grupos mantêm histórico próprio em data/source-review.json. Comentários sem decisão
ficam em editorial_notes no job; não viram rótulos de ML. Decisões v2 anteriores continuam
em feedback_events. Mesclar grupos previamente selecionados pede reconciliação explícita.

A interface abre comparação por fonte; `?group=...` abre rodada e `?job=UUID` abre
revisão individual. Nenhum grupo é unido por título, idioma ou similaridade textual.

Documentação oficial consultada em07/11/2026: [perfis](https://hermes-agent.nousresearch.com/docs/user-guide/profiles),
[Telegram/tópicos](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram),
[skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/).
Os detalhes da instalação efetiva têm precedência sobre exemplos atuais do upstream.

Entrega real confirmada: uma prévia de5.244.486bytes enviada ao tópico1687, mensagem1688, aceite BotAPI com tamanho igual. A legenda informa REJECTED/QCWARNING existentes e não registra aprovação/seleção. Recibos privados em operations/nopocket-content-install-report-20261108.json e nopocket-content-telegram-delivery-20261108.json no Pi.
