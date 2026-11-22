"""Troca de campeao na mesma aba do navegador (GET /proxima e /pegou), com uma "aba" falsa em Python."""
import json
import threading
import time
import urllib.error
import urllib.request

import comum
from comum import confere

mb = comum.carregar(porta=47991)
BASE = f"http://127.0.0.1:{mb.DADOS_PORT}"
NAV = mb.NAV


def get(caminho, origem=None):
    req = urllib.request.Request(BASE + caminho, headers={"Origin": origem} if origem else {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


URL1 = "https://www.metasrc.com/lol/arena/champions/lee-sin/build"
URL2 = "https://www.metasrc.com/lol/arena/champions/swain/build"

t = time.time()
confere("sem aba: entregar() devolve False na hora", NAV.entregar(URL1) is False and time.time() - t < 0.1)

recebido = {}


def aba(confirma):
    st, d = get("/proxima")
    recebido.update(d, status=st)
    if confirma and d.get("n"):
        get(f"/pegou?n={d['n']}")


th = threading.Thread(target=aba, args=(True,))
th.start()
time.sleep(0.3)
confere("aba aberta: entregar() devolve True", NAV.entregar(URL1) is True)
th.join(5)
confere("aba aberta: recebeu a URL certa", recebido.get("url") == URL1)

recebido.clear()
th = threading.Thread(target=aba, args=(False,))
th.start()
time.sleep(0.3)
t = time.time()
confere("aba congelada (nao confirma): desiste em ~2.5 s",
        NAV.entregar(URL2) is False and 2.0 < time.time() - t < 3.5)
th.join(5)
confere("nada pendente depois", NAV.pendente is None)

confere("Origin de outro site: /proxima da 403", get("/proxima", "https://site-malicioso.com")[0] == 403)
confere("Origin de outro site: /pegou da 403", get("/pegou?n=1", "https://site-malicioso.com")[0] == 403)
confere("Origin do METAsrc: /pegou da 200", get("/pegou?n=999999", "https://www.metasrc.com")[0] == 200)
comum.fim()
