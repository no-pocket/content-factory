# Testes e validação

## Suíte automatizada

Na workstation, a imagem já construída do worker contém pytest e dependências. Rode os testes sem build novo:

```powershell
docker run --rm -v 'E:\CodexFiles\content-factory\content-factory:/workspace' -w /workspace -e PYTHONPATH=/workspace --entrypoint python content-factory-worker:latest -m pytest -q --tb=short --basetemp=/workspace/research/pytest_temp_full
docker compose -f compose.yaml -f compose.kepler.yaml config --quiet
git diff --check
```

O primeiro comando usa o código atual montado do repositório. O diretório temporário é ignorado pelo Git. Na versão 4.1.0, **92 testes passaram**. Eles cobrem configurações por job, fila e recuperação, ranker/diretor, contexto e respostas incompletas da ponte GPU, timeline, render sintético, prévia WebM, Doctor, UI e ingestão autorizada.

Para qualquer bug novo ou feature, acrescente um teste que falhe antes da correção e passe depois. Testes unitários não demonstram que um navegador consegue reproduzir o arquivo, nem que a edição é boa; use as verificações abaixo para esses riscos.

## Teste com vídeo real autorizado

Há um arquivo de teste em `E:\CodexFiles\content-factory\_videos_test\videoplayback.mp4`. Crie um job pela interface com os ajustes desejados; aguarde `NEEDS_REVIEW`. Confira quantidade de candidatos, `ranker_used`, `director_used`, `renderer_used`, timeline e legendas. Reproduza cada prévia até o fim e abra cada MP4 baixado. Não trate `NEEDS_REVIEW` como aprovação editorial.

Para um job já existente, confirme decodificação completa dentro do worker (substitua o ID):

```powershell
$jobId = '530ade0e-7027-46ff-8173-5da8e5166ef4'
1..3 | ForEach-Object {
  docker exec content-factory-worker-1 ffmpeg -hide_banner -loglevel error -xerror -i "/data/output/$jobId/candidate_${_}.preview.webm" -f null -
  if ($LASTEXITCODE -ne 0) { throw "Prévia $_ falhou" }
}
```

O teste de navegador usa Firefox e Selenium instalados nesta workstation:

```powershell
$env:JOB_PREFIX = '530ade0e'
$env:PLAYBACK_RATE = '4'
python research/probe_firefox_playback.py
```

O script seleciona o job, verifica três fontes WebM e espera `ended` em cada vídeo; qualquer erro de mídia falha o teste. Em 05/11/2026, os três candidatos desse job terminaram sem erro. O teste verifica essa amostra, não todos os futuros jobs.

## Ponte GPU ao vivo

```powershell
Invoke-RestMethod http://127.0.0.1:11436/health
Invoke-RestMethod http://127.0.0.1:11436/api/ps
```

Além da saúde, uma geração curta deve retornar `done_reason=stop`, `prompt_truncated=false` e `context_window=4096` na configuração atual. Um pedido com `options.num_ctx=8192` deve receber HTTP 422. A suíte unitária cobre os mesmos limites sem exigir GPU; o teste ao vivo detecta divergência do servidor em execução.

## Critérios antes de publicar uma versão

1. Suíte completa e configuração Compose passam.
2. Serviços e GPU opcional ficam online após reinício.
3. Um job real chega a `NEEDS_REVIEW` com o número esperado de candidatos; todos os WebM terminam no navegador e todos os MP4 abrem.
4. Fallbacks aparecem com motivo, sem aceitar JSON gerado a partir de contexto/resposta incompletos.
5. Versão visível na UI, dados persistentes preservados e diff revisado.

Veja [Plano de aceitação](TEST_PLAN.md) para conferência manual de direitos, B-roll, legendas e aprovação.
