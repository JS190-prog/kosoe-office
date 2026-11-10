"""AI 어댑터 한 곳 — 기본은 각 사용자의 Claude Code 구독 CLI. Claude API·OpenAI 호환(사내 모델) 설정도 받는다. 실패하면 규칙 기반으로 대체한다.

모든 함수는 (결과, 메타)를 돌려준다. 메타 = {'mode': 'llm'|'rule', 'model', 'label', 'ms', 'masked', 'error'}
ctx = {'use_llm': bool, 'label': 화면 표시용 모델 이름, 'mk': Masker | None(인터넷망에서만), 'fast': 빠른 모델 사용}
"""
import glob
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

from core import CFG, DATA

WRITING_RULES = """코스콤 보고 문법을 지킨다.
- 한 항목은 90자(한글 보고서 3줄) 이내, 명사형 종결(~함, ~임, ~ 추진, ~ 예정). '~합니다/~다.'로 끝내지 않는다.
- 항목 앞 라벨은 2~6자(예: 기간, 대상, 현황). 없으면 빈 문자열.
- 숫자·고유명사·날짜는 사용자 요청과 첨부 자료에 있는 것만 쓴다. 없는 사실은 지어내지 말고 '(확인 필요)'로 둔다.
- [고객사명1] 같은 대괄호 토큰은 가려 둔 값이다. 그대로 옮겨 쓴다.
- 날짜는 '2026. 10. 28' 형식.
- 장마다 항목 2~4개. 하위 설명이 필요하면 children에 1~2개."""

BP_SCHEMA = '{"title": str, "sections": [{"heading": str, "items": [{"label": str, "text": str, "children": [{"text": str}]}], "table": {"cols": [str], "rows": [[str]]} | null}]}'

MASK_RX = {
    '주민등록번호': re.compile(r'\d{6}-[1-4]\d{6}'),
    '휴대전화번호': re.compile(r'01[016-9]-?\d{3,4}-?\d{4}'),
    '계좌번호': re.compile(r'(?<!\d)\d{3,6}-\d{2,6}-\d{2,8}(?!\d)'),
    '고객사명': re.compile(r'(?<![가-힣A-Za-z])[A-Z가-힣][A-Za-z가-힣]{0,9}?(?:저축은행|증권|은행|생명|화재|캐피탈|자산운용|카드)(?![가-힣])'),
}


class Masker:
    """인터넷망에서 외부 AI로 보내기 전 민감 정보를 [종류N] 토큰으로 바꾸고, 응답에서 되돌린다."""

    def __init__(self, kinds):
        self.kinds = [k for k in kinds if k in MASK_RX]
        self.map = {}

    def mask(self, text):
        if not text:
            return text
        for k in self.kinds:
            def sub(m, k=k):
                v = m.group(0)
                for tok, orig in self.map.items():
                    if orig == v:
                        return tok
                tok = f'[{k}{sum(1 for t in self.map if t.startswith("[" + k)) + 1}]'
                self.map[tok] = v
                return tok
            text = MASK_RX[k].sub(sub, text)
        return text

    def unmask(self, obj):
        s = json.dumps(obj, ensure_ascii=False)
        for tok, orig in self.map.items():
            s = s.replace(tok, orig)
        return json.loads(s)


def _ctx():
    # 사내 프록시 인증서가 Python 3.13의 엄격 검사(VERIFY_X509_STRICT)에 걸린다. 체인·호스트 검증은 그대로 둔다.
    c = ssl.create_default_context()
    c.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return c


# ───────────── Claude Code CLI(구독제) ─────────────
# API 키 없이, 이 PC에 로그인된 Claude 구독으로 `claude -p`를 호출한다.
# 도구·MCP·설정 파일·세션 기록을 모두 끄고, 빈 작업 폴더에서 돌려 순수한 '모델 호출'로만 쓴다.
CLI_DIR = os.path.join(DATA, 'llm-cli')
os.makedirs(CLI_DIR, exist_ok=True)
# 데스크톱 앱이 띄운 프로세스에서 물려받으면 앱 내부 인증·프록시로 붙으려다 실패하는 변수들
CLI_ENV_DROP = ('CLAUDECODE', 'ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_SCOPES',
                'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SSE_PORT')
_cli_cache = {'t': 0, 'v': None}


def _cli_version(exe):
    try:
        out = subprocess.run([exe, '--version'], capture_output=True, timeout=20, env=_cli_env()).stdout.decode('utf-8', 'replace')
        m = re.search(r'(\d+)\.(\d+)\.(\d+)', out)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
    except Exception:
        return (0, 0, 0)


_cli_found = {}


