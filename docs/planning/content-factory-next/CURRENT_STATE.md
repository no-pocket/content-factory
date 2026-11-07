# Estado real e evidências

Snapshot de 06/11/2026. Branch observada: `codex/quality-editorial-api`; HEAD `4725b999d7253301f43549e4fb70fa59f5f6b55f`. **O código atual inclui muitas alterações anteriores não commitadas e módulos não rastreados. HEAD isolado não reproduz esta baseline.** Preservar tudo. Pela instrução posterior do usuário, o próximo agente deve consolidar o trabalho de projeto em commit, push upstream e PR antes de desenvolver (G0). Auditar o staging: isso não inclui segredos, dados, modelos, mídias ou artefatos locais ignorados.

Git local observado: `main`, `codex/quality-editorial-api`, remoto `origin`, `origin/main` e `origin/HEAD -> origin/main`. Não foi feito fetch nesta etapa; verificar o remoto em G1. Nenhum commit, push ou PR foi executado por esta rodada documental.

## O que funciona

- Streamlit cria/revisa jobs pelo mesmo `app/service.py` usado na API local v1. Bearer e exposição local na API; UI acessível também por Tailscale privado.
- Worker único, Redis, checkpoints e JSON com troca atômica/retry de rename Windows. Recuperação não equivale a coordenação multiworker ou proteção contra queda de energia.
- Whisper CPU guarda segmentos/palavras em `data/work/<id>.transcript.json`. Qwen pode descobrir propostas e classificar shortlist; diretor sugere título, zoom e B-roll validado.
- MP4 mestre e WebM, decode completo, duração, resolução, áudio, silêncio/preto contextual. Retry limitado por candidato preserva irmãos válidos.
- Remotion/high e legendas karaoke foram aprovados visualmente. A variante `700982a4-ca3d-4f4a-be5f-887d9cf08a29` foi aprovada com título humano e cauda suave. **Estes estilos devem permanecer.**
- 140 testes passaram nesta investigação: código montado somente leitura, sem rede, `DATA_DIR` efêmero e cache pytest desativado. Comando exato no HANDOFF. Isso não valida qualidade editorial.

## Casos reais prioritários

Índices mostrados ao usuário abaixo começam em 1; a API atual usa zero. O snapshot JSON guarda os índices originais zero-based, comentários integrais, revisões e hashes dos registros consultados.

| Job completo | Candidatos e evidência | Regressão a preservar |
|---|---|---|
| `58924b9a-dedf-4f56-ab6d-10b25f1240b5` | C1/C3 “bom”; C2 “bom, fechamento precisa melhorar” | C2 39,96–70,25 s termina em “tipo, sei lá”; a explicação continua na fonte |
| `ae34ddee-0e98-4bba-9984-0ce95fd48abe` | C1/C2 recusados por relevância; C3 “bom” | Job APPROVED contém recusas; narrativa sobre bastidores não garante interesse no jogo |
| `4cb53aa0-ad5f-4762-8c44-5fbface0f77f` | C1/C2 aprovados com problema de encerramento; C3 aprovado com problema de enquadramento | C1 título `"0"`; C3 344,4–375,66 s corta antes da demonstração em tela cheia; crop perde a página |
| `b82453d3-e032-482c-80cc-f5e782622cdb` | Três aprovados com ressalvas de final; apenas C1 tem `rework=true` | C2 corta na referência à seção de suporte; C3 termina enquanto aponta detalhes. C1 tem timestamp de 6,48 s para “19th.”, que exige verificação, não diagnóstico automático do áudio |
| `f6b1c5c5-fb6b-429a-8b79-819fb86097bc` | C1 recusado: fala da live; C2 recusado: corta quando começa jornalista; C3 “dos 3 foi o melhor, mas não está muito bom não” | Preferência relativa não é qualidade absoluta; C2 76,86–120,76 s termina em “ele é…” |
| `8b572e41-35b5-4007-a456-1a3d9f20ee8a` | Diagnóstico anterior da mesma fonte de f6; C3 aprovado com ressalva de enquadramento | Classificador usou fallback; C3 120,76–165,74 s mostra publicação de Tom Warren, mas crop esconde parte dela. Não é sexta fonte independente |

Os cinco primeiros jobs têm 15 candidatos: 11 APPROVED legados, 4 REJECTED; 3 comentários apenas “bom”, 6 aprovações com problema de finalização, 1 com problema de enquadramento e 1 aprovação relativa fraca. Esta classificação de ressalvas é **leitura do auditor**, não anotação confirmada para ML. Nenhuma nota numérica foi preenchida. Os seis jobs da coorte, incluindo diagnóstico, representam cinco fontes e 18 saídas, com duplicação de alguns intervalos.

