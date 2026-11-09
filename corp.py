"""전사 공용 스킬 레지스트리 — registry/corp.lock.yaml 의 SHA로 고정된 전사 스킬을 PC에 받아 둔다.

- 캐시: <KOSOE_HOME>/corp/<id>/<sha12>/  (blob:none 부분 복제 + 해당 SHA 체크아웃)
- 사내 보호 도구(PIA)가 디스크의 .hwp·.pptx를 암호화할 수 있으므로, 입력 템플릿은 쓸 때마다
  git 객체에서 작업 폴더로 새로 꺼낸다(fresh_copy). 캐시의 템플릿 파일을 직접 쓰지 않는다.
"""
import os
import threading

import yaml

from core import HOME
from gitutil import GitError, git, git_remote

CORP = os.path.join(HOME, 'corp')
_lock = threading.RLock()
_lockfile = {'data': None, 'sha': None}

# 전사 스킬별 실제로 쓰는 하위 경로(희소 체크아웃). ppt-master 템플릿 폴더 전체는 1만 개가 넘어 필요한 덱만 받는다.
SPARSE = {
    'koscom-doc-pack': ['.claude/skills/ppt-master/scripts', '.claude/skills/ppt-master/templates/decks/koscom-chevron',
                        '.claude/skills/koscom-doc-pack', '.claude/skills/koscom-hwp-report/templates/presets'],
}


def _g(*a, cwd=None, **k):
    """부분 복제(blob:none)는 파일을 읽을 때 원격에서 받아 오므로, 캐시 안의 모든 git 명령에 gh 자격 증명을 붙인다."""
    return git_remote('-c', 'core.quotepath=false', *a, cwd=cwd, **k)
# 포털이 부르는 진입점(상대 경로)
ENTRY = {
    'koscom-hwp-report': {'jar': 'scripts/koscom-hwp.jar', 'lib': 'lib/hwplib-1.1.9.jar', 'templates': 'templates',
                          'guide': ['references/writing_guide.md', 'references/style_map.md']},
    'koscom-doc-pack': {'ppt_master': '.claude/skills/ppt-master', 'router': '.claude/skills/koscom-doc-pack/workflows/doc-routing.md',
                        'chevron': '.claude/skills/ppt-master/templates/decks/koscom-chevron/templates'},
    'koscom-webslide': {'root': ''},
    'kosoe-illustrations': {'root': ''},
}


def set_lock(data, sha):
    with _lock:
        _lockfile.update(data=data, sha=sha)


def lock():
    return _lockfile['data'] or {'corp_skills': {}, 'locked_keys': []}


def info(cid):
    return lock()['corp_skills'].get(cid)


def cache_dir(cid):
    c = info(cid)
    if not c:
        raise KeyError(f'전사 스킬 잠금 파일에 없는 id: {cid}')
    return os.path.join(CORP, cid, c['sha'][:12])


def ensure(cid):
    """해당 SHA의 전사 스킬을 받아 둔다. 돌려주는 값: 스킬 루트 폴더(path 반영)."""
    c = info(cid)
    d = cache_dir(cid)
    with _lock:
        mark = os.path.join(d, '.git', 'kosoe-ok')
        if not os.path.exists(mark):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            url = f"https://github.com/{c['repo']}.git"
            if os.path.isdir(d):
                import shutil
                shutil.rmtree(d, ignore_errors=True)
            _g('clone', '-q', '--filter=blob:none', '--no-checkout', url, d, timeout=600)
            if cid in SPARSE:
                _g('config', 'core.sparseCheckout', 'true', cwd=d)
                _g('config', 'core.sparseCheckoutCone', 'true', cwd=d)
                info_dir = os.path.join(d, '.git', 'info')
                os.makedirs(info_dir, exist_ok=True)
                with open(os.path.join(info_dir, 'sparse-checkout'), 'w', encoding='utf-8', newline='\n') as f:
                    f.write('/*\n!/*/\n')                         # cone: 루트 파일 + 지정 폴더
                    seen = set()
                    for p in SPARSE[cid]:
                        parts = p.split('/')
                        for i in range(1, len(parts)):
                            pre = '/'.join(parts[:i])
                            if pre not in seen:
                                f.write(f'/{pre}/\n!/{pre}/*/\n')
                                seen.add(pre)
                        f.write(f'/{p}/\n')
            _g('-c', 'advice.detachedHead=false', 'checkout', '-q', c['sha'], cwd=d, timeout=900)
            open(mark, 'w').write(c['sha'])
        elif _g('rev-parse', 'HEAD', cwd=d, check=False).strip() != c['sha']:
            _g('fetch', '-q', 'origin', cwd=d, timeout=300, check=False)
            _g('-c', 'advice.detachedHead=false', 'checkout', '-q', '-f', c['sha'], cwd=d, timeout=900)
    return os.path.join(d, *(c.get('path') or '').split('/')) if c.get('path') else d


def path(cid, rel=''):
    root = ensure(cid)
    return os.path.join(root, *rel.split('/')) if rel else root


def fresh_copy(cid, rel_files, dest):
    """git 객체에서 파일을 꺼내 dest에 쓴다(사내 보호 도구가 캐시 파일을 바꿔 놓았어도 원본을 쓴다)."""
    c = info(cid)
    d = cache_dir(cid)
    ensure(cid)
    prefix = (c.get('path') + '/') if c.get('path') else ''
    os.makedirs(dest, exist_ok=True)
    out = []
    for rel in rel_files:
        data = _g('show', f"{c['sha']}:{prefix}{rel}", cwd=d, binary=True)
        p = os.path.join(dest, os.path.basename(rel))
        with open(p, 'wb') as f:
            f.write(data)
        out.append(p)
    return out


def read_text(cid, rel):
    c = info(cid)
    d = cache_dir(cid)
    ensure(cid)
    prefix = (c.get('path') + '/') if c.get('path') else ''
    return _g('show', f"{c['sha']}:{prefix}{rel}", cwd=d, binary=True).decode('utf-8', 'replace')


def status():
    out = []
    for cid, c in lock()['corp_skills'].items():
        d = os.path.join(CORP, cid, c['sha'][:12])
        out.append({'id': cid, 'repo': c['repo'], 'sha': c['sha'], 'short': c['sha'][:7], 'cached': os.path.exists(os.path.join(d, '.git', 'kosoe-ok'))})
    return out


def warm(log=print):
    """전사 스킬을 모두 받아 둔다(설치·첫 실행). 실패해도 나머지는 계속."""
    res = {}
    for cid in lock()['corp_skills']:
        try:
            ensure(cid)
            res[cid] = 'ok'
        except (GitError, Exception) as e:
            res[cid] = f'실패: {str(e)[:160]}'
        log(f'  전사 스킬 {cid}: {res[cid]}')
    return res


def load_yaml_text(text):
    return yaml.safe_load(text) or {}
