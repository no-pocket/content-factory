# Upgrade e comparação editorial — 07/11/2026

Referência: `main` remota confirmada em `619efee4d799b8da4dcc16476da72374db63d2ef`.
Revisão dos candidatos na aplicação principal: <http://127.0.0.1:8501>.

## O que melhorou

- Revisão por candidato com comentário, aprovação limpa/com ajustes/recusa,
  histórico versionado e proteção contra conflito entre revisores.
- Identidade e hashes dos artefatos, QC dos dois formatos, retry direcionado e
  configurações/snapshots preservados por job.
- Enquadramento vertical aprovado; adaptação em intervalos explícitos de
  página/tweet, com ROI e legenda próxima. Montagem multitrecho validada.
- Contexto completo antes/corte/depois, evidências da fonte e diagnóstico
  explícito de respostas inválidas. Corrigida a repetição de timestamps por
  palavra no prompt: 15 contextos reais passaram no budget compacto e uma
  geração GPU real terminou sem fallback. Textos e palavras armazenados intactos.
- Comparações sem preenchimento heurístico: seleção, prioridade, título, efeitos
  e avaliação de fechamento vêm do motor identificado. O backend valida e
  resolve referências exatas da fonte; não inventa escolhas ou notas humanas.

## Entrega observada — rodada local concluída

| Rodada | Candidatos na aplicação principal | Situação |
|---|---:|---|
| Cinco vídeos autorizados | 15 | NEEDS_REVIEW; 30 arquivos decodificados/reproduzidos em QA e importados com hashes preservados |
| Qwen 2.5 3B, PT + EN | 6 | NEEDS_REVIEW; WebM/MP4 reproduzidos no app principal |
| DeepSeek-R1-Distill-Qwen-1.5B, PT + EN | 6 | NEEDS_REVIEW; 12 etapas de reasoning concluídas; WebM/MP4 reproduzidos no app principal |
| Hermes MCP, PT + EN | 0 | Resposta real recebida, mas truncada pelo MCP; aguardando retransmissão completa |

**27 candidatos na aplicação principal; seis Hermes ainda pendentes.**

| Motor | Job PT | Job EN |
|---|---|---|
| Qwen 2.5 3B | `bced4eb1` | `4eb2130d` |
| DeepSeek R1 Distill Qwen 1.5B | `37ab951c` | `e6730749` |

Procure por **COMPARAÇÃO ESTRITA** no seletor de jobs. Os 24 arquivos dos quatro
jobs locais terminaram no navegador principal, sem erro. Reprodução muda/4x é
validação técnica, não escuta ou aprovação editorial. Nenhuma decisão humana foi
criada. Auditoria final confirmou os planos, hashes na aplicação principal,
originais/ASR intactos e ausência de preenchimento heurístico nos 12 candidatos.

Os 15 candidatos da primeira rodada usaram Qwen no ranking e fallback heurístico
na direção por excesso de contexto. Eles são controles, não fazem parte da rodada
estrita. Não atribuir qualidade editorial ao simples estado NEEDS_REVIEW.

## Limites e próximos passos

- Avaliação humana individual continua pendente: narrativa, começo/fim, títulos,
  ASR, áudio e legibilidade. Não há ganho editorial medido ainda.
- Página/tweet/ROI ainda dependem de anotação manual, sem detector/OCR; página
  muito pequena ou mosaico na fonte pode continuar ilegível.
- Qwen usa seleção conjunta; R1 escolhe sequencialmente os melhores intervalos
  restantes e usa runtime/contexto diferentes. A comparação é prática do processo,
  não um teste isolado dos pesos ou benchmark de velocidade.
- R1 não carrega no runtime Kepler legado; a rodada usa o GGUF existente em
  Ollama isolado/CPU, sem alterar metadados nem baixar outro modelo.
- Hermes exige disparo do usuário; o MCP de mensagens corta conteúdo acima de
  2.000 caracteres. Identidade de modelo/provedor informada por Hermes é
  autodeclarada, não verificada independentemente.
- Para concluir Hermes: obter os dois JSONs inteiros por colagem nesta conversa,
  ou pedir retransmissões PT/EN em turnos separados, cada resposta abaixo de1.800
  caracteres, preservando escolhas e usando evidências por ID. Não completar um
  JSON cortado com escolhas nossas. A resposta parcial real32426 foi preservada.
- Pendências menores de UI: aviso da comparação continua dizendo que aguarda
  avaliação após decisões completas; um texto legado pode dizer motor não
  registrado, embora o banner da comparação/direção mostrem o motor real.
  Não afetam os eventos, hashes ou elegibilidade de aprovação.
- Operação: C: tem pouca folga (~1,3GB no encerramento da rodada local). Logs de
  containers de teste concluídos foram preservados antes de removê-los; volumes,
  mídias, histórico e serviços principais foram mantidos. Sem build/download novo.
- Brief permanece DRAFT/inativo; treino e recuperação não foram promovidos.
  Telegram de revisão/publicação continua em dry-run; o prompt privado ao
  Hermes foi uma exceção explicitamente autorizada. Nenhum merge em main.

Evidências locais (ignoradas pelo Git):
`research/pytest_temp_editorial/five-videos-20261107-r1` e
`research/pytest_temp_editorial/strict-three-engines-20261107-r1` na instalação
principal. Suítes finais observadas: **339 testes** na branch de aprendizado e
**310** na de produto. Revisão independente teve cinco achados importantes,
corrigidos em uma rodada com regressões RED→GREEN. Compose e diff checks passaram.
Commits de código: produto`c822e36`; aprendizado`e00636a`/`e79ffd3`.

Decisões e seus limites: qualidade continua com o revisor humano (candidatos
fracos ainda podem exigir recusa); Hermes permanece entrega parcial até resposta
íntegra; métodos diferentes não permitem atribuir ganho só aos pesos; identidade
do modelo remoto permanece incerta. Não houve merge em main nem aprovação social.
