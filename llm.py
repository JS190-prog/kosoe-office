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
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from core import CFG, DATA

WRITING_RULES = """코스콤 보고 문법을 지킨다.
- 한 항목은 90자(한글 보고서 3줄) 이내, 명사형 종결(~함, ~임, ~ 추진, ~ 예정). '~합니다/~다.'로 끝내지 않는다.
- 항목 앞 라벨은 2~6자(예: 기간, 대상, 현황). 없으면 빈 문자열.
- 숫자·고유명사·날짜는 사용자 요청과 첨부 자료에 있는 것만 쓴다. 없는 사실은 지어내지 말고 '(확인 필요)'로 둔다.
- [고객사명1] 같은 대괄호 토큰은 가려 둔 값이다. 그대로 옮겨 쓴다.
- 날짜는 '2026. 10. 28' 형식.
- 장마다 항목 2~4개. 하위 설명이 필요하면 children에 1~2개."""

def writing_rules(style=None):
    """작성 규칙. 스킬에 문체(style)가 없으면 코스콤 보고 문법, 있으면 대표 문서에서 잰 그 문서 종류의 문체."""
    import checks
    st = checks.norm_style(style)
    if st == checks.DEFAULT_STYLE:
        return WRITING_RULES
    end = {'noun': "명사형 종결(~함, ~임, ~ 추진, ~ 예정). '~합니다/~다.'로 끝내지 않는다.",
           'plain': "서술형 평서문으로 끝낸다(~한다. ~이다. ~할 수 있다.). 개조식(~함, ~임)으로 줄이지 않는다.",
           'polite': "서술형 존댓말로 끝낸다(~합니다. ~입니다.). 개조식(~함, ~임)으로 줄이지 않는다.",
           'any': '문장 끝 형태는 자료에 적힌 그대로 따른다.'}[st['ending']]
    length = f"한 항목은 {st['max_len']}자 이내." if st['max_len'] else '길이 제한 없음. 조·항 하나를 한 항목에 온전히 쓴다.'
    date = '날짜는 자료에 적힌 형식 그대로.' if st['date'] == 'any' else f"날짜는 '{checks.fmt_date(2026, 10, 28, st['date'])}' 형식."
    return f"""이 문서 종류의 문체를 지킨다(대표 문서에서 잰 기준이며, 보고서용 개조식 문법보다 우선한다).
- {end}
- {length}
- 항목 앞 라벨은 2~6자(예: 기간, 대상). 조·항 번호(①, 1.)는 본문에 그대로 두고 라벨은 빈 문자열로 둔다.
- 숫자·고유명사·날짜는 사용자 요청과 첨부 자료에 있는 것만 쓴다. 없는 사실은 지어내지 말고 '(확인 필요)'로 둔다.
- [고객사명1] 같은 대괄호 토큰은 가려 둔 값이다. 그대로 옮겨 쓴다.
- {date}
- 장(조)마다 항목 1~6개. 원문의 항·호 단위를 따른다."""


BP_SCHEMA = '{"title": str, "sections": [{"heading": str, "items": [{"label": str, "text": str, "children": [{"text": str}]}], "table": {"cols": [str], "rows": [[str]]} | null}]}'
# 기안문(preset draft): 한글 스킬 기안문 렌더러의 머리(수신자 · 제목) · 요청 문장 · 첨부 목록과 장 제목 줄 · 표 단위를 더 받는다
DRAFT_KEYS = ('recipient', 'purpose', 'attachments')
BP_SCHEMA_DRAFT = ('{"recipient": str, "title": str, "purpose": str, "attachments": [str], "sections": [{"heading": str, "text": str, '
                   '"items": [{"label": str, "text": str, "children": [{"text": str}]}], "table": {"cols": [str], "rows": [[str]], "unit": str} | null}]}')
