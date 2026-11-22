"""Arena: campeoes com bigorna (favoritos da torcida), tier de cada um e os videos do King Nidhogg."""
import queue

import comum
from comum import confere

mb = comum.carregar()
comum.tiers_arena(mb, {"Xin Zhao": "S+", "Ornn": "S", "Mel": "C", "Hwei": "C", "Camille": "A", "Lee Sin": "B"})
mb.abrir_build = lambda *a, **k: None
BIGORNA = [910, 5, 164, 800, 516]   # Hwei, Xin Zhao, Camille, Mel, Ornn


def cliente(caminho):
    if caminho == mb.BIGORNA_URL:
        return BIGORNA
    if caminho == "/lol-gameflow/v1/gameflow-phase":
        return "ChampSelect"
    if caminho == "/lol-gameflow/v1/session":
        return {"gameData": {"queue": {"mapId": 30, "gameMode": "CHERRY", "description": "Arena 3x6"}}}
    if caminho == "/lol-champ-select/v1/session":
        return {"localPlayerCellId": 0,
                "myTeam": [{"cellId": 0, "championId": 0, "championPickIntent": 800}, {"cellId": 1, "championId": 0}],
                "actions": [[{"actorCellId": 3, "championId": 164, "type": "ban", "completed": True}]],
                "theirTeam": [], "benchChampions": []}
    return {}


comum.fingir_cliente(mb, cliente)
q = queue.Queue()
mb.Observador(q, dict(mb.PADRAO)).start()
e = comum.ultimo_estado(q, 9)
nomes = [c["nome"] for c in e["bigorna"]]
confere("ordem pelo tier (S+, S, C, C), Camille (banida) fora e Mel (seu pick) dentro",
        nomes[:2] == ["Xin Zhao", "Ornn"] and sorted(nomes[2:]) == ["Hwei", "Mel"])
confere("★ so em tier A ou melhor", [c["destaque"] for c in e["bigorna"]] == [True, True, False, False])
confere("marca '⚒ bigorna' na lista e no seu campeao",
        all("⚒ bigorna" in c["texto"] for c in e["bigorna"]) and "⚒ bigorna" in e["meu"]["texto"])
xin = e["bigorna"][0].get("video") or {}
confere("Xin Zhao: combo forte do King Nidhogg com o video certo",
        xin.get("combo") == "Tanque que acumula vida" and xin.get("url", "").endswith("a2knrkFIp0o"))
confere("quem nao esta nos videos fica sem botao", not any(c.get("video") for c in e["bigorna"][1:]))
confere("resumo '1 de 4' nos videos", e["bigorna_resumo"].startswith("1 de 4 aparecem nos videos"))

raiz, app = comum.painel(mb)
app.render(e)
raiz.update()
confere("secao da bigorna aparece no painel", bool(app.bigorna.master.winfo_manager()))
app.render(dict(mb.VAZIO))
raiz.update()
confere("fora da selecao a secao some", not app.bigorna.master.winfo_manager())
comum.fechar_painel(app, raiz)
comum.fim()