def cli_path():
    """KOSOE_CLAUDE_CLI → 데스크톱 앱에 들어 있는 최신 CLI(Windows·macOS) → PATH의 claude(2.x 이상).
    1.0.x 전역 npm claude는 응답이 멈추는 사례가 있어 2.x 이상만 쓴다."""
    if CFG.get('claude_cli'):
        return CFG['claude_cli']
    if 'p' in _cli_found:
        return _cli_found['p']
    bases = [os.path.join(os.environ.get('APPDATA', ''), 'Claude', 'claude-code'),                              # Windows 데스크톱 앱
             os.path.expanduser('~/Library/Application Support/Claude/claude-code')]                          # macOS 데스크톱 앱
    found = []
    for base in bases:
        for name in ('claude.exe', 'claude'):
            for p in glob.glob(os.path.join(base, '*', '*', name)) + glob.glob(os.path.join(base, '*', name)):
                ver = next((part for part in p.replace('\\', '/').split('/') if re.fullmatch(r'\d+\.\d+\.\d+', part)), '')
                if ver and os.access(p, os.X_OK):
                    found.append((tuple(int(x) for x in ver.split('.')), p))
    if found:
        _cli_found['p'] = max(found)[1]
        return _cli_found['p']
    cands = [shutil.which('claude'), os.path.expanduser('~/.local/bin/claude'), os.path.expanduser('~/.claude/local/claude'),
             '/opt/homebrew/bin/claude', '/usr/local/bin/claude']
    for c in cands:
        if c and os.path.exists(c) and _cli_version(c) >= (2, 0, 0):
            _cli_found['p'] = c
            return c
    _cli_found['p'] = ''
    return ''


def _cli_env():
    env = {k: v for k, v in os.environ.items() if k not in CLI_ENV_DROP}
    if CFG.get('claude_token'):   # `claude setup-token`으로 만든 장기 토큰(선택)
        env['CLAUDE_CODE_OAUTH_TOKEN'] = CFG['claude_token']
    return env


def cli_status(force=False):
    """로그인 상태(60초 캐시) → {'ready', 'path', 'detail'}"""
    if not force and time.time() - _cli_cache['t'] < 60 and _cli_cache['v']:
        return _cli_cache['v']
    exe = cli_path()
    v = {'ready': False, 'path': exe, 'detail': ''}
    if not exe:
        v['detail'] = 'Claude CLI를 찾지 못했습니다 (.env의 KOSOE_CLAUDE_CLI에 경로 지정)'
    else:
        try:
            r = subprocess.run([exe, 'auth', 'status'], capture_output=True, timeout=30, env=_cli_env(), cwd=CLI_DIR)
            st = json.loads(r.stdout.decode('utf-8', 'replace') or '{}')
            v['ready'] = bool(st.get('loggedIn')) or bool(CFG.get('claude_token'))
            v['detail'] = st.get('authMethod', '') if v['ready'] else '로그인 필요: claude auth login'
        except Exception as e:
            v['detail'] = str(e)[:120]
    _cli_cache.update(t=time.time(), v=v)
    return v


def _call_cli(system, user, model=None):
    exe = cli_path()
    if not exe:
        raise RuntimeError('Claude CLI 없음')
    args = [exe, '-p', '--output-format', 'json', '--model', model or CFG['llm_model'], '--system-prompt', system,
            '--tools', '', '--strict-mcp-config', '--setting-sources', '', '--no-session-persistence']
    if CFG.get('llm_effort'):
        args += ['--effort', CFG['llm_effort']]
    r = subprocess.run(args, input=user.encode('utf-8'), capture_output=True, timeout=240, env=_cli_env(), cwd=CLI_DIR)
    out = r.stdout.decode('utf-8', 'replace').strip()
    try:
        d = json.loads(out[out.find('{'):]) if '{' in out else {}
    except json.JSONDecodeError:
        d = {}
    if not d:
        raise RuntimeError('CLI 응답 없음: ' + (r.stderr.decode('utf-8', 'replace') or out)[-200:])
    if d.get('is_error'):
        msg = str(d.get('result') or d.get('subtype'))
        if 'auth' in msg.lower() or 'login' in msg.lower():
            _cli_cache.update(t=0, v=None)
            msg += ' → 터미널에서 claude auth login'
        raise RuntimeError(msg)
    return d.get('result') or ''


