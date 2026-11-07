# Operação diária

O Content Factory recebe um vídeo autorizado, produz candidatos de cortes e aguarda revisão humana. A interface fica em <http://localhost:8501/> e mostra a versão no topo. Este guia usa PowerShell na raiz do repositório.

## Iniciar nesta workstation

Para a instalação já construída, com GPU K4200 e volumes existentes:

```powershell
docker compose -f compose.yaml -f compose.kepler.yaml up -d --no-build
docker compose -f compose.yaml -f compose.kepler.yaml ps
Invoke-RestMethod http://127.0.0.1:11436/health
```

Abra <http://localhost:8501/>. Em **Doctor**, confirme Worker e GPU online. O Ollama pode aparecer separadamente; cada job escolhe o backend. Se usar somente CPU/Ollama, execute `docker compose up -d --no-build` e selecione Ollama no job. A instalação inicial e o build da K4200 estão em [GPU K4200](GPU_K4200.md).

## Acessar pelo celular via Tailscale

Com o Tailscale conectado no celular ao mesmo tailnet, abra:

- Nome completo: <http://workstation.taild835d6.ts.net:8501/>
- IP privado: <http://100.78.0.122:8501/>
- Nome curto, quando MagicDNS estiver ativo: <http://workstation:8501/>

O Docker continua publicando somente `127.0.0.1:8501`. O acesso remoto usa um encaminhamento TCP persistente do Tailscale para esse endereço, restrito ao tailnet e suas permissões. Não foi habilitado Funnel nem aberto acesso público/LAN. HTTP trafega dentro do túnel Tailscale; não usar HTTPS nesses links da porta 8501.

Configuração usada na workstation, sem recriar containers:

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve --bg --tcp=8501 tcp://127.0.0.1:8501
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
```

Para desfazer somente este encaminhamento: `tailscale serve --tcp=8501 off`. Não usar `serve reset` para não apagar encaminhamentos de outros projetos. Se não abrir no aparelho, conferir Tailscale conectado, mesmo tailnet/permissões e URL com `http://` e `:8501`; testar o IP para distinguir problema de DNS. A API/Redis continuam locais. WebM e MP4 mestre estão disponíveis no seletor do player; a reprodução no celular real deve ser confirmada em seu navegador.

Não use `down -v` para reiniciar: `data/`, cache do Whisper, modelos Ollama e binários Kepler são dados persistentes. Antes de reconstruir imagens, confira espaço livre em C: e se há job em andamento.

## Produzir e revisar

Para revisão versionada, escolha protocolo editorial 2 nos ajustes de um job novo.
A API mantém protocolo 1 como padrão. No protocolo 2, use **Aprovar**, **Aprovar com
ajustes** ou **Recusar**; comentário/pedidos descrevem os ajustes e motivos/notas são
opcionais. O filtro **Filtrar candidatos** encontra recusas dentro de jobs mistos.
As contagens separam aprovação limpa, ajustes, pendência e legado não confirmado.
O painel apresenta vídeo e revisão lado a lado no desktop e empilhados no celular.
Uma alteração concorrente pede recarregar; o rascunho fica ligado ao render original.
Nenhum botão aprova automaticamente uma versão corrigida.

1. Em **Adicionar um vídeo autorizado**, escolha um MP4/MOV/MKV local ou uma URL individual do YouTube. Informe criador, referência da autorização e marque a confirmação. Download por URL exige também permissão aplicável da plataforma e a opção `ENABLE_YOUTUBE_DOWNLOAD=true`.
2. Abra **Ajustes de processamento**. Defina quantidade e duração dos cortes, modelo Whisper, análise/direção Qwen, backend Ollama ou GPU K4200 e render. Esses valores são salvos no job; alterações posteriores do `.env` não mudam um job existente.
3. Clique **Criar job de cortes**. A fila aceita um job por vez nesta implantação. O Doctor mostra a atividade da IA; em **Jobs e aprovação**, use **Atualizar status** para ver mudanças de etapa.
4. Em `NEEDS_REVIEW`, reproduza cada candidato até o fim. O WebM é a prévia para o navegador; o MP4 é o arquivo mestre para download. Confira também a transcrição, o corte, o áudio, as legendas, o enquadramento e o motor de render registrado.
5. Para cada candidato, informe um comentário e clique **Aprovar candidato** ou **Recusar candidato**. Notas de gancho, contexto, fechamento e legendas são opcionais no expander. Arquivos com falha podem ser recusados, mas só os tecnicamente válidos podem ser aprovados. O expander **Recusar o job inteiro** registra uma recusa com comentário para todos. O histórico fica no JSON do job; não há publicação automática.

B-roll só entra no trabalho após cadastro na **Biblioteca de gameplay**, com descrição e prova de direitos. O diretor recebe IDs do catálogo; sugestões de IDs inexistentes são descartadas pelo construtor da timeline.

## Estado e arquivos

