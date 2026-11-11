# Plano: legendas sociais e Hermes

1. `app/social_captions.py` e testes: gerar sugestões por rede, usando o contexto ancorado do candidato e modelo local do snapshot; validar resposta completa, limites e fallback rastreável. Não incluir fatos ou hashtags não ancoradas.
2. `app/worker.py` e serviço: persistir sugestões aditivas em novos candidatos e disponibilizar geração explícita para legados, preservando revisão, artefato e edições. Testar recuperação e concorrência.
3. `app/publication_calendar.py` e UI editorial: apresentar sugestões por destino e preservar edições no estado da sessão, incluindo ao trocar candidato; congelar a legenda selecionada em cada agendamento. Testar UI e publicação sem rede.
4. `app/hermes_api.py`, `app/api.py`, contratos e cliente Hermes: permitir leitura do texto ancorado e solicitação autenticada de nova sugestão para o candidato correto, sem aprovar ou publicar. Testar escopo, artefato, autorização e falhas.
5. Documentar configuração, comportamento e limites. Executar testes focados, suíte proporcional, validação de interface via agent-browser e inspeção de diff; validar Hermes em ambiente isolado antes de alterações de operação.
