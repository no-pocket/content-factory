# Controle técnico por candidato

`app/quality.py` executa ffprobe e decodificação FFmpeg completa de **MP4 e WebM**.
MP4 esperado: 720×1280; prévia: 720×1280 no perfil high, 540×960 em standard/legados.
A duração esperada vem da janela selecionada mais a cauda opcional da timeline
(`finishing.tail_seconds`, 0,35 s nas timelines novas). Legados sem cauda conservam
a duração original; aprovação, verificação e recuperação usam a mesma duração final.
Áudio é obrigatório quando a fonte possui faixa de áudio; canais/sample rate positivos,
duração da faixa (quando ffprobe a informa), erros de decodificação e arquivo legível
são critérios objetivos. Não é uma verificação de inteligibilidade ou sincronismo labial.

Estados do candidato: `RENDERING`, `VALID`, `WARNING`, `FAILED`; legado sem QC é
`UNVERIFIED` na interface. `VALID` e `WARNING` podem ser revisados. Silêncio e preto
geram **avisos contextuais**, nunca reprovação automática. Os intervalos detectados
devem ser assistidos: pausa dramática e transição preta podem ser escolhas editoriais.

## Snapshot configurável

Na API, envie `qc_settings` junto de `settings`. A UI usa os limites padrão abaixo;
o snapshot completo fica salvo no job e não muda com o ambiente.

| Campo | Padrão | Faixa aceita |
|---|---:|---|
| duration_tolerance | 0,5 s | 0,05–2 s |
| silence_db | −40 dB | −90 a −10 dB |
| silence_seconds | 1 s | 0,1–30 s |
| black_seconds | 0,5 s | 0,1–30 s |
| black_pixel_threshold | 0,10 | 0–1 |
| black_picture_ratio | 0,98 | 0,5–1 |
| timeout_seconds | 300 | inteiro 10–1800 |
| max_attempts | 2 | inteiro 1–5 |

`candidate.qc.files.mp4/webm` contém duração, dimensões, bytes, contagem de áudio,
intervalos, confirmação de decode completo, erros, avisos e diagnóstico da ferramenta.
`attempt_history` preserva relatório/motivo de cada tentativa e timestamps.

## Falhas e interrupções

Uma tentativa por despacho. O botão de retry/API agenda **somente o índice falho**;
o total inclui tentativas interrompidas e nunca excede `max_attempts`. Ao reiniciar,
o worker reaproveita transcrição atômica, candidatos e timelines já persistidos;
revalida arquivos bons sem renderizá-los. O alvo do retry fica persistido até terminar.
O worker único recupera a lista processing e reconcilia registros QUEUED órfãos.
Falha de envio à fila fica `QUEUE_FAILED`, com reenvio explícito disponível.

`NEEDS_REVIEW` novo exige todos os candidatos verificáveis. Se alguns falharem,
`PARTIAL_FAILED` disponibiliza apenas os bons e mantém falhas visíveis; se todos
falharem, `FAILED`. Revisão dos bons não oculta falhas. Aprovações ligadas a resultados
invalidados são retiradas de `approved` atual, preservadas no histórico. Um novo
render exige nova decisão editorial. Resultados legados podem ser verificados pelo
botão **Verificar arquivos existentes (sem renderizar)**; nenhum render é feito ali.
Retry é permitido apenas após estado `FAILED`; arquivos legados ainda não verificados
não podem ser sobrescritos pelo botão de retry antes de passarem por esse QC.

As falhas pré-render continuam `FAILED`; preservar entrada, transcrição e motivo
permite diagnóstico. Não há coordenação segura multiworker, nem garantia de fsync
contra perda de energia do host. Atomic rename protege contra JSON parcial durante
interrupção do processo. Erros do sistema de arquivos ou mídia alterada externamente
exigem nova verificação; revisão e download via API revalidam os arquivos.

Em bind mounts Docker/Windows, um leitor pode bloquear temporariamente o rename.
`store.save` registra aviso e tenta novamente com espera exponencial limitada (até
1,26 s no total). Se a permissão continuar negada, a falha permanece explícita e o
JSON anterior fica intacto. Isso não transforma erro persistente de disco em sucesso.