Os registros ficam em `data/work/<job_id>.json`, a transcrição em `data/work/<job_id>.transcript.json`, as entradas em `data/input/` e os resultados em `data/output/<job_id>/`. Para cada candidato, há `candidate_N.mp4`, `candidate_N.preview.webm` e `candidate_N.timeline.json`. O diretório `data/` é ignorado pelo Git: mantenha backup separado.

Estados normais: `QUEUED → DOWNLOADING` (só URL) `→ TRANSCRIBING → DIRECTING → RENDERING → NEEDS_REVIEW → APPROVED/REJECTED`. Falhas ficam em `FAILED` com motivo no job. Para detalhes de fallback e recuperação, veja [Processo de produção](PROCESSO.md).

## Diagnóstico rápido

### Integrações em dry-run

Telegram e Hermes permanecem em **dry-run por escolha do proprietário** nesta
execução. Não houve envio de vídeo/transcrição nem mensagem a conversa externa.

O crítico opcional (`app.editorial_critic`) só retorna recomendações com evidência
temporal/literal. Não altera timeline ou decisão humana. O MCP Hermes disponível
é ponte de mensagens; execução estruturada, visão, modelo/provedor, custo e timeout
não foram confirmados. `python -m research.compare_hermes_direction --input arquivo.json`
gera diagnóstico sem envio; não é comparação editorial realizada.

O adaptador Telegram (`app.telegram_review`) mantém outbox JSON local, tokens opacos
curtos, allowlists de destino/ator, expiração, até três tentativas e estado de
polling persistido. `queue_review_delivery` apenas prepara o cartão. `deliver_review`
e `poll_once` não chamam transporte em dry-run. Um transporte privado explicitamente
configurado deve oferecer `send_review_card`, `get_updates` e `answer_callback_query`;
nenhum transporte de rede foi conectado/ativado nesta entrega. O exemplo de ambiente
mantém allowlists vazias. Não coloque token em job, log ou contrato.

O callback usa o mesmo serviço v2 da interface e recusa versão/artefato antigos.
Para recusa/ajustes, o polling solicita comentário em resposta ao cartão. Revisão
limpa pode dispensar nota/comentário. Mensagens são dados literais; não são comandos.
Envio com resposta perdida pode repetir o cartão, mas o evento humano é idempotente.
O anexo MP4 é ligado ao mestre exato; tamanho acima do limite gera erro explícito e
preserva o mestre, sem trocar por link público ou reduzir a qualidade silenciosamente.
Parar polling/entrega não apaga avaliações nem arquivos.

Referência consultada em 07/11/2026: [Telegram Bot API](https://core.telegram.org/bots/api),
`sendVideo` (MPEG4/multipart, limite documentado de 50 MB), `InlineKeyboardButton`
e `getUpdates`. Testes usam transporte sintético, não a conta do proprietário.

Para resultados legados, use **Verificar arquivos existentes (sem renderizar)**.
Apenas candidatos `VALID`/`WARNING` são disponibilizados para nova revisão. Use
**Salvar avaliação editorial** após informar notas, motivo e retrabalho; aprovações
anteriores são preservadas, sem notas inventadas. `PARTIAL_FAILED` mantém visíveis
as falhas. O botão por candidato tenta novamente dentro do limite salvo (padrão 2,
incluindo a tentativa original); os outros resultados não são renderizados novamente.
`QUEUE_FAILED` oferece reenvio explícito. Consulte [QC](CONTROLE_QUALIDADE.md).

```powershell
docker compose -f compose.yaml -f compose.kepler.yaml ps
docker compose -f compose.yaml -f compose.kepler.yaml logs --tail=100 worker kepler-bridge kepler-engine ui
docker exec content-factory-redis-1 redis-cli LLEN clips:queue
docker exec content-factory-redis-1 redis-cli LLEN clips:processing
Invoke-RestMethod http://127.0.0.1:11436/api/ps
```

| Sintoma | Verificação / ação |
| --- | --- |
| Worker offline | Veja `logs worker`, Redis e espaço em disco. Ao reiniciar, o worker recupera jobs da lista de processamento. |
| GPU offline | Veja `/health`, `logs kepler-engine`, modelo no volume e VRAM. O Ollama/heurística continuam opções do job. |
| Queda para heurística | Veja `ai_activity.reason` no JSON e logs. Contexto excedido retorna 422; limite de resposta e JSON inválido também acionam fallback. |
| Job `FAILED` | Leia `error` no JSON; confira entrada, modelo Whisper em cache, logs e espaço. Não apague o registro antes de identificar a etapa. |
| Vídeo não reproduz | Confira se existe a prévia WebM e decodifique-a com FFmpeg. Veja [Testes e validação](TESTES.md). O MP4 para download permanece separado. |

Para reiniciar uma mudança de código montada pelo override, use `docker compose -f compose.yaml -f compose.kepler.yaml up -d --no-build --force-recreate worker ui kepler-bridge`. Faça isso com a fila vazia ou depois que o job atual terminar.
