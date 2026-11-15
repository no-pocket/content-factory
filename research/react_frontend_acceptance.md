# Aceitação React / FastAPI — 11/11/2026

## Entrega

Interface React/TypeScript/Vite servida por nginx em `http://localhost:8501`,
com Painel/Doctor, Novo vídeo, Revisão individual/comparação de fontes,
Publicação, Biblioteca, Métricas e Configurações. API interna FastAPI sobre os
serviços existentes; API opcional de integrações mantida. Streamlit arquivado
em `app/_legacy_streamlit/`, container antigo parado e serviço padrão removido.

YouTube habilitado por padrão, respeitando false explícito e as confirmações
de direitos/plataforma. Settings/QC dos jobs novos são snapshots; preferências
do navegador não alteram registros existentes. Revisão mantém identidade,
histórico, revisão global, receipts v2 e HTTP 409. Formulários permanecem
montados ao alternar módulos; rascunhos de revisão também sobrevivem na sessão.

Nenhum dado, snapshot, modelo, `.env`, credencial ou volume preexistente foi
apagado. Foram acrescentados um job autorizado de aceitação e uma publicação
real especificamente autorizada pelo usuário. QA usa dados/volumes separados.
Worker e publisher foram reiniciados somente após conferir ausência de trabalho
em andamento, para carregar as mudanças necessárias. Não houve build do worker,
download de modelo, alteração de GPU, remoção de órfãos ou limpeza de volumes.

## Verificações observadas

| Verificação | Resultado |
| --- | --- |
| Suíte Python completa em imagem web-api, rede bloqueada e DATA_DIR temporário | **623 passed**, 363,75 s |
| Frontend Vitest | **8 passed** |
| TypeScript + Vite build | Passou; build normal sem módulo demo e fontes servidas localmente |
| Renderer `tsc --noEmit` | Passou após instalar as dependências do lock com `npm ci --ignore-scripts` |
| Compose base + Kepler | Passou com `config --quiet` |
| Overrides API/publicação, GPU/Ollama GPU e QA | Passaram com `config --quiet` |
| `git diff --check` e revisão do diff | Passaram |
| Revisão independente | Uma revisão; corrigidos consentimento por artefato, identidade sob lock e retenção de formulários |

Os testes cobrem snapshots/fallback, ingestão e permissões, fila/heartbeat,
legados/v2, conflitos de revisão e cadastro, métricas, caminhos/IDs,
timeline/duração/formatos, Range/HEAD, limites e ciclo da agenda. Falhas
intermediárias dos testes legados decorrentes da mudança de pasta/import foram
corrigidas antes da suíte definitiva. O typecheck local do renderer inicialmente
não encontrou tsc; a instalação determinística resolveu isso, sem mudar o lock.

## Navegador: agent-browser CLI 0.42.0

- Viewports 1440×1000, 1024×768, 820×1180, 430×932 e 375×667: sem
  transbordamento horizontal. Sidebar nos três primeiros, bottom nav nos dois
  últimos; Configurações acessível pelo menu Mais no telefone.
- Retenção de formulário Novo vídeo ao alternar para Configurações e voltar:
  valor preservado. Confirmação da publicação e seu link também apareceram na
  agenda React em 375 px, sem transbordamento.
- Job `0b7bf3b8-f83f-4de2-ba30-4ef57fe3b240` criado pela UI com o vídeo local
  autorizado indicado em TESTES.md, Whisper tiny já em cache, beam 1, dois cortes,
  heurística, Remotion/high. Chegou a NEEDS_REVIEW com dois candidatos VALID.
- Ambos os WebM e ambos os MP4 chegaram a `ended`, sem erro de mídia; os quatro
  arquivos passaram por decodificação FFmpeg completa. Prévia high: 720×1280.
  Aprovação e recusa persistiram. A mudança da revisão global bloqueou o outro
  formulário, preservando seu comentário até conferência explícita.
- Instância `content-factory-web-qa`, porta 8502, sem publisher/worker: intenção
  futura criada, reagendamento aceito e cancelamento confirmado. Os testes
  automatizados também conferiram mudança de timestamp e recusa de passado/
  estado incompatível. Nenhum item de QA ficou disponível ao publisher real.
- Biblioteca em QA: fonte pendente cadastrada e asset sintético licenciado de
  2,1 s enviado pela UI. A quantidade de jobs permaneceu em 1: cadastrar não inicia
  processamento. O vídeo sintético foi criado localmente, sem mídia de terceiros.
- DEMO explícito em porta 8503: simulação externa bloqueou a revisão e manteve
  o rascunho. Performance Resource Timing registrou **zero chamadas `/api/`**.

## Instagram real autorizado

O usuário autorizou um teste com candidato aprovado, português e legendado.
Foi escolhido um candidato ainda não publicado:

- Job `af0c5e4a-1419-4683-b23a-2e683915ad1f`.
- Candidato `a87e8733-ae7a-5205-8d3b-a8ce90176b08`, decisão APPROVED e artefato
  intacto; QC completo e preflight Instagram passaram. Prévia reproduzida até
  ended: 42,888 s. Timeline contém 131 palavras de legendas em português.
- Permissões instagram_basic, instagram_content_publish e pages_read_engagement
  confirmadas por GET oficial; vínculo da conta **@nextgen.zip** confirmado.
- Preparação, seleção do destino existente, legenda, consentimento e confirmação
  de envio imediato feitos na nova UI. Intenção
  `5c46b7ad-76ec-4656-bc8d-7bb45cb85df5` chegou a **PUBLISHED**, sem erro.
- [Reel confirmado pela Meta](https://www.instagram.com/reel/Dfmv8_CCY4c/).
  Consulta remota confirmou VIDEO/REELS e permalink. O usuário editou a legenda
  depois da publicação e confirmou essa edição; ela foi preservada.

A integração existente é reutilizada em modo `CONTENT_FACTORY_META_ENABLED=auto`:
o publisher declara disponibilidade de credenciais sem compartilhá-las com a UI.
False explícito desabilita envio web. Cada envio exige seleção/consentimento,
aprovação limpa v2, QC e identidade atuais; aprovar um candidato não publica.
Operação realizada com a skill content-publish; tokens nunca foram exibidos.

## Limitações e continuidade

Não foram testados Safari nem iPhone/iPad físicos. Os cinco tamanhos foram
emulados em Chromium. Não houve novo download real do YouTube: permissões e
default/false explícito foram verificados automaticamente. O job novo cobriu
Remotion/high; standard/FFmpeg têm cobertura sintética na suíte, sem outro job
real desnecessário. O Facebook não recebeu publicação real nesta migração;
YouTube/TikTok continuam rascunhos conforme as capacidades existentes.

As imagens web/Frontend foram construídas; os serviços de produção permanecem
ativos. QA e demo são parados ao encerrar, preservando dados e volumes. Alterações
ficam na branch `codex/react-frontend`, sem commit/push/merge automático.
Próximas opções: validar Safari em aparelhos físicos ou revisar/consolidar a branch.
