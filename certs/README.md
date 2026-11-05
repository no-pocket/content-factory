# Certificados CA locais (opcional)

Se o container receber `CERTIFICATE_VERIFY_FAILED` no Hugging Face por uma CA de inspeção TLS (proxy corporativo, antivírus etc.), exporte **somente o certificado da CA emissora confiável**, em formato PEM (Base-64 X.509), para um arquivo `*.crt` nesta pasta, por exemplo `certs/local-root.crt`.

Não copie chaves privadas. Valide a procedência do certificado antes de confiar nele. Arquivos de certificado nesta pasta são ignorados pelo Git.

Em seguida, execute `docker compose up -d --force-recreate worker`. A inicialização executa `update-ca-certificates` e o HTTPX lê `/etc/ssl/certs/ca-certificates.crt`, sem desabilitar a verificação TLS.

Consulte `docs/tls-certificates.md` para detalhes e testes.
