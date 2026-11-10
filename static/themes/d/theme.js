// 코쇠오피스 화면 테마 D — 기본 index.html 의 함수 중 이 테마가 바꾼 것만 덮어쓴다.
// 기본 화면 스크립트 다음, boot() 전에 한 번 실린다(index.html 의 테마 로더).

async function showLogin() {
  $('#app').classList.add('hide'); $('#login').classList.remove('hide');
  const [p, h] = await Promise.all([api('/api/personas'), api('/api/health', {quiet: true}).catch(() => ({}))]);
  $('#login').innerHTML = `
  <div class="l"><div class="bg"><i></i><i></i><i></i></div>
    <img src="/static/kosoe.webp" alt="코쇠">
    <h1>코쇠오피스</h1>
    <p>요청과 자료를 한 번에 넣으세요. 회사 양식에 맞는 PPT, 웹슬라이드, 한글 초안을 만들고 숫자와 보안 기준까지 확인합니다.</p>
    <div class="status" style="margin-top:22px;position:relative">
      <span class="chip">${h.ai?.ok ? 'AI 연결됨 ' + esc(h.model) : 'AI 미연결: 규칙 기반 보조 모드'}</span>
      <span class="chip">${h.hwp ? '한글 엔진 준비' : '한글 엔진 없음'}</span>
      <span class="chip">${h.repo?.mode === 'github' ? '스킬 저장소 ' + esc((h.repo.head || '').slice(0, 7)) : h.repo?.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소 준비 중'}</span>
      <span class="chip" style="background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.2)">전사 공용 스킬 ${(h.corp || []).filter(c => c.cached).length}/${(h.corp || []).length}</span>
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
     <button class="${ME.net === 'internet' ? 'on i' : ''}" onclick="setNet('internet')">${ico('globe')}인터넷망${inet ? '' : ' (승인 필요)'}</button>
   </div>
   <span class="small muted">${inet ? `인터넷 승인 ~${inet.until}` : '인터넷망: 승인 필요'}</span>
   <span class="grow"></span>
   <button class="chip ${ME.ai.connected ? 'n' : 'o'}" style="cursor:pointer" onclick="aiModal()" title="눌러서 AI 바꾸기 (Claude Code CLI ↔ NVIDIA API · OpenRouter)">${ico('spark')} ${aiChipText().replace(/[⚙🤖️]/g,'').trim()} ▾</button>
   <span class="chip" title="스킬 저장소 ${esc(ME.repo.url || '')} ${esc(ME.repo.error || '')}" onclick="go('skills')" style="cursor:pointer">${ico('skills')} ${ME.repo.mode === 'github' ? '스킬 저장소 ' + esc(ME.repo.head) : ME.repo.mode === 'local' ? '로컬 스킬 저장소' : '스킬 저장소'}</span>
   <button class="row" onclick="logout()" title="사용자 바꾸기"><span class="av" style="width:32px;height:32px;background:${u.color};font-size:13px">${esc(u.name[0])}</span>
     <span style="text-align:left;line-height:1.25"><b>${esc(u.name)} ${esc(u.title)}</b><br><span class="small muted">${esc(u.team)} · ${esc(u.role_name)}</span></span></button>`;
}

const ICONS = {
  new:'<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13 7 4 4"/>',
  docs:'<path d="M4 5h6l2 2h8v12H4z"/><path d="M8 11h8M8 15h6"/>',
  templates:'<path d="M4 4h16v16H4zM9 4v16M9 10h11"/>',
  skills:'<path d="M8 3v3a2 2 0 1 0 4 0V3h4v5h3v4h-3v5h-4a2 2 0 1 1-4 0H4v-5h3a2 2 0 1 0 0-4H4V3z"/>',
  register:'<path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6-5.4-2.9-5.4 2.9 1-6-4.4-4.3 6.1-.9z"/>',
  inspect:'<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4M8 11l2 2 4-4"/>',
  approve:'<path d="M6 3h12v18H6zM9 3V1h6v2M9 12l2 2 4-5"/>',
  inet:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  dash:'<path d="M4 19V9h4v10M10 19V4h4v15M16 19v-7h4v7"/>',
  audit:'<path d="M12 3 20 6v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  demo:'<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m10 9 5 3-5 3z"/>',
  lock:'<rect x="5" y="10" width="14" height="10" rx="1"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  spark:'<path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>'
};

const ico = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.docs}</svg>`;

NAV.splice(0, NAV.length, ...[
  ['new', '새 문서'], ['docs', '문서함'], ['templates', '양식'], ['skills', '스킬'], ['register', '스킬 만들기'],
  ['inspect', '검수'], ['approve', '승인함'], ['inet', '인터넷 사용'], ['dash', '대시보드'], ['audit', '감사 로그'],
  ['demo', '시연 3분'],
]);

function renderSide() {
  const r = ME.user.role;
  const show = k => k === 'audit' ? ['security', 'corpAdmin'].includes(r) : k === 'dash' ? r !== 'user' : true;
  $('#side').innerHTML = NAV.filter(n => show(n[0])).map(([k, t]) =>
    `<a href="#" class="${VIEW === k || (VIEW === 'ws' && k === 'new') ? 'on' : ''}" onclick="go('${k}');return false"><span class="ic">${ico(k)}</span>${t}${k === 'approve' && ME.pending ? `<span class="badge">${ME.pending}</span>` : ''}</a>`).join('')
    + `<div class="grow"></div><div class="sec">이 PC에서만 · localhost</div><div class="small muted" style="padding:0 12px">가상 조직 · 가상 데이터</div>`;
}
