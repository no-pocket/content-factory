# Auditoria REA: Quadro K4200 e Content Factory

Data: 2026-11-05. Escopo: instalação em execução nesta workstation. As conclusões distinguem inspeção estática, medições em execução e hipóteses a medir. Nenhum serviço foi reiniciado e nenhuma imagem foi reconstruída.

## Resultado

O caminho de inferência GPU está funcionando, mas ainda não é possível afirmar que está no máximo de desempenho ou pronto para operação robusta. A K4200 tem 4 GiB, compute capability 3.0, e está em WDDM com driver 475.14. O servidor em execução usa llama.cpp b4300, CUDA 10.2 e Qwen 2.5 3B: os logs informam 37/37 camadas na GPU, modelo de 1.834,83 MiB, KV cache de 144 MiB e buffer de computação de 150,38 MiB. O processo está configurado com contexto 4096, batch 512, microbatch 256 e quatro threads.

Uma requisição real à ponte local retornou com sucesso: 29 tokens de prompt em 1,635 s, 64 tokens gerados em 8,108 s (7,89 tokens/s), 9,84 s totais. Essa é apenas uma amostra, não um benchmark comparativo nem uma validação de qualidade. Nos logs reais anteriores, 2.269 tokens de prompt levaram 21,54 s e 315 de saída 56,48 s. O resultado confirma que a decodificação pode dominar a latência para respostas extensas.

## Evidências inspecionadas pelo REA

Os arquivos Linux foram copiados em `E:\CodexFiles\rea-runtime\k4200-evidence` a partir do container em execução; REA examinou as cópias estáticas. Os mapas de memória de `/proc/1/maps` identificaram os arquivos carregados. Os resultados estáticos não provam que um kernel específico foi executado, nem medem sua eficiência.

| Componente | Resultado e SHA-256 |
| --- | --- |
| `libggml-cuda.so` efetivamente carregada | 135 objetos CUDA no inventário, um único alvo declarado `sm_30`; `a5c6d16e6aad2556dd6131bcbc4e8b1e8d9659796b8aebc3e2e6d18afb6d618a`. O REA não decodificou kernels no inventário. |
| `llama-server` | ELF x86-64; build-id `51051a50eabdc4a833a6a98be0d63ff4ad55ab5a`; SHA-256 `2ed711d26b90ec575a717b1c5b2065ae2a15d2f47a90c79ef23c72b95e95b019`. |
| `libcudart.so.10.2.89` | ELF x86-64, 295 exportações; `80664282d0f1388cc8644a105dff2261f20c0d0013c4db8b356c44acf6b590c8`. |
| Shim `libcuda.so.1` do container | 540 exportações; `81493f3a37aed3cb23b0f588b6fd167fca735321c5a7c2315ffac3cdc86d8e83`. |
| Driver Linux da camada WSL carregado | 550 exportações; `f07c751fa7a243415d67201f5a0e2df9ba2030869c0b8e1d91539dd5c45081ee`. |
| `C:\Windows\System32\nvcuda.dll` | PE x64, 561 exportações; `9d875fdaff35856b7d5dfd60beeca64cde68c00b80796a0aeb0dceb9f9cd4a73`. É um loader, não prova isoladamente o caminho de execução. |
| `C:\Windows\System32\nvEncodeAPI64.dll` | PE x64, duas exportações; `c6002f55debd545790cb7d464244bd7323c1fdb550c3f0d854457f26ddebc8b5`. A inspeção de exportações não estabelece que NVENC funcione no container. |

O build local informa `Release`, `CMAKE_CUDA_ARCHITECTURES=30`, CUDA habilitado, graphs desabilitados e clang 14. O checkout consultado aponta para `dafae66cc242eb766797194d3c85c5e502625623`, mas o binário isolado não prova, por si só, que foi produzido exatamente desse checkout. A imagem em execução tem ID `sha256:1acfa6b24e224bb16b1fb079da29ef0cdc7340521e687a1ec642dce080ed208a`; seu conteúdo não substitui um manifesto reprodutível de build.

## Limitações e riscos concretos

