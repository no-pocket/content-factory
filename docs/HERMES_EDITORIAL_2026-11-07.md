# Comparação editorial, duração flexível e Hermes — 07/11/2026

Comparação com main10556a7.

A área **Comparar fontes e escolher finais** reúne jobs/modelos da mesma fonte por
fingerprint e origem confirmada, com nomes dos modelos e execução/fallback visíveis.
Mostra sobreposições, reprodução, avaliações existentes e seleção de zero/um/vários
finais. Escolha não altera aprovação. Mudanças no render/rodada exigem conferência;
mesclar grupos que já tinham escolhas pede reconciliação explícita.

**Duração da história → Flexível** em novos jobs permite8–180 segundos da fonte.
A meta orienta, sem preencher tempo ou cortar conclusão. Propostas usam janelas
por tempo, texto integral compacto e divisão diagnosticada se o contexto não couber.
Snapshots antigos permanecem intactos; montagem multitrecho v3 conserva120s próprios.
QC usa duração real, incluindo cauda e encerramento opcional cadastrado.

A API privada `/v2/hermes/*`, cliente Python, personalidade e skill do perfil
`nopocket-content` estão preparados em [integração Hermes](../integrations/hermes/OPERACAO.md).
Credencial própria, ator Telegram configurado, artefatos exatos, idempotência e
comentários sem decisão evitam transformar conversa em aprovação. Comentários
sem decisão ficam visíveis no job e não viram notas/labels de ML.

**Instalação remota pendente:** SSH para nopocket-pi/localIPv4 recusou conexão;
IPv6 expirou; MCP retornou Transport closed. Nenhum perfil/tópico remoto foi
alterado nem segundo consumidor Telegram criado. O pacote preparado não equivale
a perfil instalado ou vídeo entregue no chat. A ponte permanece desativada sem
credenciais/configuração verificadas. Publicação social continua em dry-run.

Validação:427 testes passaram em126,23s na imagem existente, código somente leitura,
rede bloqueada e dados temporários isolados. Revisões independentes não encontraram
Important em aberto após correções. Browser agent-browser no app completo confirmou
modelos legíveis, comentários entre jobs, seleções2→1→0 após recarregar, reprodução
de prévia e duração máxima120 aceita no controle flexível de180, sem criar job real.
Instalação, roteamento Hermes e entrega Telegram ainda precisam de verificação real.

Migração de sessões: teste RED→GREEN confirmou que sessões com job já selecionado mantêm a área individual e o rascunho ao receber a nova interface. Sessões novas abrem comparação por fonte.
