# group-services

株式会社コンテンシャルのグループサービスを、各サイトのフッターの直前で紹介する帯の共通部品です。

## 構成

| ファイル | 役割 |
|---|---|
| `services.json` | サービスの一覧（名前・URL・紹介文・ロゴ・並び順） |
| `band.css` | 帯のスタイル（クラス名は `cgs-` で始まる） |
| `assets/` | ロゴと写真 |
| `build.py` | 上の 3 つから、載せる先ごとの HTML を `dist/` に作る |
| `dist/<id>.html` | 載せる先ごとの帯（スタイル込みの 1 枚） |
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
| `max_cards`・`all_services_url` | カードが上限を超えたとき、上位だけを出して一覧ページへ送る |

## サイトへの組み込み

1. `dist/assets/` の中身を、サイトの公開フォルダの `asset_base` に置く
2. `dist/<id>.html` を、フッターの直前に差し込む

`dist/` は生成物です。変更するときは `services.json`・`band.css` を編集して作り直します。
