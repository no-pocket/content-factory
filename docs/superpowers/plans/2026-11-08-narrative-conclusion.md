# Conclusão narrativa — implementação autorizada

Pedido: confirmar aprovação móvel e prosseguir com melhorias, pesquisando lógica
existente. Aprovação confirmada no render 4 Gameplayrj, evento humano Telegram
4ad4df52-afa6-4fe0-b4d0-e072368e2b48; nenhuma nova decisão criada pelo agente.

Direção: manter o detector de fim de frase como proteção técnica e acrescentar
verificação conservadora de promessa/pergunta ainda sem resolução. Examinar o
contexto após o corte somente dentro dos limites salvos; proposta de extensão
exige relação com a promessa e evidência temporal. Não transformar palavra-chave,
silêncio ou mudança de cena em prova de conclusão narrativa. Ausência de prova
continua UNCERTAIN. Modelos existentes recebem instruções coerentes com o gate.

Alternativas pesquisadas: wtpsplit/SaT para segmentação textual; PySceneDetect
para cortes visuais; openshorts para janelas alinhadas à transcrição. São sinais
complementares, não solução demonstrada de payoff narrativo. Nesta rodada usar
implementação própria leve, sem baixar pesos nem adicionar dependências à GPU.

1. Implementar/testar regressões PT/EN, promessa anterior ao fim, pergunta aberta,
   payoff relacionado e falso payoff de outro assunto. Preservar bons finais.
2. Integrar seleção e planner de retrabalho; reforçar prompt sem mudar contrato.
3. Comparação somente leitura com transcrições existentes, revisão independente,
   testes focados e suíte completa. Nenhuma mudança nos vídeos já aprovados.
4. Implantar o código com worker ocioso; registrar resultados e limites.
