# Sprint: qualidade, avaliação e contrato de backend

Pedido de referência: sprint iniciada em 05/11/2026. Execução autônoma autorizada;
dados, modelos e configurações existentes serão preservados.

## Escolhas e dependências

Manter worker único, Redis e persistência JSON. Um serviço de domínio compartilhado
pela UI e HTTP evita dois fluxos de negócio. HTTP com biblioteca padrão evita instalar
framework; autenticação por Bearer e porta local são obrigatórios. Um framework ASGI
seria alternativa para maior concorrência, que não é requisito desta instalação.

1. QC (`app/quality.py`), limites em snapshot separado por job: decodificar MP4/WebM,
   medir duração, resolução, áudio, silêncio/preto; sinais contextuais geram aviso.
   Testes com arquivos sintéticos, ausência de áudio e arquivo corrompido.
2. Checkpoints e tentativas (`app/candidates.py`, worker): preservar seleção, transcrição,
   timelines e resultados válidos; salvar antes de tentar render. Falha parcial permanece
   explícita, sem disponibilizar arquivo reprovado; retry só do candidato e limitado.
3. Serviço editorial (`app/service.py`, `app/editorial.py`): decisões versionadas com
   dimensões, motivo, retrabalho e snapshot; métricas com denominadores. UI usa serviço.
4. API v1 (`app/api.py`, contrato/documentação): criação upload/URL, consulta, mídia,
   revisão, retry. Testar autorização, caminhos, conflitos e paridade com UI.
5. Instrumentos de pesquisa: inventário de mídia e clones/licenças, sinais separados da
   seleção, comparação pareada de modelos disponíveis e registro de recursos/limitações.
   Sem nova regra padrão sem evidência editorial e sem fontes externas.
6. Testes focados, suíte completa, Compose, fluxo real via agent-browser, decodificação
   e revisão de diff. Registrar resultados observados e gates ainda pendentes.

## Invariantes e riscos a verificar

- Reinício durante render não apaga resultados bons nem permite retry ilimitado.
- Revisão nunca aprova candidato com falha técnica ou artefato ausente.
- Fila indisponível deixa registro recuperável, sem resposta enganosa de sucesso.
- Repetição de decisão mantém histórico; poucas amostras não modificam seleção.
- Entrada HTTP não permite caminhos arbitrários, shell, acesso externo ou leitura de segredos.

## Aceitação externa

Inventário inicial: um vídeo em `_videos_test`; faltam ao menos 19 para 20 vídeos.
Não fabricar notas ou aprovações. Aprovações humanas e corpus suficiente são gates
para validar qualidade editorial, mesmo quando os testes técnicos passarem.

Atualização: o usuário completou 12 vídeos autorizados, em português e inglês, e
definiu esse conjunto como suficiente para o piloto atual. Meta desta rodada: 12,
sem impedir o trabalho por faltar o corpus original de 20–30. Preparar baseline,
confirmar ASR automático e separar métricas por idioma; decisões humanas seguem pendentes.

## Estado de execução em 06/11/2026

O registro histórico foi consolidado para evitar referências a processos já encerrados.

- Corpus: 12 vídeos (9 PT/3 EN), 36 candidatos com QC completo. Lote heurística/FFmpeg recusado editorialmente pelo usuário; não é sucesso editorial.
- Recusas explícitas: 18 jobs; aprovado `7cb2fb21` preservado por hashes. Dois novos ensaios GPU ficam para revisão humana.
- Modelos: CPU Qwen1.5B/3B em PT/EN (proposta/reranking/direção), Whisper tiny/base nas mesmas amostras, K4200 Qwen1.5B/3B no mesmo minuto PT. Resultados e falhas registrados, sem ampliar alegações editoriais.
- Recuperação: testes automatizados de checkpoints/fila/revisão e SIGKILL/restart isolado real; hash do candidato bom preservado, retry limitado. Rename Windows corrigido.
- API: criação, acompanhamento, revisão, recusa, retries e mídia; upload streaming real de 457,2 MiB validado em ambiente isolado.
- UI: recusa individual com comentário, notas opcionais e player compacto verificados via agent-browser; novos WebM tocaram até ended.
- Última suíte completa: 136 testes. Compose e diff check passaram. Serviços restaurados, filas vazias.
- Não há coordenador de lote ou piloto GPU ainda em execução. Não recriar jobs como continuação de handles históricos.
- Decisão humana recebida: variante `700982a4` aprovada com título editorial e final suave. O ciclo de avaliação/refinamento foi exercitado. Pares adicionais seguem necessários antes de generalizar qualidade ou adotar novas regras de seleção; a entrega desta sprint não afirma essa generalização.

Evidência consolidada: [relatório da sprint](../research/SPRINT_QUALIDADE_RESULTADOS.md) e [correções recentes](../research/CORRECOES_REVISAO_USUARIO.md).
