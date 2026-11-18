"""MayhemBuild - abre a build do seu campeao no METAsrc (ARAM Mayhem e Arena).

Painel pequeno que acompanha a selecao de campeoes do League of Legends:
  * abre a build automaticamente quando voce pega/troca de campeao;
  * usa a pagina certa para o modo: Mayhem/ARAM ou Arena;
  * abre o navegador no monitor em que o LoL nao esta (quando ha dois);
  * mostra a build (feiticos, itens, habilidades) e as melhores cartinhas;
  * combos da Arena do canal King Nidhogg (arquivo combos_arena.json);
  * mostra os campeoes do banco do ARAM e dos aliados, um clique abre a build;
  * tier/winrate do METAsrc, melhores picks e sugestao de ban (Arena), com os
    dados enviados pelo script "metasrc_para_painel.user.js" (Tampermonkey);
  * inicia junto com o Windows e aparece/some junto com o cliente do LoL.

So usa a biblioteca padrao do Python. Rode com pythonw (sem janela preta):
    pyw mayhem_build.pyw
"""
from __future__ import annotations

import base64
import json
import os
import queue
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = "MayhemBuild"
BASE_URL = "https://www.metasrc.com/lol/{site}/champions/{slug}/build"
TIER_URL = "https://www.metasrc.com/lol/{site}/tier-list"
MAPA_ARAM = 12           # Abismo Uivante (ARAM e ARAM Mayhem)
# nome interno do modo no cliente -> (pagina no METAsrc, nome para mostrar)
MODOS = {"KIWI": ("mayhem", "Mayhem"), "CHERRY": ("arena", "Arena")}
ESPERA_TROCA = 1.5       # segundos com o mesmo campeao antes de abrir a pagina
LOCK_PORT = 47913        # impede abrir dois programas ao mesmo tempo
DADOS_PORT = 47914       # onde o script do navegador entrega os dados do site
QTD_SUGESTOES = 5
SCRIPT_NOME = "metasrc_para_painel.user.js"          # fica na mesma pasta deste programa
CONGELADO = getattr(sys, "frozen", False)            # rodando como .exe (PyInstaller)
PASTA_RECURSOS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
SCRIPT_ARQ = PASTA_RECURSOS / SCRIPT_NOME
ICONE_ARQ = PASTA_RECURSOS / "mayhembuild.ico"
COMBOS_ARQ = PASTA_RECURSOS / "combos_arena.json"   # combos do canal King Nidhogg (Arena)


def carregar_combos() -> list[dict]:
    try:
        return json.loads(COMBOS_ARQ.read_text(encoding="utf-8")).get("combos", [])
    except Exception:
        return []


COMBOS = carregar_combos()
ORDEM_FORCA = {"forte": 0, "boa": 1, "sorte": 2}


def combos_de(nome: str) -> list[tuple[dict, str]]:
    """[(combo, id do video)] em que o campeao aparece, do mais forte para o menos."""
    alvo = slug(nome)
    achados = []
    for combo in COMBOS:
        for campeao, video in combo.get("campeoes", {}).items():
            if slug(campeao) == alvo and re.fullmatch(r"[\w-]{11}", video):
                achados.append((combo, video))
    achados.sort(key=lambda cv: ORDEM_FORCA.get(cv[0].get("forca"), 9))
    return achados

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP
CONFIG_FILE = CONFIG_DIR / "config.json"
PADRAO = {"auto_abrir": True, "so_aram": True, "sempre_topo": True, "so_com_lol": True,
          "segundo_monitor": True}

TIERS = ["S+", "S", "A", "B", "C", "D"]
RARIDADES = [("Prismatic", "Prismatica"), ("Gold", "Ouro"), ("Silver", "Prata"), ("Item", "Item")]
QTD_CARTAS = 5           # cartinhas mostradas por raridade

# Nomes que o METAsrc escreve diferente
EXCECOES = {"Jarvan IV": "jarvan", "Nunu & Willump": "nunu", "MonkeyKing": "wukong"}


