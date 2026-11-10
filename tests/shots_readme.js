// README용 화면 그림 찍기 (읽기 위주: 기존 문서·스킬·작업을 열어 보기만 한다)
// PLAYWRIGHT_CORE=<playwright-core 경로> node tests/shots_readme.js <출력 폴더>   (앱이 localhost:8810에서 실행 중, 시연 1회 뒤)
const path = require('path'), fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_CORE || 'playwright-core');
const OUT = path.resolve(process.argv[2] || 'docs/images');
const BASE = process.env.BASE || 'http://localhost:8810';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1.25, locale: 'ko-KR' });
  const page = await ctx.newPage();
  const shot = async name => { await page.waitForTimeout(700); await page.screenshot({ path: path.join(OUT, name + '.png'), animations: 'disabled' }); console.log('shot', name); };
  const as = async uid => { await page.evaluate(async u => { await api('/api/login', { body: { uid: u } }); ME = await api('/api/me'); renderTop(); renderSide(); }, uid); };
  const go = async v => { await page.evaluate(x => go(x), v); await page.waitForTimeout(1500); };
  const close = async () => { await page.evaluate(() => closeModal()); await page.waitForTimeout(300); };

  await page.goto(BASE); await page.waitForSelector('.persona'); await shot('01-login');
  await page.click('.persona:has-text("홍길동")', { force: true }); await page.waitForSelector('#side a'); await page.waitForTimeout(1500);
  await shot('02-home');

  const docs = await page.evaluate(async () => (await api('/api/docs')).docs.map(d => ({ id: d.id, fmts: [...new Set(d.files.map(f => f.fmt))], ver: d.ver })));
  const hwp = docs.find(d => d.fmts.includes('hwp')), deck = docs.find(d => d.fmts.includes('ppt'));
  if (hwp) {
    await page.evaluate(async id => { await editDoc(id); LASTDOC = (await api('/api/docs/' + id)).doc; }, hwp.id);
    await page.waitForSelector('#outp'); await page.evaluate(() => renderOut()); await shot('03-workspace');
    await page.evaluate(([id, v]) => preview(id, 'hwp', v), [hwp.id, hwp.ver]); await page.waitForSelector('.rh-page svg, .hwpl-page', { timeout: 60000 }); await shot('04-hwp');
    await close();
  }
  if (deck) {
    await page.evaluate(([id, v]) => preview(id, 'ppt', v), [deck.id, deck.ver]); await page.waitForSelector('.shots img'); await page.waitForTimeout(1200); await shot('05-ppt');
    await close();
    await page.evaluate(([id, v]) => preview(id, 'web', v), [deck.id, deck.ver]); await page.waitForSelector('#mb iframe'); await page.waitForTimeout(4500); await shot('06-web');
    await close();
  }

  // 검수: 원본 메모 ↔ 사람이 고친 PPT
  await page.evaluate(async () => {
    IN = { src: [], tgt: [], doc: '', tpl: '', text: '', last: null, prev: null }; go('inspect');
    IN.src = (await api('/api/demo/attach', { body: { names: ['시연메모_고객세미나.txt'] } })).uploads;
    IN.tgt = (await api('/api/demo/attach', { body: { names: ['검수시연_사람이고친PPT_예산오류.pptx'] } })).uploads;
    await vInspect(); await runInspect(); document.querySelector('#inRes').scrollIntoView({ block: 'start' });
  });
  await shot('07-inspect');

  // 스킬 만들기: 가장 최근 작업을 불러와 분석·초안·검증 리포트
  const job = await page.evaluate(async () => ((await api('/api/skillgen/jobs')).jobs[0] || {}).id);
  if (job) {
    await go('register'); await page.evaluate(id => sbResume(id), job); await page.waitForSelector('#sbEval .kpis');
    await page.evaluate(() => window.scrollTo(0, 0)); await shot('08-builder');
    await page.evaluate(() => document.querySelector('#sbEval').scrollIntoView({ block: 'start' })); await shot('09-report');
  }

  // 스킬 · 승인함 (팀장)
  await as('u2'); await go('skills'); await shot('10-skills');
  await page.evaluate(() => openSkill('sales-pack')); await page.waitForSelector('.inh'); await shot('11-skill-detail'); await close();
  await go('approve'); await page.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => x.innerText.includes('전체 스킬 요청')); if (h) h.scrollIntoView({ block: 'start' }); }); await shot('12-approve');
  await as('u1'); await go('demo'); await shot('13-demo');
  await ctx.close(); await browser.close();
})().catch(e => { console.error('FAIL', e); process.exit(1); });
