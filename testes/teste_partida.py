"""Selecao -> partida -> fim de jogo: a build fica no painel durante a partida e some no fim."""
import queue

import comum
from comum import confere

mb = comum.carregar()
comum.opgg_exemplo(mb, "Lee Sin")
mb.abrir_build = lambda *a, **k: None
fase = {"agora": "ChampSelect"}


def cliente(caminho):
    if caminho == mb.BIGORNA_URL:
        return []
    if caminho == "/lol-gameflow/v1/gameflow-phase":
        return fase["agora"]
    if caminho == "/lol-gameflow/v1/session":
        return {"gameData": {"queue": {"mapId": 12, "gameMode": "KIWI", "description": "ARAM: Mayhem"}}}
    if caminho == "/lol-summoner/v1/current-summoner":
        return {"puuid": "eu"}
    if caminho == "/lol-champ-select/v1/session":
        if fase["agora"] != "ChampSelect":
            raise mb.SemSessao
        return {"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": 64}, {"cellId": 1, "championId": 14}],
                "actions": [], "benchChampions": [{"championId": 145}]}
    return {}


comum.fingir_cliente(mb, cliente)
q = queue.Queue()
mb.Observador(q, dict(mb.PADRAO)).start()
sel = comum.ultimo_estado(q, 9)
confere("selecao: build e cartinhas", bool(sel["build"]) and bool(sel["cartas"]))

fase["agora"] = "InProgress"
jogo = comum.ultimo_estado(q, 3)
confere("partida: status 'Em partida: Lee Sin'", jogo["status"] == "Em partida: Lee Sin")
confere("partida: mesma build da selecao", jogo["build"] == sel["build"])
confere("partida: sem cartinhas, combos, banco e aliados",
        not (jogo["cartas"] or jogo["combos"] or jogo["banco"] or jogo["aliados"]))

raiz, app = comum.painel(mb)
app.render(jogo)
raiz.update()
confere("painel em partida: cartinhas, banco e aliados escondidos",
        not any(x.master.winfo_manager() for x in (app.cartas, app.banco, app.aliados)))
app.render(sel)
raiz.update()
ordem = app.corpo.pack_slaves()
confere("proxima selecao: tudo volta, aliados logo depois do banco",
        all(x.master.winfo_manager() for x in (app.cartas, app.banco, app.aliados))
        and ordem.index(app.aliados.master) == ordem.index(app.banco.master) + 1)
comum.fechar_painel(app, raiz)

fase["agora"] = "WaitingForStats"
fim_jogo = comum.ultimo_estado(q, 3)
confere("fim de jogo: volta a esperar a selecao", fim_jogo["status"].startswith("Conectado") and not fim_jogo["build"])
comum.fim()
