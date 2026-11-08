# Conclusão narrativa: pesquisa e evolução

Consulta em 08/11/2026, usando repositórios originais:

| Projeto | O que fornece | Uso nesta rodada |
|---|---|---|
| [wtpsplit / SaT](https://github.com/segment-any-text/wtpsplit) | Segmentação de frases/unidades textuais, incluindo texto sem pontuação; licença MIT | Referência para separar fronteira textual de conclusão narrativa. Não instalado; exigiria pesos e avaliação PT/EN na máquina. |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Mudanças de cena, cortes e transições visuais | Sinal visual complementar futuro; mudança de imagem não comprova resolução de uma promessa falada. Não instalado. |
| [openshorts / clip_selection](https://github.com/mutonby/openshorts/blob/main/clip_selection.py) | Helpers de seleção, janelas alinhadas a segmentos e restrições de duração | Referência arquitetural de fronteiras temporais; não foi identificado nesse arquivo um detector pronto de payoff narrativo. Sem cópia de código. |

A integração escolhida é própria e leve. O gate técnico existente protege palavras
e duração; a camada narrativa examina promessas/perguntas antes do fim, exige
resolução relacionada e impede que um COMPLETE do modelo vença evidência de
incompletude. O prompt orienta o diretor a citar a resolução e o final, mantendo o
contrato story existente. Também corrige a instrução final que pedia apenas
hook/effects/broll apesar de solicitar story antes.

Promessas explícitas reconhecidas ainda abertas marcam INCOMPLETE. Perguntas sem
resposta lexicalmente reconhecida mantêm UNCERTAIN: a resposta pode ser indireta.
Elas impedem um COMPLETE sem evidência, mas não bloqueiam render nem forçam extensão.
Saudações e perguntas retóricas reconhecidas são excluídas.

Esta camada continua conservadora: padrões linguísticos cobrem construções
reconhecidas, não compreensão universal. Sem evidência suficiente, a aplicação
mantém incerteza. Não instala modelos, não transmite transcrições para terceiros,
não reavalia humanos nem modifica vídeos aprovados.

Validação: 547 testes passaram na suíte completa em container isolado, código
somente leitura e rede bloqueada (177,54 s). A regressão de contexto longo do
diretor detectou estouro do orçamento durante a elaboração do prompt; as instruções
finais compactadas passaram nesse teste, preservando o contexto integral.
Revisão independente e testes focados cobriram resposta não relacionada, promessa
negada, payoff negado, saudações e pergunta com resposta indireta.

Auditoria somente leitura dos 105 candidatos existentes: duas promessas explícitas
em cortes legados permanecem incompletas sem extensão observada disponível. Uma
pergunta no candidato positivo de Lucía permanece UNCERTAIN, sem extensão forçada.
Os demais 102 não apresentam essas obrigações abertas reconhecidas. O Gameplayrj
render 4 aprovado pelo proprietário não foi sinalizado. Isso é diagnóstico do
corpus existente, não medição de acurácia semântica ou aprovação de novas edições.
