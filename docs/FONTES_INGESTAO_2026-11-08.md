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

Implantação observada: API recriada e worker reiniciado com fila0/0, UI preservada. Gameplayrj cadastrado pending/rev1 sem comprovação ou confirmações inventadas. Cliente remoto sources e agente Hermes real retornaram o canal correto e pendência (exit0). Browser de produção conferiu fonte e comentários existentes. Os39JSONs de jobs ficaram idênticos e12eventosv2 preservados. Nenhum job/download desse vídeo foi iniciado.

## Aceitação real após confirmação do proprietário

Machado confirmou em08/11/2026 a permissão para editar/reutilizar Gameplayrj e processar
pelo Hermes. A fonte está active/rev2; a declaração e o escopo ficam no registro privado.
O vídeo g8Q1UxPJulc criou somente o job af0c5e4a-1419-4683-b23a-2e683915ad1f; repetir a
URL curta retornou duplicate=true e o mesmo job, sem nova entrada.

A execução revelou timestamps numpy do Whisper que eram válidos no JSON mas falhavam
na validação nativa em memória. Correção converte e valida na fronteira ASR sem relaxar
os contratos;47 testes focados passaram. Retomada manteve áudio/transcrição/histórico.
Também corrigidos orçamento de saída flexível (1 proposta compacta/reserva700) e
amostragem de janelas para cobrir o final da fonte;45 testes focados passaram.

Resultado observado: NEEDS_REVIEW, um candidato de0,68–43,18s, Remotion720×1280,
direção kepler_gpu/Qwen2.5 3B; MP442,867s e WebM42,888s decodificados completamente e
reproduzidos até ended no navegador. QCWARNING por silêncio28,6337–29,6587s, intervalo
idêntico confirmado no áudio original. Seleção usou cobertura heurística: as propostas
semânticas do Qwen ainda foram rejeitadas por limite/evidência, com diagnóstico salvo.
Melhorar aderência do modelo ao contrato de propostas continua em aberto; não atribuir
essa seleção à IA nem confundir QC com qualidade editorial.

Prévia entregue uma única vez ao [tópico Telegram](https://t.me/c/4410866638/1704),
16.667.790bytes com SHA conferido e aceite BotAPI. Candidato PENDING/revisão editorial0;
nenhuma avaliação artificial. Publicação e monitoramento periódico seguem separados.

Revisão em lote entregue: formulários por candidato em fragmentos, sem enviar campos
antes da decisão. Navegador comprovou zero quadros com comentário ao digitar/avaliar,
rascunho de outro candidato preservado e salvamento completo; troca de render bloqueia
ações até recarga do vídeo.39 testes focados + teste de migração passaram; CI do código
bbcab6f passou nos dois workflows. A interface e API voltaram a responder após reinício
pontual dos serviços com falha de acesso local; dados persistidos foram preservados.
