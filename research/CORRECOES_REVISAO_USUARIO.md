# Correções após revisão do usuário — 06/11/2026

O lote heurística/FFmpeg foi recusado editorialmente pelo usuário. A escolha desse perfil alterou o estilo do exemplo aprovado. QC técnico não demonstrou qualidade editorial.

Foram recusados 18 jobs existentes por instrução explícita; `7cb2fb21` permanece aprovado, com JSON e seis arquivos de mídia intactos por hash. Os dois novos ensaios abaixo foram criados depois dessa operação e ficam para revisão, sem aprovação automática.

## Correções

- FFmpeg exibia segmentos Whisper inteiros, inclusive parágrafos em inglês. Agora usa até três palavras por legenda, com timestamps de palavras; estimativas sem timestamps são diagnosticadas.
- UI oferece aprovar/recusar individualmente, comentário, notas opcionais, recusa do job inteiro e filtros. Recusa não exige arquivo tecnicamente válido. Histórico e decisões dos candidatos não refeitos são preservados.
- Player limitado a 340 px. Transcrição, QC e timeline recolhidos. Alternância entre WebM e MP4 mestre.
- Novos formulários usam GPU K4200, Remotion e alta fidelidade. Jobs existentes mantêm seus snapshots. Remotion conserva o componente do exemplo aprovado; high não troca silenciosamente para FFmpeg.
- Menor compressão: base CRF16, mestre CRF18, prévia 720×1280. A fonte aprovada é horizontal 1280×720: o recorte vertical contém aproximadamente 405 pixels de largura da fonte, antes de ampliar. Esse limite de detalhe permanece.

## Comparação pequena na GPU

Mesmos 60 segundos da fonte aprovada, mesma transcrição em português, parâmetros e artefato de entrada. Modelos GGUF locais, sem download. Um candidato por modelo, ambos selecionando 0–25,28 s. Não é comparação em inglês nem demonstra superioridade editorial.

| Modelo | Job | Tempo incluindo carga/processamento | Seleção | Direção | Render |
|---|---|---:|---|---|---|
| Qwen2.5 1.5B Q4_K_M | `77b79d5e` | 177,969 s | K4200 | K4200 | Remotion |
| Qwen2.5 3B Q4_K_M | `90dda26b` | 303,236 s | K4200 | fallback: resposta atingiu 450 tokens | Remotion |

Ambos chegaram a NEEDS_REVIEW, candidato VALID. O 3B **não passou** no critério de direção integral pela GPU; resposta incompleta foi rejeitada. Não aumentamos contexto/memória automaticamente. Amostras de VRAM: 2.176/3.183 MiB, não medições de pico. Evidência e hashes: [piloto](sprint/approved-style-gpu-pilot.json).

## Validação observada

- 132 testes passaram (19,07 s), incluindo regressões de legendas, revisão parcial, notas ausentes e preservação de decisões após retry.
- agent-browser/Edge: recusa de candidato sintético com arquivo falho e comentário persistiu na revisão 3; dimensões sem notas ficaram null. Nenhuma decisão editorial de teste foi adicionada aos jobs reais.
- Ambos os WebM reais tocaram até `ended`, sem erro, resolução 720×1280 e player de 340 px. Frame do mestre inspecionado: três palavras e palavra ativa amarela. Isso não substitui revisão humana da fala/edição.
- Compose config e git diff --check passaram. GPU/worker de produção restaurados; saúde CUDA10.2 ok. API reiniciada para carregar as rotas novas. Nenhuma alteração no job aprovado.

Não foi reprocessado o lote recusado. Os dois ensaios novos estão disponíveis na UI para comparar. Uma futura comparação em inglês deve usar a mesma disciplina antes de ampliar o lote.

## Feedback recebido e variante de título/encerramento

O usuário considerou ambos os candidatos idênticos: imagem ótima, legendas/efeitos bons e fechamento bom, mas final seco. O título repetia a fala e ocupava cinco linhas; forneceu o título editorial “ÍCONE DOURADO NO GTA 6!! CROCODILO LENDÁRIO?!”. Isso é feedback real, sem converter automaticamente em aprovação ou notas. A comparação anterior tinha `clip_count=1` deliberadamente; não demonstra diversidade nem superioridade de um modelo.

Foi criado **`700982a4`**, reaproveitando a seleção e as palavras sincronizadas de `77b79d5e`, sem inferência nova. O título humano agora ocupa três linhas menores; o fallback que copiava a abertura foi removido para novas timelines, incluindo diferenças de acentuação. Encerramento: 0,35 s de último frame congelado, silêncio após a fala e fade visual de 0,25 s. A fala não é encurtada. O renderizador recebe uma codificação adicional de acabamento; não há trilha nova. A ausência de `finishing` mantém o comportamento de timelines antigas.

MP4 25,667 s e WebM 25,673 s, ambos 720×1280 e VALID; QC adicional com tolerância de 0,05 s também passou (esperado 25,630 s, diferença por quadros/codec). Prévia terminou no Edge via agent-browser sem erro, player 340 px. Frames de abertura e fim inspecionados. Suíte: **136 testes passaram em 16,74 s**; regressões de acentuação e finishing foram vistas falhando antes da correção. Evidência: [variante](sprint/title-ending-revision.json).

Worker atualizado com montagem somente leitura de `renderer/src` no override Kepler, sem build/download. Reinício com filas vazias; UI/API recarregadas. GPU e volumes preservados. O registro do pai continuou idêntico; o job aprovado `7cb2fb21` também permanece intacto. A variante fica em NEEDS_REVIEW: opções são manter o fim anterior ou avaliar o novo encerramento suave antes de expandir testes.

**Decisão posterior do usuário:** “Ficou bom; manter os dois ajustes”. A variante `700982a4` foi aprovada pelo serviço de revisão, após nova verificação dos arquivos. Revisão 1, candidato 0, origem `explicit_user_message`; notas de dimensões permanecem null. Título compacto e cauda suave permanecem nas novas timelines. A aprovação confirma estes ajustes nesta amostra; não estabelece superioridade entre modelos ou melhoria editorial geral nos 12 vídeos.
