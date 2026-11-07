# Próximas sprints — Content Factory

Plano de 06/11/2026, fundamentado no pedido atual, nas decisões do usuário e nos relatórios desta sprint. Ordem recomendada: avaliar os cinco vídeos GPU → corrigir falhas demonstradas → melhorar revisão móvel → consolidar API/operação. Cada etapa é uma sprint proposta, sem data prometida antes de medir o esforço. Este documento é planejamento, não autorização para executar todas as etapas agora.

## Ponto de partida

- Corpus disponível: 12 vídeos autorizados, 9 PT e 3 EN. A rodada inicial heurística/FFmpeg foi recusada editorialmente, apesar de 36 candidatos passarem no QC técnico.
- Referência de estilo aprovada: Remotion, palavras sincronizadas, cores e efeitos. Variante `700982a4` aprovada com título independente da fala e final suave. Não generalizar essa aprovação a todas as fontes.
- Qwen 2.5 1.5B completou seleção/direção na K4200 no ensaio curto; 3B teve fallback por resposta truncada. As saídas curtas foram consideradas idênticas pelo usuário: não existe vencedor editorial demonstrado.
- O lote atual concluiu cinco fontes distintas, 3 PT/2 EN, Qwen2.5 1.5B GPU e três candidatos por vídeo: 15 candidatos Remotion/high, 9 VALID/6 WARNING contextuais. Um vídeo exigiu tentativa adicional de classificação com shortlist menor; o resultado anterior permanece como diagnóstico. Transcrição reaproveitada. Resultado em `research/sprint/gpu-five-results.json`; aprovação depende do usuário.
- QC MP4/WebM, comentários e decisões versionadas, retry por candidato, recuperação e API local estão implementados. A execução continua com worker único.
- Acesso privado móvel: Tailscale encaminha a porta 8501 para o Streamlit local. Abertura no celular real ainda deve ser confirmada pelo usuário; um navegador desktop com viewport móvel não substitui essa confirmação.

## Sprint 1 — Qualidade editorial nas cinco fontes (P0)

**Objetivo:** transformar a nova rodada em evidência utilizável, com decisões reais e motivos específicos, antes de mexer novamente na seleção.

**Trabalho:**

1. Apresentar os cinco jobs e registrar decisão/comentário em cada candidato, com notas opcionais de gancho, contexto, fechamento e legendas.
2. Separar falhas de trecho, enquadramento, transcrição, título, efeito e acabamento. Registrar renderizador e backend efetivamente usados; fallback nunca conta como execução integral na GPU.
3. Publicar tabela por vídeo/idioma: candidatos entregues, aprovados, rejeitados, retrabalho e tempo. Mostrar denominadores e amostras não avaliadas; evitar média global misturando testes curtos e vídeos completos.
4. Escolher uma hipótese de melhoria a partir das rejeições; produzir variante em novo job, mesmo vídeo e mesmo orçamento de candidatos. Manter fonte, modelo e configuração congelados para comparar.

**Aceite:** cinco fontes processadas e identificadas; todos os candidatos disponíveis com decisão humana ou pendência explícita; medições por coorte; nenhuma nota fabricada; nenhum arquivo aprovado sobrescrito. Não fixar promessa de taxa de aprovação sem observar esta rodada.

**Dependência:** lote GPU atual concluído e avaliação do usuário. **Entrega:** relatório editorial da coorte e uma decisão explícita sobre a próxima hipótese. Se não houver evidência suficiente, documentar o resultado sem promover nova regra.

## Sprint 2 — IA confiável em PT/EN e limites dos cortes (P0/P1)

**Objetivo:** reduzir fallbacks e decisões inválidas sem enfraquecer a validação ou esgotar os 4 GB da K4200.

**Trabalho:**

1. Analisar os erros concretos do lote e dos benchmarks ingleses: índices confundidos com segundos, janelas fora da duração e resposta truncada.
2. Experimentar respostas mais compactas e divisão de tarefa compatível com o contexto real. Se necessário, uma nova tentativa limitada com motivo salvo; nunca aceitar JSON parcial ou aumentar contexto/memória automaticamente.
3. Comparar 1.5B e 3B nas mesmas fontes/janelas, orçamento e prompt versionados. Medir sucesso por tarefa, tempo, VRAM amostrada versus pico, custo de retry e preferência humana. Não trocar modelo padrão só por velocidade.
   Validar antes do despacho que o modelo solicitado coincide com o carregado na ponte GPU. Hoje o servidor carrega um modelo por vez; os ensaios 1.5B usam uma sessão privada e pausam o worker normal. Planejar reserva/troca controlada de modelo e estado visível, preservando snapshots e evitando competição por VRAM.
4. Para começo/fim problemáticos, testar uma regra de pausa/pontuação/cena em variante opt-in. Preservar palavras completas; medir mudanças nas mesmas cinco fontes. PySceneDetect permanece isolado enquanto não houver ganho editorial demonstrado que compense seu custo.
5. Avaliar diversidade temática, repetição de informação e dependência de contexto. Não fabricar três candidatos quando a fonte não sustenta três boas ideias; tornar o motivo visível.

**Aceite:** respostas inválidas continuam recusadas; comparação PT/EN reproduzível; motivos de fallback acessíveis por candidato; regressões de contexto e GPU passam; adoção condicionada à revisão humana dos pares. Manter CPU/Ollama disponíveis.

**Dependência:** rejeições classificadas na sprint 1. **Entrega:** relatório pareado e configuração candidata ou decisão fundamentada de manter a atual.

## Sprint 3 — Revisão móvel e ajustes editoriais sem retrabalho manual (P1)

