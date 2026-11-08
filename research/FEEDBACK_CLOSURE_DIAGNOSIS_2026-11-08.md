# Feedback e limites de encerramento — 08/11/2026

Leitura somente leitura de `data/work` da instalação existente. Nenhum review,
artefato ou job foi alterado nesta análise. IDs abaixo são identidades persistidas;
a ordem dos candidatos no JSON não equivale necessariamente à ordem exibida.

## Universo e interpretação

- 35 eventos humanos v2; 34 avaliações atuais após remover um evento substituído.
  Todos os 34 correspondem a candidate_id, candidate_version, render_revision e
  artifact_id atuais. Seis famílias de fontes: b82453d3 (12), ae34ddee (12),
  f6b1c5c5 (3), 4cb53aa0 (3), 58924b9a (3), af0c5e4a (1).
- Histórico legado: 42 snapshots e 93 entradas, reduzidos a 71 últimas decisões
  por candidato em 27 jobs. Destas, 47 repetem uma instrução geral de rejeição:
  não são 47 observações editoriais independentes. Não foram misturadas às notas v2.
- Encerramentos interrompidos predominam, inclusive com gancho/desenvolvimento
  elogiados. Também há títulos fracos/ausentes ou ecoando legenda, início sem
  contexto, demora de áudio, autopromoção e enquadramento insuficiente.
- Legendas, efeitos e qualidade visual recebem elogios recorrentes; preservá-los.
  A preferência pelo acabamento Remotion não constitui aprovação de toda seleção.

## Fonte, palavras e contraexemplos

| Caso persistido | Evidência observada | Correção proposta pelo limite seguro |
|---|---|---|
| 0570af0f, JSON candidato 2 | termina 89.54 em `purchase from the`; próxima palavra `Rockstar` começa 89.54; frase chega a `incredible.` em 91.80 | 91.95, incluindo 150 ms de intervalo observado |
| 0570af0f, JSON candidato 3 | termina 189.64 em `down here,`; fonte completa `Bayside restaurant.` em 190.56 | 190.68, antes da próxima palavra |
| 1d4760d4, JSON candidato 2 | termina 132.74 em `meme do...`; `Donada!` segue até 133.40 | 133.55; reticências não são encerramento |
| bde563a3, JSON candidato 1 | reclamação de milissegundos faltantes; última palavra `hora.` termina exatamente no corte 154.35; fala seguinte começa 156.01 | 154.50, preservando a cauda sem capturar a fala seguinte |
| dcd73775, candidate_id 97aa006c | closure=5 e “melhor finalização”; corresponde ao JSON candidato 3, 209.62–237.38, despedida `Peace out.` | permanece 237.38; sem contexto observado após o fim da fonte |
| bde563a3, JSON candidatos 2 e 3 | ambos “ficou bom”, closure=5 | contraexemplos positivos; não reescrever indiscriminadamente |

O JSON candidato 2 de dcd73775 (59.62–89.54) é o caso rejeitado com closure=1,
não o exemplo positivo. A identidade do evento evita trocar os dois casos.

## Mudança e limites

O selecionador passa a buscar a primeira terminação de frase em palavras da fonte,
dentro do contexto observado e da duração máxima salva no job, e preserva até
150 ms de intervalo disponível após a fala. Se não consegue, registra motivo e
INCOMPLETE. Não acrescenta fade para disfarçar interrupção. Sem timestamps de
palavras, usa limites de segmento explicitamente; sem conclusão observada, não
inventa conteúdo nem amplia indefinidamente a duração.

Texto do candidato não inclui palavras futuras de um segmento Whisper que
atravesse o corte. Uma avaliação semântica COMPLETE também precisa citar o fim
do segmento final, não apenas uma frase anterior do mesmo segmento. Pontuação,
pausa e citação ancorada são condições técnicas; não provam conclusão narrativa.
Exemplo: `Breaking News.` pode abrir outra informação apesar do ponto final.
Casos assim continuam sujeitos à revisão editorial e ao contexto completo.

Aplicação apenas a seleções novas. Candidatos já avaliados exigem revisão de
render explícita, preservando feedback e arquivos anteriores. Nenhuma aprovação
humana é criada por esta correção.

`select_highlights` chama `annotate_candidates` antes do reranking, portanto o
limite seguro participa da seleção real. Para retrabalho autorizado,
`prepare_source_end_revision` produz plano puro com limites, contexto e timeline
regenerados, e referências ao candidato/artefato/revisão anteriores. Não salva,
agenda ou aprova. O chamador aplica somente os campos do plano mantendo os
metadados antigos e registra uma nova revisão pelo mecanismo `register_render`.
Assemblies são recusadas porque requerem revisão explícita de cada segmento.

## Validação observada

Sete regressões falharam antes da implementação e passaram após a correção:
frase atravessando segmento, palavra parcial/cauda, orçamento insuficiente,
texto futuro indevido, citação inicial indevidamente aceita como encerramento e
modelo COMPLETE sobrepondo palavra truncada e planner sem mutação do original.
44 testes focais passaram no host com diretório temporário explícito em E:.
As propostas da tabela foram calculadas contra os transcripts persistidos em
container isolado, sem rede e com dados/código somente leitura. Isso não é
evidência de reprodução nem de aprovação editorial de novos vídeos.
O planner foi também exercitado nos dados reais 0570af0f/JSON2 e bde563a3/JSON1:
117/100 palavras de legenda, respectivamente, finais `incredible.`/`hora.`,
ambos com fechamento semântico UNCERTAIN e vínculos anteriores preservados.

A primeira suíte global em container terminou com 473 testes passando e três
falhas na interface que estava sendo editada em paralelo:
`test_last_current_candidate_save_confirms_and_advances`,
`test_selected_job_survives_status_change` e
`test_v2_adjustment_and_rejection_persist_without_ratings`.
Esse resultado precede a sexta regressão e a integração final da interface;
o responsável pela tarefa deve repetir a suíte depois da integração.
