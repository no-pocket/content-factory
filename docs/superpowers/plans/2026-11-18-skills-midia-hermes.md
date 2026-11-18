# Plano de integração de skills de mídia ao Content Factory e Hermes

**Objetivo:** melhorar a escolha e o acabamento dos cortes com curadoria Hermes e análise local, mantendo revisão e publicação sob controle do usuário.

**Arquitetura:** Hermes propõe ideias, direção, trechos e legendas; Content Factory valida o plano, processa a mídia local, renderiza MP4/WebM e apresenta evidências na revisão. O processamento por job continua assíncrono, versionado e recuperável; fontes e transcrições são dados, não instruções.

**Tecnologias:** Python, faster-whisper CPU, FFmpeg/ffprobe, Remotion, React, Redis e API Hermes. A K4200 segue opcional onde já há suporte validado; não presumir CUDA atual ou NVENC. Não instalar as skills externas diretamente no Pi nem executar scripts de instalação de terceiros.

## Fontes examinadas e política de uso

- [zaddy99999 — snap-to-words](https://github.com/zaddy99999/video-editing-skills/blob/e2b8e1c3d1685de0a4f3d00efbf758988244c492/skills/captions/scripts/snap-to-words.mjs): pausas entre palavras, limite de deslocamento e relatório. Código MIT.
- [heditor — prepare_cut](https://github.com/pycodebr/heditor/blob/fdb4a830a5732ee6264a5caae8b5b2835610b64/skills/heditor/scripts/reelkit/prepare_cut.py) e [asr_window](https://github.com/pycodebr/heditor/blob/fdb4a830a5732ee6264a5caae8b5b2835610b64/skills/heditor/scripts/reelkit/asr_window.py): energia local e retranscrição de janela. Código MIT; conferir assets separadamente.
- [vidmoat — legibilidade](https://github.com/vidmoat/skills/blob/ec2c2a944a2d4524d4b3affc6af315511946d6b5/skills/core/caption-styling/scripts/check_captions.py) e [gameplay](https://github.com/vidmoat/skills/blob/ec2c2a944a2d4524d4b3affc6af315511946d6b5/skills/vidmoat/gaming-editor/SKILL.md): código Apache-2.0 e texto CC BY 4.0; preservar NOTICE e atribuição quando houver cópia/adaptação.
- [agent-video-editor — shorts](https://github.com/kmilo93sd/agent-video-editor/blob/8e32c0aff64c445ef1e2b87bc04408a34d68c973/skills/editing-videos/recipes/shorts-from-long-form.md) e [licenças do áudio](https://github.com/kmilo93sd/agent-video-editor/blob/8e32c0aff64c445ef1e2b87bc04408a34d68c973/skills/editing-videos/library/LICENSES.md): critérios editoriais e assets CC0 declarados; código MIT. Confirmar origem de cada arquivo usado.
- [Melvynx — clips](https://github.com/Melvynx/video-agent-skills/blob/f4542923f7f796a1fa0e544cbfc1109d5eec87d8/skills/clips/SKILL.md): mapa de ideias e justificativa do corte. Código MIT. Não incorporar a regra de forçar um número mínimo de cortes.
- [prathameshp107 — plano de edição](https://github.com/prathameshp107/video-editing/blob/b344da99bfaeb496c048703b82bf1a034d732f2a/scripts/check_edit_plan.py): referência de relatórios; sem licença geral encontrada na raiz, confirmar antes de copiar.
- [OpenClip](https://github.com/OpenClip-App/agent-skills/blob/ea02c98db69c437616df1db4a4400cde1f4a0832/skills/openclip-clipping/SKILL.md) e [AutoShorts](https://github.com/Upload-Post/skill-autoshorts/blob/e902b2a8d9dcd0ee98e776b5e0455c6c1f30618a/autoshorts.py): referências de produto, não dependências deste plano. Exigem serviços externos; o último envia vídeo ao Gemini. Nenhum envio adicional é autorizado por este plano.

Usar ideias por implementação própria sempre que for mais simples; se houver cópia substancial, registrar versão, licença, atribuição e alterações. Não considerar dados de treino os candidatos apenas não publicados.

## Contratos e decisões gerais

- Preservar contratos v1, jobs/snapshots existentes, identidade da fonte, revisão e hash da transcrição, histórico e idempotência. Versões novas devem ser anunciadas na solicitação editorial; validador seleciona explicitamente por versão.
- `no_suitable_candidates` com plano válido é decisão editorial terminal; fallback local só por falha técnica, expiração ou plano inválido conforme política do job, com motivo por etapa. Não impor quantidade mínima editorial.
- Análise automática é evidência e sugestão, não prova de qualidade ou de permissões. Respeitar autorizações e políticas efetivas já salvas; não registrar autorização como confirmada sem evidência.
- Nunca aceitar shell, caminhos arbitrários, URLs de mídia ou efeitos livres produzidos por modelo. Medidas de áudio/vídeo têm limites de tempo e recursos; assets usam IDs locais validados e licenças registradas.
- Avaliação, aprovação, agendamento e publicação são ações separadas. Não publicar nem criar jobs reais apenas para testes. Não treinar ou promover modelo automaticamente.

## Entrega 0 — baseline e fixtures

**Arquivos:** `docs/TEST_PLAN.md`, `tests/fixtures/editorial/`, testes já existentes de `editorial_plan`, `editorial_requests`, `assembly`, `quality` e `frame_analysis`.

- [ ] Registrar commits/fontes externos e inventariar os presets e evidências que o código atual realmente suporta; não copiar dados pessoais ou vídeos ao Git.
- [ ] Criar fixtures sintéticas para frase completa, início dependente de contexto, final incompleto, pausas intencionais, ASR sem palavras, palavra de duração zero e falas com ruído.
- [ ] Registrar baseline de evidências e tempo de execução com CPU/worker atual; selecionar depois uma fonte real previamente autorizada para aceitação humana, sem iniciar job por conta própria.
- [ ] Executar testes focados existentes; documentar qualquer falha preexistente. **Aceite:** baseline reproduzível, sem alterações em jobs de produção.

## Entrega 1 — briefing editorial do Hermes

**Referências:** Melvynx, agent-video-editor e vidmoat. **Arquivos:** `integrations/hermes/nopocket-content/skills/content-editorial/SKILL.md`, `integrations/hermes/nopocket-content/skills/content-editorial/scripts/editorial_runner.py`, `app/editorial_requests.py`, `contracts/editorial-plan-v1.schema.json`, testes de runner/planos.

- [ ] Inventariar o prompt efetivamente montado para executor automático e para tópico; atualizar ambos de forma coerente, sem tratar transcrição como instrução.
- [ ] Solicitar a Hermes justificar início autossuficiente, contexto, desenvolvimento e fechamento; sinalizar dependência visual/HUD, afirmação incerta e palavras/números de baixa confiança. Não inventar transcrição nem presumir frames vistos.
- [ ] Usar `intent` e `risks` já existentes para primeira versão; gerar legenda social quando suportado pelo contrato existente, sem inventar novos campos aceitos por v1. Resultado válido sem cortes permanece válido.
- [ ] Testar prompt/serialização e validação em fixtures; registrar versão do protocolo/solicitação sem capturar segredos. **Aceite:** plano v1 continua válido e a curadoria informa razões e riscos verificáveis sem forçar cortes.
- [ ] Após testes, atualizar apenas seção pertinente da skill no Pi com backup privado, comparar versão instalada, preservar personalizações e validar acesso autenticado; comunicar contrato e limitações ao tópico quando solicitado.

## Entrega 2 — proposta de bordas com evidência

**Referências:** zaddy e heditor. **Arquivos:** novo `app/boundary_suggestions.py`; integração em `app/editorial_requests.py`, `app/worker.py`, `app/hermes_api.py`, `app/web_api.py`; testes novos e de worker.

- [ ] Definir resposta versionada por borda: tempo original, tempo sugerido, deslocamento, método (`word_gap`/`audio_valley`), confiança, intervalo analisado e motivo; limitar janela e deslocamento por configuração validada.
- [ ] Usar intervalos entre palavras apenas quando tempos são utilizáveis; medir vales do áudio numa janela curta em CPU, considerar início/fim da mídia e preservar duração permitida. Sem evidência confiável, manter proposta original e marcar ausência de sugestão.
- [ ] Garantir que uma sugestão nunca seja aplicada silenciosamente: decisão editorial registrada ou confirmação humana no editor; não alterar plano aprovado ou artefato já aprovado. Registrar antes/depois e método.
- [ ] Testar fala contínua, palavras sobrepostas/ausentes/zero, início/fim, limites, timeout, silêncio e mudança de frase; confirmar que o ajuste não invade outra palavra confiável nem extrapola a origem. **Aceite:** sugestões reproduzíveis e auditáveis; nenhum reprocessamento automático.

## Entrega 3 — QC de legibilidade e evidência visual

**Referências:** vidmoat, zaddy, heditor e prathameshp107. **Arquivos:** `app/quality.py`, `app/frame_analysis.py`, `app/timeline.py`, `app/candidates.py`, `frontend/src/Review.tsx`, `tests/test_quality.py`, `tests/test_frame_analysis.py`, testes de frontend.

- [ ] Acrescentar métricas por bloco: caracteres/segundo, comprimento e duração, sobreposição e saída fora da timeline; limiares configuráveis e alertas, sem adaptar silenciosamente texto falado.
- [ ] Gerar em modo local quadros em pontos representativos, especialmente abertura, fechamento e transições; indicar origem e timestamp e apresentar na revisão sem transferir arquivos externos. Reutilizar extração existente e limitar armazenamento.
- [ ] Examinar loudness/true peak e congelamento como indicadores opcionais; silêncio, preto e freeze podem ser intencionais e não viram falha editorial automática. Não tratar legibilidade medida como prova de fidelidade da transcrição.
- [ ] Testar fixtures com texto rápido, campos ausentes, frames não disponíveis, áudio ausente e pausas intencionais; garantir MP4 e WebM reproduzíveis. **Aceite:** alertas com tempo e evidência na UI; QC técnico existente e aprovação não são enfraquecidos.

## Entrega 4 — múltiplos trechos no plano Hermes

**Referências:** heditor e Melvynx. **Arquivos:** novo `contracts/editorial-plan-v2.schema.json`, `app/editorial_plan.py`, `app/editorial_requests.py`, `app/assembly.py`, `app/timeline.py`, `app/candidates.py`, `renderer/src/vertical-clip.tsx`, testes de plano, montagem e render.

- [ ] Projetar v2 com lista ordenada de trechos e âncoras, tempos de origem inteiros em ms, direção limitada, riscos e identidade/revisão; negociar a versão com executor e tópico. Manter v1 exatamente legível e executável.
- [ ] Validar cada segmento contra mídia e transcrição, ordem, sobreposição, duração final, quantidade e política do job; calcular timestamps da timeline e mapear legendas sem repetir ou cortar palavras. Respeitar limites e restrições já existentes da montagem v3, inclusive teto de duração: se forem insuficientes, especificar e testar alteração antes de ampliar.
- [ ] Sem suporte de vídeo/legenda suficiente, recusar com código objetivo e manter original; sem usar fallback para discordância editorial. Proibir caminhos ou transições arbitrários e não adicionar B-roll nesta entrega.
- [ ] Testar dois trechos, limites inválidos, âncoras trocadas, ordem, frames, palavras nas junções, rejeição de campos extras e compatibilidade v1; render sintético FFmpeg/Remotion e verificar hash, duração, MP4/WebM e sincronia. **Aceite:** proposta v2 vira candidato revisável; não altera candidato anterior.

## Entrega 5 — presets e assets autorizados

**Referências:** agent-video-editor e heditor. **Arquivos:** `app/asset_library.py`, `app/director.py`, `app/timeline.py`, `renderer/src/vertical-clip.tsx`, interface da biblioteca e testes.

- [ ] Criar catálogo pequeno de presets fechados de título e legendas e, se aprovado, registrar poucos efeitos como assets com ID, origem, licença e finalidade; validar material efetivo antes de incluir. Nenhum download automático de conteúdo de terceiros.
- [ ] Hermes pode sugerir IDs/presets disponíveis, sem caminhos ou URLs; Content Factory valida existência, autorização e limites de tempo. Não inserir música/efeito de forma automática no vídeo já aprovado.
- [ ] Testar asset ausente/revogado, texto longo, área segura, compatibilidade e reprodução. **Aceite:** sugestões editáveis e rastreáveis; nova renderização gera novo artefato e exige nova aprovação.

## Verificação final e implantação

- [ ] Rodar testes focados e suíte proporcional conforme `docs/TESTES.md`, `git diff --check` e ensaio da interface com agent-browser; se indisponível, registrar alternativa e evidência. Testes devem usar fixtures isoladas.
- [ ] Avaliar ao menos uma fonte real autorizada após seleção explícita: comparar versões anteriores e novas com tempos, transcrição, bordas, sincronia, legibilidade, custo e tempo; conferir reprodução de MP4 e WebM. Não usar aprovação ou publicação real como teste.
- [ ] Antes de deploy, inspecionar jobs ativos, fila, configuração e armazenamento; não reiniciar durante render/download. Implantar apenas componentes necessários, preservar volumes e `.env`, verificar versão e consulta autenticada pela ponte.
- [ ] Atualizar instruções do Hermes no Pi com backup; validar pedido editorial real quando o proprietário fornecer fonte; informar limitações e motores/fallback por etapa. Não enviar credenciais nem dados locais ao GitHub.

**Fora de escopo inicial:** instalar terceiros diretamente, trocar o renderizador, migrar toda a biblioteca, enviar vídeos ao OpenClip/Gemini, publicar automaticamente ou avaliar qualidade só por métricas de retenção.

## Progresso de execução

- Baseline isolado: 70 testes de contratos, montagem, QC e análise visual passaram.
- Briefing v1.1: critérios editoriais acrescentados ao executor e à skill local; testes focados passaram. Implantação no Pi pendente: havia solicitação editorial ativa na verificação.
- Bordas: sugestões por intervalos de palavras e vales de energia disponíveis no editor como rascunho, com confirmação antes de gerar novo render. Falta validar interface e mídia reais, limites de duração e timeouts em cenários adicionais.
- QC: alertas consultivos de caracteres/segundo e extensão por bloco adicionados; amostragem passou a considerar início, fim e transições. Falta validar render real, medições opcionais de loudness/true peak e congelamento.
- Contrato Hermes v2 para múltiplos trechos e catálogo de presets/assets: ainda não implementados.
- Nenhuma das alterações desta execução foi implantada; o worker tinha um job em transcrição, um na fila e uma solicitação editorial pendente.
