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

**Instalado em08/11/2026:** SSH restabelecido, perfil e skill instalados no Pi,
[tópico nopocket-content](https://t.me/c/4410866638/1687) criado e roteado no gateway
existente. API privada conectada por SSH reverso em loopback, com credencial própria.
Teste real do perfil consultou a aplicação e identificou os três motores (exit0).
Publicação social continua em dry-run; nenhuma avaliação artificial foi criada.
Validação:427 testes passaram em126,23s na imagem existente, código somente leitura,
rede bloqueada e dados temporários isolados. Revisões independentes não encontraram
Important em aberto após correções. Browser agent-browser no app completo confirmou
modelos legíveis, comentários entre jobs, seleções2→1→0 após recarregar, reprodução
de prévia e duração máxima120 aceita no controle flexível de180, sem criar job real.
Instalação e roteamento foram verificados no gateway ativo; a validação de uma conversa humana completa permanece para o uso do proprietário.

Migração de sessões: teste RED→GREEN confirmou que sessões com job já selecionado mantêm a área individual e o rascunho ao receber a nova interface. Sessões novas abrem comparação por fonte.

Entrega Telegram confirmada em08/11: [prévia no tópico](https://t.me/c/4410866638/1688),5.244.486bytes aceitos pela BotAPI. A prévia preserva a recusa/aviso técnico já existentes; o envio não é aprovação nem publicação social.
