# Contratos propostos e migração

**Status:** especificação para implementação, não schema/runtime já ativo. M0 materializa validadores/fixtures; M1 ativa persistência opt-in. Campos desconhecidos e números não finitos são recusados nas entradas novas. Texto tem limite explícito e permanece dado não executável.

## Identidades

| Identidade | Regra |
|---|---|
| `source_id` | SHA-256 dos bytes originais; não confundir arquivo recortado com fonte independente |
| `source_group_id` | Família transitiva de `source_parent_job`, mesmo hash e aliases/duplicatas confirmadas. Bloqueia vazamento de trechos/variantes; desconhecido impede treino/teste |
| `candidate_id` | UUID estável da proposta/história. Para legado: UUIDv5/NAMESPACE_URL de `content-factory:{job_id}:{original_index}`; nunca recalcular pelo índice reordenado da UI |
| `candidate_version` | Inteiro crescente quando muda plano/intervalo/composição; referência ao pai |
| `render_revision` | Inteiro crescente por saída renderizada; mestre/prévia/timeline imutáveis e hashes registrados |
| `artifact_id` | Digest de manifest canônico que referencia hashes do MP4, WebM e timeline. Mesmo índice com bytes diferentes tem outra identidade |
| `comparison_set_id` | Pool de opções apresentado para o mesmo objetivo/brief. Necessário para preferências relativas e qid de ranking |
| `event_id` / `request_id` | Evento imutável / idempotência da ação. Mesmo request e corpo retorna o resultado; corpo diferente com mesma chave é conflito |

IDs e resolução de caminhos são controlados pelo backend. Não aceitar paths produzidos por Qwen/Hermes/Telegram.

## Três eixos de estado

1. **Técnico:** conservar `candidate.state` (`UNVERIFIED`, `RENDERING`, `VALID`, `WARNING`, `FAILED`) e diagnósticos QC. O estado de processamento do job é independente da revisão.
2. **Decisão v2:** `PENDING`, `APPROVED` (sem ajustes), `APPROVED_WITH_ADJUSTMENTS`, `REJECTED`.
3. **Pendências:** operações de edição abertas/resolvidas por tipo/severidade e vínculo a versões. Resolver um ajuste não aprova automaticamente o render corrigido.

`get_editorial_view` fornece contagens por candidato e estado de revisão `PENDING|PARTIAL|COMPLETED`. Um job misto não recebe rótulo visual que sugira aprovação de todos. O campo legado `job.status` permanece como projeção compatível enquanto consumidores v1 existirem.

Para legado: `legacy_decision=APPROVED` continua visível como **“Aprovado — condição não confirmada”**, `normalized_decision=null`, `qualification_status=UNCONFIRMED_LEGACY`. Isso não vira PENDING nem aprovação limpa. Ausência de avaliação é PENDING; avaliação ligada a artefato invalidado é histórica e exige nova revisão.

## Evento humano v2

Exemplo **sintético** de aprovação condicionada:

```json
{
  "schema_version": "2.0",
  "event_id": "uuid",
  "request_id": "uuid",
  "event_type": "REVIEW_SUBMITTED",
  "job_id": "uuid",
  "candidate_id": "uuid",
  "candidate_version": 1,
  "render_revision": 1,
  "artifact_id": "sha256:manifest-digest",
  "editorial_revision": 4,
  "supersedes_event_id": null,
  "actor": {"kind": "human", "id": "local-owner", "channel": "streamlit"},
  "decision": "APPROVED_WITH_ADJUSTMENTS",
  "rejection_domain": null,
  "comment_raw": "SYNTHETIC: bom, mas encerra antes da demonstração",
  "reasons": [{"code": "INCOMPLETE_PAYOFF", "severity": "MAJOR", "confirmed_by": "human"}],
  "dimensions": {"relevance": 4, "hook": null, "context": null, "narrative": null, "proof": null, "closure": 2, "framing": null, "captions": null, "editing": null, "technical_quality": null},
  "content_grade": null,
  "relative_assessment": null,
  "edit_requests": [{"edit_id": "uuid", "type": "BOUNDARY_END", "status": "OPEN", "comment": "SYNTHETIC: preservar a demonstração"}],
  "review_timing": {"active_seconds": null, "wall_seconds": null},
  "versions": {"brief_id": "brief-v1", "brief_sha256": "digest", "component_snapshot_id": "digest"},
  "created_at": "UTC-ISO8601"
}
```

