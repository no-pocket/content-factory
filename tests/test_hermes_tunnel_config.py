import subprocess
from pathlib import Path


def test_tunnel_rejects_missing_configuration():
    script = Path(__file__).resolve().parents[1] / 'integrations/hermes/tunnel/run.sh'
    result = subprocess.run(['sh', str(script)], env={'PATH': '/usr/bin:/bin'}, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'HERMES_TUNNEL_HOST' in result.stderr


def test_tunnel_rejects_option_injection_before_connecting():
    script = Path(__file__).resolve().parents[1] / 'integrations/hermes/tunnel/run.sh'
    env = {'PATH': '/usr/bin:/bin', 'HERMES_TUNNEL_HOST': '-oProxyCommand=bad',
           'HERMES_TUNNEL_USER': 'user', 'HERMES_TUNNEL_REMOTE_PORT': '18510',
           'HERMES_TUNNEL_HOSTKEY_ALIAS': 'host'}
    result = subprocess.run(['sh', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Invalid tunnel host' in result.stderr
