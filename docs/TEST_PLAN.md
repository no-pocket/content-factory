# Plano de aceitação — Content Factory 4.1.0

Use este roteiro ao publicar uma versão ou alterar a seleção, o render, a fila ou a GPU. Os comandos reproduzíveis estão em [Testes e validação](TESTES.md).

## Verificações automatizadas

1. Execute a suíte Python na imagem do worker e confira `docker compose -f compose.yaml -f compose.kepler.yaml config --quiet`.
2. Confirme testes para qualquer bug corrigido ou feature nova; nesta versão, 92 testes passaram.
3. Confira `git diff --check` e revise o diff antes de commit/push.

## Fluxo real na workstation

1. Preserve `.env`, `data/` e volumes existentes. Confirme espaço e ausência de job ativo antes de recriar serviços.
2. Verifique Worker, Ollama e, quando selecionada, a ponte GPU no Doctor. Confira `/health` e `/api/ps` da GPU.
3. Envie um vídeo local autorizado com fala clara, criador e referência de direitos. Registre os ajustes escolhidos no job.
4. Acompanhe `QUEUED → TRANSCRIBING → DIRECTING/RENDERING → NEEDS_REVIEW`; para URL autorizada também ocorre `DOWNLOADING`.
5. Se a fala permitir três cortes, confirme três candidatos e três timelines. Compare trechos, tempos de palavras e áudio com a fonte.
6. Reproduza cada prévia WebM até `ended` no navegador e abra cada MP4 mestre. Confira resolução, duração, enquadramento, áudio e legendas.
7. Cadastre um B-roll licenciado e confira que a timeline final usa apenas IDs do catálogo; áudio do B-roll não deve substituir a fala.
8. Verifique `renderer_used`: Remotion deve mostrar animações; fallback FFmpeg deve ficar identificado e ser revisado como visual simplificado.
9. Provoque uma indisponibilidade controlada do backend de teste: o job deve registrar o motivo do fallback e continuar pela heurística. Um pedido GPU acima do contexto deve receber 422 antes de gerar.
10. Salve uma aprovação e uma rejeição; recarregue a UI para confirmar persistência. Nenhum vídeo deve ser publicado automaticamente.

## Limites da aceitação

Passar nos testes não prova qualidade editorial, licença válida, ausência de erros factuais ou suporte oficial da K4200 em WSL. A pessoa revisora decide sobre publicação. Benchmark CPU/GPU e diagnóstico NVENC estão na [auditoria REA](../research/AUDITORIA_REA_K4200_2026-11-05.md).
