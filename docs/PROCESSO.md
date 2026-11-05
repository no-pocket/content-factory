# Processo de produção: da fonte à aprovação

## 1. Entrada e configuração

A interface Streamlit (`app/ui.py`) e a entrada JSON (`app/submit.py`) criam o mesmo registro via `app/store.py`. `app/job_settings.py` valida e grava um snapshot dos ajustes por job. Portanto, Streamlit é uma interface substituível: um frontend novo deve enviar o mesmo objeto `settings` e ler os estados/artefatos documentados aqui. Não deve escrever diretamente na lista Redis sem criar e validar o registro.

Upload local copia o arquivo para `data/input/`. URL do YouTube é normalizada e fica desabilitada por padrão; direitos do titular e autorização aplicável da plataforma são declarados antes do download. O projeto não verifica licenças externamente.

## 2. Fila e transcrição

A UI enfileira o ID em `clips:queue`. O worker move o ID para `clips:processing` antes de executar e o remove quando o job chega a um estado terminal. Se o worker parar, a inicialização reenvia jobs não terminais da lista de processamento. Esta recuperação assume um único worker; não existe lease distribuído para vários workers.

`faster-whisper` extrai segmentos e palavras com tempos. O worker guarda a transcrição em `data/work/<id>.transcript.json`. Modelo, beam size e outras escolhas vêm do snapshot do job, com limites em `app/job_settings.py`.

## 3. Propostas e classificação

`app/core.py` cria candidatos heurísticos. `app/ranker.py` pode pedir propostas ao Qwen em amostras da transcrição, ancoradas por IDs de segmentos, e reordenar uma shortlist. O backend é escolhido por job: Ollama ou ponte Kepler K4200 (`app/llm_routing.py`). Toda saída do modelo é tratada como dado não confiável: IDs, duração e sobreposição são validados. Contexto excedido, resposta truncada, JSON inválido ou serviço indisponível acionam a heurística; eventos e motivo ficam no job.

A ponte GPU (`app/kepler_bridge.py`) usa o tokenizer do servidor para contar prompt com template, reserva a saída e recusa pedidos que não cabem no contexto real. Ela só aceita as opções Ollama implementadas e informa a razão de término. O modo GPU está sujeito aos limites em [GPU K4200](GPU_K4200.md).

## 4. Direção e timeline

Para cada corte, `app/director.py` pode pedir título, zooms e B-roll ao Qwen. `app/timeline.py` converte sugestões aceitas em timeline v2; impõe duração, tempos, texto ancorado na fala e IDs de assets licenciados. Falha do diretor gera uma timeline heurística válida. O contrato JSON está em `contracts/timeline.schema.json`.

## 5. Render e prévia

FFmpeg normaliza a fonte e o B-roll autorizado. Remotion compõe a versão animada. Se configurado, uma falha do Remotion usa FFmpeg com legendas simplificadas; o campo `renderer_used` informa qual caminho produziu o corte. O MP4 fica em `data/output/<id>/candidate_N.mp4`.

Depois do MP4, `app/edit_render.py` cria `candidate_N.preview.webm` com VP8/Opus, decodifica a prévia inteira e só então a publica para o navegador. A UI usa WebM para assistir e oferece MP4 separadamente para download. O JSON da timeline fica ao lado dos vídeos; a decisão de aprovação registra os índices aceitos, sem alterar os arquivos mestres.

## 6. Revisão humana e limites

`NEEDS_REVIEW` significa que a renderização terminou, não que o conteúdo esteja pronto para publicar. A pessoa revisa escolha do trecho, fatos, direitos, áudio, legendas e imagem. `APPROVED`/`REJECTED` são estados locais. Não há postagem automática nem edição manual de timeline pela UI atual.

As principais lacunas planejadas constam na [auditoria de produto](AUDITORIA_E_OPCOES_2026-11-04.md). Ela é histórica; fila, descoberta por transcrição, prévias e contrato GPU já receberam as mudanças descritas neste guia.
