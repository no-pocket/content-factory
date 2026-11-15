# Reprocessamento explícito Hermes

Escopo autorizado: adicionar ação ao backend/CLI/skill, explicar zero candidatos e aprovação com ajustes. Não executar retry do job real d27316c7-6a8e-41f9-bf0e-9cbbefdfcfd7.

1. Testar FAILED sem candidatos, snapshot/histórico, corrida/idempotência, perda de resposta Redis, execução obsoleta e autorização.
2. Serviço compartilhado conserva o job e registra instrução/ator/erro anterior; reutiliza reconciliação atômica da fila existente. Nenhuma alteração de settings, heurística ou worker.
3. API privada exige instrução do dono; CLI e skill do Pi expõem `reprocess`. Status retorna run ID e diagnóstico seguro. Jobs ativos/com candidatos são recusados.
4. Testes focados e suíte, revisão, implantação somente da API/cliente sem reiniciar worker, verificação read-only pelo Pi e diff check. Nenhuma inferência ou reprocessamento real nesta validação.