1. **Contexto divergente:** `app/ranker.py` solicita `num_ctx=8192`, enquanto o servidor usa 4096 e `translate_generate` não repassa `num_ctx`. Pedidos extensos podem exceder a capacidade disponível, sofrer truncamento ou falhar, conforme o comportamento do servidor. O relatório já registra prompt de 3.270 tokens; com resposta máxima de 700 e template, a margem pode ficar pequena. Medir tokens reais e verificar eventos de truncamento, sem supor que todo pedido já tenha sido truncado.
2. **Não há encaminhamento dinâmico comprovado:** no benchmark anterior GPU ganha no prefill e perde na geração; um prompt real teve tempos menores na GPU, mas comparou execuções e caminhos diferentes. Tempo total também depende de template, tamanho de entrada/saída, cache e carga. Não afirmar ganho universal ou trocar backend automaticamente antes de um teste pareado.
3. **Suporte:** CUDA 10.2 é a última linha a incluir `sm_30` ([NVIDIA CUDA 11 release notes](https://docs.nvidia.com/cuda/archive/11.0/pdf/CUDA_Toolkit_Release_Notes.pdf)). A documentação de [CUDA em WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) especifica suporte a partir de Pascal; o funcionamento de Kepler aqui é observado, mas fora da faixa oficialmente suportada. A placa não oferece recursos modernos como Tensor Cores; atualizações de driver ou WSL podem quebrar o workaround.
4. **Vídeo:** `app/edit_render.py` usa `libx264`; o teste anterior de NVENC nativo não significa que o pipeline o use. A falha NVENC no container permanece sem diagnóstico conclusivo; CUDA funcional não demonstra suporte NVENC. Os exports da DLL não provam capacidade, versão da API ou funcionamento de encode.
5. **VRAM e disco:** no momento da coleta, cerca de 3.374/4.096 MiB da GPU estavam ocupados, compartilhados com a área de trabalho, e C: tinha cerca de 1,3 GiB livres. Os números variam. Evitar builds, downloads grandes, segundo modelo na GPU e expansão do disco Docker em C: até disponibilizar espaço. Não eliminar arquivos ou volumes sem identificar o conteúdo.
6. **Ponte parcial:** a ponte só traduz um subconjunto de opções Ollama, não informa explicitamente truncamento ou finalização por limite e retorna modelos via `/api/ps` com informação mínima. `num_ctx` é ignorado; outras opções não mapeadas também não devem ser consideradas equivalentes. Falhas e JSON incompleto precisam ser medidos e registrados.

## Caminho recomendado

1. Resolver espaço em C: e verificar capacidade real de VRAM antes de qualquer build ou alteração. Registrar driver, WSL, imagem por digest, commit, compilador, bibliotecas e hashes de modelo; preservar o ambiente funcional atual como rollback.
2. Corrigir o contrato de contexto: contabilizar template + prompt + saída reservada; configurar o contexto para o workload se couber na VRAM, ou dividir/rejeitar o pedido explicitamente. Verificar preservação das informações e JSON válido, não apenas que a chamada retornou 200. Testar limites de contexto, falhas, timeouts e reinício do serviço.
3. Em janela sem jobs, comparar pelo mesmo executável e modelo fixo CPU versus GPU, com aquecimento e pelo menos três repetições: prompts curtos e longos, saídas curtas e longas, valores iguais de contexto e sampling. Medir prefill, geração, fim a fim, uso/pico de VRAM, clocks, erros e qualidade. Testar separadamente camadas na GPU, batch/microbatch e threads, mudando uma variável por vez. Incluir Qwen 1.5B e 3B e avaliar qualidade editorial, não só tokens/s. Evitar carregamentos simultâneos que causem swapping/contenda.
4. Só depois da comparação pareada, escolher backend conforme estágio/carga se isso reduzir latência sem degradar qualidade. Nunca declarar máximo global a partir das medições existentes.
5. Se o produto exigir disponibilidade previsível e suporte de fornecedor, migrar inferência para hardware suportado; usar essa K4200 em caminho legado isolado e com fallback. Linux nativo pode ser uma hipótese comparativa, mas não foi testado aqui; não há prova de que melhorará a performance nesta máquina.
6. Para vídeo, comparar FFmpeg NVENC nativo compatível contra libx264 no pipeline completo, com mesmo material, resolução e qualidade visual, incluindo cópias entre host e container e limites de concorrência. Ativar somente após resultado funcional e de qualidade; não se deve ativar NVENC no container baseado apenas no teste Windows.

Nenhuma medição controlada de configurações alternativas ou perfil de kernel foi realizada nesta auditoria. Um teste de saúde da ponte e inspeções estáticas não estabelecem estabilidade prolongada, qualidade de saída ou desempenho máximo.

## Atualização de implementação e medições (2026-11-05)

Esta seção registra as ações posteriores à auditoria original. A versão da aplicação é **4.1.0** e aparece na interface. Nenhuma imagem GPU foi reconstruída; o volume `cf_kepler_b4300` foi preservado.

### Contrato de contexto e falhas explícitas

- A ponte consulta `/props` para obter o contexto real do servidor e `/tokenize` para contar o prompt com os marcadores ChatML do Qwen 2.5. Ela reserva a saída solicitada e uma margem configurável de 16 tokens (`KEPLER_CONTEXT_MARGIN`). Um pedido acima do limite recebe HTTP 422 antes da geração. Pedido real com `num_ctx=8192` recebeu 422 diante do servidor em 4096.
- O classificador e o diretor deixam de pedir 8192/4096 tokens fixos quando o backend é a K4200. O Ollama mantém o contexto solicitado anteriormente. A ponte recusa opções Ollama que não implementa; não há equivalência implícita.
- A ponte expõe `done_reason`, `prompt_truncated`, contagens e janela efetiva. Classificador e diretor rejeitam decisões mesmo com JSON sintaticamente válido se a resposta terminou por limite ou se o prompt foi truncado, acionando a heurística. O teste ao vivo retornou `done_reason=stop`, `prompt_truncated=false`, `context_window=4096` e `/api/ps` passou a informar modelo e contexto.
- O Doctor mostra disponibilidade, modelo e contexto da GPU quando o override Kepler está ativo. Testes automatizados cobrem estouro de contexto, opção sem suporte, saída incompleta, prompt truncado, fallback, saúde e versão da UI.

### Comparação pareada

O script `research/benchmark-kepler.ps1` usa **o mesmo `llama-bench` b4300 e os mesmos blobs Q4_K_M**, quatro threads, batch 512, microbatch 256, uma execução de aquecimento e três repetições medidas por caso. A fila Redis estava vazia. O servidor GPU foi parado durante a comparação e reiniciado ao final. GPU: 99 camadas; CPU: zero. Os CSVs originais estão em `research/benchmarks/`. Cada linha abaixo é a média de três repetições, em tokens/s.

| Modelo | Operação | CPU | GPU |
| --- | --- | ---: | ---: |
| Qwen 2.5 1.5B | leitura 128 tokens | 142,05 | 222,26 |
| Qwen 2.5 1.5B | leitura 1024 tokens | 206,45 | 237,79 |
| Qwen 2.5 1.5B | geração 32 tokens | 25,27 | 13,76 |
| Qwen 2.5 1.5B | geração 64 tokens | 25,09 | 13,18 |
| Qwen 2.5 3B | leitura 128 tokens | 75,39 | 95,07 |
| Qwen 2.5 3B | leitura 1024 tokens | 91,43 | 110,27 |
| Qwen 2.5 3B | geração 32 tokens | 12,98 | 6,80 |
| Qwen 2.5 3B | geração 64 tokens | 13,57 | 6,77 |

Isto isola leitura e geração, mas não mede a latência ponta a ponta de prompts editoriais nem compara a qualidade das decisões. Como a GPU perde na geração, nenhum encaminhamento automático por comprimento foi ativado; a escolha continua disponível por job. Durante uma amostra do benchmark 3B na GPU, `nvidia-smi` mostrou 3074 MiB usados e 99% de utilização; não é medida de pico. A unidade C: tinha aproximadamente 1,39 GB livres no início, portanto não houve build nem download novo.

### Manifesto do ambiente preservado

| Item | Identificador |
| --- | --- |
| Imagem GPU em uso | `sha256:1acfa6b24e224bb16b1fb079da29ef0cdc7340521e687a1ec642dce080ed208a` |
| Imagem worker/ponte | `sha256:d5fcdac1b9fd91aba03290d0a8653d5437b63c3636069d5b31033c3da2f8ed9d` |
| Binário e biblioteca GPU | SHA-256 registrados na tabela de evidências acima |
| Modelo Qwen 2.5 1.5B Q4_K_M | blob Ollama `sha256:183715c435899236895da3869489cc30ac241476b4971a20285b1a462818a5b4` |
| Modelo Qwen 2.5 3B Q4_K_M | blob Ollama `sha256:5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6` |
| GPU/driver/WSL | Quadro K4200, driver 475.14, WSL 2.3.26.0, kernel 5.15.167.4-1 |

### Limites que permanecem

- Kepler no CUDA/WSL continua fora da faixa de suporte oficial. O ambiente funcional está preservado; uma atualização do driver/WSL exige nova validação.
- Um bloqueio NVENC foi isolado: sem a capacidade `video`, o FFmpeg 5.1.9 do container falha em carregar `libnvidia-encode.so.1`; com `NVIDIA_DRIVER_CAPABILITIES=video,compute,utility`, ele codificou H.264/NVENC e o resultado decodificou por inteiro. Isto não reconstitui conclusivamente o `unsupported device (2)` visto na tentativa anterior, que pode ter usado outra combinação de runtime/FFmpeg. Em 5 s do vídeo de teste, com o mesmo crop 720×1280, x264 levou 2,28 s e gerou 860.276 bytes; NVENC levou 2,41 s e gerou 2.514.056 bytes (`-cq 24`, `-b:v 0`). As qualidades/bitrates não são equivalentes e o custo de iniciar o container faz parte do tempo. Este ensaio não demonstra vantagem de velocidade ou qualidade, nem valida concorrência com inferência e render Remotion. O pipeline continua em `libx264` até uma comparação de qualidade equivalente e teste completo em job real.
- O espaço livre em C: continua insuficiente para reconstruções grandes. Os CSVs ficam no projeto em E:; os modelos permanecem nos volumes Docker existentes. Nenhum volume foi apagado ou movido.
- O benchmark não cobre camadas parciais, threads/batches alternativos, clocks, latência ponta a ponta nem qualidade editorial. Esses resultados não demonstram desempenho máximo.

Na validação desta atualização, o Firefox reproduziu até o evento `ended` os três WebM do job `530ade0e-7027-46ff-8173-5da8e5166ef4`, sem erro de mídia. Isto verifica a reprodução desse conjunto; outros arquivos ainda dependem de decodificação e teste próprios.
