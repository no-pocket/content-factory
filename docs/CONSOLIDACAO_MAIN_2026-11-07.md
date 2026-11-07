# Consolidação na main — 07/11/2026

Consolidação autorizada explicitamente pelo proprietário e concluída no commit
de código `63f641e92fd4846d3681ffae631b1c5d8d7b7f5f`.

- [PR2](https://github.com/no-pocket/content-factory/pull/2): incorporado pelo
  histórico do PR3; GitHub confirmou merged. Seu conflito isolado em
  `app/worker.py` não foi reintroduzido.
- [PR3](https://github.com/no-pocket/content-factory/pull/3): produto e baseline,
  merge `9cdeccaae033ac58076f7324535581f32f274b69`.
- [PR4](https://github.com/no-pocket/content-factory/pull/4): retargetado para main
  após PR3 e mesclado preservando o histórico publicado e todo o código local
  validado. Os commits locais de comparação foram consolidados na atualização.

Verificações:339 testes da integração e310 do produto passaram localmente;
instalação npm limpa, TypeScript, Compose e diff checks passaram. A declaração
ausente dos tipos React foi corrigida no manifesto/lockfile e o renderer ganhou
um job de typecheck no CI. Revisão independente não encontrou problemas de
integração. Ambos os workflows do GitHub passaram no commit de código final.

O checkout principal foi sincronizado com main. Worker/API foram recarregados
com fila vazia; GPU/modelos, Redis e interface permaneceram ativos, com volumes
preservados.
A conferência antes/depois preservou os artefatos e eventos de revisão dos39 jobs
e104 candidatos existentes, incluindo os33 candidatos da rodada comparativa.
O fluxo real foi conferido via agent-browser: comentários/botões de revisão
habilitados e os três WebM/três MP4 de um job existente terminaram sem erro.
Isso é validação técnica; a aceitação editorial continua com o proprietário.

Recuperação permanece `off`, brief permanece DRAFT e treino continua condicionado
a dados elegíveis e aprovação explícita. Integração de código não equivale a
aprovação editorial, promoção de modelo ou publicação de conteúdo. Registros
anteriores de “sem merge” descrevem a fase de validação que precedeu esta autorização.
