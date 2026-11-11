# Agenda de publicações — proposta

## Objetivo e escopo

Depois da aprovação humana de um candidato, permitir selecionar Instagram Reels e/ou Facebook Reels, editar a legenda e escolher publicação imediata ou data e hora. A agenda é local nesta fase; sincronização com agendas das plataformas fica para uma etapa posterior. A aprovação, sozinha, não inicia postagem.

## Abordagens

- Agenda local, escolhida: um processo dedicado à publicação mantém registros persistentes e despacha no horário; usa upload direto já testado para as duas plataformas. A workstation e o serviço precisam estar ligados.
- Agenda remota: dependeria das funcionalidades e restrições de cada plataforma, ainda não verificadas para todas as contas e fluxos. Ficará para integração futura.

## Experiência

Uma aba Agenda apresenta calendário mensal com horário local, candidato, destino e estado. Exibe check verde somente após confirmação remota da publicação; distingue agendado, enviando, processando, publicado, falhou, cancelado e resultado incerto. Permite consultar detalhes, cancelar ou alterar agendamentos ainda não iniciados. Uma tentativa de publicação agora segue a mesma fila e mostra progresso e resultado.

## Dados e execução

Cada destino tem registro persistente independente com identidade do job e candidato, versão e hash do artefato, revisão, legenda, conta de destino, instante UTC, fuso informado, estado, tentativas e identificadores remotos; não guardar credenciais. Escritas atômicas e lock impedem execução concorrente na implantação de um único processador. O processo dedicado não depende da duração de transcrição ou render; reinício recupera agendamentos pendentes e mostra atrasos. Não assumir segurança multiworker.

Antes de transferir, repetir o preflight existente sob o lock do job e comparar revisão e hashes com o agendamento. Se mudaram ou a aprovação/QC deixou de valer, bloquear com motivo. Antes de cada requisição externa validar hosts e limites; nunca registrar tokens. IDs remotos e fases são salvos durante o processo. Quando a resposta de publicação for ambígua, marcar resultado incerto e exigir reconciliação antes de tentar novamente, para evitar duplicações.

Credenciais ficam na configuração secreta do processo e nunca no histórico; o arquivo .env.meta não será incluído no repositório nem exposto na interface. Validar os requisitos técnicos do vídeo para cada plataforma e preservar o MP4 mestre. O calendário registra confirmação por destino, link e horário quando fornecidos pela plataforma.

## Validação

Testes focados cobrem agendamento e fuso, cancelamento, recuperação, alterações na aprovação ou arquivo, falhas transitórias e respostas ambíguas, além de transportes simulados sem rede e ausência de segredos. Depois executar a suíte adequada, revisar o diff e verificar a interface com agent-browser quando disponível. Testes reais de publicação dependem de candidatos autorizados e credenciais válidas; testes unitários não comprovam qualidade ou reprodução.
