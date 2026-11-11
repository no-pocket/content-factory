# Plano de implementação — agenda de publicações

Referência: `AGENDA_PUBLICACAO_DESIGN.md`.

1. Criar armazenamento de agendamentos e testes de estados, fuso, escrita atômica, cancelamento e bloqueio quando revisão ou artefatos mudarem. Reutilizar o preflight de `app/publishing.py`; manter cada destino independente.
2. Implementar transportes Meta separados com cliente HTTP injetável e testes sem rede: sessão, upload, processamento, publicação e confirmação para Instagram e Facebook; validar destinos, evitar segredos nos registros e preservar resultado incerto contra reenvio automático.
3. Criar processo de agenda dedicado e configuração Compose, com um executor único, recuperação de pendências, controle de concorrência e isolamento da fila de render. Testar interrupções e reinícios.
4. Integrar controles de publicação imediata e agendada e aba de calendário Streamlit. Mostrar apenas publicação confirmada com check verde; oferecer cancelamento e edição antes do envio. Testar estados e acesso à interface.
5. Documentar operação, credenciais, fuso, indisponibilidade e reconciliação; executar testes focados, suíte adequada, verificação do Compose, browser e diff. Não iniciar serviços ou publicar candidatos reais sem necessidade.
