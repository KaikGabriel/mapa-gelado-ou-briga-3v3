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
- **Build numa janela própria no outro monitor** (2026-11-18): a primeira versão movia a janela do navegador que
  vinha para a frente, e isso levava a janela principal do usuário (com outras abas) para o segundo monitor.
  Agora o painel lê o navegador padrão no registro (`UrlAssociations\https\UserChoice`), abre o .exe com
  `--new-window` (`-new-window` no Firefox), acha a janela que não existia antes e move **só ela**, maximizada,
  para um monitor diferente do monitor do cliente do LoL (janela `RCLIENT`). Nunca mexe em janelas que já existiam.
  Com um monitor só ou navegador desconhecido, abre numa aba com `webbrowser.open`.
  Vídeos e botões "Atualizar" abrem em aba comum; só a build usa a janela própria.
- **Troca de campeão na mesma aba** (2026-11-18): para não abrir uma aba por campeão e gastar RAM.
  O script (1.3) numa aba de build deixa um pedido aberto em `GET /proxima` (o painel segura até 20 s).
  Ao trocar de campeão, o painel responde com a URL nova; a aba confirma em `GET /pegou?n=` e faz `location.href = url`.
  Sem aba ouvindo, ou sem confirmação em 2,5 s, o painel abre uma aba nova (classe `Navegacao`, função `abrir_build`).
  Usamos pedido longo em vez de `setInterval` porque o Chrome segura timers de abas em segundo plano.
- **Ícone na área de notificação** (2026-11-18): o usuário não achava o programa rodando escondido.
  Classe `Bandeja`: `Shell_NotifyIconW` via ctypes, com janela invisível e fila de mensagens numa thread própria.
  Ela não mexe no tkinter: manda "alternar", "mostrar" ou "sair" pela fila `pedidos_bandeja`, lida em `App.ler_fila`.
  O Windows 11 põe ícones novos nos ícones ocultos por padrão, que é onde o usuário queria.
- **Build no painel durante a partida** (2026-11-18): o painel guarda o campeão da seleção (`campeao_da_partida`).
  Fora da seleção, lê `/lol-gameflow/v1/gameflow-phase`: em `GameStart`, `InProgress` ou `Reconnect` mostra só o
  campeão e a build (`em_partida=True` esconde cartinhas, combos, banco e aliados). Em qualquer outra fase
  (`WaitingForStats`, `EndOfGame`, `Lobby`...) esquece o campeão e volta a esperar a seleção.
  Cartinhas e combos ficam fora da partida pela regra da Riot sobre recomendar escolhas dentro do jogo.
- **Painel aberto no meio da partida** (2026-11-21): `campeao_na_partida` lê o seu `puuid` em
  `/lol-summoner/v1/current-summoner` e procura ele em `gameData.playerChampionSelections` (e `teamOne`/`teamTwo`)
  de `/lol-gameflow/v1/session`. O modo (Mayhem ou Arena) vem de `gameData.queue.gameMode`.
  Testado no cliente real numa Arena: achou o Cho'Gath certo.
- **Bigorna = favoritos da torcida da Arena** (2026-11-21): o ícone de bigorna nos campeões da seleção é o
  "Crowd Favorites" ("You get a bonus Stats Anvil to start the game"). Achamos lendo o `assets.wad` do plugin
  `rcp-fe-lol-champ-select` do cliente: a lista vem de
  `/lol-lobby-team-builder/champ-select/v1/crowd-favorite-champion-list` (lista de ids de campeão).
  O painel lê essa lista na seleção, ordena pelo tier e marca ★ em tier A ou melhor (`TIERS_FORTES`).
  Cada campeão da bigorna é cruzado com `combos_arena.json` (`combos_de`): o combo mais forte vira um botão
  com o vídeo embaixo dele, e o topo da seção mostra "X de Y aparecem nos vídeos do King Nidhogg".
- **Mayhem sem navegador, pelo OP.GG** (2026-11-21): o usuário quer largar o navegador. METAsrc e U.GG bloqueiam
  programas (403), mas o OP.GG tem uma API pública feita para programas: `https://mcp-api.op.gg/mcp` (JSON-RPC,
  `tools/call`). Usamos `lol_get_champion_analysis` (game_mode `aram`; `position` é obrigatório mas não muda nada
  no ARAM, mandamos `mid`) e `lol_list_aram_augments` (por `champion_id`, `lang` pt_BR).
  O nome do campeão vai em UPPER_SNAKE_CASE (`chave_opgg`: "Cho'Gath" -> CHO_GATH).
  A resposta NÃO é JSON: vem num formato "class X: a,b" + `X(1,"t",[...])`, lido por `ler_opgg`.
  Tier do OP.GG 1..5 (1 = mais forte) vira S/A/B/C/D (`OPGG_TIER`). Cartinhas: ordenadas por `performance`.
  Classe `OpGG`: thread com fila, cache em `opgg_mayhem.json` por 12 h, espera 2 min antes de repetir uma falha.
  O OP.GG não cobre a Arena (só ranked, flex, urf, aram, nexus_blitz), então a Arena continua no METAsrc.
  No Mayhem o painel não abre mais o navegador sozinho. Na Arena aberta no meio da partida sem build guardada,
  ele abre a página para o script mandar a build.
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
- `Bandeja`: guarde a referência do `WNDPROC` (`self._proc`), senão o Python apaga o callback e o programa fecha.
  Se o Explorer reiniciar, o ícone volta pela mensagem `TaskbarCreated`.
- O campo `relatedPrimeItemId` de `/lol-champ-select/v1/all-grid-champions` NÃO é a bigorna (é só o id do campeão).
- Regras da Riot: não mostrar winrate de cartinhas nem de itens da Arena. Por isso o painel mostra só a ordem das
  cartinhas do OP.GG, sem os números de desempenho. Winrate de campeão pode.
- O segundo monitor do usuário é vertical e fica à esquerda (coordenadas negativas).

## Estado atual

- Funciona: painel, build no painel, cartinhas, combos do King Nidhogg, banco/aliados, ban e picks da Arena,
  início com o Windows ligado ao cliente do LoL, build numa janela própria no outro monitor
  (testado no PC do usuário: as 2 janelas do Chrome que já existiam não se mexeram).
- Troca na mesma aba: testada com o servidor do painel numa porta de teste e uma aba de verdade com o script dentro.
  Falta testar no Chrome do usuário com o Tampermonkey e o script 1.3 instalado.
- Testado só com seleção simulada: a seleção de campeões real com o script 1.2 do Tampermonkey e os dados da Arena chegando.

## Próximos passos possíveis

- Conferir numa seleção real de Mayhem e de Arena se build, cartinhas e combos aparecem.
- Voltar com o histórico do jogador, se o usuário pedir.
- Atualizar `combos_arena.json` quando o canal King Nidhogg publicar combos novos.