# ───────────── BizCoder CLI(사내 LLM) ─────────────
# 회사 계정으로 로그인된 BizCoder(opencode 계열 코딩 에이전트)로 사내 모델(기본 DeepSeek V4 Flash)을 부른다.
# Claude Code·Codex 이어받기(MCP·스킬·지침)·프로젝트 설정·자동 업데이트를 끄고 도구를 모두 막은 채, 빈 작업 폴더에서
# 요청을 표준입력으로 넘겨 순수한 '모델 호출'로만 쓴다 — 첨부 속 글이 도구(명령·파일)를 부르지 못하게.
BIZ_DIR = os.path.join(DATA, 'llm-bizcoder')
os.makedirs(BIZ_DIR, exist_ok=True)
BIZ_ENV = {'OPENCODE_DISABLE_CLAUDE_CODE': '1', 'OPENCODE_DISABLE_CODEX': '1', 'BIZCODER_DISABLE_CLAUDE_CODE': '1',
           'BIZCODER_DISABLE_CODEX': '1', 'OPENCODE_DISABLE_CLAUDE_CODE_PROMPT': '1', 'OPENCODE_DISABLE_CODEX_PROMPT': '1',
           'OPENCODE_DISABLE_CLAUDE_CODE_MEMORY': '1', 'OPENCODE_DISABLE_CODEX_SKILLS': '1', 'OPENCODE_DISABLE_PROJECT_CONFIG': '1',
           'OPENCODE_DISABLE_AUTOUPDATE': '1', 'BIZCODER_DISABLE_WORKFLOWS': '1', 'OPENCODE_PURE': '1',
           'OPENCODE_CONFIG_CONTENT': json.dumps({'tools': {'*': False}})}
_biz = {'p': None, 't': 0, 'v': None, 'm': None, 'mt': 0}


def bizcoder_path():
    """KOSOE_BIZCODER_CLI → npm 전역 bizcoder 패키지 안의 실행 파일(bizcoder-<os>-<arch>) → PATH 의 bizcoder."""
    if CFG.get('bizcoder_cli'):
        return CFG['bizcoder_cli']
    if _biz['p'] is None:
        shim = (shutil.which('bizcoder.cmd') if os.name == 'nt' else None) or shutil.which('bizcoder') or ''
        plat = {'win32': 'windows'}.get(sys.platform, sys.platform)
        arch = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine().lower(), platform.machine().lower())
        exe = os.path.join(os.path.dirname(shim), 'node_modules', 'bizcoder', 'node_modules', f'bizcoder-{plat}-{arch}', 'bin',
                           'bizcoder.exe' if plat == 'windows' else 'bizcoder') if shim else ''
        _biz['p'] = exe if exe and os.path.exists(exe) else shim
    return _biz['p']


def bizcoder_status(force=False):
    """BizCoder 로그인 상태(10분 캐시) → {'ready', 'path', 'detail'}"""
    if not force and _biz['v'] and time.time() - _biz['t'] < 600:
        return _biz['v']
    exe = bizcoder_path()
    v = {'ready': False, 'path': exe, 'detail': ''}
    if not exe:
        v['detail'] = 'BizCoder CLI를 찾지 못했습니다 (npm i -g bizcoder → bizcoder login, 또는 .env의 KOSOE_BIZCODER_CLI)'
    else:
        try:
            r = subprocess.run([exe, 'whoami'], capture_output=True, timeout=60, env={**os.environ, **BIZ_ENV}, cwd=BIZ_DIR)
            out = r.stdout.decode('utf-8', 'replace')
            v['ready'] = r.returncode == 0 and '로그인됨' in out
            v['detail'] = '로그인됨' if v['ready'] else '로그인 필요: 터미널에서 bizcoder login'
        except Exception as e:
            v['detail'] = str(e)[:120]
    _biz.update(t=time.time(), v=v)
    return v


def bizcoder_models():
    """회사 관리자가 내 계정에 허용한 모델(bizcoder models = bizcoder policy 의 「쓸 수 있는 모델」, 10분 캐시)."""
    if _biz['m'] is not None and time.time() - _biz['mt'] < 600:
        return _biz['m']
    exe, ms = bizcoder_path(), []
    if exe:
        try:
            r = subprocess.run([exe, 'models'], capture_output=True, timeout=60, env={**os.environ, **BIZ_ENV}, cwd=BIZ_DIR)
            ms = [l.strip() for l in r.stdout.decode('utf-8', 'replace').splitlines() if l.strip().startswith('bizrouter/')]
        except Exception:
            pass
    _biz.update(m=ms, mt=time.time())
    return ms


def _call_bizcoder(system, user, model=None):
    exe = bizcoder_path()
    if not exe:
        raise RuntimeError('BizCoder CLI 없음')
    r = subprocess.run([exe, 'run', '--pure', '--format', 'json', '-m', model or CFG['bizcoder_model'], '--dir', BIZ_DIR],
                       input=f'{system}\n\n{user}'.encode('utf-8'), capture_output=True, timeout=300, env={**os.environ, **BIZ_ENV}, cwd=BIZ_DIR)
    ev = []
    for line in r.stdout.decode('utf-8', 'replace').splitlines():
        if line.startswith('{'):
            try:
                ev.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    text = ''.join(e['part'].get('text', '') for e in ev if e.get('type') == 'text' and isinstance(e.get('part'), dict))
    if not text:
        msg = next((json.dumps(e.get('error') or e.get('part'), ensure_ascii=False) for e in ev if e.get('type') == 'error'), '')
        msg = msg or (r.stderr.decode('utf-8', 'replace') or '응답 없음')[-200:]
        if '로그인' in msg or 'login' in msg.lower() or 'auth' in msg.lower():
            _biz.update(t=0, v=None)
            msg += ' → 터미널에서 bizcoder login'
        raise RuntimeError('BizCoder: ' + msg[:300])
    return text


