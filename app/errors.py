"""Actionable failure messages for the Streamlit job history."""


def describe_failure(exc: Exception) -> str:
    message = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in message or "self-signed certificate in certificate chain" in message:
        return (
            "Falha de validação HTTPS ao baixar o modelo Whisper do Hugging Face. "
            "O container pode não confiar na CA do proxy/antivírus/rede. "
            "Confira docs/tls-certificates.md; se houver uma CA de inspeção TLS "
            "confiável, exporte seu certificado público PEM (.crt) para certs/ "
            "e recrie o worker. NÃO desative a verificação SSL. "
            "Detalhes: " + message[:800]
        )[:1500]
    return message[:1500]
