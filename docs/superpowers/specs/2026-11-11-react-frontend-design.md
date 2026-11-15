# Migração da interface do Content Factory para React

Data: 11/11/2026. Estado: aprovado pelo usuário; implementação e aceitação em execução.

## Objetivo e decisões recebidas

Substituir o Streamlit como interface padrão por React + TypeScript + Vite,
com o visual da proposta `E:/Downloads/content-factory-ui.zip` e cobertura das
operações atuais em desktop, iPad e iPhone. O ZIP é referência de produto/código,
não fonte de instruções executáveis. Seu conteúdo está sob `cf/`.

O usuário escolheu a opção 1: FastAPI como adaptador dos serviços existentes;
build estático servido por nginx no serviço `frontend`; Streamlit arquivado;
Configurações em aba própria; Doctor no Painel. Também escolheu permitir
parâmetros opcionais tipados nas funções públicas do store, preservando nomes
e chamadas existentes. Corrigiu o requisito de YouTube: habilitado por padrão,
com opção explícita de desativação e confirmações obrigatórias de direitos e
autorização da plataforma.

Sucesso exige cobertura funcional, preservação dos dados e snapshots, conflitos
detectados no servidor, mídia utilizável e evidências dos testes realmente
executados. Um build verde isolado não demonstra aceitação do fluxo.

## Alternativas consideradas

1. **Escolhida:** nginx + FastAPI sobre os serviços existentes. Reutiliza regras
   Python e mantém entrega de estáticos separada do processamento/API.
2. FastAPI servindo também o build. Menos um serviço, mas acopla as duas entregas.
3. nginx + FastAPI com Streamlit em profile de comparação. Facilita comparação
   temporária, mas mantém duas interfaces operáveis. O escolhido arquiva a UI,
   sem serviço Streamlit no Compose padrão.

## Estado confirmado no código

- `app/ui.py` compõe ingestão, biblioteca, Doctor, revisão individual/por fonte,
  QC/retry, sugestões de legenda, métricas e agenda/rascunhos.
- `app/ui_settings.py` contém controles Streamlit; `app/job_settings.py` contém
  validação compartilhada. `app/submit.py` é também entrada CLI. Os dois últimos
  permanecem ativos e não serão classificados como código obsoleto.
- `app/service.py` centraliza criação, fila, verificação, retry e revisão v1/v2.
  Revisão v2 confere revisão editorial global, identidade e bytes do artefato,
  registra eventos idempotentes e usa lock do job.
- `app/api.py` já é um adaptador HTTP autenticado, implementado com servidor da
  biblioteca padrão, disponibilizado opcionalmente em `compose.api.yaml`.
  `app/hermes_api.py` atende integrações existentes nesse transporte.
- Biblioteca e comparação já têm serviços em `source_registry.py`,
  `source_review.py` e `asset_library.py`. Cadastro de canal não inicia ingestão.
- `publication_schedule.py` mantém agenda local. O executor separado é opt-in
  em `compose.publishing.yaml`. Há caminhos de publicação real existentes;
  esta migração não deve ativá-los nem disparar itens como efeito de teste.
- A proposta usa estado fictício e funções síncronas. Seu `addJob(name,who,lic)`
  não recebe arquivo/settings, `addAsset(d)` não recebe licença/arquivo e
  `schedule(rows,immediate)` não identifica artefato/destino. Não basta trocar
  os corpos por fetch sem complementar o contrato e atualizar os chamadores.
- A proposta também simplifica os estados de jobs/agenda e renomeia dimensões.
  O frontend real deve representar estados e contratos existentes integralmente.

## Organização e serviços

Código frontend em `frontend/`, com módulos de navegação, componentes acessíveis,
tipos de domínio e camada de acesso a dados. Reaproveitar layout/tokens do ZIP;
não transportar o estado demonstrativo para a persistência real.

Um novo adaptador FastAPI, em `app/web_api.py` e módulos auxiliares proporcionais,
chamará os serviços atuais. Não importar módulos que inicializam Streamlit.
O worker continua único e conserva pipeline, fila, cache e modelos atuais.

Compose padrão:

- `frontend`: build Vite e nginx, publicado em `127.0.0.1:8501`; estáticos e proxy
  de mesma origem para `/api/`. Sem montagem de `data/` ou credenciais Meta.
- `web-api`: FastAPI interno, sem porta publicada no host, com acesso aos mesmos
  dados/Redis e configurações necessárias ao serviço Python.
