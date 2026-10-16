from datetime import datetime

import pytest

from stark.core.engine import strip_closers
from stark.tools import quake, router
from stark.tools.quake import QuakeQuery

LIST = """
Tarih      Saat      Enlem(N)  Boylam(E) Derinlik(km)  MD   ML   Mw    Yer                                             Çözüm Niteliği
---------- --------  --------  -------   ----------    ------------    --------------                                  --------------
2026.10.16 15:10:10  39.3308   38.1817       38.4      -.-  1.8  -.-   IKIZBASAK-DIVRIGI (SIVAS)                         İlksel
2026.10.16 09:01:00  38.4000   27.1000        7.0      -.-  3.9  3.8   BORNOVA (IZMIR)                                   İlksel
2026.10.11 01:33:00  35.1000   25.1000        5.0      -.-  4.2  -.-   GIRIT ADASI (AKDENIZ)                             İlksel
"""


class Client:
    def get(self, url, timeout=0, follow_redirects=True):
        return type("R", (), {"content": LIST.encode("windows-1254")})()


NOW = datetime(2026, 10, 16, 16, 0)


@pytest.mark.parametrize("text, q", [
    ("Son deprem nerede oldu?", QuakeQuery()),
    ("İzmir'de deprem mi oldu?", QuakeQuery("İzmir")),
    ("Son büyük deprem nerede oldu?", QuakeQuery(None, True)),
])
def test_parse(text, q):
    assert quake.parse(text) == q


@pytest.mark.parametrize("text", ["Deprem çantasında ne olmalı?", "Depremde ne yapmalıyım?", "Hava nasıl?"])
def test_not_quake_questions(text):
    assert quake.parse(text) is None


def test_latest_and_biggest_of_the_day():
    reply = quake.answer(QuakeQuery(), NOW, Client())
    assert reply.startswith("Kandilli'ye göre son deprem bugün saat 15.10, Sivas Divrigi, büyüklüğü 1,8")
    assert "Son 24 saatin en büyüğü: bugün saat 09.01, İzmir Bornova, büyüklüğü 3,8" in reply


def test_province_and_big_filters():
    assert "İzmir ilindeki son deprem bugün saat 09.01" in quake.answer(QuakeQuery("İzmir"), NOW, Client())
    assert "son büyük deprem 11.10 saat 01.33" in quake.answer(QuakeQuery(None, True), NOW, Client())


def test_filler_closers_removed():
    assert strip_closers("Nüfus 86 milyon. Patron, TÜİK sitesinden kontrol edebilirsiniz.") == "Nüfus 86 milyon."
    assert strip_closers("Tek cümle, bu kadar.") == "Tek cümle, bu kadar."


def test_why_question_about_currency_goes_to_news():
    assert router.route("Dolar neden yükseldi?").kind == "news"
    assert router.route("Dolar kaç lira?").kind == "currency"
