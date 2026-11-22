"""Roda todos os testes do painel.

    python testes/rodar_testes.py              # testes normais (precisam de internet: Data Dragon e OP.GG)
    python testes/rodar_testes.py --interativo # tambem abre uma janela de verdade do navegador
    python testes/rodar_testes.py tela partida # so os testes com esses nomes

Nenhum teste mexe nos seus dados (%APPDATA%\\MayhemBuild): cada um usa uma pasta temporaria.
O painel de verdade pode ficar aberto (os testes usam outras portas).
"""
import subprocess
import sys
import time
from pathlib import Path

PASTA = Path(__file__).resolve().parent
NORMAIS = ["selecao", "partida", "bigorna", "recuperar", "aba", "tela", "bandeja", "opgg"]
INTERATIVOS = ["janela"]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nomes = args or NORMAIS + (INTERATIVOS if "--interativo" in sys.argv else [])
    resultado = {}
    for nome in nomes:
        print(f"\n=== teste_{nome} ===", flush=True)
        t = time.time()
        r = subprocess.run([sys.executable, str(PASTA / f"teste_{nome}.py")], cwd=PASTA)
        resultado[nome] = (r.returncode == 0, time.time() - t)
    print("\n=== resumo ===")
    for nome, (ok, s) in resultado.items():
        print(f"{'OK   ' if ok else 'FALHA'} teste_{nome} ({s:.0f}s)")
    falhas = [n for n, (ok, _) in resultado.items() if not ok]
    print("tudo certo" if not falhas else f"{len(falhas)} teste(s) falharam: {', '.join(falhas)}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
