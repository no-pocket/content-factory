# API local v1

`app/api.py` é o adaptador HTTP; `app/service.py` contém criação, fila, QC, retry e
revisão usados também por Streamlit e CLI. O worker mantém processamento pesado.
Contrato legível por ferramentas: [`api-v1.openapi.json`](../contracts/api-v1.openapi.json).
Persistência JSON existente é compatível; novos campos são aditivos. Legados exigem
QC explícito antes de nova revisão; aprovações anteriores são preservadas como legado.

## Execução

Configure `CONTENT_FACTORY_API_TOKEN` com pelo menos 24 caracteres aleatórios no
ambiente da sessão ou `.env` local (nunca no Git). Com serviços existentes e sem jobs
ativos, inicie **somente o serviço novo**, sem build/recriação dos demais:

```powershell
docker compose -f compose.yaml -f compose.kepler.yaml -f compose.api.yaml up -d --no-build api
```

Na validação desta sprint, o serviço foi iniciado com token local em `data/api.token`,
ignorado pelo Git. Para recriar o serviço mantendo essa credencial (sem imprimi-la):

```powershell
$env:CONTENT_FACTORY_API_TOKEN = [IO.File]::ReadAllText((Join-Path (Get-Location) 'data/api.token')).Trim()
docker compose -f compose.yaml -f compose.kepler.yaml -f compose.api.yaml up -d --no-build --no-deps api
Remove-Item Env:\CONTENT_FACTORY_API_TOKEN
```

Porta publicada: `127.0.0.1:8510`. Sem token, o processo recusa iniciar. Não exponha
Redis ou API publicamente. `Authorization: Bearer <token>` é necessário inclusive
para consultas e mídia. Sem CORS/cookies; POST com Origin é recusado. Outro frontend
deve usar backend/proxy local autenticado; não colocar token em bundle público.
O servidor é serial, adequado à operação local de um worker; não promete concorrência
de produção nem Range requests. Streamlit chama o serviço Python compartilhado para
evitar transportar uploads grandes por JSON.

## Rotas e códigos

| Método/rota | Resultado |
|---|---|
| POST /v1/jobs | 201 job completo; criação por URL ou upload base64 |
| POST /v1/jobs/upload | 201 job completo; vídeo bruto em streaming, até 2 GiB |
| GET /v1/jobs | 200 `{api_version:"1",jobs:[...]}` |
| GET /v1/jobs/{id} | 200 job, settings, candidatos, QC, histórico |
| POST /v1/jobs/{id}/review | 200 job atualizado |
| POST /v1/jobs/{id}/candidates/{index}/review | 200 revisão individual; comentário e notas opcionais |
| POST /v1/jobs/{id}/reject | 200 recusa do job inteiro com comentário |
| POST /v1/jobs/{id}/verify | 200 QC dos arquivos existentes; body `{}` |
| POST /v1/jobs/{id}/retry-enqueue | 200 reenvio de QUEUE_FAILED; body `{}` |
| POST /v1/jobs/{id}/candidates/{index}/retry | 202 retry apenas do índice; body `{}` |
| GET /v1/jobs/{id}/candidates/{index}/media/{kind} | bytes; kind mp4/webm/timeline |
| GET /v1/metrics | 200 métricas descritivas |

Índices são base zero. Criação aceita `Content-Type: application/json`; corpo total
máximo 64 MiB, portanto upload base64 suporta aproximadamente 48 MiB de mídia. Para
vídeos maiores use `/v1/jobs/upload` (até 2 GiB, equivalente ao limite do Streamlit).
Clientes devem respeitar os limites, não
enviar caminhos de arquivos locais. URL continua sujeita à confirmação do titular,
da plataforma e `ENABLE_YOUTUBE_DOWNLOAD` no worker.

```json
{
  "source_url":"https://youtu.be/ID_DE_11_CH",
  "creator":"Nome do canal",
  "license_note":"Referência real da autorização",
  "rights_confirmed":true,
  "platform_permission":true,
  "settings":{"clip_count":3,"llm_backend":"ollama"},
  "qc_settings":{"max_attempts":2,"silence_seconds":1}
}
```

