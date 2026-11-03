from app.errors import describe_failure


def test_ssl_chain_failure_has_actionable_and_safe_message():
    error = RuntimeError("CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain")
    text = describe_failure(error)
    assert "certs/" in text
    assert "NÃO desative" in text
    assert "CERTIFICATE_VERIFY_FAILED" in text


def test_unrelated_errors_preserved():
    assert describe_failure(RuntimeError("another failure")) == "another failure"


def test_failure_message_is_bounded():
    assert len(describe_failure(RuntimeError("X" * 5000))) == 1500
