# -*- coding: utf-8 -*-
"""SNS・note用のデモ素材を作る。

    python make_demo.py

出力先: ../_demo/
  drill.mp4 / drill.gif      … 計算ドリル（ボックス図を空欄タップで埋める）＝一番の売り
  shiwake.mp4 / shiwake.gif  … 仕訳（科目タップ＋テンキーで計算して判定）
  exam.mp4 / exam.gif        … 模試（90分タイマー・大問ナビ）
  s_*.png                    … 各画面の枠つきスクショ
  threeup.png                … 3画面並び（記事の導入・SNSの1枚目）
  ogp.png                    … 1200x630 のアイキャッチ（noteのヘッダー用）

なめらかに撮るしくみ：
  ブラウザのスクリーンショットは1枚150ms前後かかるので、そのまま撮ると7fps程度になりカクつく。
  そこで **アプリのアニメーションを SLOWMO 倍だけ遅くして撮り、時間軸を 1/SLOWMO に縮めて**
  25fps へ並べ直す。見た目の速さは実際のアプリのまま、コマ数だけが増える。
  止まっている時間は撮らずに時間だけ進める（同じ絵を何枚も撮っても無駄なので）。

素材は「使い込んだ状態」を作ってから撮る。まっさらの 0/26駅 では魅力が伝わらない。
"""
import os, sys, io, json, time, glob, shutil, subprocess, datetime
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "_demo"))
TMP = os.path.join(OUT, "_frames")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import test_app as T

W, H = 375, 812        # 撮影サイズ（iPhone相当）
DSF = 2                # 2倍で撮る（750x1624）＝縮めたとき文字がきれい
SLOWMO = 8             # アプリのアニメを何倍ゆっくりにして撮るか
FPS = 25               # 書き出しのコマ数
GIF_W = 400            # GIFの横幅
MP4_W = 560            # MP4の横幅（偶数）
BG1, BG2 = (26, 38, 50), (52, 66, 86)

_cand = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages",
                               "Gyan.FFmpeg*", "*", "bin", "ffmpeg.exe")) + [shutil.which("ffmpeg")]
FFMPEG = next((f for f in _cand if f and os.path.exists(f)), None)

FONT = "C:/Windows/Fonts/meiryo.ttc"
def font(sz):
    return ImageFont.truetype(FONT, sz)


# ---------------- 使い込んだ状態を作る ----------------
def seed_js():
    today = datetime.date.today()
    days = {}
    for i in range(11):
        if i in (4, 9):        # ときどき休む方が自然
            continue
        d = today - datetime.timedelta(days=i)
        days[d.isoformat()] = [12, 10, 3, 14, 0, 8, 10, 6, 0, 11, 9][i]
    return """
      localStorage.clear();
      const DAYS = %s;
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
    """ % json.dumps(days, ensure_ascii=False)


# ---------------- 枠をつける ----------------
def framed(png_bytes, pad=26, radius=34):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    canvas = Image.new("RGB", (w + pad * 2, h + pad * 2))
    d = ImageDraw.Draw(canvas)
    for y in range(canvas.height):
        t = y / max(1, canvas.height - 1)
        d.line([(0, y), (canvas.width, y)],
               fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)))
    canvas.paste(Image.new("RGB", (w, h), (0, 0, 0)), (pad + 4, pad + 8), mask)
    canvas.paste(im, (pad, pad), mask)
    return canvas


def run(cmd):
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