# ───────────── Ollama(사내망 모델 서버) ─────────────
# 사내 모델 서버(Ollama · 인증 프록시 뒤의 Ollama · ollama.com API)를 /api/chat 으로 부른다.
# 서버 주소·API 키·모델은 사용자가 화면 설정에서 정한다(ctx['cfg'] = {'url', 'key', 'model'}). 키는 Bearer 헤더로만 보낸다.
_ol = {}


def _ol_req(cfg, path, body=None, timeout=5):
    h = {'content-type': 'application/json', **({'authorization': 'Bearer ' + cfg['key']} if cfg.get('key') else {})}
    req = urllib.request.Request(cfg['url'].rstrip('/') + path, data=json.dumps(body).encode() if body is not None else None, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return json.loads(r.read().decode())


def _ol_err(e, url):
    if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403):
        return f'API 키를 확인해 주세요 (HTTP {e.code}, {url})'
    return f'Ollama 서버에 연결할 수 없습니다 ({url}) — {str(e)[:80]}'


def ollama_models(cfg):
    """서버의 글쓰기용 모델 [{'name', 'cloud'}] — 임베딩 전용은 뺀다. cloud = ollama.com 에서 도는 모델(문서가 PC 밖으로 나감)."""
    ms = _ol_req(cfg, '/api/tags').get('models') or []
    # ponytail: 계열 이름으로 임베딩 모델을 거른다 — 틀리면 /api/show 의 capabilities 로
    return [{'name': m['name'], 'cloud': bool(m.get('remote_host'))} for m in ms
            if (m.get('details') or {}).get('family') not in ('bert', 'nomic-bert') and 'embed' not in m['name']]


def ollama_status(cfg, force=False):
    """{'ready', 'detail'} — 서버가 답하고(키 포함) 고른 모델이 있는지(30초 캐시)."""
    k = (cfg['url'], cfg.get('model'), cfg.get('key'))
    if not force and k in _ol and time.time() - _ol[k][0] < 30:
        return _ol[k][1]
    model = cfg.get('model') or ''
    try:
        ms = {m['name']: m['cloud'] for m in ollama_models(cfg)}
        name = model if model in ms else f'{model}:latest'
        if not model:
            v = {'ready': False, 'detail': '모델을 고르세요 (⚙ 설정)'}
        elif name not in ms:
            v = {'ready': False, 'detail': f'서버에 없는 모델: {model}'}
        else:
            try:     # 목록에 있어도 모델 파일이 없거나(“does not support chat”) 임베딩 전용이면 글을 못 쓴다
                caps = _ol_req(cfg, '/api/show', {'model': name}).get('capabilities')
            except urllib.error.HTTPError as e:      # 모델 없음(404 "model '…' not found")만 못 씀 — 프록시가 막은 /api/show 등은 넘어간다
                caps = [] if e.code == 404 and "model '" in e.read().decode(errors='ignore') else None
            if caps is not None and 'completion' not in caps:
                v = {'ready': False, 'detail': f'쓸 수 없는 모델: {model} — 서버에 모델 파일이 없거나 글쓰기 모델이 아닙니다(서버에서 ollama pull {model})'}
            else:
                v = {'ready': True, 'detail': '연결됨' + (' · ☁ 클라우드 모델 — 문서가 PC 밖(ollama.com)으로 나갑니다' if ms[name] else '')}
    except Exception as e:
        v = {'ready': False, 'detail': _ol_err(e, cfg['url'])}
    _ol[k] = (time.time(), v)
    return v


def _call_ollama(system, user, cfg, json_mode=False):
    need = len(system) + len(user) + 4096              # 한글 1자 ≈ 토큰 1개 + 답 자리 — 문맥이 모자라면 Ollama가 앞(지침)을 잘라 버린다
    num_ctx = 8192
    while num_ctx < min(need, 32768):
        num_ctx *= 2
    body = {'model': cfg['model'], 'stream': False, 'think': False, 'options': {'num_ctx': num_ctx},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    if json_mode:
        body['format'] = 'json'
    try:
        d = _ol_req(cfg, '/api/chat', body, timeout=600)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors='ignore')[:200]
        if e.code in (401, 403):
            raise RuntimeError(_ol_err(e, cfg['url']))
        if 'think' not in msg:
            raise RuntimeError(f'Ollama HTTP {e.code}: {msg}')
        body.pop('think')                              # 생각 끄기를 받지 않는 모델(gpt-oss 등)은 그대로 부른다
        d = _ol_req(cfg, '/api/chat', body, timeout=600)
    text = re.sub(r'<think>.*?</think>', '', (d.get('message') or {}).get('content') or '', flags=re.S).strip()
    if not text:
        raise RuntimeError('Ollama: 빈 응답')
    return text


