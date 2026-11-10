// 코쇠오피스 화면 테마 A — 기본 index.html 의 함수 중 이 테마가 바꾼 것만 덮어쓴다.
// 기본 화면 스크립트 다음, boot() 전에 한 번 실린다(index.html 의 테마 로더).

function renderTop() {
  const u = ME.user, inet = ME.inet;
  const topIcon = (name, d) => `<svg class="nav-svg" style="vertical-align:-3px;margin-right:4px" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  $('#top').innerHTML = `
   <div class="logo"><img src="/static/kosoe.webp" alt=""><span>코쇠오피스</span></div>
   <div class="net" title="인터넷망은 팀장 승인 기간에만">
     <button class="${ME.net === 'closed' ? 'on' : ''}" onclick="setNet('closed')">${topIcon('lock','<rect x="5" y="10" width="14" height="10" rx="1"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>')}폐쇄망</button>
     <button class="${ME.net === 'internet' ? 'on i' : ''}" onclick="setNet('internet')">${topIcon('globe','<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>')}인터넷망${inet ? '' : ''}</button>
   </div>
   <span class="small muted">${inet ? `인터넷 승인 ~${inet.until}` : '인터넷망: 승인 필요'}</span>
   <span class="grow"></span>
   <button class="chip ${ME.ai.connected ? 'n' : 'o'}" style="cursor:pointer" onclick="aiModal()" title="눌러서 AI 바꾸기 (Claude Code CLI ↔ NVIDIA API · OpenRouter)">${topIcon('ai','<path d="M7 8V5m10 3V5M5 10h14v9H5z"/><path d="M9 14h.01M15 14h.01M9 18h6"/>')}${aiChipText().replace(/^[^\w가-힣]+\s*/, '')} ▾</button>
   <span class="chip" title="스킬 저장소 ${esc(ME.repo.url || '')} ${esc(ME.repo.error || '')}" onclick="go('skills')" style="cursor:pointer">${topIcon('repo','<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 14h6M9 17h6"/>')}${ME.repo.mode === 'github' ? '스킬 저장소 ' + esc(ME.repo.head) : ME.repo.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소'}</span>
   <button class="row" onclick="logout()" title="사용자 바꾸기"><span class="av" style="width:32px;height:32px;background:${u.color};font-size:13px">${esc(u.name[0])}</span>
     <span style="text-align:left;line-height:1.25"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="small muted">${esc(u.team)} · ${esc(u.role_name)}</span></span></button>`;
}

const svg = d => `<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;

const ICON = {
  new:svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>'), docs:svg('<path d="M5 3h10l4 4v14H5z"/><path d="M15 3v5h5M8 13h8M8 17h6"/>'),
  templates:svg('<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M8 8h8M8 12h8M8 16h5"/>'), skills:svg('<path d="M12 3v18M3 12h18"/><path d="m5 5 14 14M19 5 5 19"/>'),
  register:svg('<path d="M12 3v18M3 12h18"/>'), inspect:svg('<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/>'), approve:svg('<path d="m5 12 4 4L19 6"/>'),
  inet:svg('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>'), dash:svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
  audit:svg('<path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6Z"/><path d="m9 12 2 2 4-4"/>'), demo:svg('<rect x="3" y="5" width="13" height="14" rx="1"/><path d="m16 10 5-3v10l-5-3"/>')
};

function renderSide() {
  const r = ME.user.role;
  const show = k => k === 'audit' ? ['security', 'corpAdmin'].includes(r) : k === 'dash' ? r !== 'user' : true;
  $('#side').innerHTML = NAV.filter(n => show(n[0])).map(([k, ic, t]) =>
    `<a href="#" class="${VIEW === k || (VIEW === 'ws' && k === 'new') ? 'on' : ''}" onclick="go('${k}');return false"><span class="ic">${ICON[k] || ic}</span>${t}${k === 'approve' && ME.pending ? `<span class="badge">${ME.pending}</span>` : ''}</a>`).join('')
    + `<div class="grow"></div><div class="sec">이 PC에서만 · localhost</div><div class="small muted" style="padding:0 12px">가상 조직 · 가상 데이터</div>`;
}

async function vNew() {
  const d = await api('/api/templates'); TPLS = d.templates;
  const mine = TPLS.filter(t => t.scope !== 'corp'), corp = TPLS.filter(t => t.scope === 'corp');
  $('#main').innerHTML = `
  <div class="page-h"><div><h2>무엇을 만들까요?</h2><p>하고 싶은 말을 적고 자료를 붙이면, 맞는 양식(스킬)을 골라 초안을 만듭니다.</p></div>
    <span class="chip ${ME.net === 'internet' ? 'o' : 'n'}">${ME.net === 'internet' ? '🌐 인터넷망 — 대외비 템플릿 제외 · 마스킹 적용' : '🔒 폐쇄망 — 모든 등급 사용 가능'}</span></div>
  <section class="new-banner" aria-label="문서 자동화 안내"><div><div class="eyebrow">KOSCOM DOCUMENT INTELLIGENCE</div><h3>신뢰할 수 있는 문서 자동화</h3><p>승인된 양식과 기준으로, 보고의 품질을 일관되게 만듭니다.</p></div></section>
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