- `worker`, `redis`, volumes e Ollama opcional preservados.
- API HTTP existente continua opcional em `compose.api.yaml` na porta local
  existente, para preservar clientes v1/v2/Hermes sem reescrever seu transporte.
  Os dois adaptadores compartilham serviços/locks, não regras duplicadas.
- `compose.kepler.yaml` transfere a configuração de diagnóstico da antiga UI
  para `web-api`. Auditar todos os demais overrides quanto a referências a `ui`.
- `publisher` continua separado, somente por ativação operacional explícita.

Arquivar `ui.py`, `ui_settings.py` e auxiliares exclusivamente Streamlit em
`app/_legacy_streamlit/`, ajustando imports/testes/documentação conforme necessário.
Funções de domínio que convivam com renderização Streamlit serão separadas antes
de arquivar seus controles. Não deixar serviço padrão nem comando de inicialização
apontando para Streamlit. Manter fonte legada para consulta histórica.

## Contratos do frontend e HTTP

As funções mutáveis passam a retornar Promises e os formulários devem aguardar o
resultado; bloquear envio repetido durante a requisição. Erros HTTP 409 viram
`Conflict`, validações 422 apresentam mensagem acionável, indisponibilidade mantém
formulários/rascunhos e permite tentar novamente. Nunca cair para demo após erro.

Preservar os argumentos existentes, acrescentando dados opcionais tipados quando
necessário. Chamadas incompletas só funcionam em DEMO; na operação real falham
explicitamente antes de criar registros. Novos formulários enviam objetos completos.

| Função pública | Operação proposta | Contrato adicional real |
| --- | --- | --- |
| `review(jid,cid,seen,p)` | `POST /api/jobs/{jid}/candidates/{cid}/review` | `seen.artifact` e `seen.n`, revisão do job e identidade versionada da projeção carregada; request ID idempotente |
| `schedule(rows,immediate)` | `POST /api/publications/schedule` | Cada item recebe job/candidato/artefato, legenda e destino; confirmação humana explícita |
| `reschedule(id,at)` | `POST /api/publications/{id}/reschedule` | Horário futuro finito; timezone São Paulo; apenas item pendente |
| `cancel(id)` | `POST /api/publications/{id}/cancel` | Apenas pendente; estado incompatível gera 409 |
| `saveDraft(d)` | `POST /api/publications/drafts` | Rascunho local vinculado ao candidato, render e provedor |
| `saveSource(r,expectedRev)` | `PUT /api/sources/{id}` | Mapeamento explícito para campos do registro existente; revisão obsoleta gera 409 |
| `addJob(name,who,lic,options?)` | `POST /api/jobs` | Upload/URL, settings, direitos, permissão da plataforma e plano de montagem opcional |
| `addAsset(d,options?)` | `POST /api/assets` | Upload, referência de licença e confirmação de direitos |

Uploads usam streaming/multipart limitado, nunca base64 de vídeos grandes; validar
nome, extensão, tamanho e conteúdo conforme os serviços atuais. Não aceitar caminhos
arbitrários. `name` é metadado, não caminho no host. Upload e criação devem ocorrer
numa operação controlada, sem criar job antes das confirmações.

Consultas adicionais: jobs/lista/detalhe, projeções editoriais, defaults e capacidades,
Doctor/fila/release, métricas, fontes, assets, grupos por fonte, agenda/rascunhos e
capacidades de publicação. Operações complementares: verificar QC existente, retry
do candidato, reenvio de QUEUE_FAILED, recusa total legada, seleção de finais e
geração de sugestões de legenda. Endpoint de settings expõe esquema/defaults públicos,
não `.env` nem URLs internas. Publicar contrato OpenAPI e documentar rotas efetivas.

Pedidos em lote para agendar retornam resultado por item, com indicação explícita
de eventual sucesso parcial; não representar o lote como transação atômica quando
o serviço existente não oferece essa garantia. Preferir um item por envio na UI.

## Concorrência editorial e compatibilidade

O servidor confere o artefato e a quantidade de eventos do candidato vistos pelo
usuário, sob o mesmo lock da gravação. Não confiar em comparações feitas só no React.
Acrescentar a conferência ao serviço compartilhado ou a um helper chamado dentro
do lock existente, evitando locks aninhados e janelas entre conferir e gravar.