DRAFT_GUIDE = ('\n기안문 칸: recipient = 수신자(예: 경영지원부장, 내부결재). title = 결재받을 일(예: ○○ 추진 및 계약 체결 의뢰). '
               'purpose = 요청 문장 「아래와 같이 ○○을 추진하고자 하오니」의 ○○ — 제목에서 「추진 및 계약 체결 의뢰」 같은 꼬리를 뺀 일. '
               'attachments = 첨부 문서 목록(「문서명 1부」 꼴, 요청 · 첨부 자료에 있는 것만, 없으면 []). '
               '장의 text = 장 제목 줄에 「제목 : 내용」으로 붙일 한 줄(필요할 때만, 없으면 ""). 표의 unit = 표 위 단위(예: (단위 : 원, 부가세 별도), 없으면 ""). '
               '하위 항목 중 각주는 text를 「* 」로, 참고는 「※ 」로 시작한다.')

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
        self.lock = threading.Lock()      # 스킬 검증은 초안 여러 개를 동시에 쓰면서 Masker 하나를 같이 쓴다

    def mask(self, text):
        if not text:
            return text
        with self.lock:
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
        with self.lock:
            pairs = list(self.map.items())
        for tok, orig in pairs:
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
    args = [exe, '-p', '--output-format', 'json', '--model', model or CFG['cli_model'], '--system-prompt', system,
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
# 회사 계정으로 로그인된 BizCoder(opencode 계열 코딩 에이전트)로 사내 모델을 부른다. 모델은 DeepSeek V4 Flash 하나로 고정한다.
# Claude Code·Codex 이어받기(MCP·스킬·지침)·프로젝트 설정·자동 업데이트를 끄고 도구를 모두 막은 채, 빈 작업 폴더에서
# 요청을 표준입력으로 넘겨 순수한 '모델 호출'로만 쓴다 — 첨부 속 글이 도구(명령·파일)를 부르지 못하게.
BIZ_MODEL, BIZ_LABEL = 'bizrouter/deepseek/deepseek-v4-flash-0731', 'DeepSeek V4 Flash'
BIZ_DIR = os.path.join(DATA, 'llm-bizcoder')
os.makedirs(BIZ_DIR, exist_ok=True)
BIZ_TOOLS_OFF = {'tools': {'*': False}}
BIZ_ENV = {'OPENCODE_DISABLE_CLAUDE_CODE': '1', 'OPENCODE_DISABLE_CODEX': '1', 'BIZCODER_DISABLE_CLAUDE_CODE': '1',
           'BIZCODER_DISABLE_CODEX': '1', 'OPENCODE_DISABLE_CLAUDE_CODE_PROMPT': '1', 'OPENCODE_DISABLE_CODEX_PROMPT': '1',
           'OPENCODE_DISABLE_CLAUDE_CODE_MEMORY': '1', 'OPENCODE_DISABLE_CODEX_SKILLS': '1', 'OPENCODE_DISABLE_PROJECT_CONFIG': '1',
           'OPENCODE_DISABLE_AUTOUPDATE': '1', 'BIZCODER_DISABLE_WORKFLOWS': '1', 'OPENCODE_PURE': '1',
           'OPENCODE_CONFIG_CONTENT': json.dumps(BIZ_TOOLS_OFF)}
_biz = {'p': None, 't': 0, 'v': None, 'think': 0}      # think = 생각 끄기 옵션이 거부된 시각(그 뒤 10분은 옵션 없이 부른다)


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


def _biz_run(exe, prompt, conf):
    """BizCoder 한 번 실행 → (답, 답이 없을 때의 오류 글)."""
    r = subprocess.run([exe, 'run', '--pure', '--format', 'json', '-m', BIZ_MODEL, '--dir', BIZ_DIR], input=prompt.encode('utf-8'), capture_output=True,
                       timeout=300, env={**os.environ, **BIZ_ENV, 'OPENCODE_CONFIG_CONTENT': json.dumps(conf)}, cwd=BIZ_DIR)
    ev = []
    for line in r.stdout.decode('utf-8', 'replace').splitlines():
        if line.startswith('{'):
            try:
                ev.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    text = ''.join(e['part'].get('text', '') for e in ev if e.get('type') == 'text' and isinstance(e.get('part'), dict))
    msg = '' if text else (next((json.dumps(e.get('error') or e.get('part'), ensure_ascii=False) for e in ev if e.get('type') == 'error'), '')
                           or (r.stderr.decode('utf-8', 'replace') or '응답 없음')[-200:])
    return text, msg


def _biz_conf(deep=False):
    """BizCoder 설정: 도구는 모두 막고 모델의 '생각(추론)' 수준(KOSOE_BIZCODER_REASONING)을 준다.
    BizCoder에 이 모델의 --variant 가 없어 공급자 옵션으로 준다. default 면 옵션 없이 모델 기본(가장 느림).
    deep(대표 문서 분석 · 긴 항목 줄이기): 생각을 끄거나 낮추면 스킬 초안이 거칠어지고 줄인 길이가 기준을 넘는다(실측) → off · low 여도 모델 기본으로 둔다."""
    level = CFG['bizcoder_reasoning']
    effort = None if deep and level in ('off', 'low') else {'off': 'none', 'low': 'low', 'medium': 'medium', 'high': 'high'}.get(level)
    return {**BIZ_TOOLS_OFF, **({'provider': {'bizrouter': {'models': {BIZ_MODEL.partition('/')[2]: {'options': {'reasoning': {'effort': effort}}}}}}} if effort else {})}


def _call_bizcoder(system, user):
    exe = bizcoder_path()
    if not exe:
        raise RuntimeError('BizCoder CLI 없음')
    prompt = f'{system}\n\n{user}'
    conf = _biz_conf(getattr(_fast, 'deep', False)) if time.time() - _biz['think'] > 600 else BIZ_TOOLS_OFF
    text, msg = _biz_run(exe, prompt, conf)
    if not text and conf != BIZ_TOOLS_OFF:          # 생각 옵션을 받지 않게 바뀌었을 수 있다 — 옵션 없이 한 번 더, 되면 10분 동안은 옵션 없이
        text, msg = _biz_run(exe, prompt, BIZ_TOOLS_OFF)
        if text:
            _biz['think'] = time.time()
    if not text:
        if '로그인' in msg or 'login' in msg.lower() or 'auth' in msg.lower():
            _biz.update(t=0, v=None)
            msg += ' → 터미널에서 bizcoder login'
        raise RuntimeError('BizCoder: ' + msg[:300])
    return text


# ───────────── Ollama(사내망 모델 서버) ─────────────
# 사내 모델 서버(Ollama · 인증 프록시 뒤의 Ollama · ollama.com API)를 /api/chat 으로 부른다.
# 서버 주소·API 키·모델(OLLAMA)은 화면의 AI 선택 창에서 정한다(app: /api/ai/ollama). 키는 Bearer 헤더로만 보낸다.
OLLAMA = {'url': CFG['ollama_url'], 'key': CFG['ollama_key'], 'model': CFG['ollama_model']}
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
                v = {'ready': True, 'cloud': ms[name], 'detail': '연결됨' + (' · ☁ 클라우드 모델 — 요청이 PC 밖(ollama.com)으로 나가 가림 처리합니다' if ms[name] else '')}
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


# ───────────── 제공자(provider) — 실행 중에 화면에서 바꿀 수 있다 ─────────────
# claude_cli : 각자의 Claude Code 구독 CLI (기본)
# bizcoder / ollama : 사내 LLM — 회사 BizCoder 계정(DeepSeek V4 Flash 고정) · 사내망 Ollama 서버
# nvidia / openrouter : 외부 API(OpenAI 호환) — 사내에 올릴 오픈 모델(DeepSeek 등)을 노트북 시연에서 대신 부르는 용도
#   nvidia = build.nvidia.com 무료 체험 엔드포인트(평가용), openrouter = 유료 · 일부 무료 모델
# anthropic / openai_compat : API 키 · 사내 모델 엔드포인트      rule : AI 없이 규칙 기반만
import threading
_fast = threading.local()
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
# 외부 API(OpenAI 호환) — 사내 GPU에 올릴 오픈 모델을 노트북 시연에서 대신 부른다. 요청이 밖으로 나가므로 항상 가림 처리한다.
HOSTED = {
    'nvidia': {'name': 'NVIDIA API (build.nvidia.com)', 'tag': 'NVIDIA API', 'url': CFG['nv_base'] + '/chat/completions', 'key': 'nv_key', 'models': 'nv_models',
               'env': 'KOSOE_NVIDIA_API_KEY', 'menv': 'KOSOE_NVIDIA_MODELS',
               'note': 'NVIDIA가 올려 둔 오픈 모델(DeepSeek 등)을 무료 체험 엔드포인트로 부릅니다(평가용 · 요청 수 제한). 사내 GPU에 같은 모델을 올렸을 때를 대신 보여 줍니다. '
                       '요청 내용이 외부로 나가므로 가림 처리를 항상 적용하고, 가상 자료만 씁니다.'},
    'openrouter': {'name': 'OpenRouter API', 'tag': 'OpenRouter API', 'url': OPENROUTER_URL, 'key': 'or_key', 'models': 'or_models',
                   'env': 'KOSOE_OPENROUTER_API_KEY', 'menv': 'KOSOE_OPENROUTER_MODELS',
                   'note': '사내 GPU에 올릴 오픈 모델(DeepSeek 등)을 시연에서는 OpenRouter로 부릅니다. 요청 내용이 외부로 나가므로 가림 처리를 항상 적용하고, 가상 자료만 씁니다.'},
}
_active = {'kind': CFG['llm_kind'], 'model': {'openrouter': CFG['or_model'], 'nvidia': (CFG['nv_models'] or [''])[0]}}
KIND_NAME = {'claude_cli': 'Claude Code CLI (구독)', 'nvidia': HOSTED['nvidia']['name'], 'openrouter': HOSTED['openrouter']['name'],
             'bizcoder': 'BizCoder (사내 LLM)', 'ollama': 'Ollama (사내망 모델 서버)', 'anthropic': 'Claude API',
             'openai_compat': 'OpenAI 호환(사내 모델)', 'rule': '규칙 기반(AI 없음)'}


def provider():
    return _active['kind']


def set_provider(kind, model=''):
    if kind not in KIND_NAME:
        raise ValueError('없는 AI 제공자: ' + str(kind))
    if kind in HOSTED and model:
        h = HOSTED[kind]
        if model not in CFG[h['models']]:
            raise ValueError(f"목록에 없는 모델: {model} — .env의 {h['menv']}에 추가하세요")
        _active['model'][kind] = model
    _active['kind'] = kind
    return state()


def chosen_models():
    """외부 API별로 고른 모델(저장용)."""
    return dict(_active['model'])


def model_name(fast=False):
    k = provider()
    if k == 'claude_cli':
        return (CFG['cli_fast'] if fast else '') or CFG['cli_model']
    if k in HOSTED:
        return _active['model'][k]
    if k == 'bizcoder':
        return BIZ_MODEL
    if k == 'ollama':
        return OLLAMA['model']
    if k == 'rule':
        return '규칙 기반'
    return (CFG.get('llm_fast') if fast else '') or CFG['llm_model']


def _ol_outside():
    """Ollama 요청이 회사 밖으로 나가는가 — ollama.com API 를 직접 부르거나, 서버가 ollama.com 에서 도는 클라우드 모델로 넘기는 경우.
    서버 확인이 안 될 때도 나간다고 본다(확인 안 된 채 가림 없이 시작한 작업이 서버가 살아난 뒤 그대로 나가지 않게)."""
    st, host = ollama_status(OLLAMA), urllib.parse.urlparse(OLLAMA['url']).hostname or ''
    return host == 'ollama.com' or host.endswith('.ollama.com') or not st['ready'] or bool(st.get('cloud'))


def external():
    """요청 내용이 제3자 API로 나가는 제공자인가(가림 처리 대상)."""
    k = provider()
    return k in HOSTED or (k == 'ollama' and _ol_outside())


def internal():
    """실제 사내 LLM(회사 BizCoder 계정 · 사내망 Ollama)인가 — 화면에 '사내 LLM 자리(시연)' 대신 '사내 LLM'으로 보인다."""
    return provider() in ('bizcoder', 'ollama') and not external()


def available():
    k = provider()
    if k == 'rule':
        return False
    if k == 'claude_cli':
        return cli_status()['ready']
    if k in HOSTED:
        return bool(CFG[HOSTED[k]['key']])
    if k == 'bizcoder':
        return bizcoder_status()['ready']
    if k == 'ollama':
        return ollama_status(OLLAMA)['ready']
    return bool(CFG['llm_key'])


def _short(m):
    return m.split('/')[-1]


def display():
    k = provider()
    if k == 'claude_cli':
        return f"Claude {CFG['cli_model']} (구독 CLI)"
    if k in HOSTED:
        return f"{_short(_active['model'][k])} ({HOSTED[k]['tag']})"
    if k == 'bizcoder':
        return f'BizCoder · {BIZ_LABEL}'
    if k == 'ollama':
        return f"Ollama · {OLLAMA['model'] or '모델 미설정'}"
    if k == 'rule':
        return '규칙 기반'
    return CFG['llm_model']


def ollama_public():
    """화면에 보여 줄 Ollama 설정 — API 키는 빼고 있는지 · 끝 4자리만."""
    k = OLLAMA.get('key') or ''
    return {'url': OLLAMA['url'], 'model': OLLAMA['model'], 'has_key': bool(k), 'key_hint': ('…' + k[-4:]) if len(k) >= 8 else ('설정됨' if k else '')}


def state(probe=False):
    """화면의 AI 선택 창에 보여 줄 제공자 목록과 현재 선택.
    사내 LLM(BizCoder 로그인 · Ollama 서버)의 연결 확인은 시간이 걸릴 수 있어, 지금 쓰는 제공자이거나 probe(선택 창을 열 때)일 때만 한다."""
    cli = cli_status()
    out = [{'kind': 'claude_cli', 'name': KIND_NAME['claude_cli'], 'ready': cli['ready'], 'model': CFG['cli_model'],
            'detail': cli['detail'] if cli['ready'] else (cli['detail'] or '로그인 필요'), 'note': '각자 구독으로 로그인한 Claude Code CLI를 부릅니다.'}]
    for k, h in HOSTED.items():
        out.append({'kind': k, 'name': h['name'], 'ready': bool(CFG[h['key']]), 'model': _active['model'][k], 'models': CFG[h['models']],
                    'detail': '키 있음' if CFG[h['key']] else f".env에 {h['env']} 필요", 'note': h['note']})
    k = provider()
    # 로그인됨은 10분 캐시 그대로, 안 됨으로 남아 있으면 창을 열 때마다 다시 본다(방금 bizcoder login 한 것이 바로 보이게)
    biz = bizcoder_status(force=probe and not (_biz['v'] or {}).get('ready')) if probe or k == 'bizcoder' else (_biz['v'] or {'ready': False, 'detail': ''})
    out.append({'kind': 'bizcoder', 'name': KIND_NAME['bizcoder'], 'ready': biz['ready'], 'model': BIZ_MODEL, 'detail': biz['detail'],
                'note': f'회사 BizCoder 계정으로 사내 모델({BIZ_LABEL} 고정)을 부릅니다. 먼저 터미널에서 bizcoder login.'})
    ol = ollama_status(OLLAMA) if probe or k == 'ollama' else {'ready': False, 'detail': ''}
    out.append({'kind': 'ollama', 'name': KIND_NAME['ollama'], 'ready': ol['ready'], 'model': OLLAMA['model'], 'detail': ol['detail'], 'ollama': ollama_public(),
                'note': '사내망 Ollama 서버(인증 프록시 · ollama.com API 포함)를 부릅니다. 주소 · API 키 · 모델은 아래에서 정합니다.'})
    if CFG['llm_key'] and CFG['llm_kind'] in ('anthropic', 'openai_compat'):
        out.append({'kind': CFG['llm_kind'], 'name': KIND_NAME[CFG['llm_kind']], 'ready': True, 'model': CFG['llm_model'], 'detail': CFG['llm_base'], 'note': ''})
    out.append({'kind': 'rule', 'name': KIND_NAME['rule'], 'ready': True, 'model': '', 'detail': '', 'note': 'AI 없이 규칙으로만 초안을 만듭니다(품질 낮음).'})
    return {'kind': provider(), 'display': display(), 'connected': available(), 'providers': out}


def _post(url, body, headers, timeout=150):
    """JSON POST. 연결 끊김·429·5xx는 한 번 더 시도한다."""
    last = ''
    for attempt in range(2):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='ignore')[:300]
            last = f'HTTP {e.code}: {msg}'
            if e.code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:            # 연결 재설정 등
            last = str(e)[:200]
        time.sleep(1.5)
    raise RuntimeError(last)


