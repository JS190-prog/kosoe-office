"""문서 테마(PPT·웹슬라이드 디자인 9가지)에 쓰는 그림을 만든다 — 한 번 돌려 static/doc_themes/ 에 둔다.

    python doc_theme_assets.py

- 재료는 화면 테마의 그림(static/themes/<id>/hero.webp·banner.webp)이다. 새 그림을 만들지 않는다.
- ppt/<id>_cover.jpg : PPT 표지 바탕(1280×720, 글자가 놓일 왼쪽을 덮는 그라데이션까지 한 장으로 합침 — PPT에서 한 그림으로 들어간다)
- img/<id>_<name>.webp : 웹슬라이드 표지·어두운 장 바탕(줄인 것)
미리보기(thumb/)는 tests/doc_theme_previews.py 가 만든다.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'static', 'themes')
OUT = os.path.join(ROOT, 'static', 'doc_themes')
W, H = 1280, 720


def load(tid, name):
    return Image.open(os.path.join(SRC, tid, name + '.webp')).convert('RGB')


def cover_fit(im, w, h, ax=0.5, ay=0.5):
    """w×h를 꽉 채우도록 잘라 맞춘다(ax·ay: 0=왼쪽/위, 1=오른쪽/아래를 남김)."""
    s = max(w / im.size[0], h / im.size[1])
    im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
    x, y = round((im.size[0] - w) * ax), round((im.size[1] - h) * ay)
    return im.crop((x, y, x + w, y + h))


def overlay(base, rgb, stops):
    """가로 그라데이션 덮개. stops = [(위치 0~1, 불투명도 0~1), …]"""
    mask = Image.new('L', (W, 1))
    px = mask.load()
    for x in range(W):
        t = x / (W - 1)
        for (p0, a0), (p1, a1) in zip(stops, stops[1:]):
            if p0 <= t <= p1:
                px[x, 0] = round(255 * (a0 + (a1 - a0) * (t - p0) / max(p1 - p0, 1e-6)))
                break
    return Image.composite(Image.new('RGB', (W, H), rgb), base, mask.resize((W, H)))


def ppt_covers():
    out = {}
    out['a'] = overlay(cover_fit(load('a', 'hero'), W, H, 1, .5), (10, 28, 54), [(0, .97), (.46, .88), (1, .36)])
    out['c'] = overlay(cover_fit(load('c', 'hero'), W, H, 1, .5), (10, 13, 16), [(0, .95), (.44, .8), (1, .22)])
    out['g'] = overlay(cover_fit(load('g', 'hero'), W, H, .5, .5), (19, 35, 58), [(0, .96), (.5, .78), (1, .26)])
    out['f'] = overlay(cover_fit(load('f', 'hero'), W, H, 1, .5), (0, 40, 120), [(0, .9), (.42, .62), (.8, 0), (1, 0)])
    b = Image.new('RGB', (W, H), (239, 239, 239))
    hb = load('b', 'hero')
    hb = hb.resize((round(hb.size[0] * H * .96 / hb.size[1]), round(H * .96)), Image.LANCZOS)
    b.paste(hb, (W - hb.size[0] + 40, round(H * .02)))
    out['b'] = overlay(b, (255, 255, 255), [(0, 1), (.38, .97), (.68, 0), (1, 0)])
    d = Image.new('RGB', (W, H), (247, 248, 247))
    hd = load('d', 'hero')
    hd = hd.resize((round(hd.size[0] * H / hd.size[1]), H), Image.LANCZOS)
    d.paste(hd, (W - hd.size[0], 0))
    out['d'] = overlay(d, (251, 251, 250), [(0, 1), (.4, .96), (.7, 0), (1, 0)])
    e = Image.new('RGB', (W, H), (255, 255, 255))
    he = load('e', 'hero')
    he = he.resize((560, round(he.size[1] * 560 / he.size[0])), Image.LANCZOS)
    e.paste(he, (W - 560 - 40, H - he.size[1] - 96))
    out['e'] = e
    h = Image.new('RGB', (W, H), (244, 244, 241))
    h.paste(cover_fit(load('h', 'hero'), 538, H, .5, .5), (W - 538, 0))
    out['h'] = h
    os.makedirs(os.path.join(OUT, 'ppt'), exist_ok=True)
    for tid, im in out.items():
        im.save(os.path.join(OUT, 'ppt', f'{tid}_cover.jpg'), 'JPEG', quality=86, optimize=True)
        print('ppt', tid, os.path.getsize(os.path.join(OUT, 'ppt', f'{tid}_cover.jpg')) // 1024, 'KB')


def web_images():
    os.makedirs(os.path.join(OUT, 'img'), exist_ok=True)
    for tid, name, width, q in [('a', 'hero', 1600, 80), ('b', 'hero', 1600, 80), ('c', 'hero', 1600, 80), ('d', 'hero', 1400, 72), ('e', 'hero', 1200, 80),
                                ('f', 'hero', 1600, 80), ('g', 'hero', 1600, 80), ('g', 'banner', 1600, 78), ('h', 'hero', 1000, 76)]:
        im = load(tid, name)
        if im.size[0] > width:
            im = im.resize((width, round(im.size[1] * width / im.size[0])), Image.LANCZOS)
        p = os.path.join(OUT, 'img', f'{tid}_{name}.webp')
        im.save(p, 'WEBP', quality=q, method=6)
        print('web', tid, name, os.path.getsize(p) // 1024, 'KB')


if __name__ == '__main__':
    ppt_covers()
    web_images()
