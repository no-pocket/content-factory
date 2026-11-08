# Fontes autorizadas e importação pelo Hermes — 08/11/2026

O cliente não recebia as variáveis personalizadas no processo do gateway. A correção
lê apenas as três configurações Content Factory do arquivo seguro adjacente ao próprio
perfil, sem consultar ambiente global/cwd ou exportar segredos. Passou com o ambiente
exato do gateway e em chamada real do Hermes via terminal, sem sourcing manual.
A tarefa de túnel privado agora tenta reconexão a cada15 segundos.

Canais ficam em data/sources.json, distintos dos grupos editoriais de vídeos já
processados. Cadastro local/admin registra ID canônico, nome, situação, referência de
autorização, confirmações de direitos/plataforma e políticas de idioma, tipo e escopo
local/externo. Hermes lê resumos, sem evidência privada de autorização; não pode ativar
fontes pela sua credencial limitada. Cadastros começam pendentes.

O cliente oferece sources, ingest e status. Importação explícita confirma metadados
reais do vídeo/canal, valida a fonte ativa e políticas, deduplica o ID do vídeo e salva
proveniência no primeiro JSON antes da fila. Retry recupera QUEUED/QUEUE_FAILED por
verificação Redis atômica sem duplicação. Worker verifica revogação antes de processar
mídia em cache; downloader verifica identidade/política antes dos bytes. Novos imports
Hermes usam revisão v2 e duração flexível8/40/180; snapshots antigos são preservados.

Material de fontes novas sem permissão externa não é exposto ao Hermes por candidato,
grupo, mídia, comentário ou review. A política atual e o snapshot são verificados.
Escopo external permite revisão Hermes; geração automática de plano externo a partir
da URL ainda não existe e é rejeitada antes de criar job. O import local existente
continua usando os modelos suportados pela aplicação.

Verificação real somente de metadados: g8Q1UxPJulc pertence a Gameplayrj,
UCJAbkIY17zAmCTNQHH0bQoQ,365s,pt. O ID informado inicialmente tinha27 caracteres e não
era canônico. Nenhum download ou job desse vídeo foi executado: a referência/escopo
da autorização foi solicitada ao proprietário e permanece pendente.

Validação:456 testes passaram em134,73s no Docker existente, rede desativada, código
somente leitura e temporários isolados emE:. Revisões independentes resolveram o
orphan de fila, a evidência privada nos resumos e o segundo cadastro no formulário.
Não há monitoramento periódico ativado nem publicação social automática. Monitoramento
contínuo fica para etapa própria depois de validar uma importação autorizada.
Browser agent-browser isolado: dois cadastros pendentes consecutivos, recusa de ativação sem referência/confirmações, edição e ativação exclusivamente sintética persistiram; ambas áreas editoriais renderizaram sem erro. Nenhum acesso YouTube ou job real no ensaio.
