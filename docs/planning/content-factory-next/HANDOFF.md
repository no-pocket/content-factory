# Handoff — próximo agente do Content Factory

## Objetivo e escopo recebido

Produzir candidatos de cortes de vídeos autorizados, com relevância, história completa e informação visual preservada, sempre terminando em revisão humana. Evoluir incrementalmente Streamlit/Python/Redis/JSON/Whisper/Qwen/FFmpeg/Remotion. O usuário aprovou qualidade/resolução, legendas sincronizadas com efeitos, título editorial distinto da fala e acabamento suave da variante 700982a4. Não reescrever a aplicação ou reduzir a qualidade para acomodar integrações.

Esta rodada entregou **planejamento**, usando `superpowers:writing-plans`, sem implementar funcionalidades, mudar jobs/avaliações, treinar, reiniciar serviços ou executar Git remoto. O usuário determinou que **o próximo agente** comece consolidando tudo em commit, push upstream e PR, crie branch local sincronizada com main e faça todo o desenvolvimento de produto. Pesquisa em fontes primárias, recuperação de exemplos, ranker leve e eventual fine-tuning ficam em branch separada. Essa orientação posterior substitui o trecho anterior do pedido que limitava o próximo agente ao primeiro marco.

## Leia antes de agir

1. `AGENTS.md`, `README.md`, `docs/README.md` na raiz.
2. [CURRENT_STATE](CURRENT_STATE.md): fatos, jobs, arquivos/funções e limitações verificadas.
3. [DECISIONS](DECISIONS.md), [ARCHITECTURE](ARCHITECTURE.md), [DATA_CONTRACTS](DATA_CONTRACTS.md).
4. [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md): executar G0/G1 primeiro; tarefas com arquivos/interfaces/testes/aceite/rollback.
5. [EDITORIAL_LEARNING](EDITORIAL_LEARNING.md), [EVALUATION](EVALUATION.md), [snapshot bruto](evidence/review_snapshot.json).
6. `docs/OPERACAO.md`, `docs/TESTES.md`, `docs/CONFIGURACAO.md`, `docs/GPU_K4200.md`; confirmar configuração efetiva, não apenas a descrição.

Raiz observada: `E:\CodexFiles\content-factory\content-factory`. Branch observada `codex/quality-editorial-api`; HEAD `4725b999d7253301f43549e4fb70fa59f5f6b55f`. Há muitas mudanças anteriores e módulos não rastreados. Esse HEAD **não é uma baseline completa** até G0. Não descartar, limpar, sobrescrever ou assumir autoria dessas mudanças. Confirmar tudo novamente.

## O que está pronto e o que ainda precisa mudar

Funciona: worker único/Redis/checkpoints, gravação JSON atômica, Qwen local/ponte Kepler opcional, Whisper CPU, render MP4/WebM com QC, revisão por serviço comum/API v1, retry por candidato e UI privada via Tailscale. Isso não prova acesso físico do celular ou qualidade editorial. Não repetir testes GPU para confundir ausência de erro com bom conteúdo.

Problemas investigados: recusa escondida dentro de job aprovado; aprovação binária com ressalva textual; contexto resumido aos primeiros700 caracteres antes da direção; título `"0"`; crop central que remove prova/site/tweet; fim de frase interrompido apesar de fade; teto60s no render base; avaliações sem vínculo forte com versão exata do render. Não existe dataset confiável/personalização automática nem labels v2 implementados.

Ainda proposto, não implementado por este pacote: contratos/eventos v2, interface estruturada, contexto completo/brief, avaliação semântica de fechamento, presets/ROI, timeline v3 multitrecho, aprendizado A/B/C, crítica Hermes e Telegram. Não tratar nomes de módulos futuros como arquivos existentes.

| Código existente | Inspeção / próximo marco |
|---|---|
| `app/editorial.py`, `app/service.py`, `app/store.py` | projeção/validação, revisão/retry/invalidação, lock/JSON; M0/M1 |
| `app/ui.py`, `app/ui_settings.py`, `app/api.py` | layout, filtros e contratos HTTP; M1/M2 |
| `app/core.py`, `app/ranker.py`, `app/director.py` | truncamento/contexto, seleção/LLM e direção; M3/M4 |
| `app/timeline.py`, `app/edit_render.py`, `app/candidates.py`, `renderer/src/vertical-clip.tsx` | corte/framing/timing/render/QC; M5/M6/M13 |
| `app/job_settings.py`, `app/submit.py`, `app/worker.py` | snapshot, criação e processamento; M1/M3/M13 |
| `contracts/clip_proposal.schema.json` | proposta estruturada; não prova integração Hermes ativa |

## Evidências e regressões indispensáveis

São cinco fontes/15 candidatos: 11 APPROVED legados, 4 REJECTED; oito aprovações com ressalvas na leitura do auditor, nenhuma confirmação v2. `rework=false` não confirma aprovação perfeita. Há 18 recusas administrativas anteriores, não18 negativos editoriais independentes. Preservar comentário/decisão originais. Snapshot documental não altera o registro vivo nem fornece rótulos para treino.

