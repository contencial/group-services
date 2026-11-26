# group-services

株式会社コンテンシャルのグループサービスを、各サイトのフッターの直前で紹介する帯の共通部品です。

## 構成

| ファイル | 役割 |
|---|---|
| `services.json` | サービスの一覧（名前・URL・紹介文・ロゴ・並び順） |
| `band.css` | 帯のスタイル（クラス名は `cgs-` で始まる） |
| `assets/` | ロゴと写真 |
| `build.py` | 上の 3 つから、載せる先ごとの HTML を `dist/` に作る |
| `dist/<id>.html` | 載せる先ごとの帯（スタイル込みの 1 枚。画像はサイトの公開フォルダから読む） |
| `dist/remote/<id>.html` | 各サイトが取りに行く帯（画像は jsDelivr から読む） |
| `php/group-services-remote.php` | 各サイトで、帯を取りに行って手元に控える部品 |
| `wordpress/mu-plugins/` | WordPress 用の mu-plugin の本体 |
| `dist/wordpress/<id>/mu-plugins/` | WordPress の mu-plugins に置くもの（本体・帯・画像） |
| `dist/preview.html` | 表示の確認用ページ |

## 作り方

```
python3 build.py
```

`dist/preview.html` をブラウザで開くと、各サイトに載る帯を確認できます。

## サービスの追加・変更

1. `services.json` の `services` を編集する（ロゴは 96px の正方形にして `assets/` に置く）
2. `python3 build.py` を実行する
3. `dist/preview.html` で表示を確認する

| 項目 | 意味 |
|---|---|
| `embed` | `true` のサイトにだけ帯用の HTML を作る |
| `tag` | カードに付ける札 |
| `desc_on` | 載せる先ごとの紹介文 |
| `order_on` | 載せる先ごとの並び順 |
| `max_width` | 帯の幅（px。既定 1152） |
| `min_card` | カードの最小の幅（px。既定 165）。1 行に並ぶ枚数が変わる |
| `asset_base` | 画像を置く場所（既定 `/group-services/`） |
| `extra_css` | 載せる先だけに足すスタイル（フッターとの間の余白など） |
| `before_html` | 帯の直前に置く HTML（テーマがフッターの位置を目印にして動く部品を持つとき、その目印を帯の上に置く） |
| `max_cards`・`all_services_url` | カードが上限を超えたとき、上位だけを出して一覧ページへ送る |

サービスではないサイト（会社サイトなど）に載せるときは、`sites` に 1 件足します。`lead` で見出しの下の文を、`operator: false` で運営者のパネルを出さない指定ができます。

## 変更が各サイトに届く仕組み

各サイトは 1 時間に 1 回、次の手順で帯を取りに行き、手元に控えます。ページはその控えを出します。

1. GitHub の API で `main` の最新のコミットを調べる
2. そのコミットの `dist/remote/<id>.html` を jsDelivr から取る（画像の URL もそのコミットに固定する）
3. 中身が帯であること（大きさ・`<section class="cgs"` があること・スクリプトが無いこと）を確かめて、控えを置き換える

取りに行けないとき・中身がおかしいときは、前の控えを出し続けます。控えが無いときは、サイトに同梱した帯を出します。このため、`services.json` などを直して `python3 build.py` を実行し、`dist/` ごと `main` に push すれば、1 時間ほどで全部のサイトの帯が変わります。サイトごとの作業は要りません。

## サイトへの組み込み

1. `dist/assets/` の中身を、サイトの公開フォルダの `asset_base` に置く
2. `dist/<id>.html` を、フッターの直前に差し込む

PHP のサイトは、`php/group-services-remote.php` を読み込み、1 時間ごとの定期実行で `Contencial_Group_Services_Remote::refresh('<id>', '<控えのパス>')` を呼びます。ページを出すときは `Contencial_Group_Services_Remote::read('<控えのパス>')` を使い、`null` のときは同梱の帯を出します。

WordPress のサイトは、`dist/wordpress/<id>/mu-plugins/` の中身を `wp-content/mu-plugins/` に置きます（有効化の操作は要りません）。控えは `wp-content/uploads/group-services-band/` に置かれ、WordPress の定期実行（1 時間ごと）で新しくなります。テーマには手を入れず、フッターの開始タグ（既定は `class` に `site-footer` を含む `footer`）の直前に帯を差し込みます。

`dist/` は生成物です。変更するときは `services.json`・`band.css` を編集して作り直します。
