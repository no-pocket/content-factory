# Documentação do Content Factory

Versão de referência: **4.1.0**. Esta página é o ponto de entrada para operar, testar e modificar a aplicação nesta workstation.

| Preciso de… | Leia |
| --- | --- |
| Subir os serviços, criar um job, aprovar vídeos ou resolver uma falha comum | [Operação diária](OPERACAO.md) |
| Entender cada etapa, os arquivos produzidos e os fallbacks | [Processo de produção](PROCESSO.md) |
| Ajustar parâmetros por job ou configuração da instalação | [Configuração](CONFIGURACAO.md) |
| Entender serviços, dados, contratos e limites de confiança | [Arquitetura](ARCHITECTURE.md) |
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

Os relatórios em [`research/`](../research/) registram experimentos, resultados e limitações. O [relatório REA da K4200](../research/AUDITORIA_REA_K4200_2026-11-05.md) contém o benchmark CPU/GPU e o manifesto do ambiente. A [auditoria de produto](AUDITORIA_E_OPCOES_2026-11-04.md) é um retrato histórico; consulte os guias acima para o comportamento atual.