Outras referências: `7cb2fb21-353c-4805-9fbb-b3c10603be44` (referência visual original aprovada); `77b79d5e-c999-45bf-86ee-a4ddfacaaf6e` / `90dda26b-ae0d-4ee1-8b3f-643c554eb078` (mesmo minuto, mesmo candidato; não demonstram superioridade editorial de modelo); 18 recusas administrativas em [user-rejections.json](../../../research/sprint/user-rejections.json).

## Matriz diagnóstico → código → validação

| Achado | Arquivo/função verificados | Testes existentes e teste futuro |
|---|---|---|
| Recusas escondidas em jobs aprovados | `app/service.py:review_candidate`, `review_job`; `app/ui.py:grouped` | `tests/test_review_actions.py`, `test_editorial.py`; M2: filtro individual com job misto |
| Aprovações com ressalvas não viram automaticamente retrabalho | `app/editorial.py:validate_decision`, `summarize`; UI expander opcional | M0/M1: legado com `rework=false` continua não qualificado |
| Modelo não vê todo o final | `app/core.py:propose_clips` e `app/ranker.py:propose_from_transcript` guardam `text[:700]`; `rerank_with_ollama` usa esse texto; `app/director.py:direct_edit` recebe `clip.text` | `tests/test_ranker.py`, `test_pipeline_benchmark.py`; M3: conteúdo final >700 caracteres aparece no contexto |
| Fade não resolve história incompleta | `app/edit_render.py:apply_finishing`; `app/timeline.py:build_timeline` | `tests/test_edit_render.py`; M4: promessa sem demonstração não passa como fechamento adequado |
| Título `0` aceito | `app/timeline.py:build_timeline`, teste lexical permite conjunto significativo vazio | `tests/test_timeline.py`; M3: rejeitar título só numérico, preservar “GTA 6” válido |
| Crop central perde conteúdo | `app/core.py:render`, `app/edit_render.py:render_edited`; `renderer/src/vertical-clip.tsx` | `tests/test_edit_render.py`; M5: ROI/site preservado em fixture com texto nas bordas |
| Apenas um intervalo e máximo 60 s | `app/timeline.py:MAX_CLIP_SECONDS`, `source_range`; `app/core.py:render`; `app/job_settings.py:RANGES`; `contracts/timeline.schema.json`; `renderer/src/index.tsx` | `tests/test_timeline.py`, `test_core.py`; M6: duração soma intervalos, palavras e áudio remapeados |
| Parecer/score do modelo não é qualidade confirmada | `app/core.py:propose_clips` calcula o campo `score`; `app/ranker.py` preserva score e admite cobertura heurística; UI exibe parecer genérico | M2/M4: distinguir score heurístico, ordem do modelo e avaliação humana |
| Feedback não alimenta ranker | `app/editorial.py` separado; `app/ranker.py:select_highlights` não consulta decisões | `tests/test_editorial.py`; M8: apenas exemplos confirmados elegíveis e de outra fonte |
| Aprovação não tem identidade de render na requisição | `app/service.py:review_candidate` verifica revisão do histórico; `invalidate_approvals` não é revisão de arquivo | M1: callback/revisão de artefato antigo deve falhar após nova renderização |

## Fontes locais e limites da evidência

Todos os caminhos acima são relativos à raiz. Também verificados: `app/candidates.py`, `app/quality.py`, `app/store.py`, `app/queueing.py`, `app/signals.py`, `app/api.py`, `app/ui_settings.py`, `app/llm_routing.py`, `app/kepler_bridge.py`, `contracts/api-v1.openapi.json`, `contracts/youtube_ingest.schema.json` e `renderer/package.json`.

Os [resultados GPU](../../../research/TESTES_GPU_5_VIDEOS_2026-11-06.md), [corpus](../../../research/CORPUS_PILOTO_12_RESULTADOS.md), [recuperação real](../../../research/sprint/recovery-real.json) e [benchmark ASR](../../../research/sprint/asr-base.json) são evidências históricas delimitadas. A revisão anterior comparou quadros e transcrições, sem transcrever novamente cada áudio nem verificar os fatos narrados. Não tratar esses vídeos como informação factual comprovada sobre lançamentos.

Nenhuma mudança nova foi implementada nesta preparação. Os contratos v2, módulos novos e testes nomeados nos próximos documentos são **propostas**, não arquivos/runtime já existentes.