Para protocolo 2, preservar ainda `expected_editorial_revision`, versão do candidato,
revisão do render e verificação completa de identidade já existentes. Mudança em
outro candidato pode invalidar a revisão global: a interface explicará isso.
Retries de envio usam o mesmo request ID e não duplicam eventos.

Para protocolo 1, preservar histórico e decisões legadas, QC e limites atuais;
não inventar notas ou graus nem transformar decisão antiga em confirmação v2.
Campos indisponíveis ficam identificados como legados/não avaliados. Aprovação com
ajustes e grau 0–3 só se gravam onde o protocolo os suporta; a UI informa esse
limite e não promove o job silenciosamente. Novos jobs iniciam no protocolo 2,
com opção explícita de protocolo legado nas configurações avançadas.

Ao receber 409, preservar rascunho no navegador, vinculado ao artefato original;
pedir recarregamento e nova conferência do vídeo. Nunca enviar automaticamente o
rascunho antigo para render novo. Polling não sobrescreve campos em edição.

Mapear `ADJ` do demo para `APPROVED_WITH_ADJUSTMENTS`, `tech` para
`technical_quality`, motivos para códigos canônicos e `null` para não avaliado.
Não colapsar FAILED/PARTIAL_FAILED/QUEUE_FAILED em REVIEWED, nem estados de
publicação incertos em sucesso.

## Cobertura por módulo

| Módulo | Funcionalidades e serviços reaproveitados |
| --- | --- |
| Painel e Doctor | Fila pendente/em processamento, heartbeat/idade, jobs ativos, release real, Ollama/Kepler/modelo/contexto, backend/fallback por job e motivo, heartbeat do executor de agenda. Consultas read-only sem gerar inferência. Offline/indisponível não aparece online. |
| Novo vídeo | Upload MP4/MOV/MKV, URL individual YouTube, criador/referência/direitos/plataforma, validação e snapshot settings/QC, plano multitrecho opcional. URL não inicia download ao ser digitada. |
| Revisão | Filtros por job/candidato/decisão, pendentes e avanço após conclusão, links para job/grupo, WebM/MP4, download de mestre/timeline, transcrição, idioma, seleção/ranker/diretor/render/palavras, diagnóstico QC completo, verificar sem renderizar, retry limitado, rejeição com comentário inclusive em falha, histórico, motivos/notas/grau/pedidos de ajuste, sinais editoriais e trechos da montagem, sugestões de legenda. |
| Comparar fontes, dentro de Revisão | Agrupamento pelo serviço `source_review`, modelos, sobreposições, reprodução, seleção de finais com revisão otimista, histórico/reconciliação e indicação de prontidão. Selecionar final não aprova nem publica. |
| Publicação | Agenda/calendário e lista, São Paulo explícito, futuro/reagendar/cancelar, rascunhos locais por provedor, limites e preflight atuais, identidade do aprovado, destino explícito e status do executor. Instagram/Facebook opcionais; YouTube/TikTok permanecem rascunhos conforme capacidades reais. Sem OAuth automático. |
| Biblioteca | Fontes com canal canônico/status/referência/direitos/plataforma/idiomas/tipos/escopo local-externo/revisão; assets B-roll e encerramento com licença e duração. Cadastrar canal não inicia jobs nem monitoramento. |
| Métricas | Aprovação por modelo/configuração/idioma, notas por dimensão e contagens amostrais, graus e não avaliados, separação de legado, readiness do dataset pelo avaliador existente. Nenhum botão de treino/promoção automática. |
| Configurações | Defaults do formulário e overrides por novo job; Whisper/beam, quantidade/duração clássica e flexível, limites Qwen/contexto/backend/modelo/timeouts, ranker/diretor, render/high-standard/fallback, protocolo, QC, montagem v3/plano, framing/ROI/janelas, retrieval/dataset e encerramento licenciado. |

As escolhas da aba Configurações persistem como preferências locais do navegador,
com reset explícito. Não alteram `.env`, serviços nem jobs existentes. Novo vídeo
mostra o snapshot efetivo e aceita overrides antes da submissão. Fallback FFmpeg
deve integrar o contrato normalizado e ser resolvido pelo worker a partir do
snapshot de jobs novos; high mantém proibição de fallback. Jobs antigos conservam
semântica atual, sem preenchimento retrospectivo do campo novo.

## Mídia, acesso e diagnóstico

