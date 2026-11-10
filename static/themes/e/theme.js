// 코쇠오피스 화면 테마 E — 기본 index.html 의 함수 중 이 테마가 바꾼 것만 덮어쓴다.
// 기본 화면 스크립트 다음, boot() 전에 한 번 실린다(index.html 의 테마 로더).

async function showLogin() {
  $('#app').classList.add('hide'); $('#login').classList.remove('hide');
  const [p, h] = await Promise.all([api('/api/personas'), api('/api/health', {quiet: true}).catch(() => ({}))]);
  $('#login').innerHTML = `
  <div class="l">
    <div class="brandline"><img src="/static/kosoe.webp" alt=""><span>코스콤 문서 자동화</span></div>
    <h1>회사 양식에 맞춰,<br>빠르고 안전하게</h1>
    <p>요청과 자료를 넣으면 PPT, 웹슬라이드, 한글 초안을 만들고 회사 기준으로 검수합니다.</p>
    <img class="hero-art" src="/static/themes/e/hero.webp" alt="코쇠가 문서를 회사 양식에 맞춰 정리하는 손그림">
    <div class="status" style="margin-top:22px;position:relative">
      <span class="chip">${h.ai?.ok ? 'AI 연결 ' + esc(h.model) : '규칙 기반 보조 모드'}</span>
      <span class="chip">${h.hwp ? '한글 엔진 준비' : '한글 엔진 확인 필요'}</span>
      <span class="chip">${h.repo?.mode === 'github' ? '스킬 저장소 ' + esc((h.repo.head || '').slice(0, 7)) : h.repo?.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소 준비 중'}</span>
      <span class="chip">전사 공용 스킬 ${(h.corp || []).filter(c => c.cached).length}/${(h.corp || []).length}</span>
    </div>
  </div>
  <div class="r">
    <div><h2 style="font-size:22px">시연 사용자 선택</h2><p class="muted" style="margin:4px 0 6px">실제 서비스에서는 사내 SSO로 로그인합니다. 시연용 가상 조직입니다.</p></div>
    ${p.users.map(u => `<button class="persona" onclick="login('${u.id}')">
      <span class="av" style="background:${u.color}">${esc(u.name[0])}</span>
      <span class="grow"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="muted small">${esc(u.dept)} · ${esc(u.team)}</span></span>
      <span class="chip ${u.role === 'user' ? '' : 'o'}">${esc(u.role_name)}</span></button>`).join('')}
  </div>`;
}

function renderTop() {
  const u = ME.user, inet = ME.inet;
  $('#top').innerHTML = `
   <div class="logo"><img src="/static/kosoe.webp" alt=""><span>코쇠오피스</span></div>
   <div class="net" title="인터넷망은 팀장 승인 기간에만">
     <button class="${ME.net === 'closed' ? 'on' : ''}" onclick="setNet('closed')">${ico('lock')}폐쇄망</button>
     <button class="${ME.net === 'internet' ? 'on i' : ''}" onclick="setNet('internet')">${ico('globe')}인터넷망${inet ? '' : ' 승인 필요'}</button>
   </div>
   <span class="small muted">${inet ? `인터넷 승인 ~${inet.until}` : '인터넷망: 승인 필요'}</span>
   <span class="grow"></span>
   <button class="chip ${ME.ai.connected ? 'n' : 'o'}" style="cursor:pointer" onclick="aiModal()" title="눌러서 AI 바꾸기 (Claude Code CLI ↔ NVIDIA API · OpenRouter)">${ico('spark')}${aiChipText().replace(/^[^가-힣A-Za-z0-9]+/, '')} ▾</button>
   <span class="chip" title="스킬 저장소 ${esc(ME.repo.url || '')} ${esc(ME.repo.error || '')}" onclick="go('skills')" style="cursor:pointer">${ico('layers')}${ME.repo.mode === 'github' ? '스킬 저장소 ' + esc(ME.repo.head) : ME.repo.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소'}</span>
   <button class="row" onclick="logout()" title="사용자 바꾸기"><span class="av" style="width:32px;height:32px;background:${u.color};font-size:13px">${esc(u.name[0])}</span>
     <span style="text-align:left;line-height:1.25"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="small muted">${esc(u.team)} · ${esc(u.role_name)}</span></span></button>`;
}

const ICO = {
  new:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  docs:'<path d="M4 5h6l2 2h8v12H4Z"/><path d="M4 9h16"/>',
  templates:'<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M8 7h8M8 11h8M8 15h5"/>',
  skills:'<path d="M8 3h8v5h5v8h-5v5H8v-5H3V8h5Z"/><path d="M8 8h8v8H8Z"/>',
  register:'<path d="M12 3v18M3 12h18"/><rect x="5" y="5" width="14" height="14" rx="1"/>',
  inspect:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5M8 11l2 2 4-5"/>',
  approve:'<rect x="4" y="3" width="16" height="18" rx="1"/><path d="m8 12 3 3 6-7"/>',
  inet:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
  dash:'<path d="M4 20V10h4v10M10 20V4h4v16M16 20v-7h4v7"/>',
  audit:'<path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6Z"/><path d="m9 12 2 2 4-5"/>',
  demo:'<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m10 9 5 3-5 3Z"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
  spark:'<path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7Z"/>',
  layers:'<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>'
};

const ico = n => `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true">${ICO[n] || ''}</svg>`;

NAV.splice(0, NAV.length, ...[
  ['new','new','새 문서'],['docs','docs','문서함'],['templates','templates','양식'],['skills','skills','스킬'],['register','register','스킬 만들기'],
  ['inspect','inspect','검수'],['approve','approve','승인함'],['inet','inet','인터넷 사용'],['dash','dash','대시보드'],['audit','audit','감사 로그'],
  ['demo','demo','시연 3분'],
]);

function renderSide() {
  const r = ME.user.role;
  const show = k => k === 'audit' ? ['security', 'corpAdmin'].includes(r) : k === 'dash' ? r !== 'user' : true;
  $('#side').innerHTML = NAV.filter(n => show(n[0])).map(([k, ic, t]) =>
    `<a href="#" class="${VIEW === k || (VIEW === 'ws' && k === 'new') ? 'on' : ''}" onclick="go('${k}');return false"><span class="ic">${ico(ic)}</span>${t}${k === 'approve' && ME.pending ? `<span class="badge">${ME.pending}</span>` : ''}</a>`).join('')
    + `<div class="grow"></div><div class="sec">이 PC에서만 · localhost</div><div class="small muted" style="padding:0 12px">가상 조직 · 가상 데이터</div>`;
}

async function vNew() {
  const d = await api('/api/templates'); TPLS = d.templates;
  const mine = TPLS.filter(t => t.scope !== 'corp'), corp = TPLS.filter(t => t.scope === 'corp');
  $('#main').innerHTML = `
  <div class="page-h"><div><h2>무엇을 만들까요?</h2><p>하고 싶은 말을 적고 자료를 붙이면, 맞는 양식(스킬)을 골라 초안을 만듭니다.</p></div>
   <span class="chip ${ME.net === 'internet' ? 'o' : 'n'}">${ME.net === 'internet' ? '🌐 인터넷망 — 대외비 템플릿 제외 · 마스킹 적용' : '🔒 폐쇄망 — 모든 등급 사용 가능'}</span></div>
  <section class="field-banner" aria-label="문서 작성 안내"><h3>요청은 자유롭게, 결과는 회사 기준에 맞게</h3><p>양식을 고르면 초안부터 숫자 교차검증까지 한 흐름에서 처리합니다.</p></section>
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