def call(system, user, max_tokens=2500, fast=False, json_mode=False):
    """모델 한 번 호출 → (텍스트, ms). 실패하면 예외. fast=True(또는 ctx['fast'])면 가벼운 일용 빠른 모델."""
    fast = fast or getattr(_fast, 'on', False)
    t0 = time.time()
    k = provider()
    model = model_name(fast)
    if k == 'bizcoder':
        return _call_bizcoder(system, user), int((time.time() - t0) * 1000)
    if k == 'ollama':
        return _call_ollama(system, user, OLLAMA, json_mode), int((time.time() - t0) * 1000)
    if k == 'claude_cli':
        return _call_cli(system, user, model), int((time.time() - t0) * 1000)
    if k in HOSTED:
        h = HOSTED[k]
        body = {'model': model, 'max_tokens': max(max_tokens, 1200) + CFG['or_reason_budget'],     # 추론 토큰이 답 토큰을 잡아먹지 않게 여유
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        headers = {'content-type': 'application/json', 'authorization': 'Bearer ' + CFG[h['key']]}
        if k == 'openrouter':
            headers['x-title'] = 'kosoe-office'
            if CFG['or_reasoning'] in ('low', 'medium', 'high'):
                body['reasoning'] = {'effort': CFG['or_reasoning']}
            elif CFG['or_reasoning'] == 'off':
                body['reasoning'] = {'enabled': False}
        else:
            if CFG['nv_thinking'] == 'off':         # 추론을 켜 두면 답 토큰을 다 써서 빈 응답이 나온다(시험에서 확인)
                body['chat_template_kwargs'] = {'thinking': False}
            if CFG['nv_extra']:
                body.update(json.loads(CFG['nv_extra']))
        data = _post(h['url'], body, headers)
        if data.get('error'):
            e = data['error']
            raise RuntimeError(str(e.get('message') if isinstance(e, dict) else e)[:200])
        text = (data.get('choices') or [{}])[0].get('message', {}).get('content') or ''
        if not text.strip():
            raise RuntimeError('빈 응답(추론만 하고 답이 없음) — ' + ('KOSOE_OPENROUTER_REASONING=off 또는 low 로 바꿔 보세요' if k == 'openrouter'
                                                           else 'KOSOE_NVIDIA_THINKING=off 로 두세요'))
        _usage.append({'kind': k, 'model': model, 'cost': (data.get('usage') or {}).get('cost'), 'tokens': (data.get('usage') or {}).get('total_tokens')})
        del _usage[:-200]
        return text, int((time.time() - t0) * 1000)
    if k == 'openai_compat':
        data = _post(CFG['llm_base'] + '/v1/chat/completions',
                     {'model': model, 'max_tokens': max_tokens, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]},
                     {'content-type': 'application/json', 'authorization': 'Bearer ' + CFG['llm_key']})
        return data['choices'][0]['message']['content'], int((time.time() - t0) * 1000)
    data = _post(CFG['llm_base'] + '/v1/messages',
                 {'model': model, 'max_tokens': max_tokens, 'system': system, 'messages': [{'role': 'user', 'content': user}]},
                 {'content-type': 'application/json', 'x-api-key': CFG['llm_key'], 'anthropic-version': '2023-06-01'})
    return ''.join(b.get('text', '') for b in data['content']), int((time.time() - t0) * 1000)


