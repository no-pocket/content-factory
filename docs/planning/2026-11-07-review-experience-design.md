# Revisão fluida e direção editorial

Proposta para aprovação do proprietário, 07/11/2026.

1. Corrigir conflitos entre candidatos: atualizar a revisão esperada quando
   somente outro candidato mudou. Manter conflito real no mesmo candidato/render,
   preservar comentário e oferecer recarregamento sem descartá-lo.
2. Reduzir leituras/hashes repetidos na navegação. A gravação continua verificando
   os bytes reais e a revisão sob lock; cache de apresentação nunca autoriza aprovação.
3. Notas opcionais por estrelas: dimensões1–5; grau de conteúdo0–3 com zero explícito
   e opção não avaliado. Tooltips explicam critérios, severidade e uso no dataset.
   Não inventar pesos: atualmente as dimensões não formam uma média decisória e o
   alvo proposto de ML usa content_grade>=2. Aprovação/recusa continuam explícitas.
4. Títulos com promessa concreta, curiosidade e assunto do corte, sem afirmação
   não demonstrada. Permitir paráfrase coerente; vocabulário literal sozinho não
   demonstra coerência. Preservar títulos/artefatos existentes até nova geração explícita.
5. Encerramento opcional por job, desligado inicialmente, com vídeo autorizado
   do proprietário. Gameplay/imagens sem áudio entram apenas de catálogo licenciado,
   mantendo a fala original. Duração final, legendas e QC abrangem o encerramento.
   O material ainda precisa ser fornecido e cadastrado; não sintetizar sua voz.
6. ML offline: revisão gera eventos versionados; exportação congela dataset e
   famílias de origem. Gates atuais:50 famílias independentes,150 candidatos
   elegíveis,30 positivos/30 negativos e15 famílias de holdout, cobertura PT/EN,
   configurações/brief válidos e aprovação explícita. Sem treino ou promoção automática.

Aceitação: revisar dois candidatos consecutivamente sem conflito artificial;
duas sessões no mesmo candidato ainda conflitam corretamente; comentários intactos;
UI com notas vazias distintas de zero; medições de navegação/gravação antes/depois;
teste de navegador sem criar avaliações falsas nos candidatos reais.
