// AI 선택 — Claude Code CLI ↔ NVIDIA API · OpenRouter(DeepSeek 등) ↔ 사내 LLM(BizCoder · Ollama) ↔ 규칙 기반. 이 PC 설정이며 다음 요청부터 적용된다.
function aiChipText() {
  const a = ME.ai;
  if (!a.connected) return '⚙️ 규칙 기반 보조 모드' + (a.detail ? ' — ' + esc(a.detail) : '');
  if (ME.net === 'internet') return '🤖 ' + esc(a.model) + ' · 마스킹';
  if (a.internal) return '🤖 사내 LLM · ' + esc(a.model);
  return '🤖 사내 LLM 자리 (시연: ' + esc(a.model) + ')' + (a.external ? ' · 마스킹' : '');
}
let AI = null;
async function aiModal() {
  const d = await api('/api/ai'); AI = d.ai;
  const row = p => `<label class="out-f row" style="cursor:pointer;align-items:flex-start;${p.kind === AI.kind ? 'border-color:var(--o);background:var(--op)' : ''}">
      <input type="radio" name="aiK" value="${p.kind}" ${p.kind === AI.kind ? 'checked' : ''} style="margin-top:4px">
      <div class="grow"><b>${esc(p.name)}</b> <span class="chip ${p.ready ? 'ok' : 'bad'}">${p.ready ? '준비됨' : '준비 안 됨'}</span>
        ${p.models ? `<select class="in" id="aiModel_${p.kind}" style="width:auto;margin-left:6px;padding:3px 8px">${p.models.map(m => `<option value="${esc(m)}" ${m === p.model ? 'selected' : ''}>${esc(m)}${m.endsWith(':free') ? ' (무료)' : p.kind === 'nvidia' ? ' (무료 체험)' : ''}</option>`).join('')}</select>` : p.model ? `<span class="small muted">· ${esc(p.model)}</span>` : ''}
        <br><span class="small muted">${esc(p.note || '')}${p.detail ? ' · ' + esc(p.detail) : ''}</span></div></label>${p.ollama ? olSettings(p) : ''}`;
  modal('🤖 AI 선택 <span class="small muted">이 PC 설정 · 다음 요청부터 적용</span>', `
    <p class="small muted" style="margin-bottom:10px">AI 호출은 한 곳(어댑터)에 모여 있어, 제공자만 바꾸면 같은 화면·같은 스킬로 문서를 만듭니다. 사내 폐쇄망에서는 사내 GPU에 올린 오픈 모델을 같은 방식으로 연결합니다.</p>
    ${AI.providers.map(row).join('')}
    <div class="row wrap" style="margin-top:12px"><button class="btn o" onclick="aiApply()">적용</button><button class="btn ghost" onclick="aiPing()">연결 시험</button>
      <span class="small muted" id="aiMsg">${aiUsage(d.usage)}</span></div>`);
  olLoad(true);
}
function aiUsage(u) { return u && u.calls ? `외부 API 이번 실행 ${u.calls}회 · $${u.cost_usd}` : ''; }
async function aiApply(quiet) {
  const kind = document.querySelector('input[name=aiK]:checked')?.value; if (!kind) return null;
  if (kind === 'ollama') await api('/api/ai/ollama', {body: olForm()});
  const d = await api('/api/ai', {body: {kind, model: $('#aiModel_' + kind)?.value || ''}});
  await refreshMe();
  if (!quiet) { closeModal(); toast(d.ai.connected ? `AI를 ${d.ai.display}(으)로 바꿨습니다` : `${d.ai.display} — 준비가 안 돼 규칙 기반으로 동작합니다`, !d.ai.connected); }
  return d.ai;
}
async function aiPing() {
  await aiApply(true); const m = $('#aiMsg'); if (m) m.textContent = '연결 시험 중…';
  const d = await api('/api/ai/ping', {body: {}});
  if (m) m.textContent = d.ping.ok ? `✅ ${d.ping.model} 응답 ${(d.ping.ms / 1000).toFixed(1)}초` + (d.usage.calls ? ' · ' + aiUsage(d.usage) : '') : `❌ ${d.ping.error}`;
}
