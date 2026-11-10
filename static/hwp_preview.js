// 한글(.hwp) 모양 미리보기 — 코스콤 요약보고 양식을 본떠 화면에 그린다(실제 파일 렌더가 아님).
// 실제 모양은 「프로그램으로 열기」(한컴 뷰어·한글)로 확인한다.
// 치수는 전사 한글 스킬 references/style_map.md 기준: 제목 HY헤드라인M 23, □ 16 Bold, ㅇ·-·· 15, * ※ 12, 표 13, 줄 간격 160%, A4.
(() => {
  const css = `
  .hwpl-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
  .hwpl-note{font-size:12.5px;color:#6e6e73}
  .hwpl-wrap{background:#8e8e93;padding:18px 0;border-radius:10px;max-height:72vh;overflow:auto}
  .hwpl-page{position:relative;width:794px;height:1123px;margin:0 auto 18px;background:#fff;box-shadow:0 4px 18px rgba(0,0,0,.35);color:#000;
    font-family:'함초롬바탕','HCR Batang','한컴바탕','HANBatang','바탕','Batang','AppleMyungjo','Noto Serif KR',serif;font-size:20px;line-height:1.6;word-break:keep-all;overflow-wrap:break-word;text-align:justify}
  .hwpl-page:last-child{margin-bottom:0}
  .hwpl-body{position:absolute;left:80px;right:80px;top:80px;height:967px;overflow:hidden}
  .hwpl-no{position:absolute;left:0;right:0;bottom:38px;text-align:center;font-size:13.3px;font-family:'함초롬돋움','HCR Dotum','Malgun Gothic','Apple SD Gothic Neo',sans-serif}
  .hwpl-title{border-top:8px solid #5b9bd5;border-bottom:8px solid #4f81c9;border-image:linear-gradient(90deg,#6aa9e0,#3f6fc4) 1;padding:5px 0 4px;text-align:center;
    font-family:'KHeadline','HY헤드라인M','Malgun Gothic','Apple SD Gothic Neo',sans-serif;font-size:30.7px;line-height:1.35;letter-spacing:.02em}
  .hwpl-sign{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.5px dotted #000;padding:2px 2px 1px;line-height:1.35}
  .hwpl-sign .a{font-size:13.3px}.hwpl-sign .d{font-size:17.3px;white-space:nowrap;padding-left:12px}
  .hwpl-h1{font-size:21.3px;font-weight:700;display:flex}.hwpl-h1 i{font-style:normal;width:26px;flex:none;font-family:'Segoe UI Symbol','Apple Symbols',sans-serif;font-weight:400}
  .hwpl-li{display:flex}.hwpl-li>i{font-style:normal;flex:none}.hwpl-li>span{flex:1;min-width:0}
  .hwpl-o>i{width:28px;margin-left:19px}.hwpl-dash>i{width:20px;margin-left:38px}.hwpl-dot>i{width:16px;margin-left:58px}
  .hwpl-note2,.hwpl-ref{font-size:16px;font-family:'함초롬돋움','HCR Dotum','Malgun Gothic','Apple SD Gothic Neo',sans-serif}
  .hwpl-note2>i{width:14px;margin-left:47px}.hwpl-ref>i{width:22px;margin-left:40px}
  .hwpl-tb{width:100%;border-collapse:collapse;font-family:'함초롬돋움','HCR Dotum','Malgun Gothic','Apple SD Gothic Neo',sans-serif;font-size:17.3px;line-height:1.35;text-align:center;table-layout:auto}
  .hwpl-tb th,.hwpl-tb td{padding:3px 6px;border-left:1px solid #000;border-top:1px solid #000;word-break:keep-all}
  .hwpl-tb tr>:first-child{border-left:0}.hwpl-tb th{background:#e6e6e6;font-weight:700}
  .hwpl-tb.t2{border-top:2.5px solid #000;border-bottom:2.5px solid #000}.hwpl-tb.t2 tr:first-child>*{border-top:0}
  .hwpl-tb.t1{border:1.5px solid #000}.hwpl-tb.t1 tr>:first-child{border-left:0}
  .hwpl-g4{height:8.5px}.hwpl-g6{height:12.8px}.hwpl-g8{height:17px}.hwpl-g10{height:21.3px}.hwpl-g12{height:25.6px}
  .hwpl-meas{position:absolute;visibility:hidden;left:-9999px;top:0;width:634px}
  .hwpl-load{color:#fff;text-align:center;padding:60px 0}
  .rh-page{width:794px;margin:0 auto 18px;background:#fff;box-shadow:0 4px 18px rgba(0,0,0,.35);line-height:0}.rh-page:last-child{margin-bottom:0}
  .rh-page svg{display:block;width:100%;height:auto}
  .hwpl-bar .seg{display:inline-flex;border:1px solid #dcdce0;border-radius:8px;overflow:hidden}
  .hwpl-bar .seg button{border:0;background:#fff;padding:5px 11px;font:inherit;font-size:12.5px;cursor:pointer;color:#2b2b2e}
  .hwpl-bar .seg button+button{border-left:1px solid #dcdce0}.hwpl-bar .seg button.on{background:#00338d;color:#fff;font-weight:700}
  @font-face{font-family:'KHeadline';src:local('HY헤드라인M'),local('HYHeadLine-Medium'),local('HYHeadLine M'),local('맑은 고딕 Bold'),local('Malgun Gothic Bold'),local('AppleSDGothicNeo-Bold'),local('Apple SD Gothic Neo Bold')}
  `;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  const rich = s => esc(s == null ? '' : String(s)).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  const lab = it => (it.label ? `<b>(${esc(it.label)})</b> ` : '') + rich(it.text);
  const gap = n => `<div class="hwpl-g${n}"></div>`;
  const MARK = {o: 'ㅇ', dash: '-', dot: '·', note: '*', ref: '※'};
  const CLS = {o: 'hwpl-o', dash: 'hwpl-dash', dot: 'hwpl-dot', note: 'hwpl-note2', ref: 'hwpl-ref'};
  const GAPB = {o: 8, num: 8, dash: 6, dot: 4, note: 4, ref: 4, table: 8};

  function itemBlocks(it, out) {
    const t = it.type || 'o';
    if (t === 'table') {
      const rows = it.rows || [];
      if (!rows.length) return;
      const n = Math.max(...rows.map(r => r.length));
      const tr = (r, tag) => '<tr>' + Array.from({length: n}, (_, j) => `<${tag}>${rich(r[j] ?? '')}</${tag}>`).join('') + '</tr>';
      out.push({g: 8, html: `<table class="hwpl-tb t${it.style === 1 ? 1 : 2}">${tr(rows[0], 'th')}${rows.slice(1).map(r => tr(r, 'td')).join('')}</table>`});
      return;
    }
    if (t === 'num') out.push({g: 8, html: `<div class="hwpl-li hwpl-o"><i><b>${esc(it.num || '①')}</b></i><span><b>${rich(it.text)}</b></span></div>`});
    else out.push({g: GAPB[t] || 8, html: `<div class="hwpl-li ${CLS[t] || 'hwpl-o'}"><i>${MARK[t] || 'ㅇ'}</i><span>${lab(it)}</span></div>`});
    for (const c of it.children || []) itemBlocks({type: 'dash', ...c}, out);
  }

  function blocksOf(rep) {
    const ap = rep.approval || {};
    const sign = ['담당', '팀장', '부서장'].filter(k => ap[k]).map(k => `${k}: ${esc(ap[k])}`).join(' / ');
    const out = [{g: 0, html: `<div class="hwpl-title">${rich(rep.title)}</div><div class="hwpl-sign"><span class="a">${sign}</span><span class="d">${esc([rep.date, rep.dept].filter(Boolean).join(', '))}</span></div>`}];
    (rep.sections || []).forEach((s, i) => {
      out.push({g: i ? 12 : 10, head: true, html: `<div class="hwpl-h1"><i>❑</i><span>${rich(s.heading)}</span></div>`});
      for (const it of s.items || []) itemBlocks(it, out);
    });
    return out;
  }

  // 쪽 나누기: 실제 한글의 조판과 같지는 않다. 본문 높이를 넘으면 다음 쪽으로, 장 제목이 쪽 끝에 홀로 남지 않게 한다.
  function paginate(blocks) {
    const meas = document.createElement('div'); meas.className = 'hwpl-page hwpl-meas'; meas.style.height = 'auto'; document.body.appendChild(meas);
    const H = 967, pages = [[]]; let used = 0;
    blocks.forEach((b, i) => {
      meas.innerHTML = (pages[pages.length - 1].length ? gap(b.g) : '') + b.html;
      let h = meas.getBoundingClientRect().height;
      if (used + h > H && pages[pages.length - 1].length) {
        const cur = pages[pages.length - 1], moved = [];
        if (cur.length > 1 && cur[cur.length - 1].head) moved.push(cur.pop());       // 장 제목만 남으면 함께 넘긴다
        pages.push(moved); used = 0;
        for (const m of moved) { meas.innerHTML = m.html; used += meas.getBoundingClientRect().height; }
        meas.innerHTML = (moved.length ? gap(b.g) : '') + b.html; h = meas.getBoundingClientRect().height;
      }
      pages[pages.length - 1].push(b); used += h;
    });
    meas.remove();
    return pages;
  }

  window.hwpLookHtml = rep => {
    const pages = paginate(blocksOf(rep));
    return pages.map((p, n) => `<div class="hwpl-page"><div class="hwpl-body">${p.map((b, i) => (i ? gap(b.g) : '') + b.html).join('')}</div><div class="hwpl-no">- ${n + 1} -</div></div>`).join('');
  };

  const OPEN_NAME = {hwp: '한컴 뷰어로 열기', ppt: 'PowerPoint로 열기', xlsx: 'Excel로 열기'};
  window.launchDoc = async (id, fmt, ver) => {
    try { await api(`/api/docs/${id}/launch`, {body: {fmt, ver}}); toast(fmt === 'hwp' ? '한글 파일을 이 PC의 프로그램(한컴 뷰어·한글)으로 열었습니다' : '파일을 이 PC의 프로그램으로 열었습니다'); } catch (e) {}
  };
  window.launchBtn = (id, fmt, ver, cls = 'btn ghost sm') => OPEN_NAME[fmt] ? `<button class="${cls}" onclick="launchDoc('${id}','${fmt}',${ver})" title="실제 파일을 이 PC에 설치된 프로그램으로 엽니다">🖥 ${OPEN_NAME[fmt]}</button>` : '';

  // ── 실제 파일 렌더: rhwp(@rhwp/core, MIT)로 .hwp를 브라우저 안에서 쪽 단위 SVG로 그린다. 문서는 밖으로 나가지 않는다.
  const RHWP = '/static/vendor/rhwp/';
  let rhwpMod = null;
  async function rhwpLoad() {
    if (rhwpMod) return rhwpMod;
    const m = await import(RHWP + 'rhwp.js');
    let ctx = null, last = '';
    globalThis.measureTextWidth = (font, text) => {            // WASM은 브라우저 글꼴을 모르므로 글자 폭을 여기서 재 준다
      if (!ctx) ctx = document.createElement('canvas').getContext('2d');
      if (font !== last) { ctx.font = font; last = font; }
      return ctx.measureText(text).width;
    };
    await m.default({module_or_path: RHWP + 'rhwp_bg.wasm'});
    rhwpMod = m;
    return m;
  }
  window.hwpRenderReal = async (id, ver) => {
    const m = await rhwpLoad();
    const r = await fetch(`/api/docs/${id}/file?fmt=hwp&ver=${ver}&inline=1`);
    if (!r.ok) throw new Error('파일을 읽지 못했습니다');
    const doc = new m.HwpDocument(new Uint8Array(await r.arrayBuffer()));
    try {
      const n = doc.pageCount();
      if (!n) throw new Error('쪽이 없습니다');
      // rhwp는 쪽마다 id(cell-clip-81 · grad3 …)를 새로 매긴다. 여러 쪽을 한 화면에 이어 붙이면 url(#…)이 앞 쪽의 같은 id를 집어
      // 뒤 쪽 표 칸 글자가 엉뚱한 영역으로 잘려 사라진다 → id와 url(#…) 참조에 쪽 번호를 붙인다(색 값 fill="#000" 은 그대로)
      return Array.from({length: n}, (_, i) => doc.renderPageSvg(i).replace(/\bid="([^"]+)"/g, `id="p${i}-$1"`).replace(/url\(#([^)]+)\)/g, `url(#p${i}-$1)`));
    } finally { try { doc.free(); } catch (e) {} }
  };

  const bar = (id, ver, mode, note) => `<div class="hwpl-bar">${launchBtn(id, 'hwp', ver, 'btn o sm')}<a class="btn sm" href="/api/docs/${id}/file?fmt=hwp&ver=${ver}">⬇ 받기</a>
      <span class="seg"><button class="${mode === 'real' ? 'on' : ''}" onclick="previewHwp('${id}',${ver},'real')">실제 파일</button><button class="${mode === 'look' ? 'on' : ''}" onclick="previewHwp('${id}',${ver},'look')">양식 모양</button><button onclick="previewHwpText('${id}',${ver})">글자만</button></span>
      <span class="hwpl-note">${note}</span></div><div class="hwpl-wrap" id="hwplWrap"><div class="hwpl-load">그리는 중…</div></div>`;
  const fit = w => { const z = Math.min(1, (w.clientWidth - 36) / 794); w.querySelectorAll('.hwpl-page,.rh-page').forEach(p => { p.style.zoom = z < 1 ? z : ''; }); };

  window.previewHwp = async (id, ver, mode = 'real') => {
    if (mode === 'real') {
      modal(`한글 미리보기 <span class="small muted">v${ver} · 실제 .hwp 파일을 그린 화면</span>`,
        bar(id, ver, 'real', '만들어진 .hwp 파일을 브라우저 안에서 그렸습니다(rhwp 0.8.7, 문서는 이 PC 밖으로 나가지 않습니다). 글꼴이 없으면 줄바꿈이 조금 다를 수 있어, 최종 확인은 「한컴 뷰어로 열기」로 하세요.'), true);
      try {
        const svgs = await hwpRenderReal(id, ver);
        const w = document.getElementById('hwplWrap'); if (!w) return;
        w.innerHTML = svgs.map((s, i) => `<div class="rh-page" title="${i + 1}쪽">${s}</div>`).join(''); fit(w);
        return;
      } catch (e) {
        console.warn('rhwp 렌더 실패 → 양식 모양으로 대체', e);
        toast('실제 파일 렌더에 실패해 양식 모양 미리보기로 보여 드립니다', true);
      }
    }
    const d = await api(`/api/docs/${id}/report?ver=${ver}`);
    modal(`한글 미리보기 <span class="small muted">v${ver} · 코스콤 요약보고 양식을 본뜬 화면</span>`,
      bar(id, ver, 'look', `양식을 본떠 그린 화면입니다(실제 파일 렌더가 아님). 줄바꿈·쪽 나눔은 실제와 다를 수 있습니다.${d.exact ? '' : ' 이 버전의 원고가 없어 최신 설계도로 그렸습니다.'}`), true);
    const w = document.getElementById('hwplWrap');
    w.innerHTML = hwpLookHtml(d.report); fit(w);
  };
})();
