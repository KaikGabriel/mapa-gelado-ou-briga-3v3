"""Abre uma janela NOVA do navegador no outro monitor e confere que as janelas que ja estavam abertas
nao sairam do lugar. Abre e fecha uma janela de verdade, por isso so roda com --interativo.
"""
import ctypes
import time
from ctypes import wintypes

import comum
from comum import confere

mb = comum.carregar()
u32, k32 = mb._win32()
exe = mb.navegador_padrao()
print("(navegador padrao:", exe, ")")
area = mb.area_do_outro_monitor(u32)
if not exe or not area:
    print("(sem navegador conhecido ou sem segundo monitor: nada a testar)")
    comum.fim()
nome = exe.name.lower()


def retangulo(h):
    rc = wintypes.RECT()
    u32.GetWindowRect(h, ctypes.byref(rc))
    return (rc.left, rc.top, rc.right, rc.bottom, bool(u32.IsZoomed(h)))


antes = {h: retangulo(h) for h in mb.janelas_do_navegador(u32, k32, nome)}
ok = mb.abrir_janela_no_outro_monitor("https://www.metasrc.com/lol/arena/champions/lee-sin/build")
time.sleep(1)
novas = [h for h in mb.janelas_do_navegador(u32, k32, nome) if h not in antes]
confere("abriu a janela", bool(ok))
confere("janelas que ja existiam ficaram no lugar",
        all(retangulo(h) == r for h, r in antes.items() if u32.IsWindow(h)))
confere("exatamente 1 janela nova", len(novas) == 1)
if len(novas) == 1:
    r = retangulo(novas[0])
    cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
    confere("janela nova no outro monitor e maximizada",
            area.left <= cx < area.right and area.top <= cy < area.bottom and r[4])
    u32.PostMessageW(novas[0], 0x0010, 0, 0)   # WM_CLOSE: fecha so a janela do teste
comum.fim()
