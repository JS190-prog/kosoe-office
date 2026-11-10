// 코쇠오피스 화면 테마 C — 기본 index.html 의 함수 중 이 테마가 바꾼 것만 덮어쓴다.
// 기본 화면 스크립트 다음, boot() 전에 한 번 실린다(index.html 의 테마 로더).

function renderTop() {
  const u = ME.user, inet = ME.inet;
  $('#top').innerHTML = `
   <div class="logo"><img src="/static/kosoe.webp" alt=""><span>코쇠오피스</span></div>
   <div class="net" title="인터넷망은 팀장 승인 기간에만">
     <button class="${ME.net === 'closed' ? 'on' : ''}" onclick="setNet('closed')">🔒 폐쇄망</button>
     <button class="${ME.net === 'internet' ? 'on i' : ''}" onclick="setNet('internet')">🌐 인터넷망${inet ? '' : ' 🔑'}</button>
   </div>
   <span class="small muted">${inet ? `인터넷 승인 ~${inet.until}` : '인터넷망: 승인 필요'}</span>
   <span class="grow"></span>
   <button class="chip ${ME.ai.connected ? 'n' : 'o'}" style="cursor:pointer" onclick="aiModal()" title="눌러서 AI 바꾸기 (Claude Code CLI ↔ NVIDIA API · OpenRouter)">${aiChipText()} ▾</button>
   <span class="chip" title="스킬 저장소 ${esc(ME.repo.url || '')} ${esc(ME.repo.error || '')}" onclick="go('skills')" style="cursor:pointer">${ME.repo.mode === 'github' ? '🧩 스킬 저장소 ' + esc(ME.repo.head) : ME.repo.mode === 'local' ? '📁 로컬 스킬 저장소' : '… 스킬 저장소'}</span>
   <button class="row" onclick="logout()" title="사용자 바꾸기"><span class="av" style="width:32px;height:32px;background:${u.color};font-size:13px">${esc(u.name[0])}</span>
     <span style="text-align:left;line-height:1.25"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="small muted">${esc(u.team)} · ${esc(u.role_name)}</span></span></button>`;
  const ico = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const topIcons = [ico('<rect x="5" y="10" width="14" height="10" rx="1"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>'),ico('<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2 2.2 3 4.9 3 8s-1 5.8-3 8c-2-2.2-3-4.9-3-8s1-5.8 3-8"/>')];
  const cleanEmoji = e => e.childNodes.forEach(n => { if (n.nodeType === 3) n.textContent = n.textContent.replace(/[\p{Extended_Pictographic}]/gu, ''); });
  $('#top').querySelectorAll('.net button,.chip').forEach(cleanEmoji);
  $('#top .net').querySelectorAll('button').forEach((b,i)=>b.insertAdjacentHTML('afterbegin',topIcons[i]));
}

function renderSide() {
  const r = ME.user.role;
  const show = k => k === 'audit' ? ['security', 'corpAdmin'].includes(r) : k === 'dash' ? r !== 'user' : true;
  const icons = {new:'<path d="M4 5h11l5 5v9H4z"/><path d="M15 5v5h5M8 14h8M12 10v8"/>',docs:'<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M8 9h8M8 13h8M8 17h5"/>',templates:'<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>',skills:'<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9 7 7m10 10 2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',register:'<path d="M4 12h16M12 4v16"/>',inspect:'<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4M8.5 11l1.7 1.7 3.4-3.4"/>',approve:'<path d="M5 12l4 4L19 6"/>',inet:'<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2 2.2 3 4.9 3 8s-1 5.8-3 8c-2-2.2-3-4.9-3-8s1-5.8 3-8"/>',dash:'<path d="M4 19V9m5 10V5m6 14v-8m5 8V3"/>',audit:'<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>',demo:'<path d="M5 4h14v16H5z"/><path d="m10 9 5 3-5 3z"/>'};
  const icon = k => `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[k]||icons.docs}</svg>`;
  $('#side').innerHTML = NAV.filter(n => show(n[0])).map(([k, ic, t]) =>
    `<a href="#" class="${VIEW === k || (VIEW === 'ws' && k === 'new') ? 'on' : ''}" onclick="go('${k}');return false"><span class="ic">${icon(k)}</span>${t}${k === 'approve' && ME.pending ? `<span class="badge">${ME.pending}</span>` : ''}</a>`).join('')
    + `<div class="grow"></div><div class="sec">이 PC에서만 · localhost</div><div class="small muted" style="padding:0 12px">가상 조직 · 가상 데이터</div>`;
}

async function vNew() {
  const d = await api('/api/templates'); TPLS = d.templates;
  const mine = TPLS.filter(t => t.scope !== 'corp'), corp = TPLS.filter(t => t.scope === 'corp');
  $('#main').innerHTML = `
  <div class="page-h"><div><h2>무엇을 만들까요?</h2><p>하고 싶은 말을 적고 자료를 붙이면, 맞는 양식(스킬)을 골라 초안을 만듭니다.</p></div>
    <span class="chip ${ME.net === 'internet' ? 'o' : 'n'}">${ME.net === 'internet' ? '🌐 인터넷망 — 대외비 템플릿 제외 · 마스킹 적용' : '🔒 폐쇄망 — 모든 등급 사용 가능'}</span></div>
    <section class="console-banner" aria-label="문서 자동화 안내"><div><div class="eyebrow">KOSCOM DOCUMENT AUTOMATION / SECURE WORKSPACE</div><h3>업무의 흐름을, 신뢰할 수 있는 문서로.</h3><p>승인된 양식과 AI 보조를 기반으로 초안부터 검수까지 하나의 워크스페이스에서 관리합니다.</p></div></section>
    <div class="ask">
    <textarea id="req" placeholder="예) 3분기 금융영업1팀 실적 결과 보고서 만들어줘. 첨부한 엑셀 숫자를 성과 표에 넣고, 향후 계획은 B증권 제안 중심으로."></textarea>
    <div class="row sp wrap" style="margin-top:8px">
      <div class="row wrap"><button class="btn ghost sm" onclick="pickFile(f => addAtt(f))">📎 자료 첨부</button><button class="btn ghost sm" onclick="demoPick(us => { ATT.push(...us); renderAtt(); })">📂 시연 자료</button><div class="files" id="att"></div></div>
      <div class="row"><button class="btn ghost" onclick="recommend()">🧭 양식 추천</button><button class="btn o" id="go" onclick="startCompose()" disabled>초안 만들기 →</button></div>
    </div>
  </div>
  <div id="rec"></div>
  <h3 style="margin:26px 0 10px;display:flex;gap:8px;align-items:center"><i class="chev"></i>우리 팀·부서·나의 스킬 양식 <span class="chip">${mine.length}</span></h3>
  <div class="tgrid">${mine.map(tplCard).join('') || '<div class="muted small">아직 없습니다. [★ 스킬 만들기]에서 대표 문서로 만들어 보세요.</div>'}</div>
  <h3 style="margin:26px 0 10px;display:flex;gap:8px;align-items:center"><i class="chev"></i>전사 공통 양식 <span class="chip">${corp.length}</span></h3>
  <div class="tgrid">${corp.map(tplCard).join('')}</div>`;
  renderAtt(); if (PICK) selTpl(PICK);
}