_usage = []          # 외부 API 호출별 비용(시연 중 확인용). NVIDIA 체험 엔드포인트는 비용이 없다.


def usage():
    cost = sum(u['cost'] or 0 for u in _usage)
    by = {}
    for u in _usage:
        by[u.get('kind', 'openrouter')] = by.get(u.get('kind', 'openrouter'), 0) + 1
    return {'calls': len(_usage), 'cost_usd': round(cost, 6), 'by': by}


def call_json(system, user, max_tokens=2500, fast=False):
    text, ms = call(system + '\n\n반드시 JSON 하나만 출력한다. 설명·코드블록 표시 없이.', user, max_tokens, fast, json_mode=True)
    a, b = text.find('{'), text.rfind('}')
    if a < 0 or b < 0:
        raise RuntimeError('JSON 응답 없음')
    return json.loads(text[a:b + 1]), ms


def ping():
    """키·네트워크 확인용 최소 호출."""
    k = provider()
    st = bizcoder_status(True) if k == 'bizcoder' else ollama_status(OLLAMA, True) if k == 'ollama' else None      # 사내 LLM은 지금 상태를 다시 확인한다
    if not available():
        return {'ok': False, 'error': cli_status(True)['detail'] if k == 'claude_cli' else '규칙 기반 설정' if k == 'rule' else
                f".env에 {HOSTED[k]['env']} 없음" if k in HOSTED else st['detail'] if st else 'KOSOE_LLM_API_KEY 없음'}
    try:
        t, ms = call('짧게 답한다.', '"ok" 한 단어만 출력', 10)
        return {'ok': True, 'ms': ms, 'model': display(), 'reply': t.strip()[:40]}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:200]}


