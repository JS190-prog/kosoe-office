// 코쇠오피스 3분 시연 자동 진행 + 녹화 (2차 리허설)
// node tests/record_demo.js <출력폴더>   (PLAYWRIGHT_CORE=playwright-core 경로, 앱이 localhost:8810에서 실행 중)
// 결과: <출력폴더>/raw.webm, marks.json(장면·대기 구간 시각)
const path = require('path'), fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_CORE || 'playwright-core');
const OUT = path.resolve(process.argv[2] || 'record_out');
const BASE = process.env.BASE || 'http://localhost:8810';
const W = 1366, H = 768;
fs.mkdirSync(OUT, { recursive: true });

const CAP = `
window.__cap = (scene, text, sub) => {
  let b = document.getElementById('__capbar');
  if (!b) {
    b = document.createElement('div'); b.id = '__capbar';
    b.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:99999;pointer-events:none;max-width:1100px;' +
      'background:rgba(16,24,44,.88);color:#fff;border-radius:14px;padding:12px 22px;font-family:KoPub,"Malgun Gothic",sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.35);text-align:center';
    document.body.appendChild(b);
  }
  b.innerHTML = (scene ? '<span style="background:#ee6d1d;border-radius:6px;padding:2px 9px;margin-right:10px;font-weight:700;font-size:15px">' + scene + '</span>' : '') +
    '<b style="font-size:19px">' + text + '</b>' + (sub ? '<div style="font-size:14.5px;opacity:.85;margin-top:4px">' + sub + '</div>' : '');
  b.style.display = text ? 'block' : 'none';
};`;

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, locale: 'ko-KR' });
  await ctx.addInitScript(CAP);
  const page = await ctx.newPage();
  const t0 = Date.now();
  const marks = []; const timings = {};
  // 화면 녹화: 브라우저 스크린캐스트(CDP) 프레임을 시각과 함께 저장 → 시스템 ffmpeg로 조립
  // 프레임을 파일 하나에 이어 쓴다(파일 수천 개를 만들면 백신 검사로 PC 전체가 느려짐)
  const BIN = path.join(OUT, 'frames.bin'); const fd = fs.openSync(BIN, 'w');
  const frames = []; let off = 0;
  const cdp = await ctx.newCDPSession(page);
  cdp.on('Page.screencastFrame', f => {
    const buf = Buffer.from(f.data, 'base64');
    fs.writeSync(fd, buf); frames.push({ o: off, n: buf.length, t: (Date.now() - t0) / 1000 }); off += buf.length;
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  const saveIndex = () => { fs.writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify({ marks, timings, size: [W, H] }, null, 1)); fs.writeFileSync(path.join(OUT, 'frames.json'), JSON.stringify(frames)); };
  process.on('exit', () => { try { saveIndex(); } catch (e) {} });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 80, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  const now = () => (Date.now() - t0) / 1000;
  const mark = (type, label, extra = {}) => { marks.push({ t: now(), type, label, ...extra }); console.log(`[${now().toFixed(1)}] ${type} ${label}`); };
  const cap = (scene, text, sub) => page.evaluate(([a, b, c]) => window.__cap && window.__cap(a, b, c), [scene, text, sub || '']);
  const pause = ms => page.waitForTimeout(ms);
  const click = async (sel, opt) => {
    const l = page.locator(sel).first();
    await l.waitFor({ state: 'visible', timeout: 30000 });
    await l.evaluate(e => e.scrollIntoView({ block: 'center' })).catch(() => {});
    try { await l.click({ timeout: 4000, ...opt }); } catch (e) { await l.click({ force: true, ...opt }); }   // 움직이는 장식이 있으면 강제 클릭
  };
  // 처리 대기: 앞뒤 구간을 기록해 편집에서 빨리 감는다
  const waitBusy = async (label, max = 240000) => {
    const s = now(); mark('wait-start', label);
    await page.waitForSelector('.busy', { state: 'attached', timeout: 3000 }).catch(() => {});
    await page.waitForSelector('.busy', { state: 'detached', timeout: max });
    const sec = now() - s; mark('wait-end', label, { sec }); return sec;
  };
  const login = async name => {
    if (await page.locator('#login').isHidden()) { await click('button[onclick="logout()"]'); await page.waitForSelector('#login .persona', { state: 'visible' }); await pause(800); }
    await click(`.persona:has-text("${name}")`); await page.waitForSelector('#side a'); await pause(900);
  };
  const nav = async v => { await click(`#side a[onclick^="go('${v}')"]`); await pause(1100); };
  const demoFiles = async (btnSel, want) => {
    await click(btnSel); await page.waitForSelector('#dpGo');
    for (const cb of await page.locator('#mb input[type=checkbox]').all()) {
      const v = await cb.getAttribute('value'); const on = want.includes(v);
      if ((await cb.isChecked()) !== on) await cb.click({ force: true });
    }
    await pause(700); await click('#dpGo'); await page.waitForSelector('#dpGo', { state: 'detached' }); await pause(900);
  };
  const closeModal = async () => { await page.evaluate(() => closeModal()); await pause(400); };

  await page.goto(BASE); await page.waitForSelector('.persona');
  await cap('', '코쇠오피스 — 3분 시연 (2차 리허설)', '각자 PC에서 실행 · AI는 각자의 Claude Code 구독 CLI · 전사 공용 스킬을 상속한 부서·개인 스킬 · 스킬은 Git 저장소에서 관리');
  mark('scene', 'intro'); await pause(4500);

  // 0:00 입력과 문제
  mark('scene', '0:00');
  await login('홍길동');
  await cap('0:00', '메모 한 장에서 출발합니다', '시연 자료(가상) 고객 세미나 메모를 붙이고, 무엇을 만들지 한 줄로 적습니다');
  await demoFiles('button:has-text("📂 시연 자료")', ['시연메모_고객세미나.txt']);
  await page.evaluate(() => document.querySelector('#req').focus());
  await page.keyboard.type('11월 고객 세미나 준비 계획을 팀장님께 올릴 요약보고로 만들어줘. 메모의 예산·인원·일정은 그대로.', { delay: 18 });
  await pause(1200);

  // 0:20 한글 제작
  mark('scene', '0:20');
  await cap('0:20', '기획 팩 → 회사 양식의 한글 요약보고', '경영기획팀 기획 팩(전사 한글 스킬 상속): 결론 먼저 · 효과 수치의 근거 성격 표시');
  await click('[id="t-planning-pack:summary-report"]'); await pause(900);
  await click('#go');
  timings.draft_hwp = await waitBusy('초안(구독 CLI)');
  await cap('0:20', `설계도 초안 — ${timings.draft_hwp.toFixed(0)}초`, '장 구성·고정 문구·작성 규칙이 스킬에서 왔습니다. 설계도에서 바로 고칠 수 있습니다');
  await pause(3500);
  await click('button:has-text("문서 만들기")');
  timings.gen_hwp = await waitBusy('한글 생성');
  await cap('0:20', `한글(.hwp) 완성 — ${timings.gen_hwp.toFixed(0)}초`, '전사 스킬 koscom-hwp-report(커밋 고정)로 조판 · 보고 문법·팩 규칙·원본값 대조 검수 통과');
  await page.evaluate(s => document.querySelector(s)?.scrollIntoView({ block: 'start' }), '#res'); await pause(2500);
  await click('#res button:has-text("미리보기")'); await page.waitForSelector('.hwpv'); await pause(4000); await closeModal();

  // 0:50 PPT·웹 제작
  mark('scene', '0:50');
  await nav('new');
  await cap('0:50', '같은 메모 → 영업 팩으로 PPT · 웹슬라이드', '영업 팩(팀) ← 금융영업본부 공통 팩 ← 전사 공용 스킬: 회사 소개·서비스 소개·유의 문구가 고정');
  await demoFiles('button:has-text("📂 시연 자료")', ['시연메모_고객세미나.txt']);
  await page.evaluate(() => document.querySelector('#req').focus());
  await page.keyboard.type('세미나 참석 고객사에 보낼 원장 클라우드 제안서. 세미나 뒤 PoC 제안으로 연결.', { delay: 18 });
  await click('[id="t-sales-pack:proposal"]'); await pause(700);
  await click('#go');
  timings.draft_ppt = await waitBusy('초안(구독 CLI)');
  await page.evaluate(() => document.querySelectorAll('.fmtpick input').forEach(i => { i.checked = ['ppt', 'web'].includes(i.value); }));
  await pause(800);
  await click('button:has-text("문서 만들기")');
  timings.gen_ppt_web = await waitBusy('PPT·웹 생성');
  await cap('0:50', `PPT · 웹슬라이드 완성 — ${timings.gen_ppt_web.toFixed(0)}초`, 'PPT: 전사 ppt-master(Koscom 셰브론) · 웹: 전사 koscom-webslide — 둘 다 편집 가능');
  await page.evaluate(s => document.querySelector(s)?.scrollIntoView({ block: 'start' }), '#res'); await pause(1500);
  await page.evaluate(() => preview(LASTDOC.id, 'web', LASTDOC.ver));
  await page.waitForSelector('#mb iframe').catch(() => {});
  if (await page.locator('#mb iframe').count()) {
    await pause(3500);
    const fr = page.frameLocator('#mb iframe');
    for (let i = 0; i < 4; i++) { await fr.locator('body').press('ArrowRight').catch(() => {}); await pause(1600); }
    await closeModal();
  }
  // PPT 그림(PowerPoint로 렌더)
  await cap('0:50', 'PPT 장표 그림을 PowerPoint로 렌더링하는 중', '');
  mark('wait-start', 'PPT 미리보기 그림');
  const pptReady = await page.evaluate(async () => { for (let i = 0; i < 25; i++) { const d = await api(`/api/docs/${LASTDOC.id}`, {quiet: true}); const f = d.doc.files.find(x => x.fmt === 'ppt' && x.ver === d.doc.ver); if (f && f.shots.length) return true; await new Promise(r => setTimeout(r, 1500)); } return false; });
  mark('wait-end', 'PPT 미리보기 그림');
  if (pptReady) { await cap('0:50', 'PPT 장표 — 전사 셰브론 디자인 그대로, 도형·글자 단위로 편집 가능', '');
    await page.evaluate(() => preview(LASTDOC.id, 'ppt', LASTDOC.ver)); await page.waitForSelector('.shots img'); await pause(1200);
    await page.evaluate(() => document.querySelector('.shots').scrollBy(0, 400)); await pause(2500); await closeModal(); }

  // 1:20 팩 변경 반영
  mark('scene', '1:20');
  await login('김철수');
  await cap('1:20', '팀장이 영업 팩의 서비스 소개 문구를 고칩니다', '스킬 화면 → 영업 팩 → 고정 문구 수정 → 변경 요청 = Git 브랜치 + PR');
  await nav('skills'); await click(`tr[onclick="openSkill('sales-pack')"]`); await page.waitForSelector('#skEd'); await pause(2500);
  await page.evaluate(() => document.querySelector('#skEd').scrollIntoView({ block: 'center' })); await pause(800);
  const idx = await page.evaluate(() => SK.blocks.findIndex(b => b.id === 'service-intro'));
  const ta = page.locator('#skEd textarea').nth(idx);
  await ta.focus(); await ta.press('End'); await ta.press('Control+A');
  await page.keyboard.type('코쇠 원장 클라우드는 원장·시세·주문을 하나의 클라우드로 운영하고 장애 대응을 30분 안에 마치는 서비스임(가상)', { delay: 12 });
  await page.locator('#skNote').fill('서비스 소개에 장애 대응 시간 명시'); await pause(900);
  await click('button:has-text("변경 요청 (브랜치 · PR)")');
  timings.pr_change = await waitBusy('PR 생성');
  const req = await page.evaluate(async () => (await api('/api/requests')).requests[0]);
  await cap('1:20', `PR #${req.pr_number} 생성 (v${req.note.version}) — ${timings.pr_change.toFixed(0)}초`, '승인함: 승인하면 PR 병합 + 버전 태그. 승인 기록은 PR 코멘트로 남습니다');
  await pause(2500);
  await page.locator('input[id^="n-"]').first().fill('서비스 소개 문구 승인');
  await click('button:has-text("승인 → 병합·태그")');
  timings.pr_merge = await waitBusy('병합·태그');
  await cap('1:20', `병합 · 태그 sales-pack@v${req.note.version} — ${timings.pr_merge.toFixed(0)}초`, '승인된 기준은 다음 문서부터 반영됩니다. 이미 만든 문서는 당시 버전을 기록해 둡니다');
  await pause(2500);
  await login('홍길동'); await nav('docs');
  await click('tr.click:has-text("제안서")'); await page.waitForSelector('#mb'); await pause(1200);
  await cap('1:20', '내 문서에 새 기준 알림', `이 문서는 이전 버전 기준 → 「새 기준으로 다시 만들기」 한 번이면 v${req.note.version} 문구로`);
  await pause(3000);
  await click('button:has-text("새 기준으로 다시 만들기")');
  timings.regen = await waitBusy('새 기준으로 다시 만들기');
  await cap('1:20', `새 버전 완성 — ${timings.regen.toFixed(0)}초`, '파일마다 쓴 스킬 버전이 남습니다: sales-common@1.0.0 ← sales-pack@' + req.note.version);
  await pause(2500); await closeModal();

  // 1:50 검수·재검사
  mark('scene', '1:50');
  await nav('inspect');
  await cap('1:50', '사람이 고친 파일의 수정 누락을 찾습니다', '원본 메모 ↔ 사람이 고친 PPT 값 대조 (가상 사례: 예산을 고치다 잘못 바꿈)');
  await demoFiles('button:has-text("📂 시연 메모")', ['시연메모_고객세미나.txt']);
  await demoFiles('button:has-text("📂 시연 자료(사람이 고친 PPT)")', ['검수시연_사람이고친PPT_예산오류.pptx']);
  await click('button:has-text("🔍 검사")'); await page.waitForSelector('#inRes table'); await pause(800);
  await page.evaluate(s => document.querySelector(s)?.scrollIntoView({ block: 'start' }), '#inRes');
  await cap('1:50', '불일치: 예산 원본 120만원 ≠ PPT 100만원', '파일에서 읽은 값으로 판정 · 읽지 못하면 「판정 불가」로 남깁니다');
  await pause(4000);
  await page.evaluate(() => window.scrollTo(0, 0)); await pause(500);
  await click('.out-f .x');
  await demoFiles('button:has-text("📂 시연 자료(사람이 고친 PPT)")', ['검수시연_사람이고친PPT_수정본.pptx']);
  await click('button:has-text("🔍 검사")'); await pause(1200);
  await page.evaluate(s => document.querySelector(s)?.scrollIntoView({ block: 'start' }), '#inRes');
  await cap('1:50', '고쳐서 다시 올리면 재검사 — 불일치 1 → 0', '');
  await pause(3500);

  // 2:15 팩 스킬 생성
  mark('scene', '2:15');
  await nav('register');
  await cap('2:15', '★ 대표 문서 3건 + "영업팀 제안서 팩 만들어줘"', '분석·검증은 시연 전에 미리 실행해 두었습니다(실측: 분석 약 20초 · 검증 약 80초) — 이어서 진행합니다');
  await pause(2500);
  await page.waitForSelector('#sbJobs button'); await click('#sbJobs button'); await page.waitForSelector('#sbEval .kpis'); await pause(1200);
  await page.evaluate(s => document.querySelector(s)?.scrollIntoView({ block: 'start' }), '#sbAna');
  await cap('2:15', '② 분석 — 공통 목차·고정 문구·바뀌는 칸', '상속할 상위 스킬을 찾았습니다: 영업 팩(팀) ← 본부 공통 팩 ← 전사 공용 스킬');
  await pause(4000);
  await page.evaluate(s => document.querySelector(s)?.scrollIntoView({ block: 'start' }), '#sbDraft');
  await cap('2:15', '③ 상속 기반 스킬 초안 — kosoe-skill.yaml', 'extends: skill:sales-pack · 구성 · 고정 문구(글자 그대로) · 작성 규칙');
  await pause(4000);
  await page.evaluate(s => document.querySelector(s)?.scrollIntoView({ block: 'start' }), '#sbEval');
  await cap('2:15', '④ 충분한 검증 — 7기준 자동 채점', '같은 과제를 스킬 사용 / 미사용으로 작성해 비교 · 모두 통과해야 등록 버튼이 열립니다');
  await pause(4500);
  await click('button:has-text("시범 1")'); await pause(900);
  await click('button:has-text("⑤ 등록 요청")');
  timings.skill_submit = await waitBusy('스킬 등록(PR·자동 검사·병합)', 300000);
  await cap('2:15', `⑤ 등록 완료 — 개인 스킬 PR · 자동 검사 · 병합 · 태그 (${timings.skill_submit.toFixed(0)}초)`, '부서 스킬로 올리면 관리자 승인 단계가 추가됩니다');
  await pause(2500);
  await nav('new'); await page.evaluate(() => document.querySelector('.tgrid').scrollIntoView()); await pause(1000);
  await cap('2:15', '바로 쓸 수 있는 「나의 스킬」 양식', '상속: 나의 스킬 ← 영업 팩 ← 본부 공통 팩 ← 전사');
  await pause(3500);

  // 2:40 운영 검증
  mark('scene', '2:40');
  await login('박지원'); await nav('skills');
  await cap('2:40', '전사 공용 스킬 4종 — 커밋 단위로 고정', '잠금 항목(CI 색·글꼴·로고·등급 표기·한글 기본 양식)은 하위 스킬이 바꿀 수 없습니다');
  await pause(3500);
  await click(`tr[onclick="openSkill('sales-pack')"]`); await page.waitForSelector('.inh'); await pause(1000);
  await cap('2:40', '상속 사슬과 고정 문구의 출처', '본선은 구독 CLI(상용 AI) · 사내 GPU·Bedrock은 설정 한 줄 — 품질·권한은 승인된 환경에서 검증');
  await pause(4000); await closeModal();

  // 2:50 마무리
  mark('scene', '2:50');
  await login('홍길동'); await nav('docs');
  await cap('2:50', '세 형식 · 버전 · 검수 내역', 'PPT · 웹슬라이드 · 한글 — 만들고, 고치고, 검수까지');
  await pause(3000);
  await nav('dash'); await pause(1000);
  await cap('', '코쇠오피스', '회사 양식대로 만들고 고치고 검수까지 · 대표 문서 몇 건이면 우리 부서 스킬 · 정본은 Git');
  await pause(4000);
  mark('end', 'end');

  await cdp.send('Page.stopScreencast').catch(() => {});
  await pause(300);
  saveIndex(); fs.closeSync(fd);
  await ctx.close(); await browser.close();
  console.log('OK frames', frames.length, JSON.stringify(timings));
})().catch(e => { console.error('FAIL', e); process.exit(1); });
