# Telegram Gameplayrj — medidas de mídia, 2026-11-08

Artefato examinado: job `af0c5e4a-1419-4683-b23a-2e683915ad1f`, candidato `a87e8733-ae7a-5205-8d3b-a8ce90176b08`, render 3. Não foi substituído, reenviado nem aprovado nesta investigação.

O download real de `getFile` para a mensagem Telegram 1704 ficou em `/srv/nopocket/data/hermes/operations/telegram-1704-actual.mp4`. Tamanho 16.667.790 bytes e SHA-256 `6783a86c0779b71e3275480dcb0abccd59aa94e46bd7f7052cb906bbc58655e5`, iguais ao mestre. A igualdade prova preservação dos bytes; não prova sincronismo percebido no aparelho.

`ffprobe`: original AV1 1280×720, 60 fps, áudio Opus; mestre H.264 720×1280, SAR 1:1, DAR 9:16, 30 fps, AAC. Mestre vídeo 42,866667 s, áudio 42,867 s; ambos começam em zero. Base 42,5 s, ambos começam em zero. Nenhuma rotação foi observada. O helper verificou índice MP4 antes do payload (`moov` antes de `mdat`).

Correlação cruzada de amostras mono a 8 kHz durante 35 segundos contra original recortado em 0,68 s: base atraso 0 ms, pico normalizado 0,99976; mestre 0 ms, 0,99967; WebM −20 ms, 0,99624. Busca por erro quadrático em recorte central de quadros aos 3, 15 e 30 s: mestre/base e prévia/base têm melhor correspondência em zero; base/original transformado difere aproximadamente 33–67 ms. Não há evidência de atraso acumulado grande introduzido entre base, mestre e prévia. Sincronia labial da fonte e reprodução no aparelho continuam sem confirmação humana.

Uma referência sintética com flash e beep coincidentes a 1 s, fonte 60 fps e corte em 0,37 s, revelou atraso pequeno reproduzível no normalizador: beep em 0,630083 s e flash em 0,700 s (69,9 ms). Adicionar `setpts=PTS-STARTPTS` ao filtro reduz para 36,6 ms. Adicionar `fps=30` ao filtro, mantendo `-r 30`, produz flash em 0,633333 s (3,25 ms do beep). O teste de integração guarda essa referência; duração e início de streams sozinhos não detectariam o problema.

A geometria enviada originalmente em `sendVideo` não está no recibo conservado. Portanto, a causa do esticamento da apresentação Telegram não está confirmada. O backend agora pode oferecer largura/altura reais, duração arredondada e capacidade de streaming verificadas; é preciso passá-las explicitamente no próximo envio autorizado e verificar o resultado no cliente. Nenhuma alteração de dados editoriais decorre destas medidas.

Correção implementada: `app.core.render` aplica `fps=30` no filtro simples e na saída do grafo de enquadramento, antes das legendas. O áudio não recebe deslocamento artificial. Teste sintético passa para os dois caminhos com diferença abaixo de um quadro. Um ensaio integrado em alta fidelidade retornou `remotion` (sem fallback), gerando apenas `/tmp/av-remotion-corrected.mp4` e sua prévia no worker. Mestre e WebM têm flash em 0,633333 s e beep em 0,630083 s: diferença 3,25 ms.

Um novo base temporário do material real, `/tmp/gameplayrj-base-cfr-corrected.mp4`, foi produzido com o mesmo intervalo 0,68–43,18 s e sem tocar no job. A busca de quadros contra a fonte aos 3/15/30 s agora encontra deslocamento 0/−16,7/0 ms (antes aproximadamente −33 a −67 ms). Áudio mantém atraso zero e pico 0,99976. Este arquivo é evidência de diagnóstico, não uma revisão aprovada nem uma substituição de artefato.

Validação: 13 testes de metadados e referência A/V passam dentro da imagem worker existente; localmente 11 passam e os 2 de sinal são pulados por ausência de FFmpeg. `tests/test_core.py` e `tests/test_framing.py`: 21 passam localmente. `git diff --check` sem erros. A reprodução em Telegram real e o ACK da geometria original continuam pendentes; os dados disponíveis não autorizam concluir que os 70 ms expliquem o relato completo de dessincronia/esticamento.