def slug(nome: str) -> str:
    if nome in EXCECOES:
        return EXCECOES[nome]
    s = re.sub(r"['.]", "", nome.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def site_de(modo: str) -> str:
    return MODOS.get(modo, MODOS["KIWI"])[0]


def url_build(nome: str, modo: str = "KIWI") -> str:
    return BASE_URL.format(site=site_de(modo), slug=slug(nome))


# ----------------------------------------------------------------- config ---
def carregar_config() -> dict:
    cfg = dict(PADRAO)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def salvar_config(cfg: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


# ----------------------------------------------- iniciar com o Windows -----
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _comando_inicio() -> str:
    # --auto: comeca escondido e so aparece quando o LoL abrir
    if CONGELADO:
        return f'"{sys.executable}" --auto'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    if pyw.exists():
        exe = pyw
    return f'"{exe}" "{Path(__file__).resolve()}" --auto'


def inicio_ativo() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
        return True
    except Exception:
        return False


def definir_inicio(ligar: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, _comando_inicio())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except FileNotFoundError:
                pass


# ------------------------------------------------- dados do METAsrc --------
class DadosSite:
    """Tiers/winrates do METAsrc que o script do navegador envia."""

    CAMPOS = ("tier", "score", "win", "top3", "lugar", "pick", "ban")

    def __init__(self):
        self.trava = threading.Lock()
        self.versao = 0                       # muda a cada envio (para redesenhar)
        self.por_site: dict[str, dict] = {}   # "arena" -> {"patch", "quando", "campeoes": {slug: {...}}}
        self.cartas: dict[str, dict] = {}     # "arena" -> {slug: {"patch", "quando", "cartas": [...]}}
        for site in ("mayhem", "arena"):
            try:
                self.por_site[site] = json.loads(self._arquivo(site).read_text(encoding="utf-8"))
            except Exception:
                pass
            try:
                self.cartas[site] = json.loads(self._arquivo_cartas(site).read_text(encoding="utf-8"))
            except Exception:
                self.cartas[site] = {}

    @staticmethod
    def _arquivo(site: str) -> Path:
        return CONFIG_DIR / f"metasrc_{site}.json"

    @staticmethod
    def _arquivo_cartas(site: str) -> Path:
        return CONFIG_DIR / f"cartas_{site}.json"

    def receber_cartas(self, bruto: dict) -> bool:
        site, campeao, lista = bruto.get("modo"), str(bruto.get("campeao", "")), bruto.get("cartas")
        if site not in ("mayhem", "arena") or not re.fullmatch(r"[a-z0-9-]{1,40}", campeao) \
                or not isinstance(lista, list):
            return False
        cartas = []
        for c in lista[:500]:
            if not isinstance(c, dict) or c.get("tier") not in TIERS:
                continue
            nome, raridade = str(c.get("nome", ""))[:60], str(c.get("raridade", ""))[:20]
            if nome and raridade:
                cartas.append({"nome": nome, "raridade": raridade, "tier": c["tier"]})
        if len(cartas) < 10:
            return False
        build = self._limpar_build(bruto.get("build"))
        with self.trava:
            self.cartas[site][campeao] = {"patch": str(bruto.get("patch", ""))[:10],
                                          "quando": time.time(), "cartas": cartas, "build": build}
            self.versao += 1
            copia = json.dumps(self.cartas[site])
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._arquivo_cartas(site).write_text(copia, encoding="utf-8")
        except Exception:
            pass
        return True

    @staticmethod
    def _limpar_build(b) -> dict | None:
        """So ids numericos e a ordem de habilidades no formato 'Q > E > W'."""
        if not isinstance(b, dict):
            return None
        limpo = {}
        for campo, maximo in (("feiticos", 2), ("inicio", 3), ("itens", 7), ("prismaticos", 4)):
            ids = []
            for x in b.get(campo) or []:
                i = str(x.get("id", "") if isinstance(x, dict) else x)
                if re.fullmatch(r"\d{1,7}", i) and i not in ids:
                    ids.append(i)
            limpo[campo] = ids[:maximo]
        hab = str(b.get("habilidades", ""))
        limpo["habilidades"] = hab if re.fullmatch(r"[QWE]( > [QWE]){0,2}", hab) else ""
        return limpo if any(limpo.values()) else None

    def tiers_cartas(self, nome: str, modo: str) -> dict[str, str]:
        """{nome da cartinha em minusculas: tier} para esse campeao."""
        with self.trava:
            reg = self.cartas.get(site_de(modo), {}).get(slug(nome))
        return {c["nome"].lower(): c["tier"] for c in (reg or {}).get("cartas", [])}

    def build_de(self, nome: str, modo: str) -> dict | None:
        with self.trava:
            reg = self.cartas.get(site_de(modo), {}).get(slug(nome))
        return (reg or {}).get("build")

    def cartas_de(self, nome: str, modo: str) -> list[tuple[str, str]]:
        """[(raridade, "Carta (S+) · Carta (S)")] com as melhores de cada raridade."""
        with self.trava:
            reg = self.cartas.get(site_de(modo), {}).get(slug(nome))
        if not reg:
            return []
        linhas = []
        for raridade, rotulo in RARIDADES:
            daqui = [c for c in reg["cartas"] if c["raridade"] == raridade]
            daqui.sort(key=lambda c: TIERS.index(c["tier"]))     # sort estavel: empate mantem a ordem do site
            if daqui:
                linhas.append((rotulo, "  ·  ".join(f"{c['nome']} ({c['tier']})"
                                                    for c in daqui[:QTD_CARTAS])))
        return linhas

    def receber(self, bruto: dict) -> bool:
        site = bruto.get("modo")
        campeoes = bruto.get("campeoes")
        if site not in ("mayhem", "arena") or not isinstance(campeoes, dict) or len(campeoes) < 50:
            return False
        limpo = {}
        for s, c in list(campeoes.items())[:400]:
            if not isinstance(c, dict) or not re.fullmatch(r"[a-z0-9-]{1,40}", str(s)):
                continue
            if c.get("tier") not in TIERS:
                continue
            item = {"tier": c["tier"]}
            for k in self.CAMPOS[1:]:
                if isinstance(c.get(k), (int, float)):
                    item[k] = float(c[k])
            limpo[s] = item
        if len(limpo) < 50:
            return False
        registro = {"patch": str(bruto.get("patch", ""))[:10], "quando": time.time(), "campeoes": limpo}
        with self.trava:
            self.por_site[site] = registro
            self.versao += 1
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._arquivo(site).write_text(json.dumps(registro), encoding="utf-8")
        except Exception:
            pass
        return True

    def de(self, nome: str, modo: str) -> dict | None:
        with self.trava:
            return self.por_site.get(site_de(modo), {}).get("campeoes", {}).get(slug(nome))

    def resumo(self) -> str:
        partes = []
        for site, rotulo in (("mayhem", "Mayhem"), ("arena", "Arena")):
            r = self.por_site.get(site)
            if not r:
                partes.append(f"{rotulo}: sem dados")
                continue
            dias = int((time.time() - r.get("quando", 0)) // 86400)
            quando = "hoje" if dias == 0 else ("ontem" if dias == 1 else f"ha {dias} dias")
            partes.append(f"{rotulo}: patch {r.get('patch') or '?'} ({quando})")
        return "Dados do site - " + "  |  ".join(partes)


def forca(st: dict | None) -> float:
    """Numero para ordenar: maior = mais forte."""
    if not st:
        return -1.0
    base = (len(TIERS) - TIERS.index(st["tier"])) * 100
    return base + st.get("score", 0)


def texto_site(st: dict | None, modo: str) -> str:
    if not st:
        return ""
    if modo == "CHERRY" and st.get("lugar"):
        return f"Tier {st['tier']}  {st['lugar']:.2f}º"
    return f"Tier {st['tier']}"


DADOS = DadosSite()


class Navegacao:
    """Manda o proximo campeao para uma aba de build do METAsrc que ja esta aberta.

    O script do navegador fica com um pedido aberto em GET /proxima. Quando voce troca de
    campeao, o painel responde esse pedido com a URL nova, a aba confirma em GET /pegou e
    troca de pagina sozinha. Sem aba aberta (ou se ela nao confirmar), abre uma aba nova.
    """

    def __init__(self):
        self.cond = threading.Condition()
        self.pendente: tuple[int, str] | None = None   # (numero, url) esperando uma aba
        self.confirmado = 0
        self.numero = 0
        self.esperando = 0          # abas com pedido aberto agora
        self.ultimo_contato = 0.0   # entre um pedido e o proximo passa so um instante

    def esperar(self, limite: float = 20.0) -> tuple[int, str] | None:
        """Chamado pela aba: espera ate ter um campeao novo (ou ate o limite)."""
        with self.cond:
            self.esperando += 1
            self.ultimo_contato = time.time()
            try:
                self.cond.wait_for(lambda: self.pendente is not None, timeout=limite)
                pedido, self.pendente = self.pendente, None   # so uma aba leva
                return pedido
            finally:
                self.esperando -= 1
                self.ultimo_contato = time.time()

    def confirmar(self, numero: int) -> None:
        with self.cond:
            self.confirmado = max(self.confirmado, numero)
            self.cond.notify_all()

    def entregar(self, url: str, limite: float = 2.5) -> bool:
        """True se uma aba aberta pegou a URL; False se nao tem aba (ai abre uma nova)."""
        with self.cond:
            if not self.esperando and time.time() - self.ultimo_contato > 3:
                return False
            self.numero += 1
            n = self.numero
            self.pendente = (n, url)
            self.cond.notify_all()
            ok = self.cond.wait_for(lambda: self.confirmado >= n, timeout=limite)
            if self.pendente and self.pendente[0] == n:
                self.pendente = None
            return ok


NAV = Navegacao()


class Receptor(BaseHTTPRequestHandler):
    """Recebe os dados do script do navegador (so de 127.0.0.1)."""

    def do_POST(self):
        origem = self.headers.get("Origin")
        receber = {"/dados": DADOS.receber, "/cartas": DADOS.receber_cartas}.get(self.path)
        if not receber or (origem and origem != "https://www.metasrc.com") \
                or not self.headers.get("Content-Type", "").startswith("application/json"):
            self.send_error(403)
            return
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            if tamanho > 2_000_000:
                raise ValueError
            ok = receber(json.loads(self.rfile.read(tamanho).decode("utf-8")))
        except Exception:
            ok = False
        self.send_response(200 if ok else 400)
        self.end_headers()

    def _json(self, dados: dict) -> None:
        corpo = json.dumps(dados).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        caminho, _, consulta = self.path.partition("?")
        if caminho in ("/proxima", "/pegou"):
            origem = self.headers.get("Origin")
            if origem and origem != "https://www.metasrc.com":
                self.send_error(403)
                return
            if caminho == "/proxima":   # a aba espera aqui pelo proximo campeao
                pedido = NAV.esperar()
                self._json({"n": pedido[0], "url": pedido[1]} if pedido else {})
            else:
                m = re.fullmatch(r"n=(\d{1,9})", consulta)
                if m:
                    NAV.confirmar(int(m.group(1)))
                self._json({})
            return
        # Abrir este endereco no navegador faz o Tampermonkey oferecer a instalacao
        if self.path != "/" + SCRIPT_NOME or not SCRIPT_ARQ.exists():
            self.send_error(404)
            return
        corpo = SCRIPT_ARQ.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass


def iniciar_receptor() -> None:
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", DADOS_PORT), Receptor)
    except OSError:
        return
    threading.Thread(target=servidor.serve_forever, daemon=True).start()


# ------------------------------------------------------- cliente do LoL ----
SSL_LOCAL = ssl.create_default_context()
SSL_LOCAL.check_hostname = False
SSL_LOCAL.verify_mode = ssl.CERT_NONE   # o cliente usa certificado proprio em 127.0.0.1
SEM_JANELA = 0x08000000                 # CREATE_NO_WINDOW


class SemSessao(Exception):
    pass


def caminho_do_lol() -> Path | None:
    """Caminho do LeagueClientUx.exe se o cliente do LoL estiver aberto (bem leve, sem abrir janelas)."""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.OpenProcess.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)          # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() == "leagueclientux.exe":
                h = k32.OpenProcess(0x1000, False, e.th32ProcessID)   # QUERY_LIMITED_INFORMATION
                if h:
                    try:
                        buf = ctypes.create_unicode_buffer(1024)
                        n = wintypes.DWORD(1024)
                        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                            return Path(buf.value)
                    finally:
                        k32.CloseHandle(h)
                return Path(r"C:\Riot Games\League of Legends\LeagueClientUx.exe")
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return None


def achar_cliente() -> tuple[str, str] | None:
    """Retorna (porta, token) da API local do cliente, ou None."""
    exe = caminho_do_lol()
    if not exe:
        return None
    try:  # o cliente escreve "lockfile" na propria pasta enquanto esta aberto
        partes = (exe.parent / "lockfile").read_text().split(":")
        return partes[2], partes[3]
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='LeagueClientUx.exe'\" | "
             "Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=10, creationflags=SEM_JANELA,
        ).stdout
        porta = re.search(r"--app-port=(\d+)", out)
        token = re.search(r"--remoting-auth-token=([\w-]+)", out)
        if porta and token:
            return porta.group(1), token.group(1)
    except Exception:
        pass
    for pasta in (r"C:\Riot Games\League of Legends", r"D:\Riot Games\League of Legends"):
        try:
            partes = (Path(pasta) / "lockfile").read_text().split(":")
            return partes[2], partes[3]
        except Exception:
            continue
    return None


def lcu(auth: tuple[str, str], caminho: str):
    porta, token = auth
    cred = base64.b64encode(f"riot:{token}".encode()).decode()
    req = urllib.request.Request(f"https://127.0.0.1:{porta}{caminho}",
                                 headers={"Authorization": f"Basic {cred}"})
    try:
        with urllib.request.urlopen(req, context=SSL_LOCAL, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SemSessao from e
        raise


# ------------------------------------------------------ segundo monitor ---
NAVEGADORES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe",
               "arc.exe", "zen.exe", "librewolf.exe", "waterfox.exe", "chromium.exe", "yandex.exe"}


def _exe_da_janela(u32, k32, hwnd) -> str:
    from ctypes import wintypes
    import ctypes
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return Path(buf.value).name.lower()
    finally:
        k32.CloseHandle(h)
    return ""


def mover_navegador_para_outro_monitor(espera: float = 5.0) -> None:
    """Coloca a janela do navegador num monitor diferente do monitor do LoL.

    Com um monitor so, nao faz nada. Se a janela ja esta no outro monitor, deixa onde esta.
    """
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    u32.MonitorFromWindow.restype = wintypes.HMONITOR
    u32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    u32.GetForegroundWindow.restype = wintypes.HWND
    u32.FindWindowW.restype = wintypes.HWND
    try:   # coordenadas reais em telas com escala (125%, 150%...)
        u32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    monitores = []   # (handle, area util, principal?)
    TIPO = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                              ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cada(hmon, _hdc, _rc, _lp):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        if u32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            monitores.append((hmon, mi.rcWork, bool(mi.dwFlags & 1)))
        return True

    u32.EnumDisplayMonitors(None, None, TIPO(cada), 0)
    if len(monitores) < 2:
        return

    # o monitor do LoL: o cliente (RCLIENT) ou o jogo; sem eles, o principal
    lol = u32.FindWindowW("RCLIENT", None) or u32.FindWindowW("RiotWindowClass", None)
    mon_lol = u32.MonitorFromWindow(lol, 2) if lol else next(m for m, _, p in monitores if p)
    alvo = next(((m, r) for m, r, p in monitores if m != mon_lol and not p), None) \
        or next(((m, r) for m, r, _ in monitores if m != mon_lol), None)
    if not alvo:
        return
    mon_alvo, area = alvo

    # espera a janela do navegador aparecer (normalmente vem para a frente)
    janela = None
    fim = time.time() + espera
    while time.time() < fim and not janela:
        h = u32.GetForegroundWindow()
        if h and _exe_da_janela(u32, k32, h) in NAVEGADORES:
            janela = h
        else:
            time.sleep(0.2)
    if not janela:   # nao veio para a frente: pega a janela de navegador mais no topo
        achadas = []
        TIPO_J = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cada_janela(h, _lp):
            if (u32.IsWindowVisible(h) and u32.GetWindowTextLengthW(h)
                    and not u32.GetWindow(h, 4)   # GW_OWNER: so janelas principais
                    and _exe_da_janela(u32, k32, h) in NAVEGADORES):
                achadas.append(h)
                return False
            return True

        u32.EnumWindows(TIPO_J(cada_janela), 0)
        janela = achadas[0] if achadas else None
    if not janela or u32.MonitorFromWindow(janela, 2) == mon_alvo:
        return

    maximizada = bool(u32.IsZoomed(janela))
    if maximizada or u32.IsIconic(janela):
        u32.ShowWindow(janela, 9)    # SW_RESTORE
    rc = wintypes.RECT()
    u32.GetWindowRect(janela, ctypes.byref(rc))
    lw, lh = area.right - area.left, area.bottom - area.top
    w, h = min(rc.right - rc.left, lw), min(rc.bottom - rc.top, lh)
    x, y = area.left + (lw - w) // 2, area.top + (lh - h) // 2
    u32.SetWindowPos(janela, None, x, y, w, h, 0x0004 | 0x0010)   # SWP_NOZORDER | SWP_NOACTIVATE
    if maximizada:
        u32.ShowWindow(janela, 3)    # SW_MAXIMIZE


def abrir(url: str, segundo_monitor: bool = True) -> None:
    """Abre a pagina no navegador e, se der, joga a janela para o outro monitor."""
    webbrowser.open(url)
    if segundo_monitor and sys.platform == "win32":
        threading.Thread(target=lambda: _sem_erro(mover_navegador_para_outro_monitor), daemon=True).start()


def abrir_build(url: str, segundo_monitor: bool = True) -> None:
    """Build de campeao: troca a pagina da aba do METAsrc que ja esta aberta; sem aba, abre uma."""
    def tentar():
        if not NAV.entregar(url):
            abrir(url, segundo_monitor)
    threading.Thread(target=lambda: _sem_erro(tentar), daemon=True).start()


def _sem_erro(f):
    try:
        f()
    except Exception:
        pass


def baixar(url: str, timeout=10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": APP})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- worker ---
VAZIO = {"meu": None, "build": None, "cartas": [], "combos": [], "banco": [], "aliados": [], "bans": [], "picks": [], "aviso": ""}


class Observador(threading.Thread):
    """Le o cliente em segundo plano e manda o estado para a interface."""

    def __init__(self, saida: queue.Queue, cfg: dict):
        super().__init__(daemon=True)
        self.saida, self.cfg = saida, cfg
        self.campeoes: dict[int, tuple[str, str]] = {}   # id -> (chave ddragon, nome)
        self.versao = None
        self.icones: dict[int, bytes] = {}
        self.modo = "KIWI"      # modo da selecao atual
        self.meus: set[int] = set()   # campeoes que voce pode jogar
        self.itens: dict[str, str] = {}                  # id do item -> nome (pt_BR)
        self.feiticos: dict[str, tuple[str, str]] = {}   # id do feitico -> (chave ddragon, nome)
        self.imgs_build: dict[str, bytes | None] = {}

    # dados dos campeoes (nomes em ingles + icones)
    def carregar_campeoes(self, auth):
        if self.campeoes:
            return
        try:
            self.versao = json.loads(baixar("https://ddragon.leagueoflegends.com/api/versions.json"))[0]
            dados = json.loads(baixar(
                f"https://ddragon.leagueoflegends.com/cdn/{self.versao}/data/en_US/champion.json"))
            for c in dados["data"].values():
                self.campeoes[int(c["key"])] = (c["id"], c["name"])
        except Exception:
            pass
        try:  # nomes dos itens e feiticos (para a build)
            base = f"https://ddragon.leagueoflegends.com/cdn/{self.versao}/data/pt_BR"
            self.itens = {k: v["name"] for k, v in json.loads(baixar(f"{base}/item.json"))["data"].items()}
            self.feiticos = {v["key"]: (v["id"], v["name"])
                             for v in json.loads(baixar(f"{base}/summoner.json"))["data"].values()}
        except Exception:
            pass
        try:  # completa com o cliente (campeoes novos)
            for c in lcu(auth, "/lol-game-data/assets/v1/champion-summary.json"):
                if c["id"] > 0 and c["id"] not in self.campeoes:
                    self.campeoes[c["id"]] = (c.get("alias", ""), c["name"])
        except Exception:
            pass

    def carregar_meus(self, auth):
        try:
            self.meus = {int(c["id"]) for c in lcu(auth, "/lol-champions/v1/owned-champions-minimal")
                         if c.get("ownership", {}).get("owned") or c.get("freeToPlay")
                         or c.get("ownership", {}).get("rental", {}).get("rented")}
        except Exception:
            pass

    def icone(self, cid: int) -> bytes | None:
        if cid in self.icones:
            return self.icones[cid]
        chave = self.campeoes.get(cid, ("", ""))[0]
        dado = None
        if self.versao and chave:
            try:
                dado = baixar(f"https://ddragon.leagueoflegends.com/cdn/{self.versao}/img/champion/{chave}.png")
            except Exception:
                pass
        self.icones[cid] = dado
        return dado

    def img_build(self, caminho: str) -> bytes | None:
        """Icone de item/feitico do Data Dragon (com cache)."""
        if caminho not in self.imgs_build:
            dado = None
            if self.versao:
                try:
                    dado = baixar(f"https://ddragon.leagueoflegends.com/cdn/{self.versao}/img/{caminho}")
                except Exception:
                    pass
            self.imgs_build[caminho] = dado
        return self.imgs_build[caminho]

    def montar_build(self, cid: int) -> dict | None:
        b = DADOS.build_de(self.nome(cid), self.modo)
        if not b:
            return None
        url = url_build(self.nome(cid), self.modo)

        def item(i):
            return {"chave": f"item/{i}", "nome": self.itens.get(i, f"item {i}"),
                    "icone": self.img_build(f"item/{i}.png"), "url": url}

        def feitico(k):
            chave, nome = self.feiticos.get(k, ("", f"feitico {k}"))
            return {"chave": f"spell/{k}", "nome": nome, "url": url,
                    "icone": self.img_build(f"spell/{chave}.png") if chave else None}

        linhas = []
        if b.get("feiticos"):
            linhas.append(("Feiticos", [feitico(k) for k in b["feiticos"]]))
        if b.get("inicio"):
            linhas.append(("Inicio", [item(i) for i in b["inicio"]]))
        if b.get("itens"):
            linhas.append(("Itens", [item(i) for i in b["itens"]]))
        if b.get("prismaticos"):
            linhas.append(("Prismaticos", [item(i) for i in b["prismaticos"]]))
        return {"linhas": linhas, "habilidades": b.get("habilidades", "")}

    def nome(self, cid: int) -> str:
        return self.campeoes.get(cid, ("", f"#{cid}"))[1]

    def site(self, cid: int) -> dict | None:
        return DADOS.de(self.nome(cid), self.modo)

    def info(self, cid: int, destaque: bool = False) -> dict:
        nome = self.nome(cid)
        linhas = [nome, texto_site(self.site(cid), self.modo)]
        if destaque:
            linhas[0] = "★ " + nome
        if self.modo == "CHERRY" and any(c.get("forca") == "forte" for c, _ in combos_de(nome)):
            linhas.append("▶ tem combo")
        return {"id": cid, "nome": nome, "icone": self.icone(cid),
                "texto": "\n".join(l for l in linhas if l), "url": url_build(nome, self.modo),
                "destaque": destaque}

    def montar_combos(self, cid: int) -> list[dict]:
        """Combos do King Nidhogg para o seu campeao, com o tier de cada cartinha no METAsrc."""
        nome = self.nome(cid)
        tiers = DADOS.tiers_cartas(nome, self.modo)
        return [{"nome": c["nome"], "forca": c.get("forca", ""), "dica": c.get("dica", ""),
                 "cartinhas": [(a, tiers.get(a.lower(), "")) for a in c.get("cartinhas", [])],
                 "video": f"https://www.youtube.com/watch?v={video}"}
                for c, video in combos_de(nome)]

    def sugestoes(self, indisponiveis: set[int], para_ban: bool) -> list[int]:
        candidatos = [c for c in self.campeoes if c not in indisponiveis and self.site(c)
                      and (para_ban or not self.meus or c in self.meus)]
        if para_ban:
            # forte E muito escolhido = o que mais vai aparecer contra voce
            def chave(c):
                st = self.site(c)
                return forca(st) * (st.get("pick", 1.0) ** 0.5)
        else:   # so o que o site diz
            chave = lambda c: forca(self.site(c))
        candidatos.sort(key=chave, reverse=True)
        return candidatos[:QTD_SUGESTOES]

    def enviar(self, status, lol=True, **estado):
        self.saida.put({"status": status, "fonte": DADOS.resumo(), "lol": lol, **{**VAZIO, **estado}})

    def montar(self, sessao, cid) -> dict:
        eu_cell = sessao.get("localPlayerCellId")
        banco = [int(b.get("championId", 0)) for b in sessao.get("benchChampions", []) or []]
        banco += [int(b) for b in sessao.get("benchChampionIds", []) or []]
        banco = [b for b in dict.fromkeys(banco) if b > 0]
        banco.sort(key=lambda c: forca(self.site(c)), reverse=True)

        aliados = [int(p.get("championId") or 0) for p in sessao.get("myTeam", [])
                   if p.get("cellId") != eu_cell]
        aliados = [a for a in aliados if a > 0]

        # Mayhem: estrela no campeao do banco que e mais forte que o seu
        melhor = None
        if banco and self.site(banco[0]) and forca(self.site(banco[0])) > forca(self.site(cid)):
            melhor = banco[0]

        estado = {"meu": self.info(cid) if cid else None,
                  "cartas": DADOS.cartas_de(self.nome(cid), self.modo) if cid else [],
                  "build": self.montar_build(cid) if cid else None,
                  "combos": self.montar_combos(cid) if cid and self.modo == "CHERRY" else [],
                  "banco": [self.info(b, b == melhor) for b in banco],
                  "aliados": [self.info(a) for a in aliados]}

        if self.modo == "CHERRY" and DADOS.por_site.get("arena"):
            indisp: set[int] = set()
            minha_vez_ban = False
            for grupo in sessao.get("actions", []) or []:
                for a in grupo:
                    if a.get("championId"):
                        indisp.add(int(a["championId"]))
                    if (a.get("actorCellId") == eu_cell and a.get("type") == "ban"
                            and a.get("isInProgress")):
                        minha_vez_ban = True
            for time_ in ("myTeam", "theirTeam"):
                for p in sessao.get(time_, []) or []:
                    for k in ("championId", "championPickIntent"):
                        if p.get(k):
                            indisp.add(int(p[k]))
            bans = sessao.get("bans", {}) or {}
            for k in ("myTeamBans", "theirTeamBans"):
                indisp.update(int(b) for b in bans.get(k, []) or [] if b)
            estado["bans"] = [self.info(c) for c in self.sugestoes(indisp, para_ban=True)]
            estado["picks"] = [self.info(c) for c in self.sugestoes(indisp | {cid}, para_ban=False)]
            if minha_vez_ban:
                estado["aviso"] = "SUA VEZ DE BANIR!"
        estado["modo"] = self.modo
        return estado

    def run(self):
        auth = None
        aberto = candidato = 0
        desde = 0.0
        fila_ok = None          # None = ainda nao checou nesta selecao
        fila_nome = ""
        ultimo = None
        while True:
            try:
                if not auth:
                    if not caminho_do_lol():        # checagem leve enquanto o LoL esta fechado
                        if ultimo != "sem_lol":
                            ultimo = "sem_lol"
                            self.enviar("Esperando o LoL abrir...", lol=False)
                        time.sleep(3)
                        continue
                    auth = achar_cliente()
                    if not auth:                    # cliente ainda carregando
                        self.enviar("LoL abrindo...")
                        time.sleep(2)
                        continue
                    ultimo = None
                    self.carregar_campeoes(auth)
                    self.carregar_meus(auth)

                try:
                    sessao = lcu(auth, "/lol-champ-select/v1/session")
                except SemSessao:
                    sessao = None

                if not sessao:
                    aberto = candidato = 0
                    if fila_ok is not None or ultimo != ("fora", DADOS.versao):
                        ultimo = ("fora", DADOS.versao)
                        self.enviar("Conectado. Esperando a selecao de campeoes...")
                    fila_ok = None
                    time.sleep(1)
                    continue

                if fila_ok is None:          # entrou agora numa selecao
                    self.carregar_meus(auth)
                    try:
                        fluxo = lcu(auth, "/lol-gameflow/v1/session")
                        q = fluxo.get("gameData", {}).get("queue", {})
                        if q.get("gameMode") == "CHERRY":
                            self.modo, fila_ok = "CHERRY", True
                        else:   # Mayhem, ARAM normal ou outro modo (usa a pagina do Mayhem)
                            self.modo, fila_ok = "KIWI", q.get("mapId") == MAPA_ARAM
                        fila_nome = q.get("description") or q.get("gameMode") or ""
                    except Exception:
                        self.modo, fila_ok, fila_nome = "KIWI", True, ""

                eu = next((p for p in sessao.get("myTeam", [])
                           if p.get("cellId") == sessao.get("localPlayerCellId")), {})
                cid = int(eu.get("championId") or eu.get("championPickIntent") or 0)

                ativo = fila_ok or not self.cfg["so_aram"]
                status = f"Selecao: {fila_nome}" if fila_nome else "Selecao de campeoes"
                if not ativo:
                    status += "  (nao e Mayhem/Arena, nao abre sozinho)"

                chave = (json.dumps(sessao.get("myTeam"), sort_keys=True),
                         json.dumps(sessao.get("benchChampions"), sort_keys=True),
                         json.dumps(sessao.get("actions"), sort_keys=True) if self.modo == "CHERRY" else "",
                         status, DADOS.versao)
                if chave != ultimo:
                    ultimo = chave
                    self.enviar(status, **self.montar(sessao, cid))

                if cid != candidato:
                    candidato, desde = cid, time.time()
                if (candidato and candidato != aberto and ativo and self.cfg["auto_abrir"]
                        and time.time() - desde >= ESPERA_TROCA):
                    abrir_build(url_build(self.nome(candidato), self.modo), self.cfg["segundo_monitor"])
                    aberto = candidato
            except Exception:
                auth, ultimo = None, None
                self.enviar("Conexao com o LoL perdida, tentando de novo...")
                time.sleep(3)
                continue
            time.sleep(0.7)


# --------------------------------------------------------------------- UI ---
FUNDO, CARTAO, TEXTO, APAGADO, DESTAQUE, ALERTA, BOM = (
    "#0f1419", "#1b232c", "#e8e6e3", "#8a949e", "#c8a24a", "#e5534b", "#57ab5a")


COR_RARIDADE = {"Prismatica": "#c58af9", "Ouro": "#e3b341", "Prata": "#adbac7", "Item": "#6cb6ff"}


class App:
    def __init__(self, raiz: tk.Tk, auto: bool = False):
        self.raiz = raiz
        self.cfg = carregar_config()
        self.fila: queue.Queue = queue.Queue()
        self.imagens: dict = {}
        self.lol_aberto = None      # None = ainda nao sabe
        self.fechado = False        # voce fechou o painel com o LoL aberto

        # iniciado pelo Windows: fica escondido ate o LoL abrir
        if auto and self.cfg["so_com_lol"]:
            raiz.withdraw()
        raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        try:
            raiz.iconbitmap(default=str(ICONE_ARQ))
        except Exception:
            pass
        raiz.title(APP)
        raiz.configure(bg=FUNDO)
        raiz.resizable(False, False)
        raiz.attributes("-topmost", self.cfg["sempre_topo"])

        fonte = ("Segoe UI", 10)
        self.status = tk.Label(raiz, text="Iniciando...", bg=FUNDO, fg=APAGADO, font=("Segoe UI", 9),
                               anchor="w", wraplength=360, justify="left")
        self.status.pack(fill="x", padx=12, pady=(10, 0))
        self.aviso = tk.Label(raiz, text="", bg=FUNDO, fg=ALERTA, font=("Segoe UI", 11, "bold"), anchor="w")
        self.aviso.pack(fill="x", padx=12)

        self.meu = self._secao("SEU CAMPEAO")
        self.build = self._secao("BUILD (METAsrc)")
        self.cartas = self._secao("CARTINHAS RECOMENDADAS (METAsrc, so na selecao)")
        self.combos = self._secao('COMBOS DO KING NIDHOGG, o "Japonês do Arena"', cor=BOM)
        self.banco = self._secao("BANCO (ordenado pelo tier, ★ = melhor que o seu)")
        self.aliados = self._secao("ALIADOS")
        # so aparecem na Arena com dados do site
        self.area_arena = tk.Frame(raiz, bg=FUNDO)
        self.area_arena.pack(fill="x")
        self.bans = self._secao("SUGESTAO DE BAN (fortes e muito escolhidos)", self.area_arena, ALERTA)
        self.picks = self._secao("MELHORES PICKS (tier do site)", self.area_arena, BOM)

        tk.Label(raiz, text="Tier = METAsrc. Na Arena: colocacao media (menor = melhor).",
                 bg=FUNDO, fg=APAGADO, font=("Segoe UI", 8), anchor="w", justify="left").pack(fill="x", padx=12)

        linha = tk.Frame(raiz, bg=FUNDO)
        linha.pack(fill="x", padx=12, pady=(6, 0))
        self.fonte = tk.Label(linha, text=DADOS.resumo(), bg=FUNDO, fg=APAGADO, font=("Segoe UI", 8),
                              anchor="w", wraplength=360, justify="left")
        self.fonte.pack(fill="x")
        botoes = tk.Frame(raiz, bg=FUNDO)
        botoes.pack(fill="x", padx=12, pady=(2, 4))
        links = [("Instalar script", f"http://127.0.0.1:{DADOS_PORT}/{SCRIPT_NOME}"),
                 ("Atualizar Mayhem", TIER_URL.format(site="mayhem")),
                 ("Atualizar Arena", TIER_URL.format(site="arena"))]
        for rotulo, url in links:
            tk.Button(botoes, text=rotulo, command=lambda u=url: abrir(u, self.cfg["segundo_monitor"]),
                      bg=CARTAO, fg=TEXTO, activebackground=FUNDO, activeforeground=DESTAQUE,
                      relief="flat", font=("Segoe UI", 8), cursor="hand2", padx=8).pack(side="left", padx=(0, 6))
        tk.Button(botoes, text="Sair", command=self.sair, bg=CARTAO, fg=ALERTA, activebackground=FUNDO,
                  activeforeground=ALERTA, relief="flat", font=("Segoe UI", 8), cursor="hand2",
                  padx=8).pack(side="right")

        opcoes = tk.Frame(raiz, bg=FUNDO)
        opcoes.pack(fill="x", padx=8, pady=(0, 10))
        self.vars = {}
        for chave, texto in (("auto_abrir", "Abrir a build automaticamente"),
                             ("so_aram", "So no ARAM / Mayhem / Arena"),
                             ("sempre_topo", "Sempre por cima das janelas"),
                             ("so_com_lol", "Aparecer so quando o LoL estiver aberto"),
                             ("segundo_monitor", "Abrir o navegador no outro monitor")):
            v = tk.BooleanVar(value=self.cfg[chave])
            self.vars[chave] = v
            self._check(opcoes, texto, v, lambda c=chave: self.mudou(c), fonte)
        self.var_inicio = tk.BooleanVar(value=inicio_ativo())
        self._check(opcoes, "Iniciar junto com o Windows", self.var_inicio, self.mudou_inicio, fonte)

        self.render(dict(VAZIO))
        Observador(self.fila, self.cfg).start()
        self.raiz.after(200, self.ler_fila)

    def _secao(self, titulo, pai=None, cor=DESTAQUE):
        caixa = tk.Frame(pai or self.raiz, bg=FUNDO)   # titulo + quadro (para poder esconder)
        caixa.pack(fill="x")
        tk.Label(caixa, text=titulo, bg=FUNDO, fg=cor, font=("Segoe UI", 8, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(6, 0))
        quadro = tk.Frame(caixa, bg=CARTAO)
        quadro.pack(fill="x", padx=12, pady=(2, 0))
        return quadro

    def _check(self, pai, texto, var, cmd, fonte):
        tk.Checkbutton(pai, text=texto, variable=var, command=cmd, bg=FUNDO, fg=TEXTO,
                       selectcolor=CARTAO, activebackground=FUNDO, activeforeground=TEXTO,
                       font=fonte, anchor="w").pack(fill="x")

    def mudou(self, chave):
        self.cfg[chave] = self.vars[chave].get()
        salvar_config(self.cfg)
        if chave == "sempre_topo":
            self.raiz.attributes("-topmost", self.cfg["sempre_topo"])

    def mudou_inicio(self):
        try:
            definir_inicio(self.var_inicio.get())
        except Exception:
            self.var_inicio.set(inicio_ativo())

    def img(self, c: dict, tamanho=1) -> tk.PhotoImage | None:
        if not c.get("icone"):
            return None
        chave = (c["id"], tamanho)
        if chave not in self.imagens:
            try:
                foto = tk.PhotoImage(data=base64.b64encode(c["icone"]))
                self.imagens[chave] = foto.subsample(tamanho) if tamanho > 1 else foto
            except Exception:
                return None
        return self.imagens[chave]

    def img_build(self, peca: dict) -> tk.PhotoImage | None:
        """Icone de item/feitico (64px no Data Dragon) reduzido para 32px."""
        if not peca.get("icone"):
            return None
        chave = ("build", peca["chave"])
        if chave not in self.imagens:
            try:
                self.imagens[chave] = tk.PhotoImage(data=base64.b64encode(peca["icone"])).subsample(2)
            except Exception:
                return None
        return self.imagens[chave]

    def render_combos(self, combos: list[dict]):
        cores = {"forte": BOM, "boa": DESTAQUE, "sorte": APAGADO}
        rotulos = {"forte": "FORTE", "boa": "BOA", "sorte": "SORTE"}
        for i, c in enumerate(combos):
            cor = cores.get(c["forca"], TEXTO)
            tk.Label(self.combos, text=rotulos.get(c["forca"], ""), bg=CARTAO, fg=cor,
                     font=("Segoe UI", 7, "bold"), anchor="nw").grid(row=i, column=0, sticky="nw",
                                                                     padx=(8, 6), pady=(5, 0))
            caixa = tk.Frame(self.combos, bg=CARTAO)
            caixa.grid(row=i, column=1, sticky="w", pady=(3, 2))
            cartas = "  +  ".join(f"{nome} ({tier})" if tier else nome for nome, tier in c["cartinhas"])
            tk.Label(caixa, text=f"{c['nome']}:  {cartas}", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 8, "bold"),
                     anchor="w", justify="left", wraplength=420).pack(anchor="w")
            if c["dica"]:
                tk.Label(caixa, text=c["dica"], bg=CARTAO, fg=APAGADO, font=("Segoe UI", 8), anchor="w",
                         justify="left", wraplength=420).pack(anchor="w")
            tk.Button(self.combos, text="▶ video", command=lambda u=c["video"]: abrir(u, self.cfg["segundo_monitor"]),
                      bg=CARTAO, fg=ALERTA, activebackground=FUNDO, activeforeground=ALERTA, relief="flat",
                      font=("Segoe UI", 8, "bold"), cursor="hand2").grid(row=i, column=2, sticky="ne",
                                                                          padx=(4, 8), pady=(3, 0))
        tk.Label(self.combos, text="(tier) = tier da cartinha para este campeao no METAsrc",
                 bg=CARTAO, fg=APAGADO, font=("Segoe UI", 7), anchor="w").grid(
            row=len(combos), column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))

    def render_build(self, build: dict | None):
        if not build:
            tk.Label(self.build, text="ainda nao carregou: abra a build deste campeao (clique no icone acima)",
                     bg=CARTAO, fg=APAGADO, font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=6)
            return
        linha = 0
        for rotulo, pecas in build["linhas"]:
            tk.Label(self.build, text=rotulo, bg=CARTAO, fg=DESTAQUE, font=("Segoe UI", 8, "bold"),
                     anchor="nw").grid(row=linha, column=0, sticky="nw", padx=(8, 6), pady=(4, 0))
            fila = tk.Frame(self.build, bg=CARTAO)
            fila.grid(row=linha, column=1, sticky="w", pady=(2, 0))
            for n, p in enumerate(pecas):
                # numero na frente dos itens = ordem de compra
                texto = f"{n + 1}. {p['nome']}" if rotulo == "Itens" else p["nome"]
                tk.Button(fila, image=self.img_build(p), text=texto, compound="top",
                          command=lambda u=p["url"]: abrir(u, self.cfg["segundo_monitor"]), bg=CARTAO, fg=TEXTO,
                          activebackground=FUNDO, activeforeground=DESTAQUE, relief="flat", bd=0,
                          cursor="hand2", font=("Segoe UI", 7), wraplength=66, width=66,
                          padx=1, pady=1).pack(side="left", anchor="n", padx=1)
            linha += 1
        if build.get("habilidades"):
            tk.Label(self.build, text="Habilidades", bg=CARTAO, fg=DESTAQUE, font=("Segoe UI", 8, "bold"),
                     anchor="w").grid(row=linha, column=0, sticky="w", padx=(8, 6), pady=(4, 6))
            tk.Label(self.build, text=f"maximizar {build['habilidades']}", bg=CARTAO, fg=TEXTO,
                     font=("Segoe UI", 10, "bold"), anchor="w").grid(row=linha, column=1, sticky="w",
                                                                     pady=(4, 6))

    def botao(self, pai, c: dict, tamanho, texto_lado=False):
        texto = c["texto"].replace("\n", "   ", 1) if texto_lado else c["texto"]
        return tk.Button(pai, image=self.img(c, tamanho), text=texto,
                         compound="left" if texto_lado else "top", justify="left" if texto_lado else "center",
                         command=lambda u=c["url"]: abrir_build(u, self.cfg["segundo_monitor"]),
                         bg=CARTAO, fg=DESTAQUE if c.get("destaque") else TEXTO,
                         activebackground=FUNDO, activeforeground=DESTAQUE, relief="flat", bd=0,
                         cursor="hand2", font=("Segoe UI", 10 if texto_lado else 8,
                                                "bold" if texto_lado or c.get("destaque") else "normal"),
                         padx=6, pady=4)

    def render(self, e: dict):
        for quadro in (self.meu, self.build, self.cartas, self.combos, self.banco, self.aliados, self.bans,
                       self.picks):
            for w in quadro.winfo_children():
                w.destroy()
        if e["meu"]:
            self.botao(self.meu, e["meu"], 2, texto_lado=True).pack(anchor="w", padx=4, pady=4)
        else:
            tk.Label(self.meu, text="-", bg=CARTAO, fg=APAGADO).pack(anchor="w", padx=8, pady=8)
        if e["meu"]:
            self.build.master.pack(fill="x", after=self.meu.master)
            self.render_build(e.get("build"))
        else:
            self.build.master.pack_forget()
        if e["meu"]:
            self.cartas.master.pack(fill="x", after=self.build.master)
            if e["cartas"]:
                for i, (rotulo, texto) in enumerate(e["cartas"]):
                    tk.Label(self.cartas, text=rotulo, bg=CARTAO, fg=COR_RARIDADE.get(rotulo, TEXTO),
                             font=("Segoe UI", 8, "bold"), anchor="nw").grid(row=i, column=0, sticky="nw",
                                                                             padx=(8, 4), pady=2)
                    tk.Label(self.cartas, text=texto, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 8),
                             anchor="w", justify="left", wraplength=440).grid(row=i, column=1, sticky="w",
                                                                              padx=(0, 8), pady=2)
            else:
                tk.Label(self.cartas, text="ainda nao carregou: abra a build deste campeao "
                                           "(clique no icone acima)",
                         bg=CARTAO, fg=APAGADO, font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=6)
        else:
            self.cartas.master.pack_forget()
        if e.get("combos"):
            self.combos.master.pack(fill="x", after=self.cartas.master)
            self.render_combos(e["combos"])
        else:
            self.combos.master.pack_forget()
        for quadro, lista in ((self.banco, e["banco"]), (self.aliados, e["aliados"]),
                              (self.bans, e["bans"]), (self.picks, e["picks"])):
            if lista:
                for i, c in enumerate(lista):
                    self.botao(quadro, c, 3).grid(row=i // 5, column=i % 5, padx=2, pady=2)
            else:
                tk.Label(quadro, text="vazio", bg=CARTAO, fg=APAGADO).pack(anchor="w", padx=8, pady=8)
        if e.get("modo") == "CHERRY":              # Arena nao tem banco
            self.banco.master.pack_forget()
        else:
            self.banco.master.pack(fill="x", after=self.cartas.master if e["meu"] else self.meu.master)
        if not e.get("combos"):
            self.combos.master.pack_forget()
        if e["bans"] or e["picks"]:
            self.area_arena.pack(fill="x", after=self.aliados.master)
        else:
            self.area_arena.pack_forget()
        self.aviso.config(text=e.get("aviso", ""))

    def fechar(self):
        """X da janela: com o LoL aberto so esconde (volta na proxima vez que o LoL abrir)."""
        if self.cfg["so_com_lol"] and self.lol_aberto:
            self.fechado = True
            self.raiz.withdraw()
        else:
            self.sair()

    def sair(self):
        self.raiz.destroy()

    def ler_fila(self):
        estado = None
        while not self.fila.empty():
            estado = self.fila.get_nowait()
        if estado:
            self.status.config(text=estado["status"])
            self.fonte.config(text=estado["fonte"])
            self.render(estado)
            lol = estado.get("lol", True)
            if lol != self.lol_aberto:
                antes, self.lol_aberto = self.lol_aberto, lol
                if lol and not self.fechado:
                    self.raiz.deiconify()
                    self.raiz.lift()
                elif not lol:
                    self.fechado = False
                    if antes and self.cfg["so_com_lol"]:   # o LoL fechou: esconde junto
                        self.raiz.withdraw()
        self.raiz.after(300, self.ler_fila)


def main():
    trava = socket.socket()
    try:
        trava.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        return  # ja esta aberto
    iniciar_receptor()
    # .exe: liga o "iniciar com o Windows" na primeira vez e mantem o caminho certo
    # se voce mover o arquivo
    if CONGELADO:
        cfg = carregar_config()
        if not cfg.get("inicio_configurado") or inicio_ativo():
            try:
                definir_inicio(True)
                cfg["inicio_configurado"] = True
                salvar_config(cfg)
            except Exception:
                pass
    raiz = tk.Tk()
    App(raiz, auto="--auto" in sys.argv)
    raiz.mainloop()


if __name__ == "__main__":
    main()
