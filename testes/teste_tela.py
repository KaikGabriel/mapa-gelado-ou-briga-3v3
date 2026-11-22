"""O painel cabe na tela: com tudo preenchido ele nunca passa da area util, e o que sobra rola."""
import comum
from comum import confere

mb = comum.carregar()


def cartao(nome, destaque=False):
    return {"id": 1, "nome": nome, "icone": None, "texto": f"{nome}\nTier S  3.20º\n⚒ bigorna\n▶ tem combo",
            "url": "https://www.metasrc.com/lol/arena/champions/x/build", "destaque": destaque}


itens = [("Itens", [{"chave": f"item/{i}", "nome": f"Item {i}", "icone": None, "url": ""} for i in range(7)]),
         ("Prismaticos", [{"chave": f"item/p{i}", "nome": f"Prisma {i}", "icone": None, "url": ""} for i in range(4)])]
# estado da Arena com TODAS as secoes cheias (o pior caso de altura)
cheio = {**mb.VAZIO, "modo": "CHERRY", "meu": cartao("Lee Sin"),
         "build": {"linhas": itens, "habilidades": "Q > W > E"},
         "cartas": [("Prismatica", "a · b · c · d · e"), ("Ouro", "a · b · c · d · e"), ("Prata", "a · b · c")],
         "combos": [{"nome": "Combo", "forca": "forte", "dica": "dica " * 20,
                     "cartinhas": [("A", "S"), ("B", "A")], "video": "https://youtu.be/x"}] * 2,
         "aliados": [cartao(f"Aliado {i}") for i in range(2)],
         "bigorna": [cartao(f"Bigorna {i}", i < 2) for i in range(5)], "bigorna_resumo": "2 de 5 nos videos",
         "bans": [cartao(f"Ban {i}") for i in range(5)], "picks": [cartao(f"Pick {i}") for i in range(5)]}

raiz, app = comum.painel(mb)
esq, topo, dir_, baixo = mb.area_util_da_janela(raiz)
app.render(cheio)
raiz.update()
alto = raiz.winfo_height() + 40   # + barra de titulo
print(f"(tela util: {baixo - topo}px | painel cheio: {alto}px | conteudo: {app.corpo.winfo_reqheight()}px)")
confere("painel cheio cabe na tela", alto <= baixo - topo)
confere("o fim do painel fica acima da barra de tarefas", raiz.winfo_y() + alto <= baixo)
confere("aparece a barra de rolagem quando o conteudo e maior", app.rolando == bool(app.barra.winfo_manager()))

# tela pequena (notebook): forca uma area util de 700 px
mb.area_util_da_janela = lambda janela: (0, 0, 1366, 700)
app.render(cheio)
raiz.update()
confere("tela de 700px: painel cabe", raiz.winfo_height() + 40 <= 700)
confere("tela de 700px: barra de rolagem aparece", app.rolando and bool(app.barra.winfo_manager()))
app.tela.yview_moveto(1.0)
raiz.update()
confere("tela de 700px: da para rolar ate o fim", app.tela.yview()[1] >= 0.999)

# painel vazio: sem rolagem
mb.area_util_da_janela = lambda janela: (0, 0, 1920, 1040)
app.render(dict(mb.VAZIO))
raiz.update()
confere("painel vazio: sem barra de rolagem", not app.rolando and not app.barra.winfo_manager())
comum.fechar_painel(app, raiz)
comum.fim()
