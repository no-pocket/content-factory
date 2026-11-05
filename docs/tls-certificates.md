# Hugging Face / Whisper — erros de certificado TLS

Se um job falhar com `CERTIFICATE_VERIFY_FAILED` / `self-signed certificate in certificate chain`, o download do modelo falhou **antes** da transcrição. Não é erro do Qwen, Remotion ou do vídeo.

## 1. Diagnóstico no worker

No PowerShell, na pasta do projeto:

```powershell
docker compose exec worker python -c "import httpx; r=httpx.get('https://huggingface.co/api/models/Systran/faster-whisper-base', timeout=20); print(r.status_code)"
```

Se retornar `200`, o acesso HTTPS funciona. Se falhar com certificado autoassinado, descubra quem está emitindo a cadeia de certificados no seu ambiente. Confirme se há inspeção HTTPS por proxy, antivírus ou filtro de rede. Compare com outra rede se necessário. O container pode não possuir uma CA privada que seu Windows já considera confiável.

## 2. Adicionar a CA correta (quando se tratar de inspeção HTTPS legítima)

1. No Windows, abra os detalhes do certificado da conexão com `https://huggingface.co` no navegador e identifique a autoridade emissora. Consulte o administrador da rede/antivírus se necessário.
2. Exporte **somente o certificado público da autoridade certificadora confiável** como Base-64 X.509/PEM (`-----BEGIN CERTIFICATE-----`). Não exporte chave privada. Você pode utilizar `certmgr.msc` ou `certlm.msc` para localizar o certificado confiável no Windows.
3. Salve-o como `certs/local-root.crt` no diretório do projeto. Se houver intermediárias necessárias, adicione-as como arquivos `.crt` separados. Não adicione certificados não verificados.
4. Execute:

```powershell
docker compose up -d --force-recreate worker
docker compose logs --tail=100 worker
```

O container monta `./certs` em `/usr/local/share/ca-certificates/content-factory` e executa `update-ca-certificates` antes de iniciar o worker. A variável `SSL_CERT_FILE` aponta para o pacote de raízes do sistema **mais** as adicionais, sem desligar a validação HTTPS.

## 3. Validar o download do modelo

```powershell
docker compose exec worker python -c "import httpx; r=httpx.get('https://huggingface.co/api/models/Systran/faster-whisper-base', timeout=20); print(r.status_code)"
docker compose exec worker python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8'); print('Whisper OK')"
```

O segundo comando pode baixar vários arquivos na primeira execução e usar o volume persistente `hf_cache` posteriormente. Após validar, envie **um novo job**: jobs `FAILED` não são reprocessados automaticamente.

Se a primeira chamada retornar 200 mas o download de arquivos maiores falhar, verifique também a cadeia TLS dos domínios usados pelo Hugging Face para distribuir modelos, o proxy e suas regras de acesso.

## 4. Não faça

- Não configure `verify=False` ou desative a checagem global de certificados.
- Não aceite uma CA cuja origem você não tenha verificado.
- Não faça commit dos certificados locais nem de credenciais do proxy.