def available():
    if CFG['llm_kind'] == 'rule':
        return False
    if CFG['llm_kind'] == 'claude_cli':
        return cli_status()['ready']
    return bool(CFG['llm_key'])


def display():
    if CFG['llm_kind'] == 'claude_cli':
        return f"Claude {CFG['llm_model']} (구독 CLI)"
    if CFG['llm_kind'] == 'rule':
        return '규칙 기반'
    return CFG['llm_model']


import threading
_fast = threading.local()
_prov = threading.local()          # ctx['provider'] · ctx['cfg'] — 'bizcoder' · 'ollama' 면 이 호출은 그 사내 LLM으로


def call(system, user, max_tokens=2500, fast=False, json_mode=False):
    """모델 한 번 호출 → (텍스트, ms). 실패하면 예외. fast=True(또는 ctx['fast'])면 가벼운 일용 빠른 모델."""
    fast = fast or getattr(_fast, 'on', False)
    t0 = time.time()
    p, pcfg = getattr(_prov, 'name', ''), getattr(_prov, 'cfg', None) or {}
    if p == 'bizcoder':
        return _call_bizcoder(system, user, pcfg.get('model')), int((time.time() - t0) * 1000)
    if p == 'ollama':
        return _call_ollama(system, user, pcfg, json_mode), int((time.time() - t0) * 1000)
    model = (CFG.get('llm_fast') if fast else '') or CFG['llm_model']
    if CFG['llm_kind'] == 'claude_cli':
        return _call_cli(system, user, model), int((time.time() - t0) * 1000)
    if CFG['llm_kind'] == 'openai_compat':
        url = CFG['llm_base'] + '/v1/chat/completions'
        body = {'model': model, 'max_tokens': max_tokens, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        headers = {'content-type': 'application/json', 'authorization': 'Bearer ' + CFG['llm_key']}
    else:
        url = CFG['llm_base'] + '/v1/messages'
        body = {'model': model, 'max_tokens': max_tokens, 'system': system, 'messages': [{'role': 'user', 'content': user}]}
        headers = {'content-type': 'application/json', 'x-api-key': CFG['llm_key'], 'anthropic-version': '2023-06-01'}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120, context=_ctx()) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'HTTP {e.code}: {e.read().decode(errors="ignore")[:200]}')
    text = data['choices'][0]['message']['content'] if CFG['llm_kind'] == 'openai_compat' else ''.join(b.get('text', '') for b in data['content'])
    return text, int((time.time() - t0) * 1000)


def call_json(system, user, max_tokens=2500, fast=False):
    text, ms = call(system + '\n\n반드시 JSON 하나만 출력한다. 설명·코드블록 표시 없이.', user, max_tokens, fast, json_mode=True)
    a, b = text.find('{'), text.rfind('}')
    if a < 0 or b < 0:
        raise RuntimeError('JSON 응답 없음')
    return json.loads(text[a:b + 1]), ms


def ping():
    """키·네트워크 확인용 최소 호출."""
    if not available():
        return {'ok': False, 'error': cli_status(True)['detail'] if CFG['llm_kind'] == 'claude_cli' else 'KOSOE_LLM_API_KEY 없음'}
    try:
        t, ms = call('짧게 답한다.', '"ok" 한 단어만 출력', 10)
        return {'ok': True, 'ms': ms, 'model': display()}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:200]}


def _try(ctx, fn_llm, fn_rule):
    ctx = ctx or {}
    mk = ctx.get('mk')
    prov, pcfg = ctx.get('provider') or '', ctx.get('cfg') or {}
    meta = {'mode': 'rule', 'model': '규칙 기반', 'label': '규칙 기반(보조)', 'ms': 0, 'masked': 0}
    # Ollama는 미리 묻지 않고 바로 부른다(꺼져 있으면 곧바로 연결 오류 → 규칙 기반으로)
    if ctx.get('use_llm', True) and (bizcoder_status()['ready'] if prov == 'bizcoder' else prov == 'ollama' or available()):
        try:
            _fast.on = bool(ctx.get('fast'))
            _prov.name, _prov.cfg = prov, pcfg
            out, ms = fn_llm(mk.mask if mk else (lambda x: x))
            if mk:
                out = mk.unmask(out)
            model = pcfg.get('model') or (CFG['bizcoder_model'] if prov == 'bizcoder' else CFG['llm_model'])
            return out, {'mode': 'llm', 'model': model, 'label': ctx.get('label') or display(),
                         'ms': ms, 'masked': len(mk.map) if mk else 0, 'tokens': dict(list(mk.map.items())[:6]) if mk else {}}
        except Exception as e:
            meta['error'] = str(e)[:200]
        finally:
            _fast.on = False
            _prov.name, _prov.cfg = '', None
    elif prov == 'bizcoder':
        meta['error'] = bizcoder_status()['detail']
    t0 = time.time()
    out = fn_rule()
    meta['ms'] = int((time.time() - t0) * 1000)
    return out, meta


