#!/usr/bin/env python3
"""グループサービスの帯を、載せる先のサイトごとに 1 枚の HTML（スタイル込み）にして dist/ へ出す。

使い方: python3 build.py
  dist/<id>.html     載せる先ごとの帯
  dist/assets/       ロゴ・写真
  dist/remote/<id>.html  各サイトが取りに行く帯（画像は jsDelivr から読む。__CGS_REF__ をコミットの番号に置き換えて使う）
  dist/wordpress/    WordPress の mu-plugins に置くもの（本体・帯・画像）
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

# 各サイトが取りに行く帯の画像の置き場。__CGS_REF__ は、取りに行く側がコミットの番号に置き換える
# （jsDelivr はコミットの番号の URL の中身を変えない。ブランチ名の URL は最大 12 時間前の中身を返す）。
REF_MARK = '__CGS_REF__'
REMOTE_ASSET_BASE = f'https://cdn.jsdelivr.net/gh/contencial/group-services@{REF_MARK}/dist/assets/'


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
    for s in data.get('sites', []):
        assert s['id'] not in ids, f"services.json: sites の id {s['id']} がサービスと重なっている"
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


GAP = 12        # カードの間（px。band.css の --cgs-gap と同じ）
MIN_CARD = 165  # カードの最小の幅の既定（px）


def best_cols(n, max_cols):
    """n 枚を、1 行 max_cols 枚までで並べるときの 1 行の枚数。行の数を最少にしたうえで、各行の枚数がなるべくそろう数。"""
    max_cols = max(1, min(n, max_cols))
    rows = -(-n // max_cols)
    return -(-n // rows)


def layout_css(site, n):
    """帯の幅ごとの 1 行の枚数（コンテナ クエリ）。帯の幅は .cgs-in の幅。"""
    m = int(site.get('min_card') or MIN_CARD)
    key = f'{n}-{m}'
    sel = f'.cgs[data-cgs-layout="{key}"] ul.cgs-list'
    rules = [f'{sel} {{ --cgs-cols: {min(2, n)}; }}']
    prev = min(2, n)
    for c in range(2, n + 1):
        cols = best_cols(n, c)
        if cols == prev:
            continue
        width = c * m + (c - 1) * GAP  # c 枚が最小の幅で入る帯の幅
        rules.append(f'@container (min-width: {width}px) {{ {sel} {{ --cgs-cols: {cols}; }} }}')
        prev = cols
    return key, '\n'.join(rules) + '\n'


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
    cards, all_url, over = shown_cards(data, site, services, all_url)
    more = ''
    if over:
        more = f'    <p class="cgs-all"><a href="{esc(all_url)}" target="_blank" rel="noopener">すべてのサービスを見る</a></p>\n'
    lead = site.get('lead') or data['lead'].replace('{site}', site['name'])
    # 載せる先の本文の幅と、カードの最小の幅（px）。書いていなければ CSS の既定
    props = []
    if site.get('max_width'):
        props.append(f'--cgs-max: {int(site["max_width"])}px')
    if site.get('min_card'):
        props.append(f'--cgs-min: {int(site["min_card"])}px')
    width = f' style="{"; ".join(props)}"' if props else ''
    n_items = len(cards) + (1 if site.get('operator', True) else 0)
    layout_key, _ = layout_css(site, n_items)
    # 運営者のパネル（会社サイトのように、載せる先が運営者自身のときは出さない）
    operator = (
        '      <li class="cgs-op">\n'
        f'        <img class="cgs-op-ph" src="{esc(asset(base, op["photo"]))}" alt="{esc(op["person"])}" width="60" height="60" loading="lazy" decoding="async">\n'
        '        <div>\n'
        f'          <div class="cgs-op-l">{esc(op["label"])}</div>\n'
        f'          <div class="cgs-op-c"><a href="{esc(op["company_url"])}" target="_blank" rel="noopener">{esc(op["company"])}</a></div>\n'
        f'          <div class="cgs-op-n">{esc(op["title"])} {esc(op["person"])}</div>\n'
        '        </div>\n'
        '      </li>\n'
    )
    return (
        f'<section class="cgs" aria-label="{esc(data["heading"])}" data-cgs-layout="{layout_key}"{width}>\n'
        '  <div class="cgs-in">\n'
        f'    <h2 class="cgs-h">{esc(data["heading"])}</h2>\n'
        f'    <p class="cgs-lead">{esc(lead)}</p>\n'
        '    <ul class="cgs-list">\n'
        + (operator if site.get('operator', True) else '')
        + ''.join(card_html(s, site['id'], base) for s in cards) +
        '    </ul>\n'
        + more +
        '  </div>\n'
        '</section>\n'
    )


def shown_cards(data, site, services=None, all_url=None):
    """帯に出すカード・一覧ページの URL・上限を超えたか。上限を超えたら上位だけ出して、一覧ページへ送る。"""
    cards = cards_for(data, site['id'], services)
    limit = data.get('max_cards', 10)
    all_url = all_url if all_url is not None else data.get('all_services_url')
    over = bool(len(cards) > limit and all_url)
    return (cards[:limit] if over else cards), all_url, over


def site_layout_css(data, site, services=None, all_url=None):
    """載せる先に出す帯の、1 行の枚数の指定。"""
    cards, _, _ = shown_cards(data, site, services, all_url)
    return layout_css(site, len(cards) + (1 if site.get('operator', True) else 0))[1]


def site_html(data, site, css, base=None):
    """載せる先 1 件分の、スタイル込みの帯。base を渡すと画像の置き場をそれにする。"""
    body = band_html(data, site if base is None else {**site, 'asset_base': base})
    # 帯の前に置く HTML（載せる先のテーマが、フッターの位置を目印に動く部品を持つ場合の目印など）
    before = (site['before_html'] + '\n') if site.get('before_html') else ''
    # 載せる先だけに要る指定（フッターとの間の余白など）を足す
    site_css = css + (minify_css(site['extra_css']) if site.get('extra_css') else '') + site_layout_css(data, site)
    stamp = hashlib.sha256((site_css + before + body).encode('utf-8')).hexdigest()[:12]
    return stamp, (f'<!-- group-services {stamp} -->\n'
                   f'<style>\n{site_css}</style>\n{before}{body}')


def main():
    data = load()
    css = minify_css((HERE / 'band.css').read_text(encoding='utf-8'))
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / 'assets').mkdir(parents=True)
    (DIST / 'remote').mkdir()
    for f in sorted((HERE / 'assets').iterdir()):
        shutil.copy2(f, DIST / 'assets' / f.name)

    # 帯を載せる先: embed が true のサービスと、サービスではない載せ先（sites）
    sites = [s for s in data['services'] if s['embed']] + data.get('sites', [])
    op_photo = data['operator']['photo']
    preview = []
    for site in sites:
        stamp, out = site_html(data, site, css)
        (DIST / f'{site["id"]}.html').write_text(out, encoding='utf-8')
        # 各サイトが取りに行く帯（画像は jsDelivr から読む）
        _, remote = site_html(data, site, css, REMOTE_ASSET_BASE)
        (DIST / 'remote' / f'{site["id"]}.html').write_text(remote, encoding='utf-8')
        print(f'{site["id"]}.html  {stamp}  {len(out.encode("utf-8"))} bytes  カード {len(cards_for(data, site["id"]))} 枚')
        # WordPress のサイトには、mu-plugins に置く形にまとめて出す（直下に本体、同名のフォルダに帯と画像）
        if site.get('wordpress_mu_plugin'):
            name = site['wordpress_mu_plugin']
            mu = DIST / 'wordpress' / site['id'] / 'mu-plugins'
            (mu / name / 'assets').mkdir(parents=True)
            shutil.copy2(HERE / 'wordpress' / 'mu-plugins' / f'{name}.php', mu / f'{name}.php')
            (mu / name / 'band.html').write_text(out, encoding='utf-8')
            # 取りに行く部品と、どの帯を取りに行くか（載せる先の id）
            shutil.copy2(HERE / 'php' / 'group-services-remote.php', mu / name / 'group-services-remote.php')
            (mu / name / 'site.txt').write_text(site['id'] + '\n', encoding='utf-8')
            used = {s['logo'] for s in cards_for(data, site['id']) if s.get('logo')}
            if site.get('operator', True):
                used.add(op_photo)
            for f in sorted(used):
                shutil.copy2(HERE / 'assets' / f, mu / name / 'assets' / f)
            print(f'wordpress/{site["id"]}/mu-plugins/{name}.php  画像 {len(used)} 枚')
        # 確認用のページでは、画像を dist/assets/ から読む
        preview.append((f'{site["name"]} に載せる帯', band_html(data, {**site, 'asset_base': 'assets/'}), site_layout_css(data, site)))

    # サービスが増えた場合の見え方（確認用ページにだけ出す）
    first = {**sites[0], 'asset_base': 'assets/'}
    for extra, all_url in ((2, None), (5, None), (9, 'https://seo.contencial.co.jp/')):
        dummy = [{'id': f'demo{i}', 'name': f'サービス{i + 1}', 'url': 'https://example.com/', 'logo': None,
                  'desc': '増えた場合の見え方を確かめるための仮のカード', 'cta': '無料で試す', 'embed': False}
                 for i in range(extra)]
        label = f'【確認用】サービスが {extra} 個増えた場合（{sites[0]["name"]}）' + ('・上限を超えた分は一覧へ' if all_url else '')
        preview.append((label, band_html(data, first, data['services'] + dummy, all_url), site_layout_css(data, first, data['services'] + dummy, all_url)))

    page = ['<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta name="robots" content="noindex">\n<title>グループサービスの帯（確認用）</title>\n'
            '<style>body{margin:0;font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;background:#fff;color:#111}'
            '.pv-l{margin:0;padding:18px 16px 8px;font-size:13px;font-weight:700;color:#b45309}'
            '.pv-f{background:#172554;color:#bfdbfe;padding:22px 16px;font-size:12px}</style>\n'
            f'<style>\n{css}{"".join(sorted(set(lc for _, _, lc in preview)))}</style>\n</head>\n<body>\n']
    for label, body, _ in preview:
        page.append(f'<p class="pv-l">{esc(label)}</p>\n{body}<div class="pv-f">（ここからサイトのフッター）</div>\n')
    page.append('</body>\n</html>\n')
    (DIST / 'preview.html').write_text(''.join(page), encoding='utf-8')
    print('preview.html')


if __name__ == '__main__':
    main()
