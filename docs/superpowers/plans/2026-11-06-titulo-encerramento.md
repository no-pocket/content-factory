# Título editorial e encerramento — implementação

**Objetivo:** aplicar o feedback humano sem refazer a seleção nem alterar resultados anteriores.

**Desenho:** novos títulos do modelo devem sintetizar o assunto e ter apoio na transcrição; título que copia a abertura é omitido, em vez de substituir por mais transcrição. O título fornecido explicitamente pelo usuário é uma entrada editorial distinta e limitada. Novas timelines registram estilo compacto e finishing opcional; timelines antigas sem esses campos conservam seu comportamento. Uma cauda de 0,35 s congela o último frame, prolonga o áudio com silêncio e faz fade na cauda, preservando a última palavra. QC usa a duração final, incluindo essa cauda.

**Alternativas consideradas:** cortar antes para disfarçar o fim perderia fala; fade durante a última palavra prejudicaria inteligibilidade. A cauda após a fala preserva o trecho. Remover todo título descartaria a preferência expressa pelo usuário; a solução mantém título editorial curto e independente.

**Stack:** Python/FFmpeg, React/Remotion existentes; nenhuma dependência ou inferência nova.

- [x] Regressões: título copiado não vira banner; título humano preservado; duração e finishing limitados; saída sintética conserva fala e acrescenta cauda.
- [x] Implementar validação/timeline, prompt, estilo compacto, finishing e QC compatível com timelines antigas.
- [x] Gerar uma variante do candidato 1.5B com o título humano e finishing, preservando os jobs anteriores e registrando proveniência.
- [x] QC, navegador, frames de abertura/final, testes e relatório com limites. Não aprovar automaticamente.