O exemplo mostra a forma; IDs/digests ilustrativos não passam no validador de produção. `comment_raw` preserva integralmente até 4.000 caracteres; sem tradução, resumo substitutivo ou score padrão. Data/ator/proveniência vêm do backend. Ratings são inteiros 1–5 ou null, todos opcionais. Grau de conteúdo, se preenchido, é inteiro 0–3 e confirmado pelo humano.

As dez dimensões são: relevância (`relevance`), gancho (`hook`), contexto independente (`context`), desenvolvimento (`narrative`), demonstração/prova (`proof`), fechamento semântico (`closure`), enquadramento (`framing`), legendas/transcrição (`captions`), edição/efeitos (`editing`) e qualidade técnica percebida (`technical_quality`). O QC automático fica em campo próprio e não preenche ratings humanos.

Motivos iniciais: `IRRELEVANT_CONTENT`, `CREATOR_SELF_PROMOTION`, `WEAK_HOOK`, `MISSING_CONTEXT`, `INCOMPLETE_PAYOFF`, `ABRUPT_ENDING`, `MISSING_DEMONSTRATION`, `BAD_FRAMING`, `IMPORTANT_CONTENT_CROPPED`, `CAPTION_ERROR`, `GOOD_CONTENT_NEEDS_REWORK`, `TECHNICAL_FAILURE`. Severidades: MINOR, MAJOR, CRITICAL ou null. A taxonomia tem versão; códigos não desaparecem de registros históricos.

Uma recusa informa `rejection_domain=EDITORIAL|TECHNICAL|ADMINISTRATIVE|MIXED|UNSPECIFIED`. Defeito técnico não implica conteúdo irrelevante. Para aprovação com ajustes, ao menos um pedido de edição aberto ou comentário de ajuste explícito é obrigatório; para APPROVED sem ajustes, nenhuma pendência MAJOR/CRITICAL pode permanecer aberta. QC válido/aviso continua obrigatório para aprovar. Recusar não exige mídia válida.

## Preferência relativa e sugestões automáticas

`relative_assessment` guarda `comparison_set_id`, `preferred_candidate_id`, alternativas, `all_options_below_bar`, comentário e confirmação humana. “Melhor dos três, mas ruim” gera uma sugestão de preferência, não `content_grade=3` nem positivo absoluto. Um par confirmado usa IDs/versões dos dois candidatos; empate e desconhecido não geram ordem artificial. Pares da mesma fonte continuam um único grupo estatístico.

Sugestões Qwen ficam em `feedback_suggestions`: `suggestion_id`, evento/comentário de origem e hash, versão do classificador/prompt, motivos/severidades sugeridos, status `PENDING|CONFIRMED|REJECTED`, ator da confirmação. Não alterar `comment_raw`, decisão, ratings ou motivos humanos ao gerar sugestão. A confirmação cria outro evento, não reescreve o original. Eventos automáticos não são rótulos de treino.

## Concorrência, API e compatibilidade

`review_candidate_v2(jid, candidate_id, request)` exige `request_id`, `expected_editorial_revision`, `expected_artifact_id` e conteúdo da avaliação. Sob o lock do job: verificar revisão/artefato, validar QC quando necessário, anexar evento e atualizar projeções numa única escrita atômica. Conflitos retornam 409 e pedem recarregar, sem registrar decisão parcial.

Interface REST proposta: `GET /v2/jobs/{id}` e `POST /v2/jobs/{id}/candidates/{candidate_id}/reviews`. A UI chama o mesmo serviço Python. Campos e erros devem constar de contrato v2 separado; preservar `contracts/api-v1.openapi.json` e semântica v1 para jobs legados.

