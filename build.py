#!/usr/bin/env python3
"""グループサービスの帯を、載せる先のサイトごとに 1 枚の HTML（スタイル込み）にして dist/ へ出す。

使い方: python3 build.py
  dist/<id>.html     載せる先ごとの帯
  dist/assets/       ロゴ・写真
  dist/preview.html  表示の確認用ページ
"""
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / 'dist'
esc = html.escape  # 既定で引用符も置き換える（属性の値にそのまま使える）


def asset(base, name):
    """画像の URL。中身から作った印（?v=）を付けて、画像を差し替えたら古いキャッシュが使われないようにする。"""
    v = hashlib.sha256((HERE / 'assets' / name).read_bytes()).hexdigest()[:8]
    return f'{base}{name}?v={v}'


def minify_css(css):
    """コメントと余分な空白を落とす（サイトに出す HTML を軽くする）。"""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    lines = [re.sub(r'\s+', ' ', line).strip() for line in css.splitlines()]
    return '\n'.join(line for line in lines if line) + '\n'


def load():
    data = json.loads((HERE / 'services.json').read_text(encoding='utf-8'))
    ids = [s['id'] for s in data['services']]
    assert len(ids) == len(set(ids)), 'services.json: id が重なっている'
    for s in data['services']:
        for key in ('id', 'name', 'url', 'desc', 'cta', 'embed'):
            assert key in s, f"services.json: {s.get('id')} に {key} が無い"
        assert s['url'].startswith('https://'), f"services.json: {s['id']} の url は https:// で始める"
        if s.get('logo'):
            assert (HERE / 'assets' / s['logo']).is_file(), f"assets/{s['logo']} が無い"
    assert (HERE / 'assets' / data['operator']['photo']).is_file(), '運営者の写真が無い'
    return data


def cards_for(data, site_id, services=None):
    """載せる先 site_id に並べるサービス（自分は除く）。order_on に順番があればそれに従う。"""
    services = services if services is not None else data['services']
    others = [s for s in services if s['id'] != site_id]
    order = data.get('order_on', {}).get(site_id)
    if order:
        rank = {sid: i for i, sid in enumerate(order)}
        others.sort(key=lambda s: rank.get(s['id'], len(rank)))  # 並べ替えは安定。書いていないものは元の順で後ろ
    return others


def card_html(s, site_id, base):
    desc = s.get('desc_on', {}).get(site_id, s['desc'])
    if s.get('logo'):
        logo = f'<img class="cgs-logo" src="{esc(asset(base, s["logo"]))}" alt="" width="36" height="36" loading="lazy" decoding="async">'
    else:  # ロゴを載せないサービスは、頭文字の札にする
        logo = f'<span class="cgs-logo cgs-logo-txt" aria-hidden="true">{esc(s["name"][0])}</span>'
    tag = f'<br><span class="cgs-tag">{esc(s["tag"])}</span>' if s.get('tag') else ''
    return (
        '      <li class="cgs-card">\n'
        f'        <div class="cgs-top">{logo}<div class="cgs-name"><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a>{tag}</div></div>\n'
        f'        <p class="cgs-desc">{esc(desc)}</p>\n'
        f'        <div class="cgs-cta" aria-hidden="true">{esc(s["cta"])} →</div>\n'
        '      </li>\n'
    )