def _try(ctx, fn_llm, fn_rule):
    ctx = ctx or {}
    mk = ctx.get('mk')
    meta = {'mode': 'rule', 'model': '규칙 기반', 'label': '규칙 기반(보조)', 'ms': 0, 'masked': 0}
    if ctx.get('use_llm', True) and available():
        try:
            _fast.on, _fast.deep = bool(ctx.get('fast')), bool(ctx.get('deep'))
            out, ms = fn_llm(mk.mask if mk else (lambda x: x))
            if mk:
                out = mk.unmask(out)
            return out, {'mode': 'llm', 'model': model_name(bool(ctx.get('fast'))), 'kind': provider(), 'label': ctx.get('label') or display(), 'ms': ms,
                         'masked': len(mk.map) if mk else 0, 'tokens': dict(list(mk.map.items())[:6]) if mk else {}}
        except Exception as e:
            meta['error'] = str(e)[:200]
        finally:
            _fast.on = _fast.deep = False
    elif ctx.get('use_llm', True) and provider() in ('bizcoder', 'ollama'):      # 사내 LLM이 준비 안 됨 — 이유를 화면에 보인다
        meta['error'] = (bizcoder_status() if provider() == 'bizcoder' else ollama_status(OLLAMA))['detail']
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
            tb = {'cols': [_plain(c) for c in tb['cols']], 'rows': [[_plain(c) for c in r] for r in tb['rows']][:12],
                  **({'unit': _plain(tb['unit'])} if _plain(tb.get('unit')) else {})}
        else:
            tb = None
        sec = {'heading': _plain(s.get('heading')) or '장', 'items': items, 'table': tb}
        if _plain(s.get('text')):                   # 기안문: 장 제목 줄에 붙이는 한 줄
            sec['text'] = _plain(s['text'])
        secs.append(sec)
    out = {'title': _title(bp.get('title')), 'sections': secs or [{'heading': h, 'items': [], 'table': None} for h in outline]}
    for k in ('recipient', 'purpose'):              # 기안문 머리 수신자 · 요청 문장의 추진하는 일
        if _plain(bp.get(k)):
            out[k] = _title(bp[k])
    atts = [_plain(a) for a in (bp.get('attachments') or []) if isinstance(a, str) and _plain(a)]
    if atts:                                        # 기안문 첨부 목록
        out['attachments'] = atts[:15]
    return out


