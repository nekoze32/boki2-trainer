# -*- coding: utf-8 -*-
"""SNS・note用のデモ素材を作る。

    python make_demo.py

出力先: ../_demo/
  drill.gif      … 計算ドリル（ボックス図を空欄タップで埋める）＝一番の売り
  shiwake.gif    … 仕訳（科目タップ＋テンキーで計算して判定）
  exam.gif       … 模試（90分タイマー・大問ナビ）
  s_home.png / s_map.png / s_drill.png / s_exam.png / s_result.png … 単体スクショ（枠つき）
  threeup.png    … 3画面並び（記事の導入・SNSの1枚目）
  ogp.png        … 1200x630 のアイキャッチ（noteのヘッダー用）

素材は「使い込んだ状態」を作ってから撮る。まっさらの 0/26駅 では魅力が伝わらない。
"""
import os, sys, io, json, time, datetime
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "_demo"))
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import test_app as T

W, H = 375, 812          # 撮影サイズ（iPhone相当）
DSF = 2                  # 2倍で撮ってから縮小するときれい
GIF_W = 320              # GIFの横幅（SNSで軽く見える大きさ）
BG1, BG2 = (26, 38, 50), (52, 66, 86)   # 枠の背景（濃紺のグラデ）

FONT = "C:/Windows/Fonts/meiryo.ttc"
def font(sz, idx=0):
    return ImageFont.truetype(FONT, sz, index=idx)

# ---------------- 使い込んだ状態を作る ----------------
def seed_js():
    today = datetime.date.today()
    days = {}
    for i in range(11):
        d = today - datetime.timedelta(days=i)
        if i in (4, 9):        # ときどき休む方が自然
            continue
        days[d.isoformat()] = [12, 10, 3, 14, 0, 8, 10, 6, 0, 11, 9][i]
    return """
      localStorage.clear();
      const T = %s, DAYS = %s;
      const prog = {};
      PROBLEMS.forEach((p, i) => {
        if(i >= 34) return;                       // 34問に着手済み
        const box = [3,4,5,2,3,5,4,1,3,4,2,5][i %% 12];
        const due = new Date(); due.setDate(due.getDate() + (i %% 7) - 2);
        prog[p.id] = {box: box, due: due.toISOString().slice(0,10), seen: 1 + (i %% 3), wrong: i %% 2};
      });
      localStorage.setItem("bokitore:progress", JSON.stringify(prog));
      localStorage.setItem("bokitore:days", JSON.stringify(DAYS));
      localStorage.setItem("bokitore:drills", JSON.stringify({D1: 2, D2: 1}));
      localStorage.setItem("bokitore:examlog", JSON.stringify({M1: {best: 74, tries: 2, last: 74}}));
      const ex = new Date(); ex.setDate(ex.getDate() + 38);
      localStorage.setItem("bokitore:settings", JSON.stringify(
        {cat: "both", n: 10, theme: "system", examDate: ex.toISOString().slice(0,10)}));
    """ % (json.dumps(True), json.dumps(days, ensure_ascii=False))

# ---------------- 枠をつける ----------------
def framed(png_bytes, pad=26, radius=34, scale=1.0):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    w, h = im.size
    # 角丸マスク
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    canvas = Image.new("RGB", (w + pad * 2, h + pad * 2))
    d = ImageDraw.Draw(canvas)
    for y in range(canvas.height):      # 縦グラデ
        t = y / max(1, canvas.height - 1)
        d.line([(0, y), (canvas.width, y)],
               fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)))
    shadow = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(shadow, (pad + 3, pad + 6), mask)
    canvas.paste(im, (pad, pad), mask)
    return canvas

def save_gif(frames, path, ms=520):
    if not frames:
        print("  !! フレームなし", path); return
    fs = [f.convert("P", palette=Image.ADAPTIVE, colors=200) for f in frames]
    fs[0].save(path, save_all=True, append_images=fs[1:], duration=ms, loop=0, optimize=True, disposal=2)
    print("  ", os.path.basename(path), "%.1f MB / %d frames" % (os.path.getsize(path) / 1e6, len(fs)))

