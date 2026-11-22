"""OP.GG: leitor do formato da resposta e uma busca de verdade (precisa de internet)."""
import time

import comum
from comum import confere

mb = comum.carregar()
opgg = mb.OpGG()   # o de verdade, sem o "pedir" desligado

amostra = ('class Lol: data\nclass Data: augments\nclass Augment: id,name,performance\n\n'
           'Lol(Data([Augment(1211,"Hora do \\u00c9xtase",70.19),Augment(3263,null,74.4)]))')
confere("leitor: le classes, listas, texto, numero e null",
        mb.ler_opgg(amostra) == {"data": {"augments": [{"id": 1211, "name": "Hora do Éxtase", "performance": 70.19},
                                                       {"id": 3263, "name": None, "performance": 74.4}]}})
confere("nome no formato do OP.GG", [mb.chave_opgg(n) for n in ("Cho'Gath", "Dr. Mundo", "Nunu & Willump")]
        == ["CHO_GATH", "DR_MUNDO", "NUNU_WILLUMP"])

t = time.time()
lee = opgg.buscar("Lee Sin", 64)
print(f"(Lee Sin em {time.time() - t:.1f}s: tier {lee.get('tier')}, win {lee.get('win')})")
confere("Lee Sin: tier e winrate", lee["tier"] in mb.TIERS and isinstance(lee["win"], float))
b = lee["build"] or {}
confere("Lee Sin: 2 feiticos, itens iniciais, 6+ itens e ordem das habilidades",
        len(b.get("feiticos", [])) == 2 and bool(b.get("inicio")) and len(b.get("itens", [])) >= 6
        and len(b.get("habilidades", "").split(" > ")) == 3)
confere("Lee Sin: 5+ cartinhas com nome", len(lee["cartas"]) >= 5 and all(lee["cartas"]))
comum.fim()
