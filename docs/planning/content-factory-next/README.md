# Content Factory — plano técnico e handoff

**Estado atual (07/11/2026):** execução autorizada em andamento. Produto M0–M6/M11–M13 implementado em `codex/editorial-product`, sem deploy/merge; aceite editorial e rebuild final pendentes. Aprendizado M7–M10 separado em `codex/editorial-learning`. Registro verificável em [EXECUTION](EXECUTION.md). O texto original abaixo descreve o planejamento de06/11/2026. Skill executada: **superpowers:writing-plans**, incluindo divisão em marcos, interfaces, testes, critérios de aceite e auto-revisão. O diretório foi escolhido pelo usuário em substituição ao caminho padrão da skill.

O objetivo é produzir candidatos de conteúdo autorizado, com revisão humana, aprendendo preferências editoriais progressivamente. Preservar a apresentação aprovada: qualidade de imagem, legendas por palavra, cores e efeitos. Manter Streamlit, Python, Redis, JSON, Whisper/CPU, Qwen local, FFmpeg e Remotion. Não há autorização para publicação automática.

## Como assumir

1. Leia `AGENTS.md`, o README da raiz e `docs/README.md`.
2. Leia os documentos abaixo na ordem indicada; confirme os caminhos no worktree antes de editar.
3. A solicitação posterior do proprietário autoriza executar o plano. G0/G1 já realizados; não repetir baseline. Consulte EXECUTION e Git antes de retomar.
4. Em G1, sincronizar com `origin/main` e criar `codex/editorial-product`. Executar todos os marcos de produto em sequência, com testes e commits por marco. A instrução posterior do usuário substitui a restrição anterior de executar apenas o primeiro marco.
5. Reservar `codex/editorial-learning` para pesquisa em fontes primárias, dataset/avaliação de aprendizado, recuperação de exemplos, ranker leve e eventual fine-tuning. Não misturar sua implementação ou dependências na branch de produto.

| Ordem | Documento | Responsabilidade |
|---|---|---|
| 1 | [CURRENT_STATE.md](CURRENT_STATE.md) | Evidências, limitações, funções e casos reais de regressão |
| 2 | [DECISIONS.md](DECISIONS.md) | Decisões aprovadas, escolhas propostas e pendências |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | Componentes atuais e módulos incrementais propostos |
| 4 | [DATA_CONTRACTS.md](DATA_CONTRACTS.md) | Estados, eventos, versões, migração e contratos entre módulos |
| 5 | [EDITORIAL_LEARNING.md](EDITORIAL_LEARNING.md) | Estágios A/B/C, recuperação, ranking, dados e promoção |
| 6 | [EVALUATION.md](EVALUATION.md) | Métricas, denominadores, splits e experimentos |
| 7 | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Marcos executáveis, arquivos, interfaces, RED/GREEN e rollback |
| 8 | [HANDOFF.md](HANDOFF.md) | Comandos, primeira tarefa e prompt para o próximo agente |

[evidence/review_snapshot.json](evidence/review_snapshot.json) congela as decisões originais dos 15 candidatos e seus comentários, sem converter ressalvas em novos rótulos. Não é dataset de treinamento nem substitui os registros de produção.

## Sequência

`G0 baseline/PR → G1 sincronização/branch → M0 contratos → M1 persistência → M2 revisão → M3 contexto/brief → M4 relevância/fechamento → M5 visual → M6 multitrecho`. Na trilha de produto, seguir com `M11 Hermes → M12 Telegram → M13 reprodutibilidade/eficiência`, respeitando capacidades e autorizações de envio.

Em branch separada: `M7 dataset → M8 recuperação → M9 ML opcional → M10 fine-tuning opcional`. A pesquisa em fontes primárias deste pacote fundamenta o plano; seu aprofundamento e os experimentos de aprendizado pertencem à branch de aprendizado. M9/M10 não autorizam treino com dados insuficientes. Nenhuma integração é pré-requisito para boa edição local. Coleta de eventos e versões começa em M1; a exportação do dataset é M7.

## Escopo e evidência

- Cinco fontes independentes da rodada recomendada, 15 candidatos, 11 aprovações legadas / 4 recusas; oito aprovações têm ressalvas na leitura dos comentários. Isso **não** fornece 11 positivos ideais.
- Os 18 jobs recusados administrativamente continuam no histórico, sem virar 18 exemplos independentes de irrelevância.
- Há **zero avaliações no novo contrato v2**, ainda não implementado. Migração/qualificação exige confirmação humana; `rework=false` legado não significa ausência de ressalva.
- Baseline de código observado: 140 testes passaram em 15,41 s, em container efêmero sem rede, repositório somente leitura e dados temporários. Não foram gerados novos vídeos ou treinados modelos nesta etapa.

## Cobertura do pedido

| Requisito | Onde se encontra |
|---|---|
| Diagnóstico, evidências e arquivos reais | CURRENT_STATE; snapshot |
| Aprovado / pendente / recusado / com ajustes; dez dimensões | DATA_CONTRACTS; M0–M2 |
| Migração conservadora e preferência relativa | DATA_CONTRACTS; EDITORIAL_LEARNING |
| Briefing e versões por job | DATA_CONTRACTS; M3 |
| Estágios prompting, ML e fine-tuning | EDITORIAL_LEARNING; M8–M10 |
| Duplicatas, vazamento, autorreforço e defeitos técnicos | EDITORIAL_LEARNING; EVALUATION |
| Métricas e atribuição da contribuição de cada alteração | EVALUATION |
| Contexto, títulos, relevância, encerramento e enquadramento | M3–M5 |
| Narrativa de 1–2 minutos e sincronismo | M6 |
| Hermes e Telegram sem aprovar/publicar automaticamente | M11–M12 |
| Reprodutibilidade, observabilidade e eficiência | M13 |
| Commit/push/PR inicial, main e duas branches | G0–G1; HANDOFF |
| Dependências, critérios, testes, risco e rollback | IMPLEMENTATION_PLAN |
| Continuidade sem memória de chat e autorização de escopo | HANDOFF |

Planos anteriores e relatórios em `docs/PROXIMAS_SPRINTS.md` e `research/` permanecem como histórico. Este pacote detalha a próxima implementação; não declara validação estatística de ganho editorial.

## Verificação desta entrega documental

- Nove documentos e um snapshot JSON; 29 links locais do pacote resolveram para arquivos existentes.
- Snapshot reconciliado com os registros vivos: 15 decisões/copias integrais dos comentários, 11 aprovações, 4 recusas e 18 jobs administrativos identificados; hashes dos cinco registros conferidos.
- 125 arquivos de código, contratos, testes, configuração e registros/transcrições foram comparados com a captura inicial: nenhum alterado. HEAD e branch também permaneceram iguais.
- Suíte segura: 140 testes passaram em 15,41 s; Compose Kepler `config --quiet` e `git diff --check` terminaram com código0. Git mostrou apenas avisos de conversão LF/CRLF, sem erro de whitespace.
- Não houve teste de navegador ou nova renderização nesta rodada, pois nenhuma interface ou funcionalidade foi implementada. O plano exige validação real desses fluxos nos marcos pertinentes.