def _title(v):
    """제목은 한 줄. AI가 표지 글 전체(여러 줄)를 제목에 넣으면 첫 줄만 쓴다 — 제목 칸·문서함·받기 파일 이름에 쓰이는 값이다."""
    first = next((l.strip() for l in re.split(r'[\r\n]+', _plain(v)) if l.strip()), '')
    return re.sub(r'\s+', ' ', first)[:80] or '문서'


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


def _fill_blueprint(form, request_text, files, ctx=None):
    """서식 채우기형 양식(계약서 등): 조항은 서식에 있으므로 칸에 넣을 값만 요청·자료에서 찾는다."""
    import fillform

    def rule():
        return fillform.to_blueprint(form, {}, {})

    def llm(M):
        sys = ('너는 코쇠오피스(코스콤 사내 문서 작성 도우미)다. 모양이 정해진 서식의 칸에 넣을 값을 요청과 첨부 자료에서 찾아 적는다.\n'
               '- 조항·본문 문장은 서식에 들어 있으므로 쓰지 않는다. 칸의 값만 적는다.\n'
               '- 요청·자료에 없는 값은 빈 문자열로 둔다. 금액·날짜·사람 이름·주소를 짐작하거나 지어내지 않는다.\n'
               '- [고객사명1] 같은 대괄호 토큰은 가려 둔 값이다. 그대로 옮겨 쓴다.\n'
               '- 금액은 자료의 숫자를 표의 단위에 맞춰 쉼표와 함께 적는다(예: 단위가 천원이면 2,400만원 → 24,000). 단위 환산이 확실하지 않으면 비워 둔다.\n'
               '- 날짜는 칸 설명의 형식을 따른다.')
        user = (f"서식: {form.get('name')} — {form.get('purpose', '')}\n\n채울 칸:\n{fillform.prompt_spec(form)}\n\n"
                f"요청: {M(request_text)}\n\n{_attach_text(files, M)}\n\n"
                '출력 형식: {"fields": {칸 key: 값}, "rows": {표 key: [{열 이름: 값}]}}')
        out, ms = call_json(sys, user, 2000)
        return fillform.to_blueprint(form, out.get('fields') or {}, out.get('rows') or {}), ms
    return _try(ctx, llm, rule)


def blueprint(template, request_text, files, ctx=None):
    if template.get('fill'):
        return _fill_blueprint(template['fill'], request_text, files, ctx)
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
        draft = template.get('preset') == 'draft'
        sys = f'너는 코쇠오피스(코스콤 사내 문서 작성 도우미)다. 템플릿 구성을 지켜 문서 설계도를 JSON으로 만든다.\n{writing_rules(template.get("style"))}\n{rules}'
        user = (f"템플릿: {template['name']} ({template['desc']})\n구성(이 순서와 제목을 그대로): {outline}\n"
                f"고정 문구(글자 그대로 넣는다. 그 안에 숫자로 끝나지 않는 [칸 이름]이 있으면 그 칸만 요청·자료의 값으로 바꾸고, 값이 없으면 [칸 이름]을 그대로 둔다):\n{fx}\n\n"
                f"요청: {M(request_text)}\n\n{_attach_text(files, M)}\n\n"
                f"첨부에 표가 있으면 가장 맞는 장의 table에 그대로 넣는다(숫자 변경 금지, 필요하면 증감 열만 추가).\n"
                f"출력 형식: {BP_SCHEMA_DRAFT if draft else BP_SCHEMA}" + (DRAFT_GUIDE if draft else ''))
        out, ms = call_json(sys, user, 3000)
        return _clean_bp(out, outline), ms
    return _try(ctx, llm, rule)