def _plain(v):
    """문서에 들어가지 않는 마크다운 강조(**·__·`)를 걷어 낸다."""
    return re.sub(r'\*\*(.+?)\*\*|__(.+?)__|`([^`]+)`', lambda m: next(g for g in m.groups() if g is not None), str(v if v is not None else '')).strip()


def _clean_bp(bp, outline):
    secs = []
    for s in bp.get('sections') or []:
        items = []
        for it in s.get('items') or []:
            if isinstance(it, str):
                it = {'label': '', 'text': it}
            items.append({'label': _plain(it.get('label'))[:12], 'text': _plain(it.get('text')),
                          'children': [{'text': _plain(c.get('text') if isinstance(c, dict) else c)} for c in (it.get('children') or [])][:3]})
        tb = s.get('table')
        if tb and tb.get('cols') and tb.get('rows'):
            tb = {'cols': [_plain(c) for c in tb['cols']], 'rows': [[_plain(c) for c in r] for r in tb['rows']][:12]}
        else:
            tb = None
        secs.append({'heading': _plain(s.get('heading')) or '장', 'items': items, 'table': tb})
    return {'title': _plain(bp.get('title')) or '문서', 'sections': secs or [{'heading': h, 'items': [], 'table': None} for h in outline]}


def _attach_text(files, M):
    out = []
    for f in files or []:
        out.append(f'### 첨부: {M(f["name"])}')
        for t in json.loads(f.get('tables') or '[]')[:3]:
            out.append(M('표 ' + t.get('title', '') + '\n' + ' | '.join(t['cols']) + '\n' + '\n'.join(' | '.join(r) for r in t['rows'][:20])))
        if f.get('text'):
            out.append(M(f['text'][:20000]))
    return '\n'.join(out) or '(첨부 없음)'


# ───────────── 1. 문서 라우터 ─────────────
KEYS = [('장애', 'issue-report'), ('경위', 'issue-report'), ('주간', 'weekly-report'), ('방문', 'visit-report'), ('미팅', 'visit-report'),
        ('회의', 'meeting-report'), ('제안', 'deck-proposal'), ('계획', 'plan-report'), ('검토', 'review-report'), ('교육', 'education-plan'),
        ('브리핑', 'web-brief'), ('임원', 'deck-exec'), ('결과', 'result-report'), ('실적', 'result-report')]


def route(text, templates, ctx=None):
    ids = {t['id'] for t in templates}

    def rule():
        for k, tid in KEYS:
            if k in text:
                special = [t for t in templates if t['scope'] != 'corp' and k in t['name']]
                if special:
                    return {'template_id': special[0]['id'], 'reason': f"'{k}'이(가) 들어 있어 우리 조직 템플릿을 골랐습니다"}
                if tid in ids:
                    return {'template_id': tid, 'reason': f"'{k}'이(가) 들어 있어 골랐습니다"}
        return {'template_id': 'result-report' if 'result-report' in ids else templates[0]['id'], 'reason': '가장 많이 쓰는 보고 형식입니다'}

    def llm(M):
        cat = '\n'.join(f"- {t['id']}: {t['name']} ({t['fmt']}, {t['desc']}, 구성 {' → '.join(json.loads(t['outline']))})" for t in templates)
        out, ms = call_json('너는 사내 문서 라우터다. 요청에 가장 맞는 템플릿 하나를 고른다. 부서·팀 전용 템플릿이 맞으면 우선한다.',
                            f'요청: {M(text)}\n\n템플릿 목록:\n{cat}\n\n출력 형식: {{"template_id": str, "reason": "한 문장(존댓말)"}}', 300, fast=True)
        if out.get('template_id') not in ids:
            raise RuntimeError('목록에 없는 템플릿')
        return out, ms
    return _try(ctx, llm, rule)


