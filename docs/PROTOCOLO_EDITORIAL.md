# Avaliação editorial e refinamento

## Corpus e revisão

Meta original: 20–30 vídeos **distintos e autorizados**, identificados por SHA-256, com fala,
ritmos, durações e formatos variados. `python -m research.evaluate_sprint inventory`
gera inventário sem inventar decisões. Arquivo presente não comprova direitos.
Vídeo com áudio original no mesmo arquivo é a entrada suportada; faixas separadas
precisam ser sincronizadas antes da submissão.

**Atualização do usuário:** os 12 vídeos autorizados presentes são suficientes para
esta rodada piloto. Português e inglês devem ser preservados, sem tradução automática.
Whisper detecta o idioma e grava `language` no job; a UI mostra o idioma detectado e
as métricas incluem `by_language`. Revisar detecções erradas e vídeos com alternância
de idioma; idioma dominante único não representa necessariamente toda a fala.
Não há exigência de completar 20 antes de avaliar os 12 desta rodada.
O manifesto do lote congela fontes/hashes antes da primeira submissão. Retomadas não
absorvem vídeos adicionados depois; fonte modificada exige novo identificador de
coorte. A coleta de sinais inclui decisões já salvas, sem apagá-las ou substituí-las.

Na UI, selecione um job, verifique os arquivos legados quando necessário e assista
MP4/WebM. Cada candidato tem botões **Aprovar** e **Recusar**, com comentário. Aprovar exige QC; recusar aceita também arquivos falhos. As notas 1–5 são opcionais:

- Gancho: 1 sem atração/com promessa enganosa; 3 compreensível; 5 forte e fiel.
- Contexto: 1 depende de informação ausente; 3 suficiente; 5 autossuficiente.
- Fechamento: 1 interrompido/sem payoff; 3 conclui ideia; 5 conclusão clara e satisfatória.
- Legendas: 1 erro grave ou ilegível; 3 utilizável com ajustes; 5 fiel e bem sincronizada.

Registre aprovação/rejeição, motivo e, quando aplicável, retrabalho e ajustes. Notas ausentes são null e não entram em médias; uma revisão parcial não entra como vídeo completamente revisado. Também é possível recusar o job inteiro com comentário. Aprovação é decisão
humana sobre uso local; nenhuma publicação ocorre. Não clique em salvar apenas para
testar com dados reais. Os testes em `tests/` usam avaliações **sintéticas**.

Cada salvamento guarda evento imutável no histórico do registro, com revisão,
timestamp, decisões, janelas e snapshots de configurações. `expected_revision` impede
sobrescrita por cliente desatualizado. Novos eventos não apagam anteriores. Aprovações
legadas não têm notas/tempo conhecidos: são preservadas como legado e não entram como
avaliações completas inventadas nas métricas novas.

## Métricas e denominadores

`GET /v1/metrics` e o painel da UI expõem:

- **Aprovados por vídeo**: candidatos aprovados / vídeos com revisão completa dos
  candidatos tecnicamente disponíveis. Zero aprovações conta como zero; sem revisão
  não entra no denominador. Falhas técnicas devem ser reportadas em paralelo.
- **Taxa de retrabalho**: candidatos marcados com retrabalho / candidatos revisados.
  Inclui aprovados condicionais e rejeitados quando necessitam ajustes.
- **Tempo**: média da soma de execuções registradas por vídeo. Tentativas e retries
  contam; fila e tempo de revisão não contam. Execuções interrompidas guardam o tempo
  até o último checkpoint como **limite inferior**, sinalizado por `timing_complete=false`.
  Tempo entre checkpoint e crash não é conhecido; não apresentar como medição completa.

Por configuração, usa-se a última execução revisada de cada fonte/configuração.
Globalmente, a última execução por fonte impede contar o mesmo vídeo duas vezes.
Decisão invalidada por mudança/falha do artefato permanece no histórico, mas sai das
métricas atuais até uma nova revisão. Não reaproveitar aprovação de bytes anteriores.
`video_configuration_pairs` conta os pares separadamente. Hash de fonte evita
duplicações de uploads novos; legados sem hash usam URL/caminho e devem ser reconciliados
antes de concluir cobertura do corpus. `unreviewed_jobs` informa trabalho sem avaliação.

## Ciclo de refinamento

1. Congele baseline, versão, configurações, modelo e fonte. Revise todos os candidatos.
   O modelo Qwen agora integra o snapshot `settings.llm_model`; mudanças posteriores
   de `OLLAMA_MODEL` não alteram jobs novos já salvos. Jobs legados sem esse campo
   adotam o valor compatível 3B na normalização.
2. Inspecione notas, razões de rejeição, ajustes e janelas início/fim; formule uma hipótese
   específica (ex.: encerramentos cortados). Não transforme poucas aprovações em regra.
3. Gere uma variante em **novo job**, sem modificar o snapshot anterior; use os mesmos
   vídeos, condições e orçamento de candidatos. Varie um fator por comparação.
   Identifique-a com `evaluation.variant` distinto: esse rótulo integra a identidade
   da configuração, mesmo quando os parâmetros numéricos são iguais. Preserve o rótulo
   da baseline e versione o da regra experimental; não renomeie jobs antigos.
4. Revise a variante sem consultar a preferência anterior quando possível. Compare
   apenas fontes comuns aos dois grupos; mostre tamanho pareado, ganhos/perdas por vídeo,
   retrabalho e custo. Diferencie dados descritivos de comprovação editorial.
5. Só altere padrões após decisões reais suficientes e revisão das regressões. Retenha
   grupos difíceis (sem aprovação, silêncio intencional, transições, múltiplos temas).

Os sinais ficam em `app/editorial.py` e `app/signals.py`, separados de `core/ranker`.
Não há treino automático nem fontes externas de marketing/tendências. A interface
de sinais permite acrescentá-las posteriormente com proveniência e avaliações próprias.
O experimento de limites temporais fica offline até existir comparação humana pareada.
# Protocolo v2 por artefato

O opt-in `settings.editorial_protocol=2` em novos jobs separa `APPROVED`,
`APPROVED_WITH_ADJUSTMENTS` e `REJECTED`. Sem decisão atual, o candidato é `PENDING`.
As dez dimensões são opcionais (1–5 ou null); grau de conteúdo 0–3 também é opcional.
Não existem notas preenchidas automaticamente. Motivos e severidades vêm da revisão
humana; recusa informa domínio editorial, técnico, administrativo, misto ou não
especificado. Aprovação com ajustes exige comentário ou pedido aberto; aprovação
limpa recusa pendências maiores/críticas. Resolver edição não aprova outro render.

Uma avaliação v2 referencia UUID do candidato, versão da proposta, revisão do render
e hash do conjunto MP4/WebM/timeline. Substituição de bytes ou nova revisão exige
nova avaliação. Eventos antigos permanecem no histórico e não aprovam a saída nova.
Legados preservam decisão/comentário e são projetados como condição não confirmada;
`rework=false` não vira rótulo de aprovação limpa. Nenhum job é migrado em leitura.
Veja [API v2](API.md) e [contrato](../contracts/editorial-feedback-v2.schema.json).