# ───────────── 3. 채팅으로 고치기 ─────────────
def edit(bp, instruction, files, ctx=None, style=None, extra=''):
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
        sys = f'너는 코쇠오피스(코스콤 사내 문서 작성 도우미)다. 사용자의 지시대로 설계도를 고친다. 지시와 관계없는 부분은 그대로 둔다.\n{writing_rules(style)}' + (f'\n{extra}' if extra else '')
        draft = any(k in bp for k in DRAFT_KEYS)
        user = (f'현재 설계도:\n{M(json.dumps(bp, ensure_ascii=False))}\n\n지시: {M(instruction)}\n\n{_attach_text(files, M)}\n\n'
                f'출력 형식: {{"reply": "무엇을 바꿨는지 한두 문장(존댓말)", "blueprint": {BP_SCHEMA_DRAFT if draft else BP_SCHEMA}}}')
        out, ms = call_json(sys, user, 3500)
        nb = _clean_bp(out.get('blueprint') or bp, [])
        for k in DRAFT_KEYS:                        # 기안문 머리 · 첨부를 AI가 빠뜨려도 지시와 관계없으면 그대로 둔다
            if k in bp and k not in nb:
                nb[k] = bp[k]
        return {'reply': str(out.get('reply') or '반영했습니다.'), 'blueprint': nb}, ms
    return _try(ctx, llm, rule)


# ───────────── 4. 긴 항목 줄이기(검수 자동 수정) ─────────────
def shorten(texts, ctx=None, style=None):
    import checks
    n = checks.norm_style(style)['max_len'] or 90

    def rule():
        out = []
        for t in texts:
            s = re.split(r'(?:으며|이며|하며|였으며|고,|,)\s', t)[0]
            out.append(s if len(s) <= n else s[:n - 2] + '…')
        return out

    def ask(M, xs, limit):
        out, ms = call_json(f'긴 항목을 {limit}자 이내 한 문장으로 줄인다. 뜻과 숫자는 유지.\n{writing_rules(style)}',
                            f'항목들: {M(json.dumps(xs, ensure_ascii=False))}\n출력 형식: {{"items": [str]}} (같은 개수, 같은 순서)', 1500, fast=True)
        items = out.get('items') or []
        if len(items) != len(xs):
            raise RuntimeError('개수 불일치')
        return [str(x) for x in items], ms

    def llm(M):
        out, ms = ask(M, texts, n)
        for k in (0.75, 0.6):   # AI는 글자 수를 정확히 세지 못해 기준을 넘겨 줄이기도 한다(실측 90자 → 96·98·106자) — 넘친 것만 더 짧은 목표로 다시
            over = [i for i, s in enumerate(out) if len(s) > n]
            if not over:
                break
            again, ms2 = ask(M, [out[i] for i in over], int(n * k))
            for i, s in zip(over, again):
                if len(s) < len(out[i]):
                    out[i] = s
            ms += ms2
        return out, ms
    # 글자 수를 맞추는 일이라 생각을 켠다(_biz_conf deep) — BizCoder 생각 끔으로는 90자 목표에 96~106자가 나왔다(실측, 켜면 6/6 이내)
    return _try({**(ctx or {}), 'deep': True}, llm, rule)


# ───────────── 5. 기존 문서에서 템플릿 추출 ─────────────
def extract(docs, ctx=None, prose=False):
    """docs = [{'name','text','heads'}] → 구성·고정 문구·채울 칸·작성 규칙. prose=True면 보고서가 아닌 서술형 문서로 분석한다."""
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
        if prose:           # 보고서가 아닌 문서(계약서·공문·규정 등): 그 문서의 구성과 문장이 기준
            sys += ('\n이 문서는 개조식 보고서가 아니라 서술형 문서(계약서·공문·규정·안내문 등)다. 그 문서의 구성과 문장을 기준으로 분석한다: '
                    '조·항 제목을 outline으로 삼고, 조항 문장은 고쳐 쓰거나 요약하지 말고 원문 그대로 fixed에 옮긴다.\n'
                    '고정 문구 안에서 문서마다 바뀌는 값(회사명·날짜·금액·업무명 등)은 지우지 말고 그 자리에 [칸 이름]을 적는다'
                    '(예: "[고객사명](이하 "갑"이라 한다)", "[기본계약 체결일] 체결한"). 칸 이름은 숫자로 끝내지 않는다.')
        user = (f'{body}\n\n출력 형식: {{"name_suggest": str, "outline": [str], "fixed": [{{"heading": str, "text": str}}], '
                f'"fields": [{{"name": str, "desc": str, "example": str, "kind": "칸"|"표"}}], "rules": [str]}}')
        out, ms = call_json(sys, user, 2500)
        for k in ('outline', 'fixed', 'fields', 'rules'):
            out.setdefault(k, [])
        return out, ms
    return _try({**(ctx or {}), 'deep': True}, llm, rule)      # 분석은 깊이 생각하게(_biz_conf)