# ───────────── 2. 설계도 작성 ─────────────
def form_blueprint(template, request_text, files, ctx=None):
    """신청서: 사양의 칸(template['form_fields'])마다 값 하나 → 설계도 한 장(입력 값)에 「칸 이름 : 값」 항목. 엔진이 {{칸}}에 넣는다."""
    fields = template['form_fields']

    def build(title, vals):
        return {'title': _plain(title) or template['name'], 'sections': [{'heading': '입력 값', 'items': [
            {'label': f, 'text': _plain(vals.get(f)) or '(확인 필요)', 'children': []} for f in fields], 'table': None}]}

    def llm(M):
        sys = ('너는 코쇠오피스(코스콤 사내 문서 작성 도우미)다. 신청서 양식의 칸을 채운다.\n'
               '- 값은 요청과 첨부에 있는 것만 쓴다. 없으면 "(확인 필요)", 해당 없음이 분명하면 "-".\n'
               "- 금액은 숫자와 쉼표만(원 단위, 예: 119,600). 날짜는 '2026. 11. 17', 기간은 '2026. 11. 17 ~ 11. 18'.\n"
               '- 칸 하나에 한두 줄. 결재라인·신청일·부서·합계는 앱이 채우므로 쓰지 않는다.\n' + (template.get('rules') or ''))
        user = (f"양식: {template['name']} ({template.get('desc', '')})\n칸(이 이름 그대로): {fields}\n\n요청: {M(request_text)}\n\n"
                f'{_attach_text(files, M)}\n\n출력 형식: {{"title": "문서 이름(예: 부산 데이터센터 출장 신청)", "values": {{"칸 이름": "값"}}}}')
        out, ms = call_json(sys, user, 1500)
        return build(out.get('title'), out.get('values') or {}), ms
    return _try(ctx, llm, lambda: build(template['name'], {}))


def blueprint(template, request_text, files, ctx=None):
    if template.get('form_fields'):
        return form_blueprint(template, request_text, files, ctx)
    outline = json.loads(template['outline'])
    tables = [t for f in files or [] for t in json.loads(f.get('tables') or '[]')]
    fixed = json.loads(template.get('fixed') or '[]')

    def rule():
        first = re.split(r'[.!?\n]', request_text.strip())[0]
        title = re.sub(r'\s*(만들어\s*줘|작성해\s*줘|써\s*줘|해\s*줘|부탁해|부탁합니다|좀)\s*', ' ', first).strip(' .,') or template['name']
        secs = []
        for h in outline:
            items = [{'label': '', 'text': f'{h} 관련 주요 사항 정리 (확인 필요)', 'children': []}]
            fx = [f['text'] for f in fixed if f.get('heading') == h]
            if fx:
                items = [{'label': '', 'text': fx[0][:90], 'children': []}]
            secs.append({'heading': h, 'items': items, 'table': None})
        if tables:
            tgt = next((s for k in ('실적', '성과', '현황', '결과', '내용') for s in secs if k in s['heading']), secs[min(1, len(secs) - 1)])
            tgt['table'] = {'cols': tables[0]['cols'], 'rows': tables[0]['rows'][:10]}
        from engines import short_title
        return {'title': short_title(title), 'sections': secs}

    def llm(M):
        fx = '\n'.join(f"- [{f.get('heading')}] {f['text']}" for f in fixed) or '(없음)'
        rules = template.get('rules') or ''
        sys = f'너는 코쇠오피스(코스콤 사내 문서 작성 도우미)다. 템플릿 구성을 지켜 문서 설계도를 JSON으로 만든다.\n{WRITING_RULES}\n{rules}'
        user = (f"템플릿: {template['name']} ({template['desc']})\n구성(이 순서와 제목을 그대로): {outline}\n"
                f"고정 문구(그대로 넣는다):\n{fx}\n\n요청: {M(request_text)}\n\n{_attach_text(files, M)}\n\n"
                f"첨부에 표가 있으면 가장 맞는 장의 table에 그대로 넣는다(숫자 변경 금지, 필요하면 증감 열만 추가).\n출력 형식: {BP_SCHEMA}")
        out, ms = call_json(sys, user, 3000)
        return _clean_bp(out, outline), ms
    return _try(ctx, llm, rule)


