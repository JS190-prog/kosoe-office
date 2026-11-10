// 코쇠오피스 화면 테마 G — 기본 index.html 의 함수 중 이 테마가 바꾼 것만 덮어쓴다.
// 기본 화면 스크립트 다음, boot() 전에 한 번 실린다(index.html 의 테마 로더).

async function showLogin() {
  $('#app').classList.add('hide'); $('#login').classList.remove('hide');
  const [p, h] = await Promise.all([api('/api/personas'), api('/api/health', {quiet: true}).catch(() => ({}))]);
  $('#login').innerHTML = `
  <div class="l">
    <div class="hero-content">
      <div class="hero-brand"><img src="/static/kosoe.webp" alt="코쇠"><strong>코쇠오피스</strong></div>
      <h1>문서에도<br>시세의 정밀함을</h1>
      <p>요청과 자료를 붙이면 회사 양식에 맞는 초안을 만듭니다. 숫자를 대조하고 승인과 감사 기록까지 한 흐름으로 관리합니다.</p>
      <svg class="market-line" viewBox="0 0 720 140" role="img" aria-label="왼쪽에서 오른쪽으로 흐르는 시세 라인">
        <path class="grid" d="M0 28H720M0 70H720M0 112H720"/>
        <path class="tick" pathLength="900" d="M0 103 L42 94 L70 101 L104 78 L136 83 L166 61 L202 69 L232 46 L270 57 L302 39 L334 51 L366 42 L398 70 L430 62 L462 76 L494 48 L526 54 L558 31 L590 38 L622 20 L654 31 L686 13 L720 18"/>
        <path class="tick rise" pathLength="900" d="M0 113 L54 110 L96 99 L138 105 L184 87 L226 92 L270 73 L314 79 L358 66 L402 75 L448 55 L492 60 L536 42 L580 47 L626 29 L670 34 L720 17"/>
        <g class="candle"><path d="M112 59V98M105 72H119V88H105Z"/><path class="up" d="M252 34V75M245 48H259V65H245Z"/><path d="M390 47V84M383 58H397V75H383Z"/><path class="up" d="M548 21V61M541 34H555V49H541Z"/><path class="up" d="M676 5V42M669 15H683V30H669Z"/></g>
      </svg>
    </div>
  </div>
  <div class="r">
    <div class="login-intro"><h2>시연 사용자 선택</h2><p class="muted" style="margin:5px 0 0">실제 서비스는 사내 SSO로 연결됩니다. 지금은 가상 조직으로 기능을 확인합니다.</p></div>
    ${p.users.map(u => `<button class="persona" onclick="login('${u.id}')">
      <span class="av" style="background:${u.color}">${esc(u.name[0])}</span>
      <span class="grow"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="muted small">${esc(u.dept)} · ${esc(u.team)}</span></span>
      <span class="chip ${u.role === 'user' ? '' : 'o'}">${esc(u.role_name)}</span></button>`).join('')}
    <div class="login-health" aria-label="시스템 준비 상태">
      <div class="health-row"><i class="health-dot ${h.ai?.ok ? '' : 'warn'}"></i><span>${h.ai?.ok ? 'AI 연결됨 / ' + esc(h.model) : '규칙 기반 보조 모드'}</span></div>
      <div class="health-row"><i class="health-dot ${h.hwp ? '' : 'warn'}"></i><span>${h.hwp ? '한글 엔진 준비됨' : '한글 엔진 확인 필요'}</span></div>
      <div class="health-row"><i class="health-dot"></i><span>전사 공용 스킬 ${(h.corp || []).filter(c => c.cached).length}/${(h.corp || []).length} 준비됨</span></div>
    </div>
  </div>`;
}

