"""녹화본 편집: 대기 구간(AI·Git 처리)을 빨리 감고, 나머지는 원래 속도로 이어 붙여 mp4로.
python tests/make_video.py <녹화 폴더(raw.webm, marks.json)> <출력.mp4> [--wait 2.0] [--act 1.0]
"""
import json
import os
import subprocess
import sys

src = sys.argv[1]
out = sys.argv[2]
WAIT = float(sys.argv[sys.argv.index('--wait') + 1]) if '--wait' in sys.argv else 2.0
ACT = float(sys.argv[sys.argv.index('--act') + 1]) if '--act' in sys.argv else 1.0
m = json.load(open(os.path.join(src, 'marks.json'), encoding='utf-8'))
raw = os.path.join(src, 'raw.mp4')
if not os.path.exists(raw):
    # 스크린캐스트 프레임(화면이 바뀔 때만 들어옴)을 30fps 고정 영상으로: 각 출력 시각에 그 직전 프레임을 쓴다
    fr = json.load(open(os.path.join(src, 'frames.json'), encoding='utf-8'))
    binf = open(os.path.join(src, 'frames.bin'), 'rb')
    p = subprocess.Popen(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'mjpeg', '-i', '-',
                          '-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', raw], stdin=subprocess.PIPE)
    # 화면이 멈추면 프레임이 안 들어오므로 마지막 표시(end)까지 마지막 프레임을 늘린다 — 안 그러면 맺음 장면이 1초 만에 잘린다
    k, last, n_out = 0, None, int((max(fr[-1]['t'], max(x['t'] for x in m['marks'])) + 1.0) * 30)
    for i in range(n_out):
        t = i / 30
        while k + 1 < len(fr) and fr[k + 1]['t'] <= t:
            k += 1
        if last is None or last[0] != k:
            binf.seek(fr[k]['o'])
            last = (k, binf.read(fr[k]['n']))
        p.stdin.write(last[1])
    p.stdin.close()
    p.wait()
    print('원본 조립', raw)
marks = m['marks']
start = max(0.0, next(x['t'] for x in marks if x['type'] == 'scene') - 0.2)
END = float(sys.argv[sys.argv.index('--end') + 1]) if '--end' in sys.argv else None
end = END or next((x['t'] for x in marks if x['type'] == 'end'), marks[-1]['t'] + 8) + 0.5

# 구간 나누기
segs, cur, wait_from, label = [], start, None, ''
for x in marks:
    if x['type'] == 'wait-start':
        if x['t'] > cur:
            segs.append((cur, x['t'], 'act', ''))
        wait_from, label, cur = x['t'], x['label'], x['t']
    elif x['type'] == 'wait-end' and wait_from is not None:
        segs.append((wait_from, x['t'], 'wait', label))
        cur, wait_from = x['t'], None
segs.append((cur, end, 'act', ''))
segs = [s for s in segs if s[1] - s[0] > 0.05]

FONT = 'C\\:/Windows/Fonts/malgunbd.ttf'
parts, labels, total = [], [], 0.0
for i, (a, b, kind, lab) in enumerate(segs):
    d = b - a
    if kind == 'wait' and d > WAIT:
        sp = d / WAIT
        spt = f'{sp:.0f}' if sp >= 10 else f'{sp:.1f}'   # 짧은 대기(×1.4)가 「×1」로 보이지 않게
        txt = f'▶▶ 빨리 감기 ×{spt}  ·  {lab} 실제 {d:.0f}초'.replace(':', '\\:').replace("'", '')
        f = (f"[0:v]trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{sp:.4f},"
             f"drawtext=fontfile='{FONT}':text='{txt}':fontcolor=white:fontsize=24:x=w-tw-32:y=83:"   # 상자가 글자 길이를 따라간다(긴 라벨이 화면 밖으로 잘리지 않게)
             f"box=1:boxcolor=0xee6d1d@0.92:boxborderw=14,format=yuv420p,setsar=1[v{i}]")
        total += WAIT
    else:
        f = f"[0:v]trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{ACT:.4f},format=yuv420p,setsar=1[v{i}]"
        total += d / ACT
    parts.append(f)
    labels.append(f'[v{i}]')
# 원본 크기(스크린캐스트는 뷰포트와 조금 다를 수 있다)
_wh = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', raw],
                     capture_output=True, text=True).stdout.strip().split(',')
RW, RH = int(_wh[0]), int(_wh[1])
# 맺음 카드(4초)
FONTR = FONT.replace('malgunbd', 'malgun')
oc = (f"color=c=0x0b1830:s={RW}x{RH}:d=4:r=30,drawtext=fontfile='{FONT}':text='코쇠오피스':fontcolor=white:fontsize=64:x=(w-tw)/2:y=270,"
      f"drawtext=fontfile='{FONTR}':text='회사 양식대로 만들고 고치고 검수까지 — PPT · 웹슬라이드 · 한글':fontcolor=0xffd9c2:fontsize=26:x=(w-tw)/2:y=370,"
      f"drawtext=fontfile='{FONTR}':text='대표 문서 몇 건이면 우리 부서 스킬 · 전사 공용 스킬 상속 · 정본은 Git':fontcolor=white:fontsize=24:x=(w-tw)/2:y=420,"
      f"drawtext=fontfile='{FONTR}':text='2차 리허설 실제 화면 녹화 · 대기 구간은 빨리 감기 · 가상 조직·가상 데이터':fontcolor=0x9fb0d0:fontsize=18:x=(w-tw)/2:y=520,"
      f"format=yuv420p,setsar=1[outro]")
parts.append(oc)
labels.append('[outro]')
total += 4
fc = ';'.join(parts) + ';' + ''.join(labels) + f'concat=n={len(labels)}:v=1:a=0,scale=1920:-2:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0b1830,fps=30,format=yuv420p[out]'
fcf = os.path.join(src, 'filter.txt')
open(fcf, 'w', encoding='utf-8').write(fc)
print(f'구간 {len(segs)}개 · 예상 길이 {total:.0f}초 ({total / 60:.1f}분)')
cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', raw, '-/filter_complex', fcf,
       '-map', '[out]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-movflags', '+faststart', out]
r = subprocess.run(cmd)
if r.returncode == 0:
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out], capture_output=True, text=True)
    print('완료', out, f'{float(p.stdout.strip()):.1f}초', f'{os.path.getsize(out) / 1e6:.1f}MB')
sys.exit(r.returncode)