# ---------------- 収録（再生時の時間軸つき） ----------------
class Rec:
    def __init__(self, page, name):
        self.page, self.name = page, name
        self.dir = os.path.join(TMP, name)
        shutil.rmtree(self.dir, ignore_errors=True); os.makedirs(self.dir)
        self.items = []      # (再生時の時刻[秒], ファイル)
        self.t = 0.0
        self.n = 0

    def _grab(self, at):
        path = os.path.join(self.dir, "raw_%05d.png" % self.n); self.n += 1
        self.page.screenshot(path=path)
        self.items.append((at, path))

    def motion(self, js=None, sec=0.42):
        """操作 → アニメの最中を連写。sec は『再生したときの秒数』"""
        if js:
            self.page.evaluate(js)
        t0 = time.time(); span = sec * SLOWMO
        while True:
            el = time.time() - t0
            self._grab(self.t + min(el / SLOWMO, sec))
            if el >= span:
                break
        self.t += sec

    def hold(self, sec=0.6):
        """止まっている時間。撮らずに時間だけ進める"""
        self.t += sec

    def do(self, js, sec=0.42, after=0.5):
        self.motion(js, sec); self.hold(after)

    def render(self):
        if not self.items:
            return
        total = self.t + 0.2
        seq = os.path.join(self.dir, "seq"); os.makedirs(seq, exist_ok=True)
        j = 0
        for k in range(int(total * FPS)):
            t = k / FPS
            while j + 1 < len(self.items) and abs(self.items[j + 1][0] - t) <= abs(self.items[j][0] - t):
                j += 1
            shutil.copyfile(self.items[j][1], os.path.join(seq, "f_%05d.png" % k))
        pat = os.path.join(seq, "f_%05d.png")
        mp4 = os.path.join(OUT, self.name + ".mp4")
        gif = os.path.join(OUT, self.name + ".gif")
        run([FFMPEG, "-y", "-framerate", str(FPS), "-i", pat,
             "-vf", "scale=%d:-2:flags=lanczos" % MP4_W,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", mp4])
        run([FFMPEG, "-y", "-framerate", str(FPS), "-i", pat,
             "-filter_complex",
             "scale=%d:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];"
             "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" % GIF_W, gif])
        for f in (mp4, gif):
            if os.path.exists(f):
                print("   %-12s %4.1f秒 / %.1f MB" % (os.path.basename(f), total, os.path.getsize(f) / 1e6))
        shutil.rmtree(self.dir, ignore_errors=True)


# ---------------- 撮影 ----------------
def main():
    if not FFMPEG:
        print("ffmpeg が見つかりません。winget install Gyan.FFmpeg を実行してください"); sys.exit(1)
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
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

        def still(name):
            framed(page.screenshot(), pad=30, radius=40).save(os.path.join(OUT, name))
            print("  ", name)

        print("静止画:")
        page.evaluate("setTab('today')"); page.wait_for_timeout(500); still("s_home.png")
        page.evaluate("setTab('map')"); page.wait_for_timeout(500); still("s_map.png")
        page.evaluate("setTab('exam')"); page.wait_for_timeout(500); still("s_exam.png")
        page.evaluate("startDrill('D1'); __t.cta(); __t.keys('200'); __t.press('OK'); "
                      "__t.cta(); __t.keys('168000'); __t.press('OK')")
        page.wait_for_timeout(800); still("s_drill.png")
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'")

        # アニメを SLOWMO 倍ゆっくりに（撮影のあいだだけ）
        page.add_style_tag(content="*, *::before, *::after { animation-duration: %.2fs !important;"
                                   " transition-duration: %.2fs !important; }"
                                   % (0.34 * SLOWMO, 0.34 * SLOWMO))
        SEC = 0.44     # 遷移1回を、再生時に何秒に見せるか

        print("ドリル:")
        r = Rec(page, "drill")
        r.motion("setTab('drills')", SEC); r.hold(1.0)
        r.do("startDrill('D1')", SEC, 1.1)
        r.do("document.querySelector('#b-boxes .blank.active').click()", SEC, 0.7)
        for ch in "200":
            r.do("__t.press('%s')" % ch, 0.10, 0.14)
        r.do("__t.press('OK')", SEC, 1.0)
        r.do("__t.cta()", SEC, 0.5)
        for ch in "168000":
            r.do("__t.press('%s')" % ch, 0.10, 0.10)
        r.do("__t.press('OK')", SEC, 1.0)
        for v in ["672000", "120000", "960000", "288000"]:
            page.evaluate("__t.cta(); __t.keys('%s')" % v); r.hold(0.25)
            r.do("__t.press('OK')", 0.30, 0.35)
        page.evaluate("__t.cta(); __t.keys('1632000')"); r.hold(0.25)
        r.do("__t.press('OK')", SEC, 2.4)
        r.render()
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'"); page.wait_for_timeout(500)

        print("仕訳:")
        r = Rec(page, "shiwake")
        r.motion(None, 0.06); r.hold(0.9)
        r.do("startSession('retry', {ids: ['K08', 'S12']})", SEC, 1.5)
        r.do("document.querySelector(`.addline[data-side='debit']`).click()", SEC, 0.8)
        r.do("__t.chip('仕掛品')", SEC, 0.6)
        for k in ["8", "00", "×", "4", "5", "0"]:
            r.do("__t.press('%s')" % k, 0.10, 0.13)
        r.hold(0.5)
        r.do("__t.press('OK')", SEC, 1.0)
        r.do("document.querySelector(`.addline[data-side='credit']`).click()", SEC, 0.5)
        r.do("__t.chip('製造間接費')", SEC, 0.4)
        page.evaluate("__t.keys('360000')"); r.hold(0.35)
        r.do("__t.press('OK')", SEC, 0.9)
        r.do("__t.cta()", 0.6, 3.2)          # 判定＝駅に到着の演出
        r.render()
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'"); page.wait_for_timeout(500)

        print("模試:")
        r = Rec(page, "exam")
        r.do("setTab('exam')", SEC, 1.3)
        r.do("startExam('M1', true)", SEC, 2.0)
        for sec in [1, 2, 3, 4]:
            r.do("__t.examGo(%d)" % sec, 0.34, 1.0)
        r.do("__t.examGo(0)", 0.34, 1.8)
        r.render()
        page.evaluate("goHome()"); page.wait_for_function("mode === 'home'")

        page.evaluate("""startSession('retry', {ids: PROBLEMS.slice(0,5).map(p => p.id)});
            sessionLog = PROBLEMS.slice(0,5).map((p,i) => ({id: p.id, ok: i !== 3}));
            renderResult(); show('result', {replace:true});""")
        page.wait_for_timeout(1200); still("s_result.png")
        b.close()
    httpd.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)

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
