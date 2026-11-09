"""스킬 빌더 끝까지 시험(실행 중인 앱에 HTTP로): 대표 문서 3건 → 분석 → 검증 → 등록(PR·병합).
python tests/e2e_skillgen.py [--scope me|team] [--base http://localhost:8810]
"""
import http.cookiejar
import json
import mimetypes
import os
import sys
import time
import urllib.request
import uuid

for s in (sys.stdout, sys.stderr):
    s.reconfigure(encoding='utf-8', errors='replace')
BASE = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else 'http://localhost:8810'
SCOPE = sys.argv[sys.argv.index('--scope') + 1] if '--scope' in sys.argv else 'me'
UID = sys.argv[sys.argv.index('--uid') + 1] if '--uid' in sys.argv else 'u1'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'seed', 'out', '대표문서')
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(path, body=None, files=None, timeout=900):
    if files:
        b = uuid.uuid4().hex
        data = b''
        for name, p in files:
            data += (f'--{b}\r\nContent-Disposition: form-data; name="{name}"; filename="{os.path.basename(p)}"\r\n'
                     f'Content-Type: {mimetypes.guess_type(p)[0] or "application/octet-stream"}\r\n\r\n').encode() + open(p, 'rb').read() + b'\r\n'
        data += f'--{b}--\r\n'.encode()
        req = urllib.request.Request(BASE + path, data=data, headers={'content-type': f'multipart/form-data; boundary={b}'})
    else:
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'content-type': 'application/json'})
    d = json.loads(op.open(req, timeout=timeout).read().decode())
    if not d.get('ok'):
        raise SystemExit(f'{path}: {d}')
    return d


def main():
    call('/api/login', {'uid': UID})
    ids = [call('/api/upload', files=[('file', os.path.join(DOCS, f))])['upload']['id'] for f in sorted(os.listdir(DOCS))]
    print('uploaded', len(ids))
    t = time.time()
    j = call('/api/skillgen/analyze', {'upload_ids': ids, 'request': '영업팀 제안서 팩 만들어줘', 'scope': SCOPE})['job']
    a = j['analysis']
    print(f'② analyze {time.time() - t:.1f}s', a['meta']['mode'], 'base', a['base'], 'parent', a['parent'])
    print('   draft', j['draft']['id'], j['draft']['extends'], j['draft']['forms'][0]['outline'], [b['text'][:20] for b in j['draft']['blocks']])
    t = time.time()
    r = call(f"/api/skillgen/{j['id']}/evaluate", {'draft': j['draft']})['report']
    print(f'④ evaluate {time.time() - t:.1f}s auto_pass={r["auto_pass"]} with={r["with_score"]}/{r["full"]} without={r["without_score"]}/{r["full"]}')
    for c in r['criteria']:
        print('   ', '✅' if c['pass'] else '❌', c['name'], c.get('detail', ''))
    if '--no-submit' in sys.argv or not r['auto_pass']:
        sys.exit(0 if r['auto_pass'] else 1)
    need = next(c['human'] for c in r['criteria'] if c['id'] == 'human')
    t = time.time()
    q = call(f"/api/skillgen/{j['id']}/submit", {'thumbs': need})['request']
    print(f'⑤ submit {time.time() - t:.1f}s stage={q["stage"]} pr={q["pr_url"]}', [h['act'] for h in q['history']])


if __name__ == '__main__':
    main()
