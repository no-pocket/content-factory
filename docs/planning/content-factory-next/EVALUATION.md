# Avaliação reproduzível e contribuição de cada mudança

As métricas de avaliação e a coleta humana são compartilhadas pelo produto; CLIs de dataset, experimentos de recuperação/ML e suas dependências são implementados somente em `codex/editorial-learning`. Ver G1 e M7–M10 no plano.

## Baseline e populações

Baseline de engenharia: código/worktree descrito em CURRENT_STATE, eventos originais e os 15 candidatos do snapshot. Comparação humana disponível: 11 aprovações binárias, oito com ressalvas interpretadas na auditoria, quatro recusas. **Não calcular Acceptance@3 limpo/condicional v2 a partir dessa interpretação.** Esses rótulos exigem confirmação; agora são desconhecidos. Os 18 jobs administrativos não compõem exemplos negativos independentes.

Congelar `experiment_id`, `comparison_set_id`, famílias de origem, pool, ordem, fonte/transcrição, artefatos e versões. Um vídeo pode ter várias execuções; conta uma vez por condição/experimento. Não misturar o teste curto do mesmo minuto com cinco fontes completas para calcular rendimento diário.

## Métricas e denominadores exatos

Para cada consulta `v` (família + objetivo + pool/versão), considerar os três primeiros resultados apresentados, `K=3`. Uma consulta com menos resultados tem slots faltantes iguais a zero nas métricas de rendimento; não fabricar candidatos para preenchê-los. Consultas com avaliações humanas pendentes/desconhecidas não entram na estimativa editorial principal; informar sua quantidade e cobertura sobre **todas** as consultas geradas.

| Métrica | Definição |
|---|---|
| Acceptance@3 sem ajustes | Média por consulta de `n(APPROVED v2 no top3, artefato atual) / 3` |
| Acceptance@3 com ajustes | Média de `n(APPROVED_WITH_ADJUSTMENTS no top3) / 3`, separada da anterior; cumulativa limpa+condicional recebe nome explícito |
| Aprovados por vídeo | Contagem média limpa e condicional, separadas; equivale a 3×as taxas acima na mesma população |
| Hit@3 opcional | Fração de consultas com ao menos um aprovado limpo; não chamar essa métrica de Acceptance sem qualificador |
| Precision@3 | Fração dos três slots com `content_grade>=2`, somente onde relevância humana está confirmada; grade ausente exclui consulta, não vira 0 |
| NDCG@3 | Grau humano 0–3 como ganho **linear**; DCG=`sum(g_i/log2(i+1))`; normalizar pelo ideal do mesmo pool. Pool com grau desconhecido ou IDCG=0 é não elegível; informar quantos foram excluídos. Empates de score usam média, não ordem arbitrária |
| Rejeição por motivo | Candidatos REJECTED com motivo confirmado / candidatos revisados elegíveis. Multirrótulo pode somar >100%; mostrar também cobertura de motivos e visão editorial/técnica separada |
| Problemas de fechamento/enquadramento | Candidatos revisados com códigos correspondentes confirmados / revisados com avaliação dessa dimensão. Relatar também taxa sobre todos revisados e cobertura; não confundir ausência de tag com ausência do problema |
| Tempo médio de revisão | Soma de tempo ativo instrumentado / sessões concluídas com medida. Idle proposto >60 s não conta como ativo; registrar wall time à parte. Legado desconhecido é null |
| Ajustes por vídeo | Pedidos distintos de edição por família/condição, dedup por `edit_id`; solicitado e resolvido separados. Comentário repetido ou histórico copiado não aumenta contagem |
| Preferência A/B | Vitórias A/B/empates/sem decisão em pares do mesmo objetivo; taxa de vitória entre pares não empatados mais tabela completa. B pode ser o melhor e continuar abaixo do padrão absoluto |
| Evolução por versão | Mesma população pareada ou curva estratificada por idioma/tipo/brief; mostrar diferenças de composição da amostra |

Confiabilidade operacional fica em painel próprio: jobs/candidatos tentados, backend solicitado/resolvido, respostas inválidas/truncadas, fallback por fase, QC, retries, latência por etapa, bytes e RAM/VRAM medida/amostrada. Candidato com falha técnica não é exemplo de irrelevância; excluir da avaliação de render assistido exige registrar exclusão para não favorecer configuração que falha mais.

## Splits e deduplicação