| Referência completa | Uso |
|---|---|
| `58924b9a-dedf-4f56-ab6d-10b25f1240b5` | C2 aprovado, ressalva de fechamento |
| `ae34ddee-0e98-4bba-9984-0ce95fd48abe` | C1/C2 recusados dentro de job aprovado |
| `4cb53aa0-ad5f-4762-8c44-5fbface0f77f` | título 0 e C3 sem preservar demonstração/página |
| `b82453d3-e032-482c-80cc-f5e782622cdb` | três encerramentos com ressalvas, só um `rework=true` |
| `f6b1c5c5-fb6b-429a-8b79-819fb86097bc` | autopromoção vs descoberta e “melhor dos três, mas ruim” |
| `8b572e41-35b5-4007-a456-1a3d9f20ee8a` | diagnóstico anterior de mesma fonte f6, não sexta origem |
| `7cb2fb21-353c-4805-9fbb-b3c10603be44` | referência visual original preservada |
| `700982a4-ca3d-4f4a-be5f-887d9cf08a29` | título humano distinto e final suave aprovados |

Variantes77b79d5e/90dda26b geraram o mesmo intervalo/candidato: não são evidência de superioridade entre modelos. Detalhes e relatórios com nomes completos estão em CURRENT_STATE.

## Primeiro: Git sem perder a baseline

Comandos para inspecionar, em PowerShell, a partir da raiz:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git branch -vv
git remote
git diff --stat
git diff --check
git ls-files --others --exclude-standard
```

G0 é a **primeira ação de entrega**, antes de desenvolvimento: auditar todos os arquivos de projeto acumulados, stage por caminhos auditados, conferir diff staged/testes, commit, push com upstream e criar/atualizar PR para main. Nunca incluir `.env`, vídeos/modelos/`data/`, credenciais ou artefatos ignorados. Não usar `git add -f`, nem revelar segredo em saída de ferramenta. PR deve conter o que mudou, verificações reais e limitações, sem alegar aprovação editorial. Inspecionar PR existente para não duplicar. Usar ferramenta GitHub disponível; CLI é fallback. O usuário autorizou push/abertura de PR, não merge.

Exemplo após confirmar a branch observada e auditar staging:

```powershell
git diff --cached --check
git diff --cached --stat
git commit -m 'chore: consolidate content factory editorial baseline'
git push --set-upstream origin codex/quality-editorial-api
```

Criar o corpo exato do PR em arquivo temporário e usar `--body-file` se usar `gh`. Confirmar o commit está no remoto e registrar URL do PR. Se identidade/auth/remoto não permitirem, reportar a falha concreta; não fazer checkout com trabalho incompleto ou fingir publicação.

G1, com tree limpo:

```powershell
git fetch origin
git switch main
git merge --ff-only origin/main
git switch -c codex/editorial-product origin/main
```

Se main local divergiu, não resetar: preservar e criar a branch a partir de `origin/main`. Se branch destino já existir, inspecionar seu conteúdo/base antes de reutilizar. Se baseline G0 ainda não foi integrada em main, fazer merge da branch baseline em produto, testar conflitos e documentar dependência no PR; não esperar ou integrar main sem autorização. Confirmar ambos os ancestrais:

```powershell
git merge-base --is-ancestor origin/main HEAD
git merge-base --is-ancestor <commit-G0> HEAD
```

Os dois devem retornar 0. Fazer merge futuro de origin/main para manter sincronismo; sem force push. Abrir PR de produto separado. Aprendizado nasce em `codex/editorial-learning` sobre fundações M1/M3, em checkout/worktree limpo separado quando necessário, PR com base produto enquanto dependente. Nenhuma dependência de treinamento/recuperação entra em produto. Pesquisa/experimentos de aprendizado nunca são condição para concluir os marcos de produto.

## Primeira mudança de código: M0

Criar somente contrato/validação/projeção puros, schema v2 e testes sintéticos conforme plano. Teste inicial exato: `tests/test_editorial_contracts.py::test_legacy_qualified_approval_is_unknown`. Uma aprovação legada com comentário de fechamento ruim e `rework=false` deve manter decisão/comentário e projetar `normalized_decision=None`, `qualification_status='UNCONFIRMED_LEGACY'`, sem modificar input.

Depois: RED pelo comportamento ausente → implementar `candidate_key`, `project_legacy_review`, `validate_feedback_event` → GREEN focado e `tests/test_editorial.py` → diff/check/commit. Não migrar jobs nem plugar produção em M0. Ao concluir, seguir M1/M2 e demais marcos de produto; não parar automaticamente após M0.

## Validações e fluxo real

Baseline observada nesta investigação: **140 passed in 15.41s**. Comando seguro executado, sem rede, volume read-only, sem dados reais ou cache no repositório:

```powershell
docker run --rm --network none --cpus 2 -v 'E:\CodexFiles\content-factory\content-factory:/workspace:ro' -w /workspace -e PYTHONPATH=/workspace -e PYTHONDONTWRITEBYTECODE=1 -e DATA_DIR=/tmp/content-factory-planning --entrypoint python content-factory-worker:latest -m pytest -q --tb=short --basetemp=/tmp/planning_pytest -p no:cacheprovider
```

Confirmar a imagem existe antes, sem baixar/reconstruir desnecessariamente. Para RED/GREEN focado, trocar `-m pytest ...` pelos argumentos do arquivo/teste do marco, preservando `DATA_DIR` temporário e cache desligado. Depois das alterações, executar suíte completa apropriada; o resultado140 é histórico, não garantia para código futuro. Testes que exigirem dependências novas rodam em imagem/venv isolado, nunca instaladas no ambiente ativo só para satisfazer um teste.

Verificação Compose sem subir serviço:

```powershell
docker compose -f compose.yaml -f compose.kepler.yaml config --quiet
git diff --check
```

Para mudanças UI, testar fluxo com **agent-browser CLI**, conforme AGENTS. Verificar `Get-Command agent-browser`/ajuda antes; usar app com `DATA_DIR` temporário, Redis/fixtures isolados e porta alternativa, nunca escrever reviews reais para teste. Testar viewport móvel/desktop, filtros, recusa com comentário, aprovação com ajuste, recarregar e reproduzir vídeo. Se CLI não existir, usar fallback de navegador disponível para obter evidência real e declarar que o requisito específico de CLI ficou pendente; não alegar teste não realizado. Não confundir AppTest com reprodução de mídia.

Mudanças em ranker/render exigem também nova variante de fonte já autorizada, somente quando necessária, com configurações salvas e comparação controlada. Antes de usar/reconstruir/reiniciar ambiente ativo: verificar jobs em andamento, configuração Compose efetiva, volumes e disco conforme OPERACAO. MP4 e WebM precisam de decode/reprodução e inspeção visual/áudio. Aprovação humana nunca é inferida pelo agente.

## Fronteiras de autorização

O desenvolvimento de produto, testes isolados, commits, push upstream e PRs descritos foram solicitados para a próxima execução; prosseguir sem reabrir confirmação a cada mudança reversível. Não fazer aprovação de design repetitiva quando o plano já fixa a decisão.

Ainda precisam de informação/autorização concreta quando aplicáveis: destino/bot/usuário Telegram, conteúdo/provedor autorizado para Hermes externo, promoção de brief/modelo, merge em main, publicação social, treino/fine-tuning/custo de infraestrutura e novo download relevante. Falta de dado/infra pode impedir M9/M10, sem bloquear produto. Nunca apagar/limpar dados/volumes/modelos ou sobrescrever avaliações. Um pedido de integração não identifica sozinho uma conversa de destino autorizada para envios reais.

## Prompt de inicialização para copiar

```text
Assuma o Content Factory em E:\CodexFiles\content-factory\content-factory.
Leia AGENTS.md, README.md e docs/README.md, depois todos os documentos em
docs/planning/content-factory-next/, começando por CURRENT_STATE e HANDOFF.
Use a skill de execução adequada; o plano foi elaborado com writing-plans.
Confirme o estado real do Git e preserve todas as mudanças existentes.

