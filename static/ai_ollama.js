// AI 선택 창의 Ollama 설정 — 서버 주소 · API 키 · 모델(이 PC 설정). [적용]·[연결 시험]을 누르면 저장한다(ai_select.js 의 aiApply).
// API 키는 서버(이 PC의 코쇠오피스 데이터)에만 두고, 화면에는 있는지와 끝 4자리만 온다.
function olSettings(p) {
  const o = p.ollama;
  return `<div class="ol-set" onfocusin="document.querySelector('input[name=aiK][value=ollama]').checked = true">
    <label><span>Ollama 서버 주소 <span class="muted">(사내 Ollama · ollama.com API — 예: https://llm.사내.kr, 로컬은 http://localhost:11434)</span></span>
      <input class="in" id="ol-url" value="${esc(o.url)}"></label>
    <label><span>API 키 <span class="muted">(인증이 걸린 서버만 — 로컬 Ollama는 비워 둠)</span></span>
      <span class="row"><input class="in grow" id="ol-key" type="password" autocomplete="off" placeholder="${o.has_key ? `저장됨 (${esc(o.key_hint)}) — 바꿀 때만 입력` : '키 없음'}"><button class="btn ghost sm" onclick="olLoad(); return false">모델 불러오기</button></span></label>
    ${o.has_key ? '<label class="chk"><input type="checkbox" id="ol-key-clear"> 저장된 키 지우기</label>' : ''}
    <label>Ollama 모델 <select class="in" id="ol-model"><option value="${esc(o.model)}">${esc(o.model || '— 모델 불러오기를 누르세요 —')}</option></select></label>
    <div class="small muted" id="ol-st"></div>
    <div class="small muted">API 키는 이 PC의 코쇠오피스 데이터에만 저장되고, 화면에는 끝 4자리만 보입니다. 서버 주소가 바뀌면 새로 넣어야 합니다. 키를 쓰면 https 주소를 권장합니다.</div>
  </div>`;
}
const olForm = () => ({url: $('#ol-url').value.trim(), model: $('#ol-model').value, key: $('#ol-key').value.trim(), key_clear: !!$('#ol-key-clear')?.checked});
async function olLoad(quiet) {      // 입력한 서버의 모델을 고르기 칸에 채운다(클라우드 모델은 따로 묶어 표시)
  const st = $('#ol-st'), sel = $('#ol-model'); if (!sel) return;
  const cur = sel.value;
  st.textContent = '모델 목록을 불러오는 중…';
  try {
    const f = olForm();
    const d = await api('/api/ai/ollama/models', {body: {url: f.url, key: f.key, key_clear: f.key_clear}, quiet: true});
    const opt = m => `<option value="${esc(m.name)}" ${m.name === cur ? 'selected' : ''}>${esc(m.name)}</option>`;
    const loc = d.models.filter(m => !m.cloud), cl = d.models.filter(m => m.cloud);
    sel.innerHTML = (cur && !d.models.some(m => m.name === cur) ? `<option value="${esc(cur)}" selected>${esc(cur)} (서버에 없음)</option>` : '')
      + loc.map(opt).join('') + (cl.length ? `<optgroup label="☁ 클라우드 — 요청이 PC 밖(ollama.com)으로 나가 가림 처리합니다">${cl.map(opt).join('')}</optgroup>` : '');
    st.textContent = `연결됨 · 글쓰기 모델 ${loc.length}개${cl.length ? ` · 클라우드 ${cl.length}개` : ''}`;
  } catch (e) { st.textContent = '⚠ ' + e.message; if (!quiet) toast(e.message, true); }
}
