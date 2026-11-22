"""Selecao de campeoes simulada no Mayhem e na Arena: build, cartinhas, banco e o que o painel recusa."""
import queue

import comum
from comum import confere

mb = comum.carregar(porta=47990)

# o que o script do navegador manda (Arena) e o OP.GG (Mayhem)
confere("Arena: painel aceita cartinhas + build do script",
        comum.mandar(mb, "/cartas", {**comum.cartas_exemplo("arena"), "build": comum.BUILD_ARENA}) == 200)
confere("painel recusa dados de outro site (Origin)",
        mb.Receptor and comum.mandar(mb, "/nada", {}) in (403, 404))
lixo = mb.DadosSite._limpar_build({"itens": ["<script>", "../../x", "9999999999"], "habilidades": "rm -rf"})
confere("build com lixo e descartada", lixo is None)
for nome, tier in (("Lee Sin", "A"), ("Ahri", "S"), ("Garen", "C"), ("Lux", "B")):
    comum.opgg_exemplo(mb, nome, tier)

abertos = []
mb.abrir_build = lambda url, *a, **k: abertos.append(url)
modo = {"agora": "KIWI"}


def cliente(caminho):
    if caminho == mb.BIGORNA_URL:
        return []
    if caminho == "/lol-gameflow/v1/gameflow-phase":
        return "ChampSelect"
    if caminho == "/lol-gameflow/v1/session":
        kiwi = modo["agora"] == "KIWI"
        return {"gameData": {"queue": {"mapId": 12 if kiwi else 30, "gameMode": modo["agora"],
                                       "description": "ARAM: Mayhem" if kiwi else "Arena 3x6"}}}
    if caminho == "/lol-champ-select/v1/session":
        return {"localPlayerCellId": 0,
                "myTeam": [{"cellId": 0, "championId": 64}, {"cellId": 1, "championId": 86}],
                "actions": [],
                "benchChampions": [{"championId": 103}, {"championId": 99}] if modo["agora"] == "KIWI" else []}
    return {}


comum.fingir_cliente(mb, cliente)
q = queue.Queue()
mb.Observador(q, dict(mb.PADRAO)).start()
e = comum.ultimo_estado(q, 9)
rotulos = [r for r, _ in (e["build"] or {}).get("linhas", [])]
confere("Mayhem: build do OP.GG com feiticos, inicio e itens", rotulos == ["Feiticos", "Inicio", "Itens"])
confere("Mayhem: 7 itens", len(dict(e["build"]["linhas"])["Itens"]) == 7)
confere("Mayhem: cartinhas do OP.GG em 2 linhas", [r for r, _ in e["cartas"]] == ["Melhores", "Boas"])
confere("Mayhem: tier e winrate no seu campeao", "Tier A  51%" in e["meu"]["texto"])
confere("Mayhem: banco ordenado pelo tier (Ahri S antes de Lux B)",
        [c["nome"] for c in e["banco"]] == ["Ahri", "Lux"])
confere("Mayhem: ★ no banco so em quem e melhor que o seu", e["banco"][0]["destaque"] and not e["banco"][1]["destaque"])
confere("Mayhem: nao abre o navegador", abertos == [])

modo["agora"] = "CHERRY"
q2 = queue.Queue()
mb.Observador(q2, dict(mb.PADRAO)).start()
e = comum.ultimo_estado(q2, 9)
rotulos = [r for r, _ in (e["build"] or {}).get("linhas", [])]
confere("Arena: build do METAsrc com itens e prismaticos", rotulos == ["Itens", "Prismaticos"])
confere("Arena: cartinhas por raridade", [r for r, _ in e["cartas"]] == ["Prismatica", "Ouro", "Prata"])
confere("Arena: abre a build no navegador", any("/arena/champions/lee-sin/build" in u for u in abertos))
comum.fim()
