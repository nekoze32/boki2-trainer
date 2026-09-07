# ボキトレイン — ソースとテスト

| ファイル | 役割 |
|---|---|
| `bokitore_v2.tpl.html` | アプリ本体のテンプレート（CSS・HTML・JS）。問題データは含まない |
| `bank_shogyo.json` / `bank_kogyo.json` | 仕訳問題バンク（商業30・工業20）。旧10問は `build.py` の `BASE` に直書き |
| `exams.py` | CBT模試の問題データ（1回＝90分・100点）。答案用紙のHTMLもここで組み立てる |
| `build.py` | 問題を検証してテンプレートへ差し込み、`bokitore.html`（artifact用）・`bokitore_standalone.html`・`../index.html`（GitHub Pages用）を出力 |
| `test_app.py` | Playwright（Chromiumヘッドレス）で30本の流れを実機同様に操作して検証 |
| `ビルドとテスト.cmd` | 上2つをまとめて実行。**ダブルクリックでOK** |

## 普段の手順

1. 問題を足す／直す → JSON か `build.py` の `FIX` を編集
2. `ビルドとテスト.cmd` をダブルクリック → 「30 / 30 passed」→ そのまま **git commit と push まで自動**（テストが落ちたら push しない）
3. 1〜2分で https://nekoze32.github.io/boki2-trainer/ に反映

Claude に頼むときは「ビルドしてテストして push して」で同じことになる（`python build.py && python test_app.py && git add -A && git commit && git push`）。

## 初回だけ（別のPCで動かすとき）

```bash
python -m pip install playwright
python -m playwright install chromium
gh auth login            # GitHub.com → HTTPS → Login with a web browser（表示されるコードをブラウザで承認）
gh auth setup-git
git clone https://github.com/nekoze32/boki2-trainer.git
```

会社PC（Windows）は 2026-09-07 に設定済み。Mac はこの手順をまだやっていない。
リポジトリはリポジトリ直下が GitHub Pages のルート（`index.html`）。`src/` にソースとテスト。
ビルド生成物（`src/bokitore.html`・`src/bokitore_standalone.html`）と `_send/`・`__pycache__/` は `.gitignore` で除外。

Safari エンジンでも走らせたいときは `BOKI_BROWSER=webkit python test_app.py`（初回は `python -m playwright install webkit`）。

## テストが見ているもの

起動／問題データの整合／仕訳の正答・誤答と復習日／電卓（＝省略・÷0・桁上限・小数）／行の修正削除／途中保存と再開（二重採点なし）／結果画面とシェア文／ドリル（空欄タップ・ヒント・選択式・途中再開・コレクション）／タブと戻る操作／復習ロジック／壊れた保存データ／320px画面／ダブルタップ拡大が止まりピンチ拡大は残ること／電卓が市販と同じ並びであること／進行（分母固定・電車が進む・正解は解説を畳む・コンボ／箱／論点・途中保存）／終点到着（称号・積み上げ・紙吹雪）／路線図（2路線・開通）／合格までの道のり（開通→模試→本番・試験日・連続を煽らない）／操作バーが下部ツールバーに隠れず最下端の帯にも置かれずシートを閉じても死なないこと／ドリルで番でない「？」をタップしたら案内が出ること／長押しで文字選択にならず入力欄だけ選択できること

模試はさらに、配点の整合（満点100・設問配点＝欄配点・答案用紙の欄と解答が1対1）／答案入力と大問ナビ／中断と再開／採点（満点・白紙・部分点）／時間切れの自動提出／残り時間が実時間で減ること／書きかけの行は不正解・同じ側に同じ科目を2回書けないこと／提出後は書き換え不可・二重提出しないこと／壊れた中断データ

実機（iPhone・Android）の触り心地はテストでは分からないので、公開URLをスマホで開いて確認する。

## 模試を1回増やすとき

`exams.py` の `EXAMS` に1件足す。ブロックは2種類だけ。

- `je` … 仕訳。`rows` 行の答案用紙を出し、全問一致で `pt`（部分点なし）
- `sheet` … 答案用紙の穴埋め。`sheet` のHTMLに `f("キー")` で欄を置き、`fields` の1欄ごとに `pt`

`build.py` が起動時に、満点100・設問配点＝ブロック配点・ブロック配点＝欄配点・仕訳の貸借一致・
正解科目が `cands` にあること・答案用紙の欄と `fields` が1対1であることを検査して、
合わなければビルドを止める。