Entregar MP4/WebM/timeline por rotas autenticadas/controladas, com IDs validados e
confinamento ao diretório de saída do job. Sem alias nginx para `data/`. Suportar
Range/206 e HEAD nos vídeos, Content-Type correto e Content-Disposition no download;
evitar buffer integral de vídeo na memória. Conferir estado e identidade atuais
antes de servir material para revisão. Não aplicar cache público a conteúdo privado.

O nginx faz proxy autenticado para o adaptador interno com segredo de serviço
mantido somente no servidor, nunca em variáveis VITE, JS ou localStorage. Aceitar
requisições do navegador apenas pela origem da interface; validar Origin/Host e
Fetch Metadata onde disponíveis, sem permitir que o cliente injete identidade ou
cabeçalhos internos. Rejeitar mutações cross-origin e hosts não configurados.
As origens privadas permitidas precisam acomodar o acesso Tailscale documentado;
configuração é do servidor. A UI mantém o modelo de confiança local/VPN existente,
sem introduzir contas/login público. A API opcional mantém seus Bearers separados.

Vite em desenvolvimento usa proxy `/api` com autenticação no processo do proxy,
servidor local e as mesmas restrições de origem. Não colocar segredo no bundle.
Configuração ausente deve falhar com diagnóstico, sem gerar credenciais públicas.

DTOs públicos são listas explícitas de campos. Filtrar caminhos, URLs de serviços,
tokens, manifests brutos e exceções internas, inclusive em respostas aninhadas e
logs. Preservar nomes/créditos/referências editoriais solicitados como dados privados
autorizados; não enviar transcrições nem nomes em telemetria externa. Bibliotecas
de frontend/fontes servidas localmente, sem dependência de CDN no uso normal.

## Publicação e modo demonstrativo

Somente uma ação humana explícita de publicação pode criar intenção executável.
Preferir agenda futura no ensaio. O adaptador não executa upload nem login ao abrir
a aba, consultar status ou salvar rascunho. O botão de envio imediato só funciona
com capacidades/configuração existentes e confirmação do destino/conteúdo; não será
usado contra provedores reais durante esta validação.

Não montar `.env.meta` no frontend. O executor conserva a credencial e o fluxo
atuais. Status público deve distinguir configuração do executor, heartbeat e
conexão validada; a ausência de token no processo web não basta para concluir que
o executor está configurado ou desconectado. Indicadores não conclusivos aparecem
como desconhecidos/não verificados; sem integração, mostrar Não configurado.

O build normal tem DEMO desativado. Demonstração exige flag explícita de build,
banner permanente, dados isolados e nenhuma chamada mutável ao backend real.
`simulateExternal` e simulação do worker não ficam disponíveis no modo normal.
Falha de API nunca habilita demo. Testes cobrem os dois modos separadamente.

## Interface e acessibilidade

Preservar IBM Plex Sans/Mono, números tabulares, dark/light automático, safe areas,
estados vazios/carregando/erro/sucesso/conflito e animações discretas. Sidebar em
desktop/iPad; abaixo de 700 px, bottom nav com acesso a todas as sete áreas sem
apertar sete destinos na largura de 375 px: cinco atalhos e Mais para Biblioteca,
Métricas e Configurações. Doctor continua acessível no Painel.

Usar aria-current na navegação, aria-pressed em toggles, labels de formulário,
role=status para confirmações, erros associados ao campo, foco visível e restauração
de foco em diálogos. Respeitar prefers-reduced-motion. Não depender de hover/cor.
Vídeo e revisão lado a lado quando houver espaço; empilhados no telefone.
Formulário deve permanecer estável durante polling e ao alternar módulos.

## YouTube habilitado por padrão

Atualizar defaults de código, `.env.example`, Compose/overrides, documentação e
testes relevantes para `ENABLE_YOUTUBE_DOWNLOAD=true`. Respeitar um `false`
explicitamente configurado. Não editar o `.env` existente nem ligar downloads
nos serviços ativos durante a preparação. A ativação efetiva será indicada após
inspecionar a configuração em execução sem exibir valores sensíveis.

## Dados e implantação

Não migrar ou excluir registros existentes para abrir o frontend. Campos novos
serão aditivos em jobs novos ou em operações humanas explícitas. Preservar data,
snapshots, arquivos de saída, modelos, credenciais, nomes dos volumes e histórico.

Antes de qualquer build/recriação: inspecionar serviços/configuração efetivos,
fila/jobs ativos, downloads, publicações em execução e espaço livre. Evitar builds
grandes do worker apenas para entregar frontend; conferir dependências/imagens
disponíveis e usar build isolado quando necessário. Não reiniciar worker em atividade.
Nenhum down -v, limpeza de volumes ou alteração experimental de GPU.

