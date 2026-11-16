# Ponte privada Hermes em Docker

`compose.hermes-tunnel.yaml` fornece o serviço opcional `hermes-tunnel`. Defina
`HERMES_TUNNEL_*` em `.env` e coloque uma chave SSH dedicada e o `known_hosts`
verificado em `data/hermes-tunnel/`. Esses arquivos não pertencem ao Git.
Restrinja a chave no servidor remoto ao encaminhamento de porta necessário e
configure o cliente Hermes para acessar a porta remota de loopback.

Inclua o override e o perfil `hermes-tunnel` nos comandos Compose da instalação.
A conexão usa verificação estrita da chave do host, retransmite apenas para a
API na rede Compose e tenta reconectar após falhas. A política `unless-stopped`
reinicia o serviço enquanto o Docker Engine estiver disponível. Ela não inicia
o Docker Desktop antes do logon do Windows; essa etapa requer uma configuração
de inicialização não interativa separada.

Para uma instalação nova:

1. Gere `data/hermes-tunnel/id_ed25519` com `ssh-keygen -t ed25519 -N ''` e
   confirme a identidade do servidor por um canal independente. Salve a chave
   pública do servidor verificada em `data/hermes-tunnel/known_hosts`, usando
   como nome o valor configurado em `HERMES_TUNNEL_HOSTKEY_ALIAS`.
2. Cadastre apenas a chave pública dedicada no servidor SSH remoto. Restrinja-a
   com `restrict,port-forwarding,permitopen="none",permitlisten="127.0.0.1:PORTA"`,
   substituindo `PORTA` pela porta escolhida. Preserve as demais chaves existentes.
3. Em `.env`, configure `HERMES_TUNNEL_HOST`, `HERMES_TUNNEL_USER`,
   `HERMES_TUNNEL_HOSTKEY_ALIAS` e `HERMES_TUNNEL_REMOTE_PORT`. Nenhum desses
   valores, nem os arquivos em `data/hermes-tunnel/`, deve ser incluído no Git.
4. Com os overrides normalmente usados, adicione `-f compose.hermes-tunnel.yaml
   --profile hermes-tunnel` e execute `up -d --no-deps hermes-tunnel`.
   Configure o cliente Hermes com a porta remota de loopback e confirme uma
   consulta autenticada. Teste a recuperação após reiniciar o container antes
   de retirar outra ponte ativa.