Para upload, substitua `source_url/platform_permission` por `filename:"video.mp4"`
e `upload_base64:"..."`. Exemplo de resposta abreviada (IDs ilustrativos):

```json
{"api_version":"1","schema_version":"1.0","id":"UUID","status":"QUEUED",
 "approved":[],"candidates":[],"settings":{},"qc_settings":{},"decision_history":[]}
```

Os snapshots reais são completos. Campos de caminho de fonte/candidato não fazem
parte do contrato público de consumo; use rotas de mídia. Diagnósticos podem conter
caminhos locais e são dados privados para o cliente autenticado.

`settings.llm_model` aceita `qwen2.5:3b` ou `qwen2.5:1.5b` e é preservado por job.
O modelo precisa estar instalado; a API não baixa modelos. Na ponte GPU, o modelo
precisa corresponder ao que o servidor legado carregou; incompatibilidade aciona
fallback diagnosticado. `evaluation:{"cohort":"nome","variant":"baseline"}` é
metadado opcional para identificar lotes comparáveis (textos de até 100 caracteres).

Revisão precisa cobrir exatamente os candidatos VALID/WARNING disponíveis:

```json
{"expected_revision":0,"decisions":[{"candidate":0,"decision":"APPROVED",
 "hook":4,"context":4,"closure":5,"captions":3,"reason":"Motivo real do revisor",
 "rework":true,"adjustments":"Correção indicada pelo revisor"}]}
```

Exemplo sintético; não representa avaliação do corpus. Consulte
[QC](CONTROLE_QUALIDADE.md) para estados técnicos e [protocolo](PROTOCOLO_EDITORIAL.md)
para revisão, métricas e compatibilidade com decisões legadas.

Erros usam `{"error":{"code":"conflict","message":"..."}}`:
401 token ausente/incorreto; 403 direitos/Origin; 404 job/artefato/rota;
409 revisão desatualizada, estado incompatível ou limite de tentativas;
413 corpo fora do limite; 422 entrada/índice/configuração inválida;
503 fila indisponível (mensagem contém job_id recuperável); 500 erro interno.
Não repetir criação automaticamente após resposta ambígua: consulte a lista primeiro.
Criação não tem chave de idempotência nesta versão; retries de fila são explícitos.

Estados: QUEUED, DOWNLOADING, TRANSCRIBING, DIRECTING, RENDERING, NEEDS_REVIEW,
PARTIAL_FAILED, FAILED, QUEUE_FAILED, APPROVED, REJECTED. Clientes v1 devem tolerar
campos adicionais e apresentar estado desconhecido como diagnóstico, sem aprovar.
Mudanças incompatíveis exigirão novo prefixo de API. Nunca escrever diretamente em Redis.

## Upload grande sem base64 do vídeo

`POST /v1/jobs/upload` recebe `Content-Type: application/octet-stream` e exatamente
um `Content-Length`, de 1 byte a 2 GiB. Não aceita Transfer-Encoding/chunked. O vídeo
é copiado em blocos para o diretório de entrada, sem carregar o corpo inteiro na RAM.

O header `X-Content-Factory-Metadata` contém **Base64 de JSON UTF-8**, até 48 KiB de
header codificado. Campos: `filename`, `creator`, `license_note`, `rights_confirmed`,
`settings`, `qc_settings` e `evaluation` opcional. `source_url` e `upload_base64`
não são aceitos nessa rota. Direitos e configurações são validados pela mesma função
do Streamlit antes de gravar o vídeo. EOF prematuro/erro de leitura apaga somente o
arquivo parcial dessa tentativa e não cria job; envio completo registra SHA-256.

Exemplo de cliente Python (substitua os metadados ilustrativos pela autorização real):

```python
import base64, http.client, json, os
from pathlib import Path

path = Path('video.mp4')
metadata = {'filename': path.name, 'creator': 'Criador autorizado',
            'license_note': 'Referência real da autorização', 'rights_confirmed': True,
            'settings': {'clip_count': 3}}
headers = {'Authorization': 'Bearer ' + os.environ['CONTENT_FACTORY_API_TOKEN'],
           'Content-Type': 'application/octet-stream',
           'Content-Length': str(path.stat().st_size),
           'X-Content-Factory-Metadata': base64.b64encode(
               json.dumps(metadata, ensure_ascii=False).encode('utf-8')).decode('ascii')}
connection = http.client.HTTPConnection('127.0.0.1', 8510, timeout=120)
with path.open('rb') as video:
    connection.request('POST', '/v1/jobs/upload', body=video, headers=headers)
response = connection.getresponse()
print(response.status, json.loads(response.read()))
connection.close()
```

