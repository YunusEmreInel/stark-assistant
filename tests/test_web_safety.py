"""Web sayfası okuma yalnızca internetteki adreslere gider; ev ağı ve bilgisayarın kendisi engellenir."""
import socket

import pytest

from stark.tools import web

FAKE_DNS = {"ornek.com": "93.184.216.34", "modem.local": "192.168.1.1", "kotu.com": "127.0.0.1",
            "ipv6.com": "2606:2800:220:1::1", "ic.com": "10.0.0.5"}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    def getaddrinfo(host, port, *a, **k):
        ip = FAKE_DNS.get(host, host)
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(fam, socket.SOCK_STREAM, 6, "", (ip, port))]
    monkeypatch.setattr(web.socket, "getaddrinfo", getaddrinfo)


@pytest.mark.parametrize("url, ok", [
    ("https://ornek.com/haber", True),
    ("https://ipv6.com/", True),
    ("http://192.168.1.1/ayarlar", False),
    ("http://modem.local/", False),
    ("https://kotu.com/", False),          # alan adı bilgisayarın kendisine çözülüyor
    ("http://127.0.0.1:11434/api/tags", False),
    ("http://[::1]/", False),
    ("http://10.0.0.5/", False),
    ("http://ic.com/", False),
    ("http://169.254.169.254/", False),
    ("file:///C:/Windows/win.ini", False),
    ("ftp://ornek.com/", False),
])
def test_only_public_addresses(url, ok):
    assert web.is_public_url(url) is ok


def test_redirect_into_local_network_is_not_followed(monkeypatch):
    calls = []

    class Resp:
        def __init__(self, url):
            self.url = url
            self.is_redirect = url.startswith("https://ornek.com")
            self.headers = {"location": "http://192.168.1.1/reboot"} if self.is_redirect else {}
            self.status_code = 302 if self.is_redirect else 200

        def __enter__(self):
            calls.append(self.url)
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(web.httpx, "stream", lambda method, url, **k: Resp(url))
    assert web._page_text("https://ornek.com/yonlendir") == ""
    assert calls == ["https://ornek.com/yonlendir"]  # modem adresine hiç istek gitmedi
