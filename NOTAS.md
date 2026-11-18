# NOTAS do MayhemBuild

Memória do projeto entre sessões: o que foi decidido, o que costuma dar errado e onde paramos.
O uso e a instalação estão no [README.md](README.md).

## Decisões (e por quê)

- **Dados do METAsrc vêm de um script do Tampermonkey, não do programa.**
  O METAsrc responde 403 para programas que leem o site sozinhos. Não tentamos contornar esse bloqueio.
  O script roda no navegador do usuário, nas páginas que ele abre, e manda os dados para `127.0.0.1:47914`.
- **U.GG não foi integrado.** Em 2026-11-16 testamos ler a build direto pelo programa: a página de build do U.GG
  também responde 403 para programas. O usuário preferiu manter o navegador abrindo a build.
- **O histórico do jogador foi tirado** (2026-11-16) a pedido do usuário: o painel mostra só dados do site.
  Os picks da Arena usam só o tier. A lista de campeões que o jogador tem continua sendo usada para não sugerir
  campeão que ele não pode jogar. A ideia pode voltar no futuro.
- **Navegador no outro monitor:** depois de abrir a página, o painel procura a janela do navegador
  (a que vier para a frente ou, se nenhuma vier, a de navegador mais no topo) e a move para um monitor diferente
  do monitor do cliente do LoL (janela `RCLIENT`), mantendo maximizada se estava. Com um monitor só, não faz nada.
- **Troca de campeão na mesma aba** (2026-11-18): para não abrir uma aba por campeão e gastar RAM.
  O script (1.3) numa aba de build deixa um pedido aberto em `GET /proxima` (o painel segura até 20 s).
  Ao trocar de campeão, o painel responde com a URL nova; a aba confirma em `GET /pegou?n=` e faz `location.href = url`.
  Sem aba ouvindo, ou sem confirmação em 2,5 s, o painel abre uma aba nova (classe `Navegacao`, função `abrir_build`).
  Usamos pedido longo em vez de `setInterval` porque o Chrome segura timers de abas em segundo plano.
- **Só biblioteca padrão do Python** (tkinter, urllib, ctypes). Nada de `pip install` para rodar pelo código.
- **O `.exe` fica commitado na raiz do repositório.** Não há `gh` no PC do usuário para criar Releases.
- **Nomes de campeão vêm do Data Dragon em inglês** (o cliente em pt_BR devolve nomes traduzidos, que não batem
  com as URLs do METAsrc). Itens e feitiços usam o Data Dragon em pt_BR.
- **Cartinhas só aparecem na seleção de campeões**, nunca durante a partida (regra da Riot sobre programas que
  indicam escolhas dentro do jogo).

## Armadilhas conhecidas

- No cliente, **Mayhem é `gameMode` KIWI** (mapa 12, filas 2400 e 3270) e **Arena é CHERRY** (mapa 30, fila 1750).
- O histórico de partidas da API local do cliente devolve no máximo 20 partidas e não pagina. Por isso a versão antiga
  guardava o histórico em arquivo. Versões antigas deixaram `%APPDATA%\MayhemBuild\historico_mayhem.json`, que não é mais usado.
- O servidor local só aceita POST com `Origin: https://www.metasrc.com` e `Content-Type: application/json`.
- No PyInstaller, use `--add-data` sem `--specpath` apontando para outra pasta: com `--specpath` ele não acha os arquivos.
- Para gerar o `.exe` de novo, feche antes o `MayhemBuild.exe` que está rodando (ele fica escondido quando o LoL está fechado).
- Coordenadas de monitor: a thread que move o navegador usa `SetThreadDpiAwarenessContext(-4)` para trabalhar em pixels reais
  com escala de tela. O tkinter continua sem DPI awareness, para não mudar o tamanho do painel.
- Abas congeladas pelo navegador (economia de memória) podem pegar o pedido e não reagir. Por isso existe a confirmação:
  sem ela, o painel abre uma aba nova.
- O script instalado só se atualiza sozinho a partir da 1.3 (`@updateURL` aponta para o painel em `127.0.0.1:47914`).
  Quem tem a 1.2 precisa clicar em **Instalar script** de novo.
- O segundo monitor do usuário é vertical e fica à esquerda (coordenadas negativas).

## Estado atual

- Funciona: painel, build no painel, cartinhas, combos do King Nidhogg, banco/aliados, ban e picks da Arena,
  início com o Windows ligado ao cliente do LoL, navegador no outro monitor (testado nos dois monitores do usuário).
- Troca na mesma aba: testada com o servidor do painel numa porta de teste e uma aba de verdade com o script dentro.
  Falta testar no Chrome do usuário com o Tampermonkey e o script 1.3 instalado.
- Testado só com seleção simulada: a seleção de campeões real com o script 1.2 do Tampermonkey e os dados da Arena chegando.

## Próximos passos possíveis

- Conferir numa seleção real de Mayhem e de Arena se build, cartinhas e combos aparecem.
- Voltar com o histórico do jogador, se o usuário pedir.
- Atualizar `combos_arena.json` quando o canal King Nidhogg publicar combos novos.
