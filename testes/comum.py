"""Coisas que todos os testes usam.

Cada teste carrega o painel (mayhem_build.pyw) como modulo, usa uma pasta de dados temporaria
(nunca mexe na sua pasta %APPDATA%\\MayhemBuild) e finge ser o cliente do LoL quando precisa.
Os dados de cartinhas e tiers aqui sao inventados, so para testar.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAINEL = RAIZ / "mayhem_build.pyw"
falhas: list[str] = []


def carregar(porta: int | None = None):
    """Carrega o painel com uma pasta de dados temporaria e sem o OP.GG de verdade."""
    loader = importlib.machinery.SourceFileLoader("mb", str(PAINEL))
    spec = importlib.util.spec_from_loader("mb", loader)
    mb = importlib.util.module_from_spec(spec)
    loader.exec_module(mb)
    mb.CONFIG_DIR = Path(tempfile.mkdtemp(prefix="mayhembuild_teste_"))
    mb.DADOS = mb.DadosSite()
    mb.OPGG = mb.OpGG()
    mb.OPGG.dados = {}
    mb.OPGG.pedir = lambda nome, cid: None          # sem internet para o OP.GG nos testes comuns
    if porta:
        mb.DADOS_PORT = porta
        mb.iniciar_receptor()
    return mb


def confere(nome: str, cond) -> None:
    print(("OK    " if cond else "FALHA ") + nome, flush=True)
    if not cond:
        falhas.append(nome)


def fim() -> None:
    print("RESULTADO:", "tudo certo" if not falhas else f"{len(falhas)} falha(s): {falhas}", flush=True)
    sys.exit(1 if falhas else 0)


# ------------------------------------------------------------ dados de exemplo
RARIDADES = ["Prismatic", "Gold", "Silver"]
TIERS = ["S+", "S", "A", "B", "C"]


def cartas_exemplo(modo: str, campeao: str = "lee-sin") -> dict:
    """30 cartinhas inventadas (10 de cada raridade), no formato que o script do navegador manda."""
    cartas = [{"nome": f"Carta {r} {i}", "raridade": r, "tier": TIERS[i % len(TIERS)]}
              for r in RARIDADES for i in range(10)]
    return {"modo": modo, "campeao": campeao, "patch": "26.23", "cartas": cartas}


def ids(texto: str) -> list[dict]:
    return [{"id": i, "nome": ""} for i in texto.split()]


BUILD_MAYHEM = {"feiticos": ids("4 32"), "inicio": ids("1036 3133"),
                "itens": ids("6692 3111 6610 6333 3071 3156 2140"), "prismaticos": [],
                "habilidades": "Q > E > W"}
BUILD_ARENA = {"feiticos": [], "inicio": [], "itens": ids("3158 6692 6676 6333 4017 2142 3071"),
               "prismaticos": ids("446691 446632 447103 447115"), "habilidades": "Q > W > E"}


def mandar(mb, caminho: str, dados: dict) -> int:
    """POST no servidor do painel, como o script do navegador faz."""
    req = urllib.request.Request(f"http://127.0.0.1:{mb.DADOS_PORT}{caminho}", data=json.dumps(dados).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=5).status
    except urllib.error.HTTPError as e:
        return e.code


def tiers_arena(mb, tiers: dict[str, str]) -> None:
    """Coloca tiers da Arena inventados direto nos dados do painel ({nome do campeao: tier})."""
    campeoes = {mb.slug(n): {"tier": t, "score": 50.0, "lugar": 3.5, "pick": 1.0, "ban": 1.0}
                for n, t in tiers.items()}
    mb.DADOS.por_site["arena"] = {"patch": "26.23", "quando": time.time(), "campeoes": campeoes}


def opgg_exemplo(mb, nome: str, tier: str = "A", win: float = 51.0) -> None:
    """Registro do OP.GG inventado para um campeao do Mayhem."""
    mb.OPGG.dados[mb.slug(nome)] = {
        "quando": time.time(), "tier": tier, "win": win,
        "build": {"feiticos": ["4", "32"], "inicio": ["1036", "2003"],
                  "itens": ["6692", "3111", "6610", "6333", "3071", "3053", "3065"],
                  "prismaticos": [], "habilidades": "Q > E > W"},
        "cartas": [f"Carta OP.GG {i}" for i in range(8)]}


# --------------------------------------------------------- cliente falso do LoL
def fingir_cliente(mb, responder) -> None:
    """Troca a conversa com o cliente do LoL por `responder(caminho)`.

    `responder` devolve o JSON do caminho; para "sem selecao" levante mb.SemSessao.
    """
    from pathlib import Path as _P
    mb.achar_cliente = lambda: ("1", "x")
    mb.caminho_do_lol = lambda: _P("x")

    def lcu(_auth, caminho):
        if "owned-champions" in caminho or caminho.endswith("champion-summary.json"):
            return []
        return responder(caminho)

    mb.lcu = lcu


def ultimo_estado(fila, espera: float):
    time.sleep(espera)
    e = None
    while not fila.empty():
        e = fila.get()
    return e


def painel(mb):
    """Cria a janela do painel sem o leitor do cliente rodando por tras."""
    mb.Observador.start = lambda self: None
    mb.carregar_config = lambda: dict(mb.PADRAO)
    raiz = mb.tk.Tk()
    raiz.geometry("+40+40")
    return raiz, mb.App(raiz)


def fechar_painel(app, raiz) -> None:
    if app.bandeja:
        app.bandeja.fechar()
    raiz.destroy()
