"""Painel aberto com a partida ja rolando: descobre o seu campeao pelo cliente.

Se o LoL estiver aberto numa partida, tambem mostra (so lendo) qual campeao o cliente diz que e o seu.
"""
import queue

import comum
from comum import confere

mb = comum.carregar()

# cliente de verdade, se estiver aberto (so leitura, nao conta como falha)
auth = mb.achar_cliente()
if auth:
    fase = mb.lcu(auth, "/lol-gameflow/v1/gameflow-phase")
    ob = mb.Observador(queue.Queue(), dict(mb.PADRAO))
    ob.carregar_campeoes(auth)
    cid = ob.campeao_na_partida(auth) if fase in mb.EM_PARTIDA else 0
    print(f"(cliente real: fase={fase}, seu campeao={ob.nome(cid) if cid else '-'}, modo={ob.modo})")

comum.opgg_exemplo(mb, "Lee Sin")
abertos = []
mb.abrir_build = lambda url, *a, **k: abertos.append(url)
fila_modo = {"agora": "KIWI"}


def cliente(caminho):
    if caminho == "/lol-gameflow/v1/gameflow-phase":
        return "InProgress"
    if caminho == "/lol-summoner/v1/current-summoner":
        return {"puuid": "meu-puuid"}
    if caminho == "/lol-gameflow/v1/session":
        return {"gameData": {"queue": {"gameMode": fila_modo["agora"]},
                             "playerChampionSelections": [{"puuid": "outro", "championId": 31},
                                                          {"puuid": "meu-puuid", "championId": 64}]}}
    if caminho == "/lol-champ-select/v1/session":
        raise mb.SemSessao
    return {}


comum.fingir_cliente(mb, cliente)
q = queue.Queue()
mb.Observador(q, dict(mb.PADRAO)).start()
e = comum.ultimo_estado(q, 9)
confere("Mayhem: acha o Lee Sin pelo puuid", e["status"] == "Em partida: Lee Sin")
confere("Mayhem: mostra a build sem abrir o navegador", bool(e["build"]) and abertos == [])

fila_modo["agora"] = "CHERRY"
q2 = queue.Queue()
mb.Observador(q2, dict(mb.PADRAO)).start()
e = comum.ultimo_estado(q2, 9)
confere("Arena: acha o campeao e o modo", e["status"] == "Em partida: Lee Sin" and e["modo"] == "CHERRY")
confere("Arena sem build guardada: abre a pagina uma vez para o script mandar",
        len([u for u in abertos if "/arena/champions/lee-sin/build" in u]) == 1)
comum.fim()