A resposta 201 tem o mesmo contrato de job das outras formas de criação. O campo
`source_fingerprint` permite conferir a integridade binária. Os testes cobrem corpo
truncado, limite, direitos, UTF-8 e ausência de arquivo parcial. Um envio real isolado
de 457,2 MiB retornou 201 e SHA-256 idêntico; ver
[evidência](../research/sprint/api-stream-real.json).

## Revisão individual e recusa

`POST /v1/jobs/{id}/candidates/{index}/review` recebe `decision` (`APPROVED` ou `REJECTED`), `reason` e `expected_revision`. `ratings`, `rework` e `adjustments` são opcionais. `ratings` usa gancho/contexto/fechamento/legendas pelas chaves `hook`, `context`, `closure`, `captions`, com 1–5 ou null. Sem nota não entra em médias. Índice começa em zero.

A aprovação exige QC válido; a recusa aceita candidato falho ou não verificado. Revisão parcial preserva as decisões dos demais candidatos e mantém o job em revisão até concluir todos. Retry invalida somente a decisão do candidato refeito. Histórico preservado.

`POST /v1/jobs/{id}/reject` recebe `reason` e recusa todo um job ocioso, preservando arquivos e histórico. A UI oferece os mesmos botões, comentários, notas opcionais e filtros por status.
# Revisão editorial v2 (opt-in)

Novos jobs podem salvar `settings.editorial_protocol=2`; o padrão da API continua 1.
O snapshot do job guarda a escolha. Jobs legados não são migrados nem qualificados
automaticamente. Antes de ativar v2 na instalação, preserve um backup verificável
de `data/work` e `data/output`; os testes usam apenas dados temporários.

`GET /v2/jobs/{id}` usa o mesmo Bearer local e retorna `editorial`, com revisão,
candidatos, contagens e estado `PENDING|PARTIAL|COMPLETED`. A decisão técnica e a
editorial são independentes. Caminhos absolutos de mídia não são retornados.

`POST /v2/jobs/{id}/candidates/{candidate_id}/reviews` exige UUID `request_id`,
`expected_editorial_revision`, `expected_artifact_id`, `decision` e `comment_raw`.
Aceita motivos, dez dimensões opcionais, grau, preferência e pedidos de edição
conforme [OpenAPI v2](../contracts/api-v2.openapi.json). Ator e data são produzidos
pelo servidor. A API registra o proprietário local autenticado, não uma identidade
individual inferida do Bearer compartilhado. Corpo JSON limitado a 64 KiB.

Mesmo request/corpo retorna o evento original. Reuso com corpo diferente, revisão
desatualizada ou bytes alterados retorna 409: recarregue e confira o render antes
de reenviar com novo request ID. Evento, recibo e projeção são salvos sob o mesmo
lock/transação JSON. V1 retorna 409 `editorial_protocol_required` nas operações de
revisão de jobs v2, inclusive recusa em lote; continua operacional para legado.

Novos renders v2 usam diretórios por candidato/revisão e manifest com hashes do
mestre, WebM e timeline. Falha/retry preserva saídas anteriores. QC válido continua
obrigatório para aprovar; recusa técnica não exige reprodução válida. Ajustes não
entram na lista compatível de aprovações limpas. Rollback desativa criação v2,
preservando leitor, eventos e arquivos; não converta ajustes em aprovação limpa.

## Ponte privada Hermes

A superfície /v2/hermes usa credencial própria e operações editoriais limitadas. Veja [contratos, perfil e instalação](../integrations/hermes/OPERACAO.md). Token Hermes não autoriza rotas gerais; configurar tokens iguais bloqueia ambas as superfícies. Comentário sem decisão é distinto de review e seleção final.
