<p align="center">
  <img src="assets/icone.png" alt="Ícone do MayhemBuild" width="128" height="128">
</p>

<h1 align="center">MayhemBuild</h1>

<p align="center">
  Painel para <b>League of Legends</b> que abre a build do seu campeão no
  <a href="https://www.metasrc.com/lol/mayhem">METAsrc</a> assim que você o pega na seleção,
  com foco em <b>ARAM: Mayhem</b> (o ARAM das cartinhas) e <b>Arena</b>.
</p>

<p align="center">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
  <img alt="Dependências" src="https://img.shields.io/badge/depend%C3%AAncias-nenhuma-57ab5a">
</p>

---

## O que ele faz

| | |
|---|---|
| **Abre a build sozinho** | Quando você pega ou troca de campeão, a página certa do METAsrc abre no navegador: Mayhem ou Arena, conforme a fila. |
| **Build no painel** | Mostra no próprio painel a build do seu campeão: feitiços, itens iniciais, os 7 itens na ordem de compra (com ícone e nome em português), a ordem para maximizar as habilidades e, na Arena, os itens prismáticos. |
| **Cartinhas recomendadas** | Mostra as melhores cartinhas (Prismática, Ouro e Prata) do seu campeão, com o tier do METAsrc. Só aparece na seleção de campeões. |
| **Combos do King Nidhogg (Arena)** | Se o seu campeão aparece num combo do canal [King Nidhogg](https://www.youtube.com/@KingNidhogg), o painel mostra as cartinhas do combo (com o tier delas para o seu campeão), uma dica e um botão para o vídeo. Nas listas, campeões com combo forte ganham a marca **▶ tem combo**. |
| **Banco do ARAM** | Mostra os campeões do banco ordenados pelo tier. O que for mais forte que o seu ganha uma ★. Um clique abre a build. |
| **Aliados** | Mostra os campeões do seu time (no ARAM dá para trocar com eles), com botão para abrir a build. |
| **Sugestão de ban (Arena)** | Lista os campeões fortes e muito escolhidos que ainda não foram banidos nem escolhidos. Avisa quando é a sua vez de banir. |
| **Melhores picks (Arena)** | Junta o tier do site com a **sua** colocação média em cada campeão. Só lista campeões que você tem. |
| **Seu histórico** | Mostra as suas vitórias e derrotas no Mayhem e a sua colocação média na Arena com cada campeão. |
| **Liga junto com o LoL** | Inicia com o Windows escondido, aparece quando o cliente do LoL abre e some quando ele fecha. |

## Como funciona

```
 Cliente do LoL ──(API local do cliente)──►  MayhemBuild  ◄──(127.0.0.1:47914)── Script no navegador
 seleção, fila,                              painel                                (Tampermonkey)
 histórico                                     │                                   lê o METAsrc que
                                               ▼                                   VOCÊ abriu
                                   abre a build no navegador
```

- **Cliente do LoL:** o painel lê a seleção de campeões, a fila, o banco, os bans e o seu histórico pela API local que o próprio cliente deixa aberta no seu PC (a chamada LCU). Não usa login nem chave de API.
- **METAsrc:** o site bloqueia programas que tentam ler as páginas sozinhos. Por isso quem lê os dados é um script do Tampermonkey, **no seu navegador**, nas páginas que você mesmo abre. As builds que o painel abre já servem para isso. O script manda os dados para o painel pelo `127.0.0.1`, sem passar pela internet.
- **Nomes e ícones:** vêm do [Data Dragon](https://developer.riotgames.com/docs/lol#data-dragon), da própria Riot.

## Instalação

### 1. O painel

**Opção A: `.exe` (mais fácil)**
1. Baixe o `MayhemBuild.exe` na página de [Releases](../../releases).
2. Coloque o arquivo numa pasta fixa, por exemplo `Documentos\MayhemBuild`, e abra com dois cliques.
3. Na primeira vez, o Windows pode mostrar *"O Windows protegeu o computador"*. Isso acontece com qualquer `.exe` sem assinatura digital. Clique em **Mais informações → Executar assim mesmo**.

Na primeira vez que o `.exe` abre, ele já liga a opção **Iniciar junto com o Windows**.

**Opção B: pelo código (precisa do Python 3.10 ou mais novo)**
```bash
pyw mayhem_build.pyw
```
Só usa a biblioteca padrão do Python, então não precisa instalar nada com `pip`.

### 2. O script do navegador (para tiers, winrates, cartinhas e build)

1. Instale a extensão [Tampermonkey](https://www.tampermonkey.net/).
2. **No Chrome e em outros navegadores baseados nele:** abra `chrome://extensions` → **Detalhes** do Tampermonkey e ligue **Permitir scripts de usuário**. Se essa opção não aparecer, ligue o *Modo do desenvolvedor* antes.
3. No painel, clique em **Instalar script** e depois em **Instalar** na página do Tampermonkey.
   Também dá para abrir o [`metasrc_para_painel.user.js`](metasrc_para_painel.user.js) direto no Tampermonkey.
4. No painel, clique em **Atualizar Mayhem** e **Atualizar Arena**. Quando o Tampermonkey perguntar sobre `127.0.0.1`, escolha **Sempre permitir**.

Pronto. Embaixo dos botões, o painel mostra de qual patch são os dados e de quando, por exemplo *"Arena: patch 26.22 (hoje)"*.

## Usando

- **Clique em qualquer campeão** do painel para abrir a build dele.
- **X da janela:** com o LoL aberto, só esconde o painel. Ele volta na próxima vez que o LoL abrir.
- **Sair:** fecha de vez. Ele volta a ligar com o Windows.
- **Opções:**
  - *Abrir a build automaticamente*
  - *Só no ARAM / Mayhem / Arena*: em ranqueada e normal não abre nada sozinho.
  - *Sempre por cima das janelas*
  - *Aparecer só quando o LoL estiver aberto*
  - *Iniciar junto com o Windows*

## Onde ficam os dados

Tudo fica em `%APPDATA%\MayhemBuild\`:

| Arquivo | Conteúdo |
|---|---|
| `config.json` | Suas opções |
| `historico_mayhem.json` | Suas partidas de Mayhem e Arena (cresce com o tempo, veja as limitações) |
| `metasrc_mayhem.json` / `metasrc_arena.json` | Tiers e estatísticas do METAsrc |
| `cartas_mayhem.json` / `cartas_arena.json` | Cartinhas e build de cada campeão |

O início com o Windows é a entrada `MayhemBuild` em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Para desligar, desmarque a opção no painel.

## Gerar o `.exe`

```bash
build_exe.bat
```
O script instala o [PyInstaller](https://pyinstaller.org/) e gera `dist\MayhemBuild.exe`, já com o ícone, o script do navegador e os combos dentro.

## Segurança e regras da Riot

- O painel só escuta em `127.0.0.1`, então nenhum outro computador consegue falar com ele. Ele só aceita dados vindos do `https://www.metasrc.com` e confere o formato antes de salvar.
- Ele **não joga por você**: não escolhe campeão, não bane, não compra itens e não escolhe cartinhas. Só mostra informações e abre páginas.
- As cartinhas recomendadas **só aparecem na seleção de campeões**. Durante a partida o painel não mostra nada, porque a Riot não permite programas que indicam o que escolher dentro do jogo.
- Para os dados do METAsrc, o script só lê as páginas que você mesmo abre no navegador. O painel não acessa o site sozinho.

## Limitações

- O cliente do LoL só mostra as **últimas 20 partidas**. O painel guarda as partidas que vê, então o histórico cresce enquanto ele está rodando.
- No **Mayhem**, o METAsrc só publica o tier, sem winrate. Na **Arena** tem tier, nota, colocação média e taxas de pick e ban.
- Se o METAsrc mudar o site, o script pode parar de ler os dados até ser ajustado.
- Funciona só no Windows.

## Arquivos

| Arquivo | O que é |
|---|---|
| `mayhem_build.pyw` | O painel (código-fonte) |
| `metasrc_para_painel.user.js` | O script do Tampermonkey |
| `combos_arena.json` | Combos da Arena tirados dos vídeos do King Nidhogg. Dá para editar à mão: cada combo tem as cartinhas, a força (`forte`, `boa` ou `sorte`), uma dica e o vídeo de cada campeão |
| `mayhembuild.ico` / `assets/icone.png` | O ícone |
| `build_exe.bat` | Gera o `.exe` |
| `MayhemBuild.ps1` / `MayhemBuild.bat` | Primeira versão, em PowerShell: só abre a build, sem painel |

---

<sub>O MayhemBuild não é endossado pela Riot Games e não representa as opiniões da Riot Games nem de ninguém oficialmente envolvido na produção ou gestão de League of Legends. League of Legends e Riot Games são marcas registradas da Riot Games, Inc. Os dados de builds, tiers e cartinhas são do <a href="https://www.metasrc.com">METAsrc</a>.</sub>