Comece obrigatoriamente por G0: audite e comite todo o trabalho de projeto
acumulado (sem segredos/dados/modelos/mídia ignorados), dê push com upstream
e abra ou atualize o PR para main, confirmando URL e commit remoto.
Depois G1: fetch, main atualizado sem reset, branch local
codex/editorial-product sincronizada com origin/main e contendo a baseline.
Se o PR baseline ainda estiver pendente, integre sua branch em produto e
declare a dependência; não faça merge em main por conta própria.

Execute todos os marcos de produto M0–M6 e M11–M13, na sequência/dependências
do IMPLEMENTATION_PLAN, com testes RED/GREEN, validação real proporcional,
diff/check, commit por entrega e PR separado de produto. Não pare após M0.
M0 é contrato puro: não migre decisões existentes nem altere produção ali.
Preserve a qualidade visual aprovada, MP4/WebM, snapshots e histórico.

Mantenha pesquisa em fontes primárias, dataset/avaliação de aprendizado,
recuperação de exemplos, ranker leve e eventual fine-tuning em
codex/editorial-learning, PR separado e sem misturar dependências ML no produto.
Execute M7/M8 nessa trilha após fundações; M9/M10 só até onde dados e gates
permitirem. Não invente labels, treino, ganho estatístico ou aprovação humana.
Não envie conteúdo a Hermes/Telegram sem destino/capacidade autorizados;
implemente e teste adaptadores isolados enquanto isso. Não publique conteúdo,
não apague dados/volumes, não altere .env e não faça merge automático em main.
Reporte evidências, hashes/PRs, pendências concretas e testes não realizados.
```

**Modo recomendado:** execução nativa incremental para manter coerência entre contratos/persistência/pipeline, com revisão independente nos marcos de maior risco quando escolhida. Alternativa: execução por subagentes isolados com revisão por tarefa. Nenhuma delegação foi usada para produzir este plano; a auto-revisão documental foi feita conforme a skill.