**Objetivo:** revisar e corrigir cortes pelo celular com menos passos e sem perder histórico.

**Trabalho:**

1. Validar acesso Tailscale e reprodução em Android/Chrome e iPhone/Safari reais, incluindo conexão móvel, download e tela pequena. Exibir alternativa MP4 quando o navegador não reproduzir a prévia WebM.
2. Facilitar seleção dos jobs recentes/coortes; recolher parâmetros técnicos; manter comentário e botões de decisão próximos ao player; preservar estado ao atualizar.
3. Permitir editar título e solicitar ajuste de início/fim ou acabamento pela UI. Cada alteração cria uma revisão/variante e exige novo QC e nova aprovação; título humano tem proveniência distinta do modelo.
4. Comparar original/variante e mostrar quais decisões são atuais versus invalidadas. Re-renderizar somente o candidato alterado e preservar os demais.
5. Avaliar enquadramento em gameplay, rosto e fontes horizontais: priorizar o conteúdo importante. Resolução de saída maior não recupera detalhe ausente na fonte; testar composição/enquadramento antes de prometer nitidez.

**Aceite:** um fluxo completo de comentário, ajuste, nova prévia e decisão funciona nos dois grupos de navegador; sem rolagem horizontal; player compacto; nenhum resultado aprovado apagado; índices e revisões concorrentes verificados no backend.

**Dependência:** fluxo editorial estável e amostras reais dos problemas. **Entrega:** revisão móvel validada e edição limitada/versionada, mantendo Streamlit como cliente do serviço compartilhado.

## Sprint 4 — API para outro frontend e operação recuperável (P1/P2)

**Objetivo:** consolidar o backend para uso por outra interface sem aumentar a complexidade operacional desnecessariamente.

**Trabalho:**

1. Acrescentar idempotência na criação/submissão e contrato de cancelamento por etapa/checkpoint, sem interromper arbitrariamente um arquivo aprovado.
2. Avaliar upload retomável e Range HTTP para mídia conforme necessidades do frontend e dos navegadores. Testar streaming sem carregar vídeos inteiros em RAM.
3. Definir/versionar endpoints de variantes e edições editoriais, mantendo o mesmo serviço usado pela UI e testes de contrato de cliente.
4. Exercitar backup/restauração de registros, entradas/saídas e catálogo em ambiente isolado; definir retenção voluntária. Nenhuma limpeza automática de modelos, mídia ou volumes por padrão.
5. Melhorar saúde/diagnóstico para distinguir worker, modelo, fila e renderer. Ensaiar perda do processo por etapa e esclarecer limites frente à queda do host. Multiworker só se medições demonstrarem necessidade; exigirá lease/coordenação próprios.

**Aceite:** requisição repetida não duplica job; erros/estados documentados; restore isolado preserva hashes e histórico; autenticação e exposição privada mantidas; testes de cliente não dependem de Streamlit. Não publicar serviço ou conteúdo na internet.

**Dependência:** necessidades concretas do novo frontend. **Entrega:** contrato incremental, cliente mínimo de integração e roteiro operacional reproduzível.

## Pontos abertos e decisões ainda necessárias

| Ponto | Evidência atual | Próxima decisão |
|---|---|---|
| Qualidade real das cinco fontes | 15 candidatos em cinco fontes com classificação/direção GPU; QC técnico concluído | Usuário aprova/recusa com motivo; hipóteses partem dessas decisões |
| Quantidade útil por vídeo | Até três é orçamento, não garantia de qualidade/diversidade | Medir aprovados por vídeo e explicar quando houver menos candidatos |
| Modelo 1.5B versus 3B | Um ensaio curto idêntico; 3B teve truncamento | Comparação pareada com tarefas completas e revisão humana |
| Modelo solicitado versus modelo carregado | GPU com um modelo por sessão; testes privados pausam a produção | Preflight de compatibilidade e sessão/reserva explícita da GPU |
| Títulos automáticos | Cópia da abertura agora omitida; título humano aprovado em uma amostra | Avaliar síntese/fidelidade nos cinco novos vídeos; oferecer edição humana versionada |
| Fronteiras e final suave | Cauda aprovada em uma fonte; sinais offline alteraram 21/36 janelas | Confirmar em outras fontes antes de adotar novas regras de limite |
| Legendas PT/EN | Palavras sincronizadas; não há transcrição humana de referência/WER | Revisar nomes, erros de idioma e timing em amostras; alinhamento adicional só se necessário |
| Nitidez/enquadramento | Fonte 720p horizontal pode ter recorte efetivo estreito | Comparar crop/composição nas fontes difíceis |
| Acesso do celular | Proxy tailnet e navegador responsivo verificados na workstation | Confirmar celular real e permissões do mesmo tailnet |
| Limites operacionais | Worker único; sem idempotência/Range/cancelamento; backup não exercitado no host | Priorizar pelos incidentes e pelo novo frontend |

## Regra para promover mudanças

Uma alteração funcional precisa de regressão significativa, testes focados, suíte proporcional e `git diff --check`. Alterações em IA/render também exigem job autorizado, QC dos dois formatos, reprodução e avaliação humana. Guardar versão, fonte/hash, prompt/modelo, parâmetros, tempo e motivo. Dados reais de marketing/tendências e publicação automática continuam fora do escopo.

Referências: [auditoria da sprint atual](../research/AUDITORIA_ACEITACAO_SPRINT.md), [resultados](../research/SPRINT_QUALIDADE_RESULTADOS.md), [API](API.md), [QC](CONTROLE_QUALIDADE.md), [protocolo editorial](PROTOCOLO_EDITORIAL.md).
