"""설정 · DB · 조직/권한 · 감사 로그.

데이터는 사용자 PC의 KOSOE_HOME(기본 %USERPROFILE%\\.kosoe)에 둔다. 앱 폴더(git clone)는 읽기 전용처럼 쓴다.
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_env():
    """`.env`(KEY=VALUE)를 읽는다. 실제 환경 변수가 있으면 그쪽이 우선."""
    env = {}
    p = os.path.join(ROOT, '.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    get = lambda k, d='': os.environ.get(k) or env.get(k) or d
    key = get('KOSOE_LLM_API_KEY')
    kind = get('KOSOE_AI', 'claude_cli')          # claude_cli | nvidia | openrouter | anthropic | openai_compat | rule
    kind = {'cli': 'claude_cli', 'openai': 'openai_compat'}.get(kind, kind)           # + openrouter
    return {
        'home': os.path.expanduser(get('KOSOE_HOME', os.path.join('~', '.kosoe'))),
        'llm_kind': kind,
        'llm_key': key,
        'llm_model': get('KOSOE_LLM_MODEL', 'sonnet' if kind == 'claude_cli' else ''),
        'llm_fast': get('KOSOE_LLM_FAST_MODEL', 'haiku' if kind == 'claude_cli' else ''),
        'llm_effort': get('KOSOE_LLM_EFFORT', 'low' if kind == 'claude_cli' else ''),
        'llm_base': get('KOSOE_LLM_BASE_URL', 'https://api.anthropic.com').rstrip('/'),
        'claude_cli': get('KOSOE_CLAUDE_CLI'),
        'cli_model': get('KOSOE_CLAUDE_MODEL', get('KOSOE_LLM_MODEL', 'sonnet') if kind == 'claude_cli' else 'sonnet'),
        'cli_fast': get('KOSOE_CLAUDE_FAST_MODEL', get('KOSOE_LLM_FAST_MODEL', 'haiku') if kind == 'claude_cli' else 'haiku'),
        'or_key': get('KOSOE_OPENROUTER_API_KEY'),
        'or_models': [m.strip() for m in get('KOSOE_OPENROUTER_MODELS', 'deepseek/deepseek-v4.1-flash,nvidia/nemotron-3-ultra-550b-a55b:free,nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,google/gemma-4-31b-it:free').split(',') if m.strip()],
        'or_model': get('KOSOE_OPENROUTER_MODEL', '') or [m.strip() for m in get('KOSOE_OPENROUTER_MODELS', 'deepseek/deepseek-v4.1-flash').split(',')][0],
        'nv_key': get('KOSOE_NVIDIA_API_KEY'),                              # build.nvidia.com 무료 체험 엔드포인트(평가용)
        'nv_models': [m.strip() for m in get('KOSOE_NVIDIA_MODELS', 'deepseek-ai/deepseek-v4.1-flash,nvidia/nemotron-3-ultra-550b-a55b').split(',') if m.strip()],
        'nv_thinking': get('KOSOE_NVIDIA_THINKING', 'off'),                 # off(추론 끔 — 빠르고 답이 비지 않음) | on
        'nv_base': get('KOSOE_NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1').rstrip('/'),
        'nv_extra': get('KOSOE_NVIDIA_EXTRA_BODY', ''),                     # 요청 본문에 더할 JSON(추론 끄기 등 모델별 옵션)
        'or_reasoning': get('KOSOE_OPENROUTER_REASONING', 'low'),          # off | low | medium | high | default
        'or_reason_budget': int(get('KOSOE_OPENROUTER_REASON_BUDGET', '3000')),
        'claude_token': get('KOSOE_CLAUDE_TOKEN'),
        'closed_llm': get('KOSOE_CLOSED_LLM', 'same'),
        'skills_repo': get('KOSOE_SKILLS_REPO', 'humanist96/kosoe-office-skills'),
        'skills_offline': get('KOSOE_SKILLS_OFFLINE', '') == '1',
        'corp_local': get('KOSOE_CORP_LOCAL', ''),                 # 원격에 올리기 전의 전사 스킬을 이 PC 저장소에서 쓰기: id=경로;id=경로
        'ppt_engine': get('KOSOE_PPT_ENGINE', 'ppt-master'),      # ppt-master | lite
        'port': int(os.environ.get('PORT') or get('KOSOE_PORT', '8810')),
    }


CFG = load_env()
HOME = CFG['home']
DATA = HOME
for d in ('', 'out', 'uploads', 'jobs', 'llm-cli', 'corp'):
    os.makedirs(os.path.join(HOME, d), exist_ok=True)
DB_PATH = os.path.join(HOME, 'kosoe.db')
_lock = threading.RLock()

GRADE = {'c': '대외비', 'i': '사내한정', 'n': '일반'}
FMT = {'hwp': '한글', 'ppt': 'PPT', 'web': '웹슬라이드', 'xlsx': '엑셀'}   # 엑셀은 서식 채우기형 전사 스킬(견적서 등)로만 만든다
ROLE = {'user': '일반 사용자', 'lead': '팀장', 'deptAdmin': '부서 관리자', 'corpAdmin': '전사 관리자', 'security': '보안 관리자'}

# 가상 조직 (SSO 자리). org = '본부/팀'
USERS = [
    ('u1', '홍길동', '대리', '금융영업1팀', '금융영업본부', 'user', '#1f4b9b'),
    ('u2', '김철수', '팀장', '금융영업1팀', '금융영업본부', 'lead', '#2b2b2e'),
    ('u3', '이영희', '차장', '금융영업2팀', '금융영업본부', 'deptAdmin', '#b85415'),
    ('u4', '박지원', '부장', '경영기획팀', '경영기획본부', 'corpAdmin', '#00338d'),
    ('u5', '최수민', '과장', '정보보호팀', 'IT운영본부', 'security', '#1f7a4d'),
]


def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    con.row_factory = sqlite3.Row
    return con


SCHEMA = '''
create table if not exists users(id text primary key, name text, title text, team text, dept text, role text, color text, net text default 'closed');
create table if not exists templates(id text primary key, name text, fmt text, use text, scope text, outline text, desc text, preset text,
  grade text, dept text, team text, owner text, uses int, ver text, path text, tag text, fields text, rules text, fixed text, pr text, created text,
  skill text);
create table if not exists uses(template_id text primary key, n int);
create table if not exists requests(id text primary key, name text, fmt text, scope text, requester text, dept text, team text, stage text,
  outline text, fields text, rules text, fixed text, branch text, pr_number int, pr_url text, path text, note text, history text, created text, updated text);
create table if not exists docs(id text primary key, title text, template_id text, fmt text, grade text, owner text, acl text, ver int,
  blueprint text, made text, created text, updated text);
create table if not exists doc_files(doc_id text, ver int, fmt text, path text, checks text, warns text, elapsed_ms int, llm text, created text,
  resolution text);
create table if not exists compose(id text primary key, owner text, template_id text, fmt text, grade text, title text, blueprint text,
  chat text, files text, started real, doc_id text, llm text, source text);
create table if not exists uploads(id text primary key, owner text, name text, path text, kind text, text text, tables text, drm int, created text);
create table if not exists skill_jobs(id text primary key, owner text, request text, scope text, stage text, files text, analysis text,
  skill text, report text, request_id text, created text, updated text);
create table if not exists ireq(id text primary key, uid text, team text, purpose text, days int, feats text, status text, until text, decided_by text, created text);
create table if not exists events(id integer primary key autoincrement, t text, who text, what text);
create table if not exists policy(k text primary key, v text);
'''


def init_db():
    with _lock:
        con = db()
        con.executescript(SCHEMA)
        if not con.execute('select 1 from users limit 1').fetchone():
            con.executemany('insert into users(id,name,title,team,dept,role,color) values(?,?,?,?,?,?,?)', USERS)
            con.executemany('insert into policy values(?,?)', [('maxDays', '30'), ('feats', json.dumps({'ai': True, 'search': True, 'access': True})),
                                                               ('mask', json.dumps(['주민등록번호', '휴대전화번호', '고객사명', '계좌번호'], ensure_ascii=False))])
            con.execute('insert into events(t,who,what) values(?,?,?)', (now(), '시스템', '코쇠오피스 초기화 — 가상 조직 5명'))
        con.commit()
        con.close()


def now(fmt='%m/%d %H:%M'):
    return datetime.now().strftime(fmt)


def today_kr():
    d = datetime.now()
    return f'{d.year}. {d.month}. {d.day}'


def log(who, what):
    with _lock:
        con = db()
        con.execute('insert into events(t,who,what) values(?,?,?)', (now(), who, what))
        con.commit()
        con.close()


def row(con, sql, *a):
    r = con.execute(sql, a).fetchone()
    return dict(r) if r else None


def rows(con, sql, *a):
    return [dict(r) for r in con.execute(sql, a).fetchall()]


def get_user(con, uid):
    return row(con, 'select * from users where id=?', uid)


def lead_of(con, team):
    return row(con, "select * from users where team=? and role='lead'", team)


def inet_active(con, uid):
    r = row(con, "select * from ireq where uid=? and status='ok' order by created desc", uid)
    if r and r['until'] and datetime.strptime(r['until'], '%Y-%m-%d') >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
        return r
    return None


def can_use_template(t, u, net='closed'):
    if net == 'internet' and t['grade'] == 'c':
        return False
    if u['role'] in ('corpAdmin',):
        return True
    return (t['scope'] == 'corp' or (t['scope'] == 'dept' and t['dept'] == u['dept'])
            or (t['scope'] == 'team' and t['team'] == u['team']) or (t['scope'] == 'me' and t['owner'] == u['id']))


def doc_perm(d, u):
    """'m'(관리) / 'w'(쓰기) / 'r'(읽기) / ''(없음)."""
    if d['owner'] == u['id']:
        return 'm'
    best = ''
    for a in json.loads(d['acl'] or '[]'):
        hit = (a['t'] == 'user' and a['v'] == u['name']) or (a['t'] == 'team' and a['v'] == u['team']) or \
              (a['t'] == 'dept' and a['v'] == u['dept']) or a['t'] == 'corp'
        if hit and (a['p'] == 'w' or not best):
            best = a['p']
    return best


def acl_allowed(grade, t):
    """등급별 공유 상한: 대외비 = 사람·팀까지."""
    return grade != 'c' or t in ('user', 'team')


def until_date(days):
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')


def new_id(prefix):
    return f'{prefix}{int(time.time() * 1000) % 10**10:x}'
