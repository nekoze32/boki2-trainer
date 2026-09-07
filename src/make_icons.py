# -*- coding: utf-8 -*-
"""アプリアイコンの生成。src/icon.svg から PNG を書き出す。

    python make_icons.py

出力（リポジトリ直下）:
  icon-512.png  … PWA（maskable でない通常アイコン）
  icon-192.png  … PWA
  apple-touch-icon.png (180px) … iOS「ホーム画面に追加」
  favicon-32.png / favicon-16.png … ブラウザのタブ
デザインを変えるときは icon.svg を直してから実行する。
"""
import os, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SVG = os.path.join(HERE, "icon.svg")
SIZES = [("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180),
         ("favicon-32.png", 32), ("favicon-16.png", 16)]

def main():
    if not os.path.exists(SVG):
        print("icon.svg がありません"); sys.exit(1)
    svg = open(SVG, encoding="utf-8").read()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name, size in SIZES:
            page = b.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
            body = svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)
            page.set_content(f'<html><body style="margin:0;background:transparent">{body}</body></html>')
            page.wait_for_timeout(80)
            page.screenshot(path=os.path.join(ROOT, name), omit_background=True)
            page.close()
            print("  ", name, size)
        b.close()
    print("OK icons ->", ROOT)

if __name__ == "__main__":
    main()