Jobs novos opt-in guardam `editorial_protocol=2`; o v1 não pode aprová-los sem identidade de artefato: retornar 409 `editorial_protocol_required`, sem simular aprovação limpa. Implantação de M1 deve documentar esse limite e atualizar os clientes que ativarem v2. V1 legado permanece operacional e suas decisões continuam não qualificadas para aprendizado. Não desativar v1 globalmente.

Nova revisão técnica invalida a decisão atual daquele artefato, preserva evento/bytes anteriores e incrementa versão do render. Um callback Telegram de versão antiga deve falhar mesmo que a contagem de decisões humanas não tenha mudado.

## Migração conservadora

1. Criar inventário/dry-run com hashes, sem alterar jobs. Não inferir ratings pelo comentário.
2. Projetar legados em leitura: decisão original, condição não confirmada, índices/UUIDs determinísticos. Histórico continua fonte da verdade do legado.
3. Sugerir normalização de ressalvas/motivos, sempre pendente de confirmação humana. Os 18 jobs administrativos recebem escopo administrativo na análise/proposta, nunca negativos editoriais independentes por padrão.
4. Na confirmação explícita, anexar evento v2 apontando para evento legado e artefato visto; não modificar avaliação original. Sem confirmação, elegibilidade de alvo absoluto é UNKNOWN.
5. Antes de ativar escrita v2, backup/export verificável; rollback desabilita projeção nova sem apagar eventos nem interpretar APPROVED_WITH_ADJUSTMENTS como APPROVED limpo.

## Briefing e versões

`editorial_brief_v1.json` será artefato **novo e aprovado explicitamente**, em `data/editorial/briefs/`, não criado nesta etapa. Forma: `schema_version`, `id`, `parent_id`, `status=DRAFT|APPROVED|RETIRED`, `scope=GTA_VI`, prioridades, penalidades, regras de encerramento/prova, regras visuais/títulos, critérios de história completa, referências a feedback confirmado, autor e aprovação. Texto inicial: favorecer novidades/análises/descobertas/demonstrações; evitar autopromoção dominante; cumprir promessa; concluir a ideia; preservar informação visual; título apoiado em evidência; duração subordinada à história.

Atualizações são propostas com diff, exemplos que as motivaram e avaliação; aprovação humana e ponteiro ativo com revisão/lock. Rollback troca ponteiro para versão já aprovada. Brief não pode executar ações nem autorizar novas fontes externas.

Todo job novo resolve e salva: brief ID/hash/conteúdo, prompts de ranker/diretor/classificador ID/hash, modelo solicitado e efetivamente carregado/digest quando disponível, backend/contexto/opções, versão do ranker/regras/features/retrieval/dataset, transcript/source hash, renderer/timeline, Git HEAD **e hash do patch sujo**, versões de dependências conhecidas. Legados recebem `UNKNOWN` em projeção quando informação não foi registrada, sem preencher pela configuração atual.

## Dataset e montagem

Exemplo exportado: identidade/família, candidato/versões/artefato, pool e ordem original, eventos humanos elegíveis, comentários integrais, motivos confirmados, grau/pares opcionais, features pré-decisão/proveniência e versões. Manifest registra hashes, cutoff, critérios de inclusão/exclusão, contagens por fonte/idioma/classe, splits e parent dataset. Alvos descritos em EDITORIAL_LEARNING.

Timeline v3 proposta: uma origem autorizada, `segments=[{segment_id,source_in,source_out,output_start,purpose,framing}]`, duração final igual à soma dos segmentos mais acabamento explícito. Tempos em segundos com precisão definida, limites verificados por quadros. Ordem cronológica por padrão; reordenação precisa de validação editorial explícita. `map_words` aplica `output_start + source_word_time - source_in`; palavras parcialmente cortadas são recusadas, não silenciosamente encurtadas. Preservar sincronismo áudio/vídeo/legendas, direitos, versões e compatibilidade com timeline v2.