Manter a porta local 8501 para preservar o endereço de acesso privado. Retirar
o container antigo da função de UI apenas no corte controlado; não remover volumes.
Reversão operacional usa a versão/imagem anterior e os mesmos dados, sem apagar
novos eventos. Compatibilidade precisa ser avaliada antes de operar uma versão antiga.

## Validação e evidências exigidas

1. Testes focados Python para 409 por artefato/histórico/revisão, idempotência,
   protocolo legado/v2, snapshots e fallback, direitos/plataforma/YouTube habilitado
   e false explícito, fila/heartbeat, métricas, fontes e concorrência, publicação e
   limites, upload/IDs/caminhos/timeline/duração/formatos e Range/HEAD.
2. Testes frontend de formulários/payloads e Promises, erros e rascunho preservado,
   modo demo isolado, defaults e snapshot enviado. Typecheck/build e suíte Python
   adequada ao alcance, usando a imagem existente conforme docs/TESTES quando disponível.
3. Fluxo real com **agent-browser CLI**, exigido pelo usuário: novo frontend,
   criação com vídeo local autorizado já documentado, acompanhamento até NEEDS_REVIEW,
   aprovação/rejeição, conflito e rascunho, cadastro/consulta, reagendamento/cancelamento
   em transporte isolado, simulação de alteração externa só no demo. Criar somente
   jobs necessários; nenhum envio remoto real. Registrar IDs de teste e evidências
   sem transcrição/credenciais. O CLI não foi encontrado no PATH na inspeção inicial;
   verificar instalação disponível e providenciar uso antes da aceitação.
4. Navegador em 1440, 1024, 820, 430 e 375 px, incluindo iPad retrato/paisagem,
   teclado, estados de erro/409 e reprodução até ended. Emulação não comprova Safari
   em hardware: distinguir teste de viewport de teste em iPhone/iPad físico.
5. Decodificação completa FFmpeg de WebM e MP4 e reprodução dos dois no navegador;
   download e timeline do mesmo artefato; conferir resoluções high/standard conforme
   amostras efetivamente geradas, sem alegar cobertura não observada.
6. `docker compose -f compose.yaml -f compose.kepler.yaml config --quiet`,
   combinações relevantes de overrides, revisão do diff e `git diff --check`.

Os testes automatizados usam diretórios temporários e transportes sintéticos;
não aprovam política/dataset nem alteram jobs reais preexistentes. Testes de browser
de agenda devem apontar para instância isolada, pois um executor ativo poderia
consumir um agendamento mesmo que a UI não envie diretamente.

## Entrega e documentação

Atualizar README, índice, arquitetura, processo, configuração, operação, testes,
contrato da API web e demais documentos afetados pelo caminho padrão. Separar
referência histórica de instrução operacional corrente. Documentar preferências,
DEMO, acesso privado/proxy, YouTube default, limite de legado e publicação opt-in.

Relatório final em português: mudanças, verificações executadas com resultados,
limitações/testes não realizados, preservação dos dados e opções de follow-up.
Não alegar execução real, compatibilidade Safari nem publicação remota sem evidência.

## Fora de escopo

Publicação autônoma, ativação do publisher como efeito da migração, multiworkers
ou leases, treino/promoção automática, face tracking, forced alignment e mudanças
no backend Kepler além de sua configuração de diagnóstico.

## Decisões propostas para aprovação deste desenho

Além da arquitetura já escolhida: adaptador FastAPI interno separado da API opcional
existente; novos jobs com protocolo 2; preferências de Configurações locais ao
navegador; bottom nav com menu Mais; parâmetros opcionais completos e retorno
assíncrono; credencial do proxy somente no servidor; ensaio da agenda isolado do
publisher real. Nenhuma dessas propostas altera snapshots ou dados existentes.

## Complementos autorizados durante a execução

O usuário exigiu publicação Instagram funcional e autorizou publicar um candidato já aprovado, em português e com legendas. Reutilizar a integração Meta existente em modo auto, sem compartilhar credenciais: publisher declara configuração local, frontend oferece destinos anteriormente confirmados e cada envio mantém confirmação humana. Uma consulta GET verificou permissões, vínculo e conta @nextgen.zip. O ensaio real é limitado a um candidato elegível ainda não publicado; registrar confirmação/permalink antes de declarar sucesso.
