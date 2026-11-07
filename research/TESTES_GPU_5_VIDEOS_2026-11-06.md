# Cinco vídeos com GPU e Qwen 2.5 — 06/11/2026

Rodada solicitada pelo usuário: **cinco fontes distintas, três em português e duas em inglês, três candidatos por fonte (15 no total)**. Qwen2.5 1.5B Q4_K_M na Quadro K4200, seleção e direção concluídas na GPU nos cinco jobs indicados abaixo. Remotion/high, títulos compactos e final suave. Nenhuma aprovação editorial foi criada pelo agente.

| Fonte | Idioma | Job para avaliar | Candidatos | Tempo observado |
|---|---|---|---:|---:|
| GTA 6 - URGENTE! NOVAS IMAGENS DE GTA 6.mp4 | pt | `58924b9a` | 3 | 291.7 s |
| RETROSPECTIVA-GTA-6-SnapYT.App.mp4 | pt | `ae34ddee` | 3 | 296.0 s |
| GTA-6-File-Size-is-Absolutely-Insane_001_1080p.mp4 | en | `4cb53aa0` | 3 | 349.8 s |
| Rockstar-Updated-the-GTA-6-Release-Time_003_1080p.mp4 | en | `b82453d3` | 3 | 335.7 s |
| retentativa GPU · JOGANDOO GTA 6 AGORAAA!!!! TÁ ACONTECENDO GALERA GTA 6 É REALIDADE.mp4 | pt | `f6b1c5c5` | 3 | 369.5 s |

## Método e resultados

- Mesmas fontes autorizadas do corpus anterior, com hashes conferidos antes do teste. Transcrições Whisper base e palavras foram reaproveitadas; tempos não incluem nova transcrição.
- Orçamento: alvo 30 s, limites 18–45 s, até dois blocos de descoberta e shortlist de cinco. Na tentativa adicional da fonte JOGANDOO, shortlist reduzida para três; o snapshot distingue essa configuração. O experimento não isola o efeito dessa mudança para concluir ganho editorial.
- A geração de janelas continua híbrida. Qwen pode classificar na GPU janelas provenientes da cobertura heurística; propostas inválidas por índice/duração são descartadas. Isso é diferente de um fallback de classificação.
- QC final: **9 VALID e 6 WARNING, zero FAILED**. MP4 e WebM 720×1280, 30 arquivos com decodificação completa, áudio esperado e duração conferidos. Avisos: silence_intervals_context_required. São sinais contextuais, não rejeições editoriais.
- Soma dos tempos dos cinco jobs selecionados: **27.38 min**, incluindo preparação de cada worker, inferência e render, excluindo carga inicial do servidor e ASR reaproveitada. Não é uma medição de pico de RAM/VRAM.
- O primeiro teste JOGANDOO (`8b572e41`) atingiu o limite da resposta de classificação e usou fallback. Seus três candidatos e histórico foram preservados como diagnóstico. A nova variante `f6b1c5c5` completou classificação/direção GPU e substitui esse resultado na lista recomendada. Não foi sobrescrito nem aprovado o teste anterior.
- O erro inicial do coordenador impedia o worker de processar os registros; foi corrigido e retomado nos mesmos IDs, sem duplicar o lote. Resultados sem processamento agora geram erro; teste automatizado cobre o caso.
- Servidor GPU e worker de produção restaurados, saúde CUDA10.2 conferida, filas vazias. Hashes dos cinco pais e dos registros aprovados de referência preservados. Sem build/download de modelos, alteração de .env ou limpeza de volumes.

## Acesso e revisão

Abrir [Streamlit pelo nome Tailscale](http://workstation.taild835d6.ts.net:8501/) ou [pelo IP privado](http://100.78.0.122:8501/), com o celular conectado ao mesmo tailnet. Em **Para revisar**, escolher os cinco IDs da tabela. Há um sexto job diagnóstico, `8b572e41`, que teve fallback; usar `f6b1c5c5` para a rodada integral na GPU.

A aprovação técnica não demonstra que os trechos sejam bons. Registrar aprovação/recusa com comentário, especialmente sobre início/fim, contexto, títulos e legenda no idioma original. Notas são opcionais. Nenhuma seleção de modelo vencedor decorre deste teste.

## Evidências

- [Dados da rodada e snapshots](sprint/gpu-five-results.json); [primeira passagem com fallback](sprint/gpu-five-first-pass.json).
- [Acesso Tailscale](sprint/tailnet-access.json) e [operação](../docs/OPERACAO.md#acessar-pelo-celular-via-tailscale).
- [Plano das próximas sprints](../docs/PROXIMAS_SPRINTS.md).
- Suíte: **140 testes passaram em 37,07 s**; Compose e git diff --check passaram. A reprodução pelo navegador é registrada separadamente; o aparelho físico do usuário não foi testado pelo agente.

Reprodução final: **15/15 WebM terminaram sem erro pelo endereço Tailscale**, com durações conferidas contra os respectivos jobs. [Evidência do navegador](sprint/browser-gpu-five.json). A primeira automação trocava de job antes de o terceiro player atualizar; as verificações afetadas foram repetidas após esperar os metadados corretos, sem refazer os vídeos.
