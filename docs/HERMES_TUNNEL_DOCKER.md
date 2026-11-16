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
