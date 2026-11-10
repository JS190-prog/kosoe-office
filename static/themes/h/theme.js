// 코쇠오피스 화면 테마 H — 기본 index.html 의 함수 중 이 테마가 바꾼 것만 덮어쓴다.
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
  decorateTop();
}

const ICON_PATHS = {
  new:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  docs:'<path d="M6 2h9l5 5v15H6Z"/><path d="M14 2v6h6"/><path d="M9 13h8M9 17h8"/>',
  templates:'<path d="M4 4h16v16H4Z"/><path d="M4 9h16M10 9v11"/>',
  skills:'<path d="M12 3 4 7l8 4 8-4Z"/><path d="m4 12 8 4 8-4M4 17l8 4 8-4"/>',
  register:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  inspect:'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M8 11l2 2 4-5"/>',
  approve:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-5"/>',
  inet:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  dash:'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  audit:'<path d="M5 3h14v18H5Z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  demo:'<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m10 9 5 3-5 3Z"/>',
  closed:'<rect x="5" y="10" width="14" height="11" rx="1"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  ai:'<path d="M12 3v3M12 18v3M3 12h3M18 12h3"/><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 10v4M15 10v4M9 15h6"/>',
  repo:'<circle cx="6" cy="5" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="8" cy="19" r="2"/><path d="M8 5h5a5 5 0 0 1 5 5v2M7 7l1 10M10 19h4a4 4 0 0 0 4-4v-3"/>'
};

function iconSvg(k){return `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true">${ICON_PATHS[k]||ICON_PATHS.docs}</svg>`;}

function decorateTop(){
  const clean=b=>{for(const n of b.childNodes){if(n.nodeType===3){n.textContent=n.textContent.replace(/^[^\p{L}\p{N}]+/u,'').trimStart();break;}}};
  const nets=$('#top').querySelectorAll('.net button');
  nets.forEach((b,i)=>{clean(b);b.insertAdjacentHTML('afterbegin',iconSvg(i?'inet':'closed'));});
  const signals=$('#top').querySelectorAll(':scope > .chip');
  signals.forEach((b,i)=>{clean(b);b.insertAdjacentHTML('afterbegin',iconSvg(i?'repo':'ai'));});
}

function renderSide() {
  const r = ME.user.role;
  const show = k => k === 'audit' ? ['security', 'corpAdmin'].includes(r) : k === 'dash' ? r !== 'user' : true;
  $('#side').innerHTML = NAV.filter(n => show(n[0])).map(([k, ic, t]) =>
    `<a href="#" class="${VIEW === k || (VIEW === 'ws' && k === 'new') ? 'on' : ''}" onclick="go('${k}');return false"><span class="ic">${iconSvg(k)}</span>${t}${k === 'approve' && ME.pending ? `<span class="badge">${ME.pending}</span>` : ''}</a>`).join('')
    + `<div class="grow"></div><div class="sec">이 PC에서만 · localhost</div><div class="small muted" style="padding:0 12px">가상 조직 · 가상 데이터</div>`;
}

// 기본 go() 를 감싸 #main 에 현재 화면 이름을 남긴다(테마 CSS가 화면별로 쓴다)
const _baseGo = go;
go = function (v) { _baseGo(v); $('#main').dataset.view = v; };