1. Construir famílias transitivas por parent/proveniência, mesmo conteúdo e aliases confirmados, antes de sortear splits. Excertos de `7cb2fb21` e seus descendentes ficam juntos, mesmo com hashes de arquivo diferentes.
2. Dataset do estágio B propõe 15 famílias intocadas de holdout e desenvolvimento com GroupKFold de cinco grupos, quando as classes/idiomas forem representados. Se não forem, coletar dados ou reduzir escopo declarado; nunca sortear candidatos da mesma fonte entre treino/teste.
3. Ajustar imputer/scaler, exemplares recuperados, modelos e thresholds somente em treino/desenvolvimento. Fechar seleção de método antes de uma avaliação do holdout.
4. Para histórico de preferências, usar cutoff temporal e brief compatível. Eventos posteriores ao teste não podem explicar retrospectivamente sua própria seleção.
5. Detectar duplicatas por identidade de candidato/artefato/tarefa. Eventos copiados em snapshots antigos e múltiplos pares da mesma fonte não aumentam N independente. Guardar auditoria das exclusões, sem apagar originais.

## Experimentos por componente

| Experimento | Manter fixo | Variar e medir |
|---|---|---|
| Contexto completo | Modelo, pool, brief e renderer | Envelope de contexto; medir identificação de fechamento e escolhas |
| Relevância/brief | Modelo, fonte, pool e edição | Versão do brief, depois exemplos em ensaio separado |
| Recuperação lexical × embeddings | Mesmos dados elegíveis, orçamento e Qwen | Seletor de exemplos; medir utilidade dos recuperados e saída final |
| Reranker B | Pool/feature extractor/brief/render idênticos | Ordem produzida; avaliar top3 sobre pool totalmente julgado, não só aprovados do baseline |
| Fronteira final | Mesma história/objetivo e enquadramento | Limite semântico da janela; medir promessa entregue, fala completa e duração |
| Enquadramento | Mesmos intervalos/palavras/efeitos/qualidade | ROI/layout; avaliar informação visual preservada |
| Efeito de acabamento | Mesmos intervalos e frames | Fade/cauda, sem atribuir melhoria à compreensão do conteúdo |
| Montagem | Mesmo objetivo e insumos | Contínuo × multitrecho, explicitando mudança de duração e efeitos de interação |
| Hermes | Mesmo brief, contexto completo e evidências disponíveis | Processo local × local+crítica; registrar modelos, modalidades, chamadas, custo e tempo adicionais |

Mudanças simultâneas exigem ablação ou análise explícita da interação. Comparar FFmpeg simples com Remotion/GPU e atribuir o ganho ao Qwen é inválido. Se Hermes receber frames e o baseline só texto, o resultado é do processo assistido, não superioridade isolada de modelo.

## Gates de aceitação/promoção

- M0–M2: invariantes de contrato, migração e filtros devem passar integralmente; nenhuma reclassificação humana silenciosa ou aprovação de arquivo antigo.
- M3–M6: regressões sintéticas e reais autorizadas com contexto/legendas/ROI corretos; QC dos dois formatos, reprodução e aprovação humana antes de promover novo estilo/regra. Não regenerar o corpus inteiro para cada ajuste.
- Estágio A com a amostra atual: piloto opt-in e resultados descritivos por fonte. Sem IC confiável ou alegação de generalização em cinco fontes.
- B: atender dados de EDITORIAL_LEARNING, registrar modelo/hiperparâmetros antes do holdout; delta pareado de Acceptance@3 limpo positivo, IC bootstrap **por família** 95% com limite inferior >0; sem falha crítica de mídia e sem regressão de idioma/motivo acima da margem acordada. Proposta de margem de qualidade por idioma: 5 pontos percentuais; cobertura insuficiente impede promoção, não autoriza ignorar EN.
- Revisão humana explícita do relatório e ativação. Se o conjunto for pequeno ou IC amplo, manter baseline e coletar mais dados. Contagem mínima não garante poder estatístico.
- C: estudo separado autorizado após B, demonstração de limitação persistente, dados/infrastrutura/orçamento confirmados. Não desbloquear só por disponibilidade de LoRA.

Guardar relatório com população, exclusões, outputs/versões, exemplos recuperados, sementes, tempos, hashes e decisão de promoção/rejeição. Rollback aponta para política/modelo anterior; nunca reescreve métricas antigas com o modelo novo.

## Casos que obrigatoriamente entram nos testes

Mistura aprovado/recusado num job; legado `rework=false` com ressalva; melhor relativo entre ruins; recusa por crop sem rótulo de conteúdo; ação administrativa repetida; filho/excerto no grupo do pai; novo render com revisão humana inalterada; callback antigo; nenhum positivo limpo; IDCG=0; pool de dois itens; grau ausente; score empatado; feature ausente; recuperação do próprio vídeo; prompt sem orçamento; mudança de idioma; cópia de histórico; política revogada; confirmação humana posterior ao cutoff.

Referências primárias: [GroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html) mantém grupos não sobrepostos; [NDCG](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html) documenta tratamento de empates. As escolhas de população e gates deste documento são decisões propostas do projeto, não conclusões desses documentos.
