# Corpus piloto autorizado — 12 vídeos

Português e inglês preservados. Resultados técnicos; não representam aprovação editorial.

**Revisão posterior:** o usuário recusou editorialmente este lote heurística/FFmpeg. As verificações técnicas abaixo não equivalem a boa edição. Veja [correções e comparação GPU](CORRECOES_REVISAO_USUARIO.md).

12 fontes distintas; 36 candidatos: 26 VALID, 10 WARNING, zero FAILED.
Fonte: 112.49 min; processamento registrado: 48.08 min; sinais: 9.10 min.

Cada MP4/WebM foi completamente decodificado e passou em duração, resolução e áudio esperado. As 36 primeiras tentativas concluíram sem retry. Hashes dos inputs copiados e analisados conferem com o corpus congelado; as janelas da baseline conferem com os jobs renderizados.

| Job / sinais | Idioma | Fonte, min | Processamento, s | VALID / WARNING | Sinais, s | Pausas / cenas | Janelas alteradas |
|---|---|---:|---:|---:|---:|---:|---:|
| [255f7f42](sprint/signals-255f7f42-5d82-45ae-9707-0fa142c2d985.json) | pt | 11.05 | 184.9 | 0 / 3 | 54.0 | 141 / 13 | 2 / 3 |
| [df57ad76](sprint/signals-df57ad76-3234-4110-9619-372f06ed7579.json) | pt | 11.25 | 299.5 | 3 / 0 | 65.1 | 16 / 178 | 0 / 3 |
| [3aad3ea8](sprint/signals-3aad3ea8-42ef-4e2b-8ce9-54b9b06cf741.json) | pt | 13.92 | 271.1 | 3 / 0 | 86.4 | 2 / 418 | 3 / 3 |
| [a5f108ff](sprint/signals-a5f108ff-c572-42db-905a-a73def7c4ba1.json) | en | 8.51 | 227.9 | 3 / 0 | 49.5 | 2 / 185 | 2 / 3 |
| [551502d9](sprint/signals-551502d9-fcc5-4a66-9175-b7077c89194b.json) | pt | 9.24 | 235.5 | 0 / 3 | 45.6 | 132 / 86 | 2 / 3 |
| [526f20e5](sprint/signals-526f20e5-4cf3-4055-95af-161a20dfebd7.json) | pt | 16.34 | 228.1 | 3 / 0 | 93.6 | 3 / 43 | 2 / 3 |
| [583bd5d7](sprint/signals-583bd5d7-6373-4e21-8926-7fd1b02dc914.json) | pt | 6.29 | 295.0 | 3 / 0 | 36.0 | 14 / 4 | 1 / 3 |
| [127b2a1a](sprint/signals-127b2a1a-c5c5-451e-88bf-f4ad3cb22a39.json) | pt | 4.14 | 102.7 | 0 / 3 | 11.6 | 59 / 1 | 3 / 3 |
| [7256c7f7](sprint/signals-7256c7f7-ab16-464b-8314-ce84e138f0e1.json) | en | 3.96 | 336.2 | 3 / 0 | 21.0 | 1 / 25 | 1 / 3 |
| [91714be6](sprint/signals-91714be6-b6f3-4076-95f5-0893cd062002.json) | pt | 7.26 | 303.4 | 3 / 0 | 39.2 | 1 / 21 | 1 / 3 |
| [87ea2ec6](sprint/signals-87ea2ec6-5ca1-44c0-acff-0dd25bd2dffb.json) | en | 10.32 | 242.4 | 3 / 0 | 33.2 | 27 / 33 | 1 / 3 |
| [0d0714a6](sprint/signals-0d0714a6-aca1-41d6-b5b8-7fd983358887.json) | pt | 10.20 | 158.1 | 2 / 1 | 11.1 | 152 / 0 | 3 / 3 |

## Interpretação

Tempos são de execuções observadas na workstation, não um benchmark isolado de idioma. Duração, codec, conteúdo e carga da QA variam; não atribuir diferenças de tempo ao idioma.

WARNING exige ouvir/assistir os intervalos; silêncio e preto podem ser intencionais. Não foram reprovações técnicas nem aprovações editoriais.

A regra offline de limites temporais alterou 21 das 36 janelas. A energia RMS foi registrada como evidência, sem peso calibrado. Não houve mudança na seleção de produção nem render das variantes experimentais. Sem avaliação humana pareada, não há comprovação de melhora.

## Localização

- [Resumo estruturado](sprint/corpus-summary.json)
- [Manifesto congelado e IDs dos jobs](sprint/corpus-manifest.json)
- [QC completo e medições](sprint/corpus-results.json)
- [Protocolo para decisões reais](../docs/PROTOCOLO_EDITORIAL.md)
- [Interface local](http://127.0.0.1:8501/)

Procure o prefixo do job na lista da UI. Preencha notas, motivo e retrabalho antes de salvar a avaliação. O agente não criou decisões editoriais nesses 12 vídeos.
