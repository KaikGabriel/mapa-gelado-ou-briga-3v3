"""Icone perto do relogio: aparece, clique esconde/mostra o painel, Sair tira o icone."""
import ctypes
from ctypes import wintypes

import comum
from comum import confere

mb = comum.carregar()


class NOTIFYICONIDENTIFIER(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("guidItem", ctypes.c_byte * 16)]


shell = ctypes.WinDLL("shell32")
u32 = ctypes.WinDLL("user32")
u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def icone_existe(hwnd) -> bool:
    ni = NOTIFYICONIDENTIFIER(ctypes.sizeof(NOTIFYICONIDENTIFIER), hwnd, 1)
    return shell.Shell_NotifyIconGetRect(ctypes.byref(ni), ctypes.byref(wintypes.RECT())) == 0


raiz, app = comum.painel(mb)
guardado = {}


def clique():
    u32.PostMessageW(app.bandeja.hwnd, mb.Bandeja.WM_BANDEJA, 0, 0x0202)   # WM_LBUTTONUP


def passo1():
    app.bandeja.pronto.wait(3)
    guardado["h"] = app.bandeja.hwnd
    confere("icone criado", bool(app.bandeja.hwnd) and icone_existe(app.bandeja.hwnd))
    confere("painel visivel no comeco", raiz.state() == "normal")
    clique()
    raiz.after(1000, passo2)


def passo2():
    confere("clique esconde o painel", raiz.state() == "withdrawn")
    clique()
    raiz.after(1000, passo3)


def passo3():
    confere("outro clique mostra de novo", raiz.state() == "normal")
    app.pedidos_bandeja.put("sair")   # o mesmo que o menu "Sair"


app.ler_fila()   # o painel le os pedidos do icone por aqui
raiz.after(1500, passo1)
raiz.mainloop()
confere("Sair tira o icone", not icone_existe(guardado.get("h")))
comum.fim()