const ICON_PATHS = {
  lock:'<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
  cpu:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3M9 9h6v6H9z"/>',
  repo:'<circle cx="6" cy="5" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="8" cy="19" r="2"/><path d="M8 5h5a5 5 0 0 1 5 5v4M7 7l1 10"/>',
  new:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  docs:'<path d="M4 6h6l2 2h8v11H4z"/><path d="M4 6V4h6l2 2"/>',
  templates:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 4v16M8 9h13"/>',
  skills:'<path d="M9 3H4a1 1 0 0 0-1 1v5a3 3 0 1 1 0 6v5a1 1 0 0 0 1 1h5a3 3 0 1 1 6 0h5a1 1 0 0 0 1-1v-5a3 3 0 1 0 0-6V4a1 1 0 0 0-1-1h-5a3 3 0 1 1-6 0Z"/>',
  register:'<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9Z"/>',
  inspect:'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M8 11l2 2 4-4"/>',
  approve:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 3h6v4H9zM8 13l2.5 2.5L16 10"/>',
  inet:'<path d="M4 4h7v7H4zM13 13h7v7h-7zM15 4h5v5M20 4l-7 7M4 15v5h5"/>',
  dash:'<path d="M4 19V9M10 19V5M16 19v-7M22 19V3"/>',
  audit:'<path d="M12 3 4 6v6c0 5 3.4 8.1 8 9 4.6-.9 8-4 8-9V6Z"/><path d="m8.5 12 2.2 2.2 4.8-4.8"/>',
  demo:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3Z"/>'
};

const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICON_PATHS[name] || ICON_PATHS.new}</svg>`;

function renderTop() {
  const u = ME.user, inet = ME.inet;
  const aiLabel = aiChipText().replace(/^[🤖⚙️]\ufe0f?\s*/u, '');
  $('#top').innerHTML = `
   <div class="logo"><img src="/static/kosoe.webp" alt=""><span>코쇠오피스</span></div>
   <div class="net" title="인터넷망은 팀장 승인 기간에만">
     <button class="${ME.net === 'closed' ? 'on' : ''}" onclick="setNet('closed')">${icon('lock')}<span>폐쇄망</span></button>
     <button class="${ME.net === 'internet' ? 'on i' : ''}" onclick="setNet('internet')">${icon('globe')}<span>인터넷망${inet ? '' : ' / 승인 필요'}</span></button>
   </div>
   <span class="small muted">${inet ? `인터넷 승인 ~${inet.until}` : '인터넷망: 승인 필요'}</span>
   <span class="grow"></span>
   <button class="chip ${ME.ai.connected ? 'n' : 'o'}" style="cursor:pointer" onclick="aiModal()" title="눌러서 AI 바꾸기 (Claude Code CLI ↔ NVIDIA API · OpenRouter)">${icon('cpu')}${aiLabel} ▾</button>
   <button class="chip repo-chip" title="스킬 저장소 ${esc(ME.repo.url || '')} ${esc(ME.repo.error || '')}" onclick="go('skills')" style="cursor:pointer">${icon('repo')}${ME.repo.mode === 'github' ? '스킬 저장소 ' + esc(ME.repo.head) : ME.repo.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소 준비 중'}</button>
   <button class="row" onclick="logout()" title="사용자 바꾸기"><span class="av" style="width:32px;height:32px;background:${u.color};font-size:13px">${esc(u.name[0])}</span>
     <span class="user-copy" style="text-align:left;line-height:1.25;color:#fff"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="small muted">${esc(u.team)} · ${esc(u.role_name)}</span></span></button>`;
}

NAV.splice(0, NAV.length, ...[
  ['new', '새 문서'], ['docs', '문서함'], ['templates', '양식'], ['skills', '스킬'], ['register', '스킬 만들기'],
  ['inspect', '검수'], ['approve', '승인함'], ['inet', '인터넷 사용'], ['dash', '대시보드'], ['audit', '감사 로그'],
  ['demo', '시연 3분'],
]);

function renderSide() {
  const r = ME.user.role;
  const show = k => k === 'audit' ? ['security', 'corpAdmin'].includes(r) : k === 'dash' ? r !== 'user' : true;
  $('#side').innerHTML = NAV.filter(n => show(n[0])).map(([k, t]) =>
    `<a href="#" title="${t}" class="${VIEW === k || (VIEW === 'ws' && k === 'new') ? 'on' : ''}" onclick="go('${k}');return false"><span class="ic">${icon(k)}</span>${t}${k === 'approve' && ME.pending ? `<span class="badge">${ME.pending}</span>` : ''}</a>`).join('')
    + `<div class="grow"></div><div class="sec">이 PC에서만 · localhost</div><div class="small muted" style="padding:0 12px">가상 조직 · 가상 데이터</div>`;
}
