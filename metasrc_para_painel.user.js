// ==UserScript==
// @name         METAsrc -> MayhemBuild
// @namespace    mayhembuild
// @version      1.1
// @description  Quando voce abre uma pagina de Mayhem ou Arena no METAsrc, manda tiers/winrates e as cartinhas do campeao para o painel MayhemBuild no seu PC.
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

  // ---------- cartinhas do campeao (pagina de build) ----------
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
    enviar('/cartas', { modo: m[1], campeao: m[2], patch: patchDa(document), cartas });
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