if __name__ == '__main__':      # 자체검사(BizCoder 없이): 생각 끄기 옵션이 거부되면 옵션 없이 다시 부르고, 그 뒤 10분은 옵션 없이 부른다
    seen, reject = [], True
    bizcoder_path = lambda: 'bizcoder'      # noqa: E731

    def _biz_run(exe, prompt, conf):        # noqa: F811
        seen.append('provider' in conf)
        return ('', '옵션 거부') if reject and 'provider' in conf else ('답', '')
    CFG['bizcoder_reasoning'] = 'default'
    assert _biz_conf() == BIZ_TOOLS_OFF                                            # default = 옵션 없음(모델 기본)
    CFG['bizcoder_reasoning'] = 'high'
    assert _biz_conf(deep=True) == _biz_conf() != BIZ_TOOLS_OFF                    # 분석(deep)도 높게 준 수준은 그대로
    CFG['bizcoder_reasoning'] = 'off'
    assert _biz_conf(deep=True) == BIZ_TOOLS_OFF                                   # 분석은 off 여도 모델 기본으로 생각
    assert _biz_conf() == {'tools': {'*': False}, 'provider': {'bizrouter': {'models': {'deepseek/deepseek-v4-flash-0731': {'options': {'reasoning': {'effort': 'none'}}}}}}}
    assert _call_bizcoder('s', 'u') == '답' and seen == [True, False]              # 거부 → 옵션 없이 다시
    assert _call_bizcoder('s', 'u') == '답' and seen == [True, False, False]       # 그 뒤 10분은 옵션 없이 한 번에
    _biz['think'], reject = 0, False
    assert _call_bizcoder('s', 'u') == '답' and seen[-1] is True             # 평소: 옵션을 주고 한 번에
    reject = True
    _biz_run = lambda exe, prompt, conf: ('', '로그인이 필요해요')                  # noqa: E731
    try:
        _call_bizcoder('s', 'u')
        raise AssertionError('오류가 나야 한다')
    except RuntimeError as e:
        assert 'bizcoder login' in str(e)
    # 가림 대상: 사내 LLM(BizCoder · 사내망 Ollama)은 가리지 않고, 회사 밖으로 나가는 Ollama 는 가린다
    st = {'ready': True}
    ollama_status = lambda cfg, force=False: st      # noqa: E731
    _active['kind'] = 'bizcoder'
    assert internal() and not external()
    _active['kind'], OLLAMA['url'] = 'ollama', 'http://10.10.1.20:11434'
    assert internal() and not external()                                           # 사내망 서버의 모델
    st = {'ready': True, 'cloud': True}
    assert external() and not internal()                                           # ollama.com 에서 도는 클라우드 모델
    st = {'ready': False}
    assert external()                                                              # 서버 확인이 안 됨 → 안전한 쪽(가림)
    st, OLLAMA['url'] = {'ready': True}, 'https://ollama.com'
    assert external()                                                              # ollama.com API 를 직접 부름
    _active['kind'] = 'nvidia'
    assert external() and not internal()
    # 가림: 여러 스레드가 Masker 하나를 같이 써도 같은 값은 같은 토큰, 다른 값은 다른 토큰 — 되돌리면 원문
    from concurrent.futures import ThreadPoolExecutor
    mk, src = Masker(['휴대전화번호']), [f'연락처 010-{1000 + i % 7}-{5000 + i % 7}' for i in range(200)]
    with ThreadPoolExecutor(8) as ex:
        out = list(ex.map(mk.mask, src))
    assert len(mk.map) == 7 and mk.unmask(out) == src and not any('010-' in o for o in out)
    # 줄이기: 기준(90자)을 넘겨 줄인 항목만 더 짧은 목표로 한 번 더, 이미 맞는 항목은 그대로
    asks, available = [], (lambda: True)

    def call_json(system, user, max_tokens=2500, fast=False):        # noqa: F811
        lim = int(re.search(r'(\d+)자 이내 한 문장', system).group(1))
        xs = json.loads(user.split('항목들: ', 1)[1].split('\n', 1)[0])
        asks.append((lim, len(xs)))
        return {'items': [('가' * 96 if i == 0 else '나' * 80) if lim == 90 else '라' * 95 if lim == 67 else '다' * 50 for i in range(len(xs))]}, 10
    out, meta = shorten(['x' * 120, 'y' * 130], {'use_llm': True})
    assert meta['mode'] == 'llm' and asks == [(90, 2), (67, 1), (54, 1)] and out == ['다' * 50, '나' * 80], (asks, out)
    # 기안문 설계도: 머리 · 요청 문장의 일 · 첨부 목록, 장 제목 줄 · 표 단위가 정리 뒤에도 남고, 없으면 키를 만들지 않는다
    c = _clean_bp({'title': 'T 추진 및 계약 체결 의뢰', 'recipient': '경영지원부장', 'purpose': '**T**', 'attachments': ['A 1부', '', 3],
                   'sections': [{'heading': '예산 현황', 'text': '소요 예산 신규 배정', 'items': [],
                                 'table': {'cols': ['a'], 'rows': [['1']], 'unit': '(단위 : 원)'}}]}, [])
    assert (c['recipient'], c['purpose'], c['attachments']) == ('경영지원부장', 'T', ['A 1부'])
    assert c['sections'][0]['text'] == '소요 예산 신규 배정' and c['sections'][0]['table']['unit'] == '(단위 : 원)'
    c = _clean_bp({'title': 'T', 'sections': [{'heading': 'h', 'items': [], 'table': {'cols': ['a'], 'rows': [['1']]}}]}, [])
    assert set(c) == {'title', 'sections'} and set(c['sections'][0]) == {'heading', 'items', 'table'} and 'unit' not in c['sections'][0]['table']
    print('llm selftest OK')
