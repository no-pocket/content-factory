# Documentação do Content Factory

Atualização: [revisão editorial e conectores locais](REVISAO_CONECTORES_2026-11-07.md). Histórico: [consolidação dos três PRs na main](CONSOLIDACAO_MAIN_2026-11-07.md).

Versão de referência: **4.1.0**. Esta página é o ponto de entrada para operar, testar e modificar a aplicação nesta workstation.

| Preciso de… | Leia |
| --- | --- |
| Subir os serviços, criar um job, aprovar vídeos ou resolver uma falha comum | [Operação diária](OPERACAO.md) |
| Entender cada etapa, os arquivos produzidos e os fallbacks | [Processo de produção](PROCESSO.md) |
| Ajustar parâmetros por job ou configuração da instalação | [Configuração](CONFIGURACAO.md) |
| Entender serviços, dados, contratos e limites de confiança | [Arquitetura](ARCHITECTURE.md) |
| Preparar rascunhos de Instagram/Facebook, YouTube e TikTok | [Publicação em dry-run](PUBLICACAO.md) |
| Configurar ou diagnosticar a Quadro K4200 | [GPU K4200](GPU_K4200.md) |
| Rodar testes e confirmar que três candidatos são reproduzíveis | [Testes e validação](TESTES.md) |
| Conferir a aceitação de uma versão | [Plano de aceitação](TEST_PLAN.md) |

## Código e contratos

- Interface: [`app/ui.py`](../app/ui.py); controles de cada job: [`app/ui_settings.py`](../app/ui_settings.py) e [`app/job_settings.py`](../app/job_settings.py).
- Fila, estado e worker: [`app/queueing.py`](../app/queueing.py), [`app/store.py`](../app/store.py), [`app/worker.py`](../app/worker.py).
- Seleção e edição: [`app/ranker.py`](../app/ranker.py), [`app/director.py`](../app/director.py), [`app/timeline.py`](../app/timeline.py).
- Render e prévia: [`app/edit_render.py`](../app/edit_render.py), [`renderer/`](../renderer/).
- Integrações: [`contracts/`](../contracts/); entrada JSON para URL autorizada: [`app/submit.py`](../app/submit.py).

## Medições e histórico

Sprint de qualidade e API: [plano e dependências](SPRINT_QUALIDADE_PLANO.md),
[QC por candidato](CONTROLE_QUALIDADE.md), [protocolo editorial](PROTOCOLO_EDITORIAL.md),
[API v1](API.md) e [evidências e pendências](../research/SPRINT_QUALIDADE_RESULTADOS.md).

Revisão mais recente: [correções solicitadas pelo usuário e ensaio GPU](../research/CORRECOES_REVISAO_USUARIO.md).

Continuação: [plano das próximas sprints e pontos em aberto](PROXIMAS_SPRINTS.md).
Plano executável e handoff atual: [Content Factory — revisão editorial e aprendizado](planning/content-factory-next/README.md), com branches de produto e aprendizado separadas.
Para revisão no celular: [acesso privado via Tailscale](OPERACAO.md#acessar-pelo-celular-via-tailscale).
Rodada atual para avaliação: [cinco vídeos, quinze candidatos GPU/Qwen 2.5](../research/TESTES_GPU_5_VIDEOS_2026-11-06.md).

Os relatórios em [`research/`](../research/) registram experimentos, resultados e limitações. O [relatório REA da K4200](../research/AUDITORIA_REA_K4200_2026-11-05.md) contém o benchmark CPU/GPU e o manifesto do ambiente. A [auditoria de produto](AUDITORIA_E_OPCOES_2026-11-04.md) é um retrato histórico; consulte os guias acima para o comportamento atual.

Execução atual: [aceitação e limites da evolução editorial](planning/content-factory-next/ACCEPTANCE_STATUS.md); proposta de [brief DRAFT](planning/content-factory-next/EDITORIAL_BRIEF_DRAFT.json), sem ativação automática.