# ---------------- 撮影 ----------------
def main():
    httpd = T.serve()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=DSF,
                            is_mobile=True, has_touch=True, locale="ja-JP")
        page = ctx.new_page()
        page.goto(T.URL); page.wait_for_function("typeof PROBLEMS !== 'undefined' && PROBLEMS.length")
        page.evaluate(seed_js())
        page.reload(); page.wait_for_function("typeof PROBLEMS !== 'undefined'")
        page.evaluate(T.HELPERS)
        page.wait_for_timeout(500)

        # 画面の取り込み（GIF用・枠つき）
        def grab():
            im = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
            im = im.resize((GIF_W, int(im.height * GIF_W / im.width)), Image.LANCZOS)
            w, h = im.size
            mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=255)
            pad = 16
            canvas = Image.new("RGB", (w + pad * 2, h + pad * 2))
            d = ImageDraw.Draw(canvas)
            for y in range(canvas.height):
                t = y / max(1, canvas.height - 1)
                d.line([(0, y), (canvas.width, y)],
                       fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)))
            canvas.paste(im, (pad, pad), mask)
            return canvas

        def hold(n=1):
            """止まっている画（同じ絵をn枚）"""
            f = grab(); return [f] * n

        def motion(sec=0.9):
            """アニメーションの最中を、撮れるだけ連写する"""
            fs = []; t0 = time.time()
            while time.time() - t0 < sec:
                fs.append(grab())
            return fs

        def act(js, sec=0.9, after=2):
            """操作 → その直後から連写 → 落ち着いた画を数枚"""
            page.evaluate(js)
            return motion(sec) + hold(after)

        def still(name):
            buf = io.BytesIO()
            Image.open(io.BytesIO(page.screenshot())).convert("RGB").save(buf, "PNG")
            framed(buf.getvalue(), pad=30, radius=40).save(os.path.join(OUT, name))
            print("  ", name)

        # ---------- 静止画 ----------
        print("静止画:")
        page.evaluate("setTab('today')"); page.wait_for_timeout(400); still("s_home.png")
        page.evaluate("setTab('map')"); page.wait_for_timeout(400); still("s_map.png")
        page.evaluate("setTab('exam')"); page.wait_for_timeout(400); still("s_exam.png")
        page.evaluate("startDrill('D1'); __t.cta(); __t.keys('200'); __t.press('OK'); __t.cta(); __t.keys('168000'); __t.press('OK')")
        page.wait_for_timeout(600); still("s_drill.png")
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'")

        # アニメーションを3倍ゆっくりにして、その最中を連写する。
        # 再生は100ms間隔なので、captureのコマ落ちが埋まって「動いて見える」GIFになる。
        SLOWMO = """*, *::before, *::after {
            animation-duration: .72s !important;
            transition-duration: .72s !important;
        }"""
        slow = page.add_style_tag(content=SLOWMO)

        # ---------- GIF：計算ドリル ----------
        print("GIF ドリル:")
        f = []
        page.evaluate("setTab('drills')"); page.wait_for_timeout(700)
        f += hold(6)
        f += act("startDrill('D1')", 1.1, 4)                                  # 右からスライドイン
        f += act("document.querySelector('#b-boxes .blank.active').click()", 1.0, 3)   # テンキーがせり上がる
        for ch in "200":
            f += act("__t.press('%s')" % ch, 0.18, 1)
        f += act("__t.press('OK')", 1.0, 4)                                   # シートが下がって欄が埋まる
        f += act("__t.cta()", 0.9, 2)
        for ch in "168000":
            f += act("__t.press('%s')" % ch, 0.14, 1)
        f += act("__t.press('OK')", 1.0, 4)
        for v in ["672000", "120000", "960000", "288000"]:
            page.evaluate("__t.cta(); __t.keys('%s')" % v); page.wait_for_timeout(120)
            f += act("__t.press('OK')", 0.5, 1)
        page.evaluate("__t.cta(); __t.keys('1632000')"); page.wait_for_timeout(120)
        f += act("__t.press('OK')", 1.2, 8)                                   # 完答
        save_gif(f, os.path.join(OUT, "drill.gif"), ms=100)
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'"); page.wait_for_timeout(400)

        # ---------- GIF：仕訳 ----------
        print("GIF 仕訳:")
        f = hold(4)
        f += act("startSession('retry', {ids: ['K08', 'S12']})", 1.1, 4)
        f += act("document.querySelector(`.addline[data-side='debit']`).click()", 1.0, 3)
        f += act("__t.chip('仕掛品')", 1.0, 2)
        for k in ["8", "00", "×", "4", "5", "0"]:
            f += act("__t.press('%s')" % k, 0.16, 1)
        f += act("__t.press('OK')", 1.0, 4)
        page.evaluate("document.querySelector(`.addline[data-side='credit']`).click()"); page.wait_for_timeout(700)
        page.evaluate("__t.chip('製造間接費')"); page.wait_for_timeout(600)
        page.evaluate("__t.keys('360000')"); page.wait_for_timeout(200)
        f += act("__t.press('OK')", 1.0, 3)
        f += act("__t.cta()", 1.4, 10)                                        # 判定＝駅に到着の演出
        save_gif(f, os.path.join(OUT, "shiwake.gif"), ms=100)
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'"); page.wait_for_timeout(400)

        # ---------- GIF：模試 ----------
        print("GIF 模試:")
        f = []
        f += act("setTab('exam')", 0.9, 4)
        f += act("startExam('M1', true)", 1.3, 6)
        for sec in [1, 2, 3, 4]:
            f += act("__t.examGo(%d)" % sec, 0.7, 3)
        f += act("__t.examGo(0)", 0.7, 5)
        save_gif(f, os.path.join(OUT, "exam.gif"), ms=110)
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'")
        page.evaluate("(e => e && e.remove())(document.querySelector('style[data-slowmo]'))")

        # ---------- 結果画面の静止画 ----------
        page.evaluate("""startSession('retry', {ids: PROBLEMS.slice(0,5).map(p => p.id)});
            sessionLog = PROBLEMS.slice(0,5).map((p,i) => ({id: p.id, ok: i !== 3}));
            renderResult(); show('result', {replace:true});""")
        page.wait_for_timeout(900); still("s_result.png")
        b.close()
    httpd.shutdown()

    # ---------------- 並べ画・OGP ----------------
    print("合成:")
    three = [Image.open(os.path.join(OUT, n)) for n in ("s_home.png", "s_drill.png", "s_exam.png")]
    gap, pad = 26, 40
    tw = sum(i.width for i in three) + gap * 2 + pad * 2
    th = max(i.height for i in three) + pad * 2
    canvas = Image.new("RGB", (tw, th))
    d = ImageDraw.Draw(canvas)
    for y in range(th):
        t = y / max(1, th - 1)
        d.line([(0, y), (tw, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)))
    x = pad
    for im in three:
        canvas.paste(im, (x, pad)); x += im.width + gap
    canvas.save(os.path.join(OUT, "threeup.png")); print("   threeup.png", canvas.size)

    # OGP 1200x630
    ogp = Image.new("RGB", (1200, 630))
    d = ImageDraw.Draw(ogp)
    for y in range(630):
        t = y / 629
        d.line([(0, y), (1200, y)], fill=(int(14 + 6 * t), int(122 - 26 * t), int(95 - 24 * t)))
    shot = Image.open(os.path.join(OUT, "s_drill.png"))
    sh = 540; sw = int(shot.width * sh / shot.height)
    ogp.paste(shot.resize((sw, sh), Image.LANCZOS), (1200 - sw - 40, 45))
    d.text((66, 120), "ボキトレイン", font=font(64), fill=(255, 255, 255))
    d.text((66, 216), "一駅一問。", font=font(40), fill=(255, 180, 58))
    d.text((66, 274), "鉛筆も紙も出さずに、", font=font(40), fill=(255, 255, 255))
    d.text((66, 332), "片手で簿記2級。", font=font(40), fill=(255, 255, 255))
    d.text((66, 430), "下書き用紙を、画面にしました", font=font(26), fill=(214, 235, 228))
    d.text((66, 476), "仕訳60問／計算ドリル4本／本番と同じ90分の模試3回", font=font(22), fill=(180, 214, 202))
    d.text((66, 520), "nekoze32.github.io/boki2-trainer", font=font(22), fill=(255, 180, 58))
    ogp.save(os.path.join(OUT, "ogp.png")); print("   ogp.png", ogp.size)
    print("\n出力先:", OUT)

if __name__ == "__main__":
    main()