# ───────────── 3. 채팅으로 고치기 ─────────────
def edit(bp, instruction, files, ctx=None):
    def rule():
        b = json.loads(json.dumps(bp))
        secs = b['sections']
        if re.search('결론|요약', instruction):
            if not any(s['heading'] == '핵심 요약' for s in secs):
                secs.insert(0, {'heading': '핵심 요약', 'items': [{'label': '', 'text': '(핵심 결론 한 줄 — 확인 필요)', 'children': []}], 'table': None})
            return {'reply': '결론을 맨 앞에 두도록 **핵심 요약** 장을 첫 번째로 넣었습니다.', 'blueprint': b}
        if re.search('한 장|1쪽|한장|짧게', instruction):
            for s in secs:
                s['items'] = s['items'][:2]
            return {'reply': '한 쪽에 맞도록 장마다 2개 항목으로 줄였습니다.', 'blueprint': b}
        if re.search('빼|삭제', instruction):
            for s in list(secs):
                if s['heading'] in instruction:
                    secs.remove(s)
                    return {'reply': f"**{s['heading']}** 장을 뺐습니다.", 'blueprint': b}
        if files:
            tbs = [t for f in files for t in json.loads(f.get('tables') or '[]')]
            if tbs:
                tgt = next((s for s in secs if s['heading'] in instruction), next((s for s in secs if re.search('실적|성과|현황', s['heading'])), secs[-1]))
                tgt['table'] = {'cols': tbs[0]['cols'], 'rows': tbs[0]['rows'][:10]}
                return {'reply': f"첨부 표를 **{tgt['heading']}** 장에 넣었습니다.", 'blueprint': b}
        tgt = next((s for s in secs if s['heading'] in instruction), secs[-1])
        tgt['items'].append({'label': '', 'text': instruction.strip()[:80] + ' (반영 예정)', 'children': []})
        return {'reply': f"**{tgt['heading']}**에 지시를 메모로 넣었습니다. (규칙 기반 보조 모드 — AI가 연결되면 문장으로 반영합니다)", 'blueprint': b}

    def llm(M):
        sys = f'너는 코쇠오피스(코스콤 사내 문서 작성 도우미)다. 사용자의 지시대로 설계도를 고친다. 지시와 관계없는 부분은 그대로 둔다.\n{WRITING_RULES}'
        user = (f'현재 설계도:\n{M(json.dumps(bp, ensure_ascii=False))}\n\n지시: {M(instruction)}\n\n{_attach_text(files, M)}\n\n'
                f'출력 형식: {{"reply": "무엇을 바꿨는지 한두 문장(존댓말)", "blueprint": {BP_SCHEMA}}}')
        out, ms = call_json(sys, user, 3500)
        return {'reply': str(out.get('reply') or '반영했습니다.'), 'blueprint': _clean_bp(out.get('blueprint') or bp, [])}, ms
    return _try(ctx, llm, rule)


# ───────────── 4. 긴 항목 줄이기(검수 자동 수정) ─────────────
def shorten(texts, ctx=None):
    def rule():
        out = []
        for t in texts:
            s = re.split(r'(?:으며|이며|하며|였으며|고,|,)\s', t)[0]
            out.append(s if len(s) <= 90 else s[:88] + '…')
        return out

    def llm(M):
        out, ms = call_json(f'긴 보고서 항목을 90자 이내 한 문장으로 줄인다. 뜻과 숫자는 유지.\n{WRITING_RULES}',
                            f'항목들: {M(json.dumps(texts, ensure_ascii=False))}\n출력 형식: {{"items": [str]}} (같은 개수, 같은 순서)', 1500, fast=True)
        items = out.get('items') or []
        if len(items) != len(texts):
            raise RuntimeError('개수 불일치')
        return [str(x) for x in items], ms
    return _try(ctx, llm, rule)


# ───────────── 5. 기존 문서에서 템플릿 추출 ─────────────
def extract(docs, ctx=None):
    """docs = [{'name','text','heads'}] → 구성·고정 문구·채울 칸·작성 규칙."""
    def rule():
        hints = [d.get('heads') or [] for d in docs]
        base = hints[0] if hints else []
        common = [h for h in base if all(h in hh for hh in hints[1:])] or base
        texts = [d['text'] for d in docs]
        fixed = []
        if len(texts) > 1:
            lines0 = [l.strip() for l in texts[0].split('\n') if len(l.strip()) > 25]
            fixed = [{'heading': '', 'text': l} for l in lines0 if all(l in t for t in texts[1:])][:3]
        return {'outline': common[:8] or ['개요', '주요 내용', '향후 계획'], 'fixed': fixed,
                'fields': [{'name': h, 'desc': f'{h}에 들어갈 내용', 'example': '', 'kind': '칸'} for h in common[:6]],
                'rules': ['결론을 먼저 쓴다'], 'name_suggest': docs[0]['name'].rsplit('.', 1)[0][:30] if docs else '새 템플릿'}

    def llm(M):
        body = '\n\n'.join(f"=== 문서 {i + 1}: {M(d['name'])} ===\n장 제목 후보: {d.get('heads')}\n{M(d['text'][:5000])}" for i, d in enumerate(docs))
        sys = ('너는 사내 문서 양식 분석가다. 같은 종류의 문서 여러 건에서 공통 구성(목차), 매번 똑같이 들어가는 고정 문구, '
               '문서마다 바뀌는 채울 칸, 작성 규칙을 뽑아 템플릿 초안을 만든다. 개인 이름·연락처·고객사 실명은 예시에서 가린다.')
        user = (f'{body}\n\n출력 형식: {{"name_suggest": str, "outline": [str], "fixed": [{{"heading": str, "text": str}}], '
                f'"fields": [{{"name": str, "desc": str, "example": str, "kind": "칸"|"표"}}], "rules": [str]}}')
        out, ms = call_json(sys, user, 2500)
        for k in ('outline', 'fixed', 'fields', 'rules'):
            out.setdefault(k, [])
        return out, ms
    return _try(ctx, llm, rule)
