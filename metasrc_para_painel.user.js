// ==UserScript==
// @name         METAsrc -> MayhemBuild
// @namespace    mayhembuild
// @version      1.2
// @description  Quando voce abre uma pagina de Mayhem ou Arena no METAsrc, manda tiers/winrates, cartinhas e a build do campeao para o painel MayhemBuild no seu PC.
// @match        https://www.metasrc.com/lol/mayhem*
// @match        https://www.metasrc.com/lol/arena*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @connect      127.0.0.1
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const PAINEL = 'http://127.0.0.1:47914';
  const INTERVALO_HORAS = 6; // tiers: nao manda de novo antes disso (por modo)

  const modoAtual = () => (location.pathname.startsWith('/lol/arena') ? 'arena' : 'mayhem');
  const patchDa = doc => ((doc.body.textContent.match(/Patch\s+(\d+\.\d+)/) || [])[1] || '');

  function enviar(caminho, dados, aoDarCerto) {
    GM_xmlhttpRequest({
      method: 'POST',
      url: PAINEL + caminho,
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify(dados),
      timeout: 4000,
      onload: r => { if (r.status === 200 && aoDarCerto) aoDarCerto(); },
      // painel fechado: tenta de novo na proxima pagina que voce abrir
    });
  }

  // ---------- tiers / winrate de todos os campeoes ----------
  const num = (txt, rotulo) => {
    const m = txt.match(new RegExp(rotulo + '\\s*:?\\s*([\\d.,]+)'));
    return m ? parseFloat(m[1].replace(',', '')) : null;
  };

  async function enviarTiers() {
    const modo = modoAtual();
    const chave = 'ultimo_envio_' + modo;
    // na pagina de tier list sempre manda (e o botao "Atualizar" do painel)
    const forcar = location.pathname.includes('/tier-list');
    if (!forcar && Date.now() - GM_getValue(chave, 0) < INTERVALO_HORAS * 3600e3) return;

    // a mesma lista que o site usa para as dicas ao passar o mouse
    const html = await fetch(`/api/lol/tooltip/champions/${modo}/stats`, { credentials: 'same-origin' })
      .then(r => r.text());
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const campeoes = {};
    for (const el of doc.querySelectorAll('div[id^="champion-"]')) {
      const m = el.id.match(/^champion-([a-z0-9-]+)$/);
      if (!m) continue;
      const txt = el.textContent.replace(/\s+/g, ' ');
      const tier = (txt.match(/Tier:\s*([SABCD]\+?)/) || [])[1];
      if (!tier) continue;
      campeoes[m[1]] = {
        nome: (el.querySelector('strong') || {}).textContent || m[1],
        tier,
        score: num(txt, 'Score'),
        win: num(txt, 'Win %'),
        top3: num(txt, 'Top 3 %'),
        lugar: num(txt, 'Placement'),
        pick: num(txt, 'Pick %'),
        ban: num(txt, 'Ban %'),
      };
    }
    if (Object.keys(campeoes).length < 50) return; // pagina mudou? nao manda lixo
    enviar('/dados', { modo, patch: patchDa(document), campeoes }, () => GM_setValue(chave, Date.now()));
  }

  // ---------- build do campeao (pagina de build) ----------
  // Cada parte da build fica numa secao com titulo <h2>; dentro, os itens/feiticos
  // tem data-tooltip-select="#item-3071" / "#spell-4".
  function lerBuild() {
    const nomes = {};
    for (const el of document.querySelectorAll('[data-tooltip-select]')) {
      const img = el.querySelector('img');
      if (img && img.alt) nomes[el.dataset.tooltipSelect] = img.alt;
    }
    const secoes = [];
    for (const h of document.querySelectorAll('h2')) {
      let sec = h; // maior bloco que so tem este titulo
      while (sec.parentElement && sec.parentElement.querySelectorAll('h2').length === 1) sec = sec.parentElement;
      secoes.push({ titulo: h.textContent.trim(), sec });
    }
    const pegar = (regex, tipo, max) => {
      const s = secoes.find(x => regex.test(x.titulo));
      if (!s) return [];
      const vistos = new Set(), lista = [];
      for (const el of s.sec.querySelectorAll(`[data-tooltip-select^="#${tipo}-"]`)) {
        const sel = el.dataset.tooltipSelect, id = sel.slice(tipo.length + 2);
        if (!/^\d+$/.test(id) || vistos.has(id)) continue;
        vistos.add(id);
        lista.push({ id, nome: nomes[sel] || '' });
        if (lista.length >= max) break;
      }
      return lista;
    };
    const prioridade = (document.body.textContent.match(/Priority\s*([QWE](?:\s*>\s*[QWE])+)/) || [])[1] || '';
    return {
      feiticos: pegar(/Summoner Spells/i, 'spell', 2),
      inicio: pegar(/Starting Items/i, 'item', 2),
      // build completa na ordem do site (ja inclui as botas e o elixir)
      itens: pegar(/^(?!.*(Starting|Prismatic|Option|Order)).* Items$/i, 'item', 7),
      prismaticos: pegar(/Best Prismatic Items/i, 'item', 4),
      habilidades: prioridade.replace(/\s+/g, ' '),
    };
  }

  // ---------- cartinhas + build do campeao (pagina de build) ----------
  function enviarCartas() {
    const m = location.pathname.match(/^\/lol\/(mayhem|arena)\/champions\/([a-z0-9-]+)\/build/);
    if (!m) return;
    const bloco = document.querySelector('script#ArenaWidget_row_data[type="application/json"]');
    if (!bloco) return;
    let lista;
    try { lista = JSON.parse(bloco.textContent); } catch (e) { return; }
    const cartas = lista
      .filter(a => a && a.displays && /^augment-/.test(a.key || ''))
      .map(a => ({ nome: a.displays.name, raridade: a.displays.rarity, tier: a.displays.tier }));
    if (cartas.length < 10) return;
    let build = null;
    try { build = lerBuild(); } catch (e) { /* sem build, manda so as cartinhas */ }
    enviar('/cartas', { modo: m[1], campeao: m[2], patch: patchDa(document), cartas, build });
  }

  function rodar() {
    enviarTiers().catch(() => {});
    enviarCartas();
  }

  rodar();
  // o site troca de pagina sem recarregar (htmx): roda de novo quando o conteudo muda
  let ultimaUrl = location.href;
  document.addEventListener('htmx:afterSettle', () => {
    if (location.href !== ultimaUrl) { ultimaUrl = location.href; rodar(); }
  });
})();
