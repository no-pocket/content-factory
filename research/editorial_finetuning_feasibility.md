# Fine-tuning editorial: decisão NO-GO

Estudo M10 de07/11/2026, somente na branch `codex/editorial-learning`.
Nenhum trainer neural, modelo, dataset externo, GPU nova ou serviço foi instalado
ou contratado. Não há treino em startup nem promoção automática.

## Decisão e lacunas

**NO-GO nesta rodada.** Existem cinco fontes/15 candidatos na coorte;11 aprovações
legadas e4 recusas não substituem planos finais humanos ou pares confirmados. O
export M7 encontrou0 graus v2 elegíveis,0 planos finais curados para SFT e0 pares
validados para DPO. Nem o ranker linear B passou nos gates de dados. Portanto não
há evidência de que A/B atingiram uma limitação que justifique ajustar um LLM.

Os gates do projeto são propostas de engenharia, não mínimos universais dos
artigos: SFT exige estudo após >=500 famílias e2.000 planos finais humanos; DPO
exige >=1.000 pares válidos de mesmo contexto em >=200 famílias, mais holdout
separado. Quantidade isolada não autoriza treino: direitos, consistência dos
rótulos, PT/EN, comparação A/B, infraestrutura e orçamento continuam necessários.

## O que cada técnica exigiria

| Opção | Dados necessários | Benefício a testar | Custo/risco adicional |
|---|---|---|---|
| SFT | Contexto/brief → plano final corrigido por humano, ligado a render revisado | Produzir planos válidos e completos com menos correção | Curadoria, overfitting ao criador e regressão fora do domínio |
| LoRA sobre SFT | A mesma supervisão; base treinável compatível e versão fixa | Adaptar geração com menos parâmetros treináveis | Pesos base e ativações ainda consomem memória; adapters precisam de base compatível |
| DPO | Mesmo contexto/objetivo com saída escolhida e rejeitada, confirmação e versões | Alinhar preferências de planos comparáveis | Preferência relativa não garante qualidade absoluta; ambos os planos podem ser ruins |
| QLoRA | Dados elegíveis de SFT/preferência e stack de treino quantizado compatível | Reduzir memória do experimento | Não equivale a carregar o GGUF de inferência existente nem demonstra funcionamento em Kepler |

[SFT no InstructGPT](https://arxiv.org/abs/2203.02155) usa demonstrações humanas como
etapa supervisionada. Isso sustenta a distinção entre plano-alvo revisado e um
comentário livre de aprovação; não prova ganho neste corpus.

[LoRA, Hu et al., v2](https://arxiv.org/abs/2106.09685v2) congela a base e treina
adaptações de baixo rank. A redução de parâmetros treináveis não é uma medição de
VRAM desta aplicação.

[DPO, Rafailov et al., v3](https://arxiv.org/abs/2305.18290v3) otimiza preferências
entre gerações sem a etapa separada de reward model do RLHF tradicional. Continua
sendo treino de política; escolher o “melhor dos três” de objetivos diferentes não
cria automaticamente um par apropriado.

[QLoRA, Dettmers et al.](https://arxiv.org/abs/2305.14314) demonstra treino de65B em
uma GPU de48GB no seu experimento. Esse resultado não pode ser extrapolado para a
Quadro K4200 de4GB desta workstation.

## Base, licença e hardware

A base de treino deve ter revisão/tokenizer/config e formato de pesos apropriados,
com licença verificada. O GGUF usado no servidor `llama.cpp` legado é um artefato
de inferência; sua presença não fornece um ambiente de treinamento validado.
Um eventual adapter exigiria teste de merge/conversão/quantização e regressões no
servidor CPU/Ollama e na ponte Kepler antes de qualquer ativação.

A [tabela oficial NVIDIA](https://developer.nvidia.com/cuda/gpus/legacy) classifica
K4200 como compute capability3.0. Suporte do trainer/kernel/driver e consumo de
memória não foram demonstrados; o funcionamento do servidor CUDA10.2 legado não
valida PyTorch/bitsandbytes atuais. Um piloto precisaria de GPU moderna suportada
pelo stack escolhido e medição com o contexto/batch reais. Nenhum novo backend de
Whisper é proposto; ASR continua CPU.

A [licença oficial do Qwen2.5-3B-Instruct, revisão14d7620](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/14d7620ba47cf51be0b176e14e27e38a34d4ff88/LICENSE)
é identificada como `qwen-research`. Não assumir que todos os tamanhos Qwen ou uma
quantização de terceiros têm a mesma licença. A revisão e os usos pretendidos
precisam constar do estudo específico antes de baixar uma base para treino.

## Orçamento e aceite de um futuro experimento

Orçamento autorizado nesta execução: **R$0 em serviços/hardware/modelos pagos**;
zero upload de transcrição, frames ou feedback para terceiros. O custo observado
foi desenvolvimento/testes locais; não houve medição de treinamento neural.

Se dados e A/B justificarem outro escopo, propor primeiro um piloto com limite de
4 horas de GPU e uma configuração fixa, em infraestrutura compatível. Esse limite
é um teto proposto, não estimativa de conclusão nem contratação. Preço vigente,
localidade, retenção, base/licença, download, espaço e destino externo precisam de
um orçamento concreto aprovado antes do experimento. Falha de memória/tempo encerra
o piloto com relatório, sem expandir recursos automaticamente.

Fixar dataset, famílias/holdout, prompt/brief, base/tokenizer, seed, hparams,
trainer/dependências e hashes antes de avaliar. Comparar com A e B no mesmo pool;
Acceptance@3 limpo deve melhorar em famílias não vistas, com intervalo bootstrap
por família de95% inteiramente positivo, sem falha crítica de mídia e sem regressão
PT/EN acima da margem de5 pontos percentuais proposta em EVALUATION. Um IC amplo ou
cobertura insuficiente mantém a baseline. Aprovação humana é necessária para ativar
um artefato; rollback preserva dados/artefatos e troca apenas o ponteiro ativo.

## Manutenção e alternativa atual

Adapters/base/quantização, dependências, avaliação, drift de tema e licença têm
custo contínuo. A alternativa entregue é coleta humana versionada, brief explícito
e recuperação lexical opt-in; ranker leve só após elegibilidade. Fine-tuning não
é necessário para encerrar este plano e não será usado para compensar rótulos
insuficientes ou enquadramento incorreto.