def band_html(data, site, services=None, all_url=None):
    """site（services.json の 1 件）に載せる帯の HTML（スタイルは含まない）。"""
    op = data['operator']
    base = site.get('asset_base', '/group-services/')
    cards = cards_for(data, site['id'], services)
    limit = data.get('max_cards', 10)
    all_url = all_url if all_url is not None else data.get('all_services_url')
    more = ''
    if len(cards) > limit and all_url:  # 上限を超えたら上位だけ出して、一覧ページへ送る
        cards = cards[:limit]
        more = f'    <p class="cgs-all"><a href="{esc(all_url)}" target="_blank" rel="noopener">すべてのサービスを見る</a></p>\n'
    lead = data['lead'].replace('{site}', site['name'])
    # 載せる先の本文の幅と、カードの最小の幅（px）。書いていなければ CSS の既定
    props = []
    if site.get('max_width'):
        props.append(f'--cgs-max: {int(site["max_width"])}px')
    if site.get('min_card'):
        props.append(f'--cgs-min: {int(site["min_card"])}px')
    width = f' style="{"; ".join(props)}"' if props else ''
    return (
        f'<section class="cgs" aria-label="{esc(data["heading"])}"{width}>\n'
        '  <div class="cgs-in">\n'
        f'    <h2 class="cgs-h">{esc(data["heading"])}</h2>\n'
        f'    <p class="cgs-lead">{esc(lead)}</p>\n'
        '    <ul class="cgs-list">\n'
        '      <li class="cgs-op">\n'
        f'        <img class="cgs-op-ph" src="{esc(asset(base, op["photo"]))}" alt="{esc(op["person"])}" width="60" height="60" loading="lazy" decoding="async">\n'
        '        <div>\n'
        f'          <div class="cgs-op-l">{esc(op["label"])}</div>\n'
        f'          <div class="cgs-op-c"><a href="{esc(op["company_url"])}" target="_blank" rel="noopener">{esc(op["company"])}</a></div>\n'
        f'          <div class="cgs-op-n">{esc(op["title"])} {esc(op["person"])}</div>\n'
        '        </div>\n'
        '      </li>\n'
        + ''.join(card_html(s, site['id'], base) for s in cards) +
        '    </ul>\n'
        + more +
        '  </div>\n'
        '</section>\n'
    )


def main():
    data = load()
    css = minify_css((HERE / 'band.css').read_text(encoding='utf-8'))
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / 'assets').mkdir(parents=True)
    for f in sorted((HERE / 'assets').iterdir()):
        shutil.copy2(f, DIST / 'assets' / f.name)

    sites = [s for s in data['services'] if s['embed']]
    preview = []
    for site in sites:
        body = band_html(data, site)
        stamp = hashlib.sha256((css + body).encode('utf-8')).hexdigest()[:12]
        out = (f'<!-- group-services {stamp} -->\n'
               f'<style>\n{css}</style>\n{body}')
        (DIST / f'{site["id"]}.html').write_text(out, encoding='utf-8')
        print(f'{site["id"]}.html  {stamp}  {len(out.encode("utf-8"))} bytes  カード {len(cards_for(data, site["id"]))} 枚')
        # 確認用のページでは、画像を dist/assets/ から読む
        preview.append((f'{site["name"]} に載せる帯', band_html(data, {**site, 'asset_base': 'assets/'})))

    # サービスが増えた場合の見え方（確認用ページにだけ出す）
    first = {**sites[0], 'asset_base': 'assets/'}
    for extra, all_url in ((2, None), (5, None), (9, 'https://seo.contencial.co.jp/')):
        dummy = [{'id': f'demo{i}', 'name': f'サービス{i + 1}', 'url': 'https://example.com/', 'logo': None,
                  'desc': '増えた場合の見え方を確かめるための仮のカード', 'cta': '無料で試す', 'embed': False}
                 for i in range(extra)]
        label = f'【確認用】サービスが {extra} 個増えた場合（{sites[0]["name"]}）' + ('・上限を超えた分は一覧へ' if all_url else '')
        preview.append((label, band_html(data, first, data['services'] + dummy, all_url)))

    page = ['<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta name="robots" content="noindex">\n<title>グループサービスの帯（確認用）</title>\n'
            '<style>body{margin:0;font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;background:#fff;color:#111}'
            '.pv-l{margin:0;padding:18px 16px 8px;font-size:13px;font-weight:700;color:#b45309}'
            '.pv-f{background:#172554;color:#bfdbfe;padding:22px 16px;font-size:12px}</style>\n'
            f'<style>\n{css}</style>\n</head>\n<body>\n']
    for label, body in preview:
        page.append(f'<p class="pv-l">{esc(label)}</p>\n{body}<div class="pv-f">（ここからサイトのフッター）</div>\n')
    page.append('</body>\n</html>\n')
    (DIST / 'preview.html').write_text(''.join(page), encoding='utf-8')
    print('preview.html')


if __name__ == '__main__':
    main()
