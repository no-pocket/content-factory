# Legendas sociais para candidatos

## Objetivo

Gerar para cada candidato uma sugestão de legenda atraente para publicação em redes sociais, baseada no texto e no contexto reais do trecho. A sugestão aparece no fluxo editorial e no formulário de publicação, onde pode ser editada antes de qualquer envio. Uma legenda sugerida não aprova um candidato nem autoriza publicação.

## Abordagens

- **Escolhida: IA local com alternativa automática.** Usar o backend local configurado no snapshot do job quando disponível. Se a chamada ou a validação falhar, criar uma sugestão conservadora baseada no próprio texto, identificando a origem e o motivo da alternativa.
- Modelo determinístico sem IA: mais previsível, porém com menos variedade editorial.
- Somente IA: oferece variedade, mas pode deixar o candidato sem sugestão quando o modelo estiver indisponível.

## Comportamento

- Gerar sugestões no processamento do candidato usando texto ancorado à transcrição e o contexto já registrado. Não inventar fatos, promessas ou hashtags que não tenham suporte. Adaptar a língua à do candidato e o formato às redes suportadas, inicialmente Instagram e Facebook.
- Quando disponível, usar as palavras da timeline renderizada, para não sugerir como conteúdo falas removidas do vídeo. Ao criar outro render, arquivar as sugestões anteriores no histórico do candidato e gerar sugestões novas a partir da nova timeline.
- Guardar o resultado e os metadados de geração de forma aditiva por candidato, sem modificar snapshots de configuração nem invalidar artefatos ou decisões editoriais existentes. Jobs antigos podem receber uma sugestão quando o usuário solicitar, sem processamento de vídeo novamente.
- Mostrar legenda, origem e motivo de fallback de forma transparente. O usuário pode alterar a sugestão; nunca sobrescrever uma edição ao trocar de candidato ou provocar rerun. Congelar a versão escolhida no agendamento existente.
- Impor limites de comprimento por destino, validar a resposta de IA e não aceitar saída truncada, inválida ou vazia. Preservar o caminho CPU/Ollama e os limites de contexto da K4200; sem envio externo de transcrições.
- Para múltiplas plataformas, oferecer sugestões próprias quando houver diferença real de formato e permitir ajustes independentes. Evitar criar hashtags arbitrárias e deixar a seleção final para revisão humana.

## Validação

Testar respostas válidas, falhas e truncamento do modelo, ausência de texto, texto não confiável, limites de comprimento, snapshots por job, candidatos legados, preservação de edições e legenda efetivamente congelada no agendamento. Rodar testes focados, suíte adequada e fluxo na interface com `agent-browser`. Não publicar conteúdo real apenas para testar a geração.
