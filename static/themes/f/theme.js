// 코쇠오피스 화면 테마 F — 기본 index.html 의 함수 중 이 테마가 바꾼 것만 덮어쓴다.
// 기본 화면 스크립트 다음, boot() 전에 한 번 실린다(index.html 의 테마 로더).

const ICONS = {
  lock:'<rect x="5" y="10" width="14" height="10" rx="1"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
  spark:'<path d="m12 3 1.3 4.2L17.5 9l-4.2 1.8L12 15l-1.3-4.2L6.5 9l4.2-1.8L12 3Z"/><path d="m18.5 15 .7 2.2 2.3.8-2.3.8-.7 2.2-.7-2.2-2.3-.8 2.3-.8.7-2.2Z"/>',
  repo:'<path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 11h6M9 15h6"/>',
  edit:'<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
  folder:'<path d="M3 6h7l2 2h9v11H3z"/>',
  ruler:'<path d="m4 17 13-13 3 3L7 20H4v-3Z"/><path d="m12 9 3 3M9 12l2 2M15 6l2 2"/>',
  puzzle:'<path d="M8 4h3a2 2 0 1 1 4 0h3v4a2 2 0 1 1 0 4v4h-4a2 2 0 1 1-4 0H6v-4a2 2 0 1 1 0-4V4h2Z"/>',
  star:'<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3Z"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  check:'<path d="M5 12.5 9.5 17 19 7"/><rect x="3" y="3" width="18" height="18" rx="2"/>',
  chart:'<path d="M4 20V10h4v10M10 20V4h4v16M16 20v-7h4v7M3 20h18"/>',
  shield:'<path d="M12 3 20 6v5c0 5-3.4 8.3-8 10-4.6-1.7-8-5-8-10V6l8-3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
  play:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m10 9 5 3-5 3V9Z"/>'
};

const icon = n => `<span class="ui-ic" aria-hidden="true"><svg viewBox="0 0 24 24">${ICONS[n] || ICONS.folder}</svg></span>`;

const cleanIconText = s => String(s || '').replace(/^[^A-Za-z가-힣0-9]+/, '');

// ───────────── 로그인 ─────────────

async function showLogin() {
  $('#app').classList.add('hide'); $('#login').classList.remove('hide');
  const [p, h] = await Promise.all([api('/api/personas'), api('/api/health', {quiet: true}).catch(() => ({}))]);
  $('#login').innerHTML = `
  <div class="l">
    <div class="cover-copy">
      <h1>코쇠오피스<em>회사 양식에 맞는 문서를<br>빠르고 안전하게</em></h1>
      <p>요청과 자료를 넣으면 회사 기준을 상속한 양식으로 초안을 만들고, 숫자 검수와 승인 기록까지 한 화면에서 관리합니다.</p>
    </div>
    <img class="kosoe-mark" src="/static/kosoe.webp" alt="코쇠">
    <div class="status" style="margin-top:22px;position:relative">
      <span class="chip" style="background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.2)">${h.ai?.ok ? 'AI 연결됨 ' + esc(h.model) : 'AI 미연결, 규칙 기반 보조 모드'}</span>
      <span class="chip" style="background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.2)">${h.hwp ? '한글 엔진 준비' : '한글 엔진 없음'}</span>
      <span class="chip" style="background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.2)">${h.repo?.mode === 'github' ? '스킬 저장소 ' + esc((h.repo.head || '').slice(0, 7)) : h.repo?.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소 준비 중'}</span>
      <span class="chip" style="background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.2)">전사 공용 스킬 ${(h.corp || []).filter(c => c.cached).length}/${(h.corp || []).length}</span>
    </div>
  </div>
  <div class="r">
    <div class="login-head"><h2>시연 사용자 선택</h2><p class="muted">실제 서비스에서는 사내 SSO로 로그인합니다. 아래 계정과 조직 정보는 시연용 가상 데이터입니다.</p></div>
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
     <button class="${ME.net === 'closed' ? 'on' : ''}" onclick="setNet('closed')">${icon('lock')}폐쇄망</button>
     <button class="${ME.net === 'internet' ? 'on i' : ''}" onclick="setNet('internet')">${icon('globe')}인터넷망${inet ? '' : ' 승인 필요'}</button>
   </div>
   <span class="small muted">${inet ? `인터넷 승인 ~${inet.until}` : '인터넷망: 승인 필요'}</span>
   <span class="grow"></span>
   <button class="chip ${ME.ai.connected ? 'n' : 'o'}" style="cursor:pointer" onclick="aiModal()" title="눌러서 AI 바꾸기 (Claude Code CLI ↔ NVIDIA API · OpenRouter)">${icon('spark')}<span>${esc(cleanIconText(aiChipText()))}</span></button>
   <span class="chip" title="스킬 저장소 ${esc(ME.repo.url || '')} ${esc(ME.repo.error || '')}" onclick="go('skills')" style="cursor:pointer">${icon('repo')}<span>${ME.repo.mode === 'github' ? '스킬 저장소 ' + esc(ME.repo.head) : ME.repo.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소'}</span></span>
   <button class="row" onclick="logout()" title="사용자 바꾸기"><span class="av" style="width:32px;height:32px;background:${u.color};font-size:13px">${esc(u.name[0])}</span>
     <span style="text-align:left;line-height:1.25"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="small muted">${esc(u.team)} · ${esc(u.role_name)}</span></span></button>`;
}

NAV.splice(0, NAV.length, ...[
  ['new', 'edit', '새 문서'], ['docs', 'folder', '문서함'], ['templates', 'ruler', '양식'], ['skills', 'puzzle', '스킬'], ['register', 'star', '스킬 만들기'],
  ['inspect', 'search', '검수'], ['approve', 'check', '승인함'], ['inet', 'globe', '인터넷 사용'], ['dash', 'chart', '대시보드'], ['audit', 'shield', '감사 로그'],
  ['demo', 'play', '시연 3분'],
]);

function renderSide() {
  const r = ME.user.role;
  const show = k => k === 'audit' ? ['security', 'corpAdmin'].includes(r) : k === 'dash' ? r !== 'user' : true;
  $('#side').innerHTML = NAV.filter(n => show(n[0])).map(([k, ic, t]) =>
    `<a href="#" class="${VIEW === k || (VIEW === 'ws' && k === 'new') ? 'on' : ''}" onclick="go('${k}');return false"><span class="ic">${icon(ic)}</span>${t}${k === 'approve' && ME.pending ? `<span class="badge">${ME.pending}</span>` : ''}</a>`).join('')
    + `<div class="grow"></div><div class="sec">이 PC에서만 · localhost</div><div class="small muted" style="padding:0 12px">가상 조직 · 가상 데이터</div>`;
}
