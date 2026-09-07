# -*- coding: utf-8 -*-
"""ボキトレイン 自動テスト（Playwright / Chromium ヘッドレス）

使い方（src フォルダで）:
    python build.py && python test_app.py

ビルド済みの bokitore.html をローカルHTTPで配信し、スマホ画面サイズで主要な流れを実機同様に操作して検証する。
落ちたテストは FAIL と理由を出し、終了コード 1 で終わる。
"""
import os, sys, json, threading, http.server, socketserver, functools, traceback
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765

# ---------------- ローカル配信 ----------------
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
def serve():
    handler = functools.partial(Quiet, directory=HERE)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

URL = f"http://127.0.0.1:{PORT}/bokitore.html"
results = []

def test(name):
    def deco(fn):
        fn._test_name = name
        results.append(fn)
        return fn
    return deco

# ---------------- ページ操作ヘルパ（JSで実機と同じ経路を叩く） ----------------
HELPERS = """
window.__t = {
  press(label){ [...document.querySelectorAll('#sheet-num .npk')].find(k => (k.dataset.k||k.dataset.op||k.textContent.trim()) === label).click(); },
  keys(str){ for(const ch of String(str)) this.press(ch); },
  enter(side, acct, amt){
    document.querySelector('.addline[data-side="'+side+'"]').click();
    const chip = [...document.querySelectorAll('#acct-chips .chip')].find(c => c.textContent === acct);
    if(!chip) throw new Error('chip missing: ' + acct);
    chip.click(); this.keys(amt); this.press('OK');
  },
  answerCorrect(){
    const p = curP();
    for(const side of ['debit','credit']) for(const [a, m] of p[side]) this.enter(side, a, m);
    document.querySelector('#cta').click();
  },
  cta(){ document.querySelector('#cta').click(); },
  chip(text){ const c = [...document.querySelectorAll('#acct-chips .chip')].find(c => c.textContent === text); if(!c) throw new Error('chip missing: ' + text); c.click(); },
  fresh(){ localStorage.clear(); progress = {}; days = {}; drillDone = {}; examLog = {}; renderHome(); },

  // ---- 模試 ----
  fld(key){ const el = document.querySelector('#e-body .fld[data-k="' + key + '"]'); if(!el) throw new Error('fld missing: ' + key); el.click(); },
  setNum(key, v){ this.fld(key); this.keys(String(v)); this.press('OK'); },
  setChip(key, text){ this.fld(key); this.chip(text); },
  jeSet(si, bi, side, row, acct, amt){
    const P = 'S' + si + 'B' + bi, s = (side === 'debit' ? 'd' : 'c');
    this.setChip(P + '_' + s + row + 'a', acct);
    this.setNum(P + '_' + s + row + 'm', amt);
  },
  examFill(all){   // all=true で全問正解、false で第1問(1)だけ正解
    exam.sections.forEach((sec, si) => sec.blocks.forEach((b, bi) => {
      if(!all && !(si === 0 && bi === 0)) return;
      const P = blockPrefix(si, bi);
      if(b.kind === 'je'){
        b.debit.forEach((l, r) => { exAns[P+'_d'+r+'a'] = l[0]; exAns[P+'_d'+r+'m'] = l[1]; });
        b.credit.forEach((l, r) => { exAns[P+'_c'+r+'a'] = l[0]; exAns[P+'_c'+r+'m'] = l[1]; });
      } else b.fields.forEach(f => { exAns[P+'_'+f.k] = f.a; });
    }));
    renderExam();
  },
  examGo(sec){ exSec = sec; renderExam(); },
  examClock(sec){ stopTimer(); exRemain = sec; startTimer(); },   // 残り時間を差し替える（stopTimerが先。でないと旧deadlineから同期し直されて戻る）
};
"""

def fresh_page(ctx):
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("typeof PROBLEMS !== 'undefined' && PROBLEMS.length > 0")
    page.evaluate(HELPERS)
    page.evaluate("__t.fresh()")
    page._errors = errors
    return page

def ev(page, js):
    return page.evaluate(js)

def wait_cta(page):
    page.wait_for_function("!document.querySelector('#cta').disabled", timeout=3000)

# ---------------- テスト ----------------
@test("起動：問題60・ドリル4・模試1・タブ5・エラーなし")
def t_boot(ctx):
    p = fresh_page(ctx)
    n = ev(p, "PROBLEMS.length"); d = ev(p, "DRILLS.length"); tabs = ev(p, "document.querySelectorAll('#tabbar button').length")
    assert n == 60, n
    assert d == 4, d
    assert ev(p, "EXAMS.length") == 1
    assert tabs == 5, tabs
    assert ev(p, "document.querySelector('.tabpane.on').id") == "pane-today"
    assert ev(p, "document.body.classList.contains('home')")
    assert not p._errors, p._errors

@test("問題データ：全問の正解科目が候補に含まれ貸借一致（別解含む）")
def t_data(ctx):
    p = fresh_page(ctx)
    bad = ev(p, """PROBLEMS.filter(q => {
      const answers = [q].concat(q.alts || []);
      return answers.some(a => a.debit.reduce((s,l)=>s+l[1],0) !== a.credit.reduce((s,l)=>s+l[1],0)
        || [...a.debit, ...a.credit].some(l => !q.cands.includes(l[0])));
    }).map(q => q.id)""")
    assert bad == [], bad

@test("仕訳：正答→箱1・翌日復習、誤答→末尾再出題・翌日")
def t_quiz(ctx):
    p = fresh_page(ctx)
    ev(p, "document.querySelector('#btn-today').click()")
    assert ev(p, "queue.length") == 10
    ev(p, "__t.answerCorrect()")
    assert ev(p, "document.querySelector('#q-fb-title').textContent") == "正解！"
    pr = ev(p, "progress[queue[0]]")
    assert pr["box"] == 1 and pr["due"] == ev(p, "addDays(todayStr(), 1)"), pr
    wait_cta(p); ev(p, "__t.cta()")
    # 2問目：科目だけ合わせて金額を1円にして誤答
    ev(p, "const q = curP(); __t.enter('debit', q.debit[0][0], 1); __t.enter('credit', q.credit[0][0], 1); __t.cta()")
    assert ev(p, "document.querySelector('#q-fb-title').textContent") == "不正解…"
    assert ev(p, "queue.length") == 11
    assert ev(p, "progress[curP().id].due") == ev(p, "addDays(todayStr(), 1)")
    assert not p._errors, p._errors

@test("電卓：＝を押さずにOKで計算確定、÷0はE、12桁制限、メモは小数保持")
def t_calc(ctx):
    p = fresh_page(ctx)
    ev(p, "document.querySelector('#btn-today').click()")
    ev(p, """document.querySelector('.addline[data-side="debit"]').click();
             document.querySelectorAll('#acct-chips .chip')[0].click();
             __t.keys('800'); __t.press('×'); __t.keys('450'); __t.press('OK')""")
    assert ev(p, "entry.debit[0][1]") == 360000
    ev(p, "document.querySelector('#q-dlines .jline').click(); __t.press('C'); __t.keys('5'); __t.press('÷'); __t.keys('0'); __t.press('＝')")
    assert ev(p, "document.querySelector('#np-val').textContent") == "E"
    ev(p, "__t.press('OK')")
    assert ev(p, "document.querySelector('#sheet-num').classList.contains('on')"), "÷0 のまま確定できてしまう"
    ev(p, "closeSheet()")
    assert ev(p, "npCalc.clear(); __t ; '12345678901'.split('').forEach(d => npCalc.digit(d)); for(const c of '000') npCalc.digit(c); npCalc.cur.length") == 12
    assert ev(p, "cpCalc.clear(); cpCalc.digit('1'); cpCalc.digit('0'); cpCalc.pressOp('÷'); cpCalc.digit('4'); cpCalc.value(true)") == 2.5

@test("ダブルタップで拡大しない・ただしピンチ拡大は残す")
def t_doubletap(ctx):
    p = fresh_page(ctx)
    vp = ev(p, "document.querySelector('meta[name=viewport]').content")
    assert "user-scalable=no" not in vp and "maximum-scale" not in vp, "拡大そのものを禁止している（アクセシビリティ後退）: " + vp
    assert ev(p, "getComputedStyle(document.body).touchAction") == "manipulation", "ダブルタップ拡大が止まっていない"
    # シートの中でもピンチ拡大を殺していないこと
    for sel in ["#sheet-num", "#sheet-calc", "#sheet-acct"]:
        ta = ev(p, f"getComputedStyle(document.querySelector('{sel}')).touchAction")
        assert "pinch-zoom" in ta or ta in ("auto", "manipulation"), f"{sel} でピンチ拡大が殺されている: {ta}"

@test("電卓は市販と同じ並び（＝が右下・0が横長・OKはグリッド外）")
def t_pad_layout(ctx):
    p = fresh_page(ctx)
    for sel in ["#sheet-num", "#sheet-calc"]:
        rows = ev(p, """(() => {
          const g = document.querySelector('%s .npgrid');
          const out = []; let last = null, row = [];
          [...g.children].forEach(el => {
            const t = Math.round(el.getBoundingClientRect().top);
            if(last !== null && t !== last){ out.push(row.join(' ')); row = []; }
            last = t; row.push(el.textContent.trim());
          });
          out.push(row.join(' '));
          return out;
        })()""" % sel)
        assert rows == ["C ⌫ 000 ÷", "7 8 9 ×", "4 5 6 −", "1 2 3 ＋", "0 00 ＝"], (sel, rows)
        # ＝ はグリッドの最後＝右下
        assert ev(p, f"document.querySelector('{sel} .npgrid').lastElementChild.dataset.op") == "＝", sel
        # 0 は 00 のおよそ2倍幅
        w = ev(p, f"""(() => {{
          const g = document.querySelector('{sel} .npgrid');
          const z = g.querySelector('.zero').getBoundingClientRect().width;
          const d = [...g.querySelectorAll('.npk')].find(k => k.dataset.k === '00').getBoundingClientRect().width;
          return [Math.round(z), Math.round(d)];
        }})()""")
        assert w[0] > w[1] * 1.8, (sel, w)
        # 確定ボタンはグリッドの中に無い（＝の押し間違いを防ぐ）。表示行にだけ置く
        assert ev(p, f"document.querySelectorAll('{sel} .npgrid .okmini, {sel} .npgrid .okk, {sel} .npgrid .okwide').length") == 0, sel
        assert ev(p, f"!!document.querySelector('{sel} .npdisp .okmini')"), sel
    # 並べ替えても計算と確定は効く
    ev(p, "document.querySelector('#btn-today').click()")
    ev(p, """document.querySelector('.addline[data-side="debit"]').click();
             document.querySelectorAll('#acct-chips .chip')[0].click();
             __t.keys('12'); __t.press('000'); __t.press('＋'); __t.keys('5'); __t.press('00'); __t.press('＝')""")
    assert ev(p, "document.querySelector('#np-val').textContent") == "12,500"
    ev(p, "__t.press('OK')")
    assert ev(p, "entry.debit[0][1]") == 12500
    assert not p._errors, p._errors

@test("行の修正と削除（誤タップで消えない）")
def t_edit(ctx):
    p = fresh_page(ctx)
    ev(p, "document.querySelector('#btn-today').click()")
    ev(p, "__t.enter('debit', curP().cands[0], 111111)")
    ev(p, "document.querySelector('#q-dlines .jline').click()")
    assert ev(p, "document.querySelector('#np-val').textContent") == "111,111"
    assert ev(p, "document.querySelector('#np-del').classList.contains('on')")
    ev(p, "__t.keys('222222'); __t.press('OK')")
    assert ev(p, "entry.debit[0][1]") == 222222
    ev(p, "document.querySelector('#q-dlines .jline').click(); document.querySelector('#np-del').click()")
    assert ev(p, "entry.debit.length") == 0

@test("途中保存：入力途中→再読み込み→続きから復元、判定済みは二重採点しない")
def t_resume(ctx):
    p = fresh_page(ctx)
    ev(p, "startSession('retry', {ids:['S12','S13']}); __t.enter('debit','クレジット売掛金',288000)")
    p.reload(); p.wait_for_function("typeof PROBLEMS !== 'undefined'"); p.evaluate(HELPERS)
    assert not ev(p, "document.querySelector('#btn-resume').hidden")
    ev(p, "document.querySelector('#btn-resume').click()")
    assert ev(p, "entry.debit.length") == 1 and ev(p, "curP().id") == "S12"
    ev(p, "__t.enter('debit','支払手数料',12000); __t.enter('credit','売上',300000); __t.cta()")
    assert ev(p, "document.querySelector('#q-fb-title').textContent") == "正解！"
    box_before = ev(p, "progress['S12'].box")
    p.reload(); p.wait_for_function("typeof PROBLEMS !== 'undefined'"); p.evaluate(HELPERS)
    ev(p, "document.querySelector('#btn-resume').click()")
    assert ev(p, "curP().id") == "S13", "判定済みの問題を再表示している"
    assert ev(p, "progress['S12'].box") == box_before

@test("結果画面：初見の得点・論点別・間違えた問題だけ再挑戦・シェア文")
def t_result(ctx):
    p = fresh_page(ctx)
    ev(p, "settings.n = 3; saveSettings(); document.querySelector('#btn-today').click()")
    ev(p, "__t.answerCorrect()"); wait_cta(p); ev(p, "__t.cta()")
    ev(p, "const q = curP(); __t.enter('debit', q.debit[0][0], 1); __t.enter('credit', q.credit[0][0], 1); __t.cta()"); wait_cta(p); ev(p, "__t.cta()")
    ev(p, "__t.answerCorrect()"); wait_cta(p); ev(p, "__t.cta()")
    ev(p, "__t.answerCorrect()"); wait_cta(p); ev(p, "__t.cta()")  # 再出題分
    assert ev(p, "mode") == "result"
    assert ev(p, "document.querySelector('#r-score').textContent") == "3/3駅", "停車駅を再挑戦でクリアしたら全駅クリア"
    assert ev(p, "document.querySelector('#r-title').textContent") == "全駅停車で完走"
    assert "2/3" in ev(p, "document.querySelector('#r-stats').textContent"), "一発正解の数は別に残す"
    assert ev(p, "document.querySelectorAll('#r-wrongs .w').length") == 1
    ev(p, "Object.defineProperty(navigator, 'share', {value: undefined, configurable: true}); window.__copied = null; navigator.clipboard.writeText = t => { window.__copied = t; return Promise.resolve(); }; document.querySelector('#r-share').click()")
    p.wait_for_function("window.__copied !== null")
    txt = ev(p, "window.__copied")
    assert "3/3駅" in txt and "#ボキトレイン" in txt and "github.io" in txt, txt
    ev(p, "document.querySelector('#r-retry').click()")
    assert ev(p, "queue.length") == 1

@test("進行：分母は固定・電車は毎問進む・正解は解説を畳む・コンボ／箱／論点が動く・途中保存に残る")
def t_progress(ctx):
    p = fresh_page(ctx)
    ev(p, "document.querySelector('#btn-today').click()")
    assert ev(p, "stations.length") == 10
    assert ev(p, "document.querySelectorAll('#q-route .st').length") == 10
    assert ev(p, "document.querySelector('#q-count').textContent").startswith("0/10駅")
    x0 = ev(p, "parseFloat(document.querySelector('#q-route .train').style.left)")
    # 3問間違えても分母は10のまま。電車は先へ進み、駅が停車（黄）になる
    for _ in range(3):
        ev(p, "const q=curP(); __t.enter('debit',q.debit[0][0],1); __t.enter('credit',q.credit[0][0],1); __t.cta()")
        wait_cta(p); ev(p, "__t.cta()")
    cnt = ev(p, "document.querySelector('#q-count').textContent")
    assert cnt.startswith("0/10駅") and "停車3" in cnt, cnt
    assert ev(p, "queue.length") == 13, "再挑戦はキューには足す"
    assert ev(p, "document.querySelectorAll('#q-route .st.miss').length") == 3
    assert ev(p, "parseFloat(document.querySelector('#q-route .train').style.left)") > x0, "間違えても電車は先へ進む"
    # 正解：解説は畳まれ、駅・箱・論点のご褒美が出る
    ev(p, "__t.answerCorrect()")
    assert ev(p, "document.querySelector('#q-fb-more').open") is False, "正解なのに解説が開いている"
    rw = ev(p, "document.querySelector('#q-reward').textContent")
    assert "4駅目に到着" in rw and "○○○○○ → ●○○○○" in rw and "% →" in rw, rw   # 路線上の位置＝4駅目（1〜3駅目は停車中）
    assert ev(p, "document.querySelectorAll('#q-reward .rw.stn').length") == 0, "路線図用の .stn がご褒美ピルに混ざっている"
    assert ev(p, "document.querySelector('#q-count').textContent").startswith("1/10駅")
    wait_cta(p); ev(p, "__t.cta()")
    ev(p, "__t.answerCorrect()")
    assert "2連続" in ev(p, "document.querySelector('#q-reward').textContent")
    assert ev(p, "combo") == 2 and ev(p, "comboMax") == 2 and ev(p, "boxUps") == 2
    # 不正解：解説は開いた状態、コンボは切れる
    wait_cta(p); ev(p, "__t.cta()")
    ev(p, "const q=curP(); __t.enter('debit',q.debit[0][0],1); __t.enter('credit',q.credit[0][0],1); __t.cta()")
    assert ev(p, "document.querySelector('#q-fb-more').open") is True
    assert ev(p, "combo") == 0 and ev(p, "comboMax") == 2
    # 途中保存に駅の状態が入り、再読み込みで復元される
    st = ev(p, "JSON.stringify(stState)")
    p.reload(); p.wait_for_function("typeof PROBLEMS !== 'undefined'"); p.evaluate(HELPERS)
    ev(p, "document.querySelector('#btn-resume').click()")
    assert ev(p, "JSON.stringify(stState)") == st and ev(p, "stations.length") == 10 and ev(p, "comboMax") == 2
    assert ev(p, "document.querySelectorAll('#q-route .st.miss').length") == 4
    assert not p._errors, p._errors

@test("終点到着：路線が点灯・称号・最大コンボ・きょうの積み上げ・一発完走で紙吹雪")
def t_arrive(ctx):
    p = fresh_page(ctx)
    ev(p, "settings.n = 3; saveSettings(); document.querySelector('#btn-today').click()")
    for _ in range(3):
        ev(p, "__t.answerCorrect()"); wait_cta(p); ev(p, "__t.cta()")
    assert ev(p, "mode") == "result"
    assert ev(p, "document.querySelector('#r-title').textContent") == "ノンストップ運転"
    assert ev(p, "document.querySelector('#r-score').textContent") == "3/3駅"
    assert ev(p, "document.querySelectorAll('#r-route .st.ok.light').length") == 3
    s = ev(p, "document.querySelector('#r-stats').textContent")
    assert "3/3" in s and "3連続" in s and "3個" in s, s
    assert "3問" in ev(p, "document.querySelector('#r-today').textContent")
    assert ev(p, "document.querySelectorAll('#r-confetti i').length") > 0, "一発完走なのに紙吹雪が無い"
    p.wait_for_timeout(200)
    assert ev(p, "parseFloat(document.querySelector('#r-route .train').style.left)") > 0, "電車が終点まで走っていない"
    assert not p._errors, p._errors

@test("路線図：商業線・工業線の2本、駅数＝論点数、定着した論点が「開通」になる")
def t_routemap(ctx):
    p = fresh_page(ctx)
    ev(p, "setTab('map')")
    assert ev(p, "document.querySelectorAll('#h-tmap .line').length") == 2
    assert ev(p, "document.querySelectorAll('#h-tmap .stn').length") == ev(p, "topicStats().length")
    assert ev(p, "document.querySelectorAll('#h-tmap .stn.s2').length") == 0
    assert "駅 開通" in ev(p, "document.querySelector('#h-tmap .lhead').textContent")
    ev(p, "const st = topicStats()[0]; PROBLEMS.filter(q => q.cat===st.cat && q.topic===st.topic).forEach(q => { progress[q.id] = {box:3, due:'2099-01-01', seen:1, wrong:0}; }); store.set('progress', progress); renderHome()")
    assert ev(p, "document.querySelectorAll('#h-tmap .stn.s2').length") == 1
    assert ev(p, "document.querySelector('#h-tmap .stn.s2 .st').textContent") == "開通"
    assert "開通 1/" in ev(p, "document.querySelector('#h-teaser-map-t').textContent")
    ev(p, "document.querySelector('#h-tmap .stn').click()")
    assert ev(p, "mode") == "quiz", "駅をタップしたら論点ドリルが始まる"
    assert not p._errors, p._errors

@test("合格までの道のり：開通／模試／本番の3段・試験日で残り日数・模試の最高点・タップで各タブ・連続を煽らない")
def t_journey(ctx):
    p = fresh_page(ctx)
    steps = ev(p, "[...document.querySelectorAll('#h-journey .jstep')].map(b => b.className.replace('jstep ','') + '|' + b.textContent)")
    assert len(steps) == 3, steps
    assert steps[0].startswith("cur|開通0/") and "未受験" in steps[1] and "試験日を設定" in steps[2], steps
    ev(p, "const d = addDays(todayStr(), 30); const i = document.querySelector('#set-examdate'); i.value = d; i.dispatchEvent(new Event('change'))")
    assert "あと30日" in ev(p, "document.querySelectorAll('#h-journey .jstep')[2].textContent")
    assert ev(p, "getSettings().examDate") == ev(p, "addDays(todayStr(), 30)")
    ev(p, "examLog = {M1:{date:todayStr(), score:72, best:72}}; store.set('examlog', examLog); renderHome()")
    assert ev(p, "document.querySelectorAll('#h-journey .jstep')[1].className") == "jstep done"
    assert "72点" in ev(p, "document.querySelectorAll('#h-journey .jstep')[1].textContent")
    ev(p, "document.querySelectorAll('#h-journey .jstep')[0].click()")
    assert ev(p, "tab") == "map"
    assert "週3日" not in ev(p, "document.querySelector('#h-teaser-week-t').textContent"), "継続を煽る文言が残っている"
    # 壊れた試験日は捨てる
    ev(p, "localStorage.setItem('bokitore:settings', JSON.stringify({examDate:'2026/12/01'}))")
    assert ev(p, "getSettings().examDate") == ""
    assert not p._errors, p._errors

@test("操作バー（判定する／この欄に入力する）はブラウザ下部ツールバーに隠れず、最下端の帯にも置かず、シートを閉じても死なない")
def t_actionbar(ctx):
    p = fresh_page(ctx)
    ev(p, "startDrill('D1')")
    # ツールバーで見える領域が88px縮んだ状態
    ev(p, "Object.defineProperty(window,'visualViewport',{configurable:true, value:{height: window.innerHeight - 88, offsetTop:0, addEventListener(){}, removeEventListener(){}}}); fitBottom()")
    assert ev(p, "document.querySelector('.actionbar').style.bottom") == "88px"
    r = ev(p, "(() => { const b = document.querySelector('#cta').getBoundingClientRect(); return {bottom: Math.round(b.bottom), vis: window.innerHeight - 88}; })()")
    assert r["bottom"] <= r["vis"], r
    # ツールバーが畳まれていても、画面の最下端ぎりぎりには置かない
    ev(p, "Object.defineProperty(window,'visualViewport',{configurable:true, value:{height: window.innerHeight, offsetTop:0, addEventListener(){}, removeEventListener(){}}}); fitBottom()")
    gap = ev(p, "window.innerHeight - document.querySelector('#cta').getBoundingClientRect().bottom")
    assert gap >= 28, gap
    # シートを開いて閉じても操作バーは死なない（inert を使わない）
    ev(p, "answerB()")
    assert ev(p, "document.querySelector('.actionbar').classList.contains('behind')")
    ev(p, "closeSheet()")
    assert not ev(p, "document.querySelector('.actionbar').classList.contains('behind')")
    assert ev(p, "!document.querySelector('.actionbar').inert"), "操作バーに inert が残っている"
    ev(p, "document.querySelector('#cta').click()")
    assert ev(p, "document.querySelector('#sheet-num').classList.contains('on')"), "シートを閉じたあとにボタンが効かない"
    assert not p._errors, p._errors

@test("ドリル：いま解く番でない「？」をタップしたら、どこを入力する番か知らせる")
def t_blank_hint(ctx):
    p = fresh_page(ctx)
    ev(p, "startDrill('D1')")
    ev(p, "[...document.querySelectorAll('#b-boxes .blank')].find(b => !b.classList.contains('active')).click()")
    t = ev(p, "document.querySelector('#toast').textContent")
    assert "STEP 1" in t, t
    assert not ev(p, "document.querySelector('#sheet-num').classList.contains('on')")
    assert not p._errors, p._errors

@test("長押しで文字選択・コピーの吹き出しが出ない（入力欄だけは選択できる）")
def t_noselect(ctx):
    p = fresh_page(ctx)
    # WebKit（Safari）は userSelect でなく webkitUserSelect に値を返すので両方見る
    US = "(el => { const s = getComputedStyle(el); return s.userSelect || s.webkitUserSelect; })"
    assert ev(p, f"{US}(document.body)") == "none"
    ev(p, "document.querySelector('#btn-today').click()")
    for sel in ["#q-text", "#cta", ".addline", "#tabbar", ".jline, .jstep", "#sheet-num .npk"]:
        us = ev(p, f"(() => {{ const el = document.querySelector('{sel}'); return el ? {US}(el) : 'none'; }})()")
        assert us == "none", (sel, us)
    ev(p, "openSheet(document.querySelector('#sheet-calc'))")
    assert ev(p, f"{US}(document.querySelector('#memo'))") == "text", "メモ欄が選択できない"
    assert ev(p, f"{US}(document.querySelector('#set-examdate'))") == "text"
    assert not p._errors, p._errors

@test("ドリル：空欄タップで入力、誤答でヒント、選択式、途中再開、完答でコレクション")
def t_drill(ctx):
    p = fresh_page(ctx)
    ev(p, "startDrill('D1')")
    ev(p, "document.querySelector('.blank.active').click(); __t.keys('200'); __t.press('OK')")
    assert ev(p, "bi") == 1
    ev(p, "__t.cta(); __t.keys('1'); __t.press('OK')")  # 誤答
    # 誤答：その場に「おしい！」シート（スクロールさせない）。ヒントは選んだ時だけ、番は進まない
    assert ev(p, "document.querySelector('#sheet-miss').classList.contains('on')"), "不正解シートが出ない"
    assert "STEP 2" in ev(p, "document.querySelector('#miss-body').textContent")
    assert ev(p, "getComputedStyle(document.querySelector('#miss-hint')).display") == "none", "頼んでいないのにヒントが見えている"
    ev(p, "document.querySelector('#miss-hint-btn').click()")
    assert ev(p, "getComputedStyle(document.querySelector('#miss-hint')).display") != "none" and "420" in ev(p, "document.querySelector('#miss-hint').textContent")
    assert ev(p, "(() => { const b = document.querySelector('#b-boxes .blank.active'); return b.classList.contains('wrong') && b.textContent.includes('1'); })()"), "誤答の値が欄に見えない"
    assert ev(p, "bi") == 1
    ev(p, "document.querySelector('#miss-retry').click()")
    assert ev(p, "document.querySelector('#sheet-num').classList.contains('on')"), "「もう一度入力」でテンキーが開かない"
    ev(p, "closeSheet()")
    ev(p, "__t.cta(); __t.keys('168000'); __t.press('OK')")
    assert ev(p, "store.get('drillpos')") == {"id": "D1", "bi": 2}
    p.reload(); p.wait_for_function("typeof PROBLEMS !== 'undefined'"); p.evaluate(HELPERS)
    assert "続き" in ev(p, "document.querySelector('#h-next-drill-t').textContent")
    ev(p, "document.querySelector('#h-next-drill').click()")
    assert ev(p, "bi") == 2 and ev(p, "document.querySelectorAll('#b-boxes .blank.done').length") == 2
    for v in ["672000", "120000", "960000", "288000", "1632000"]:
        ev(p, f"__t.cta(); __t.keys('{v}'); __t.press('OK')")
    assert ev(p, "bDone") and ev(p, "drillDone.D1") == 1 and ev(p, "store.get('drillpos')") is None
    # D3 選択式
    ev(p, "startDrill('D3')")
    for v in ["2000", "1000000", "42000"]:
        ev(p, f"__t.cta(); __t.keys('{v}'); __t.press('OK')")
    ev(p, "__t.cta()")
    assert ev(p, "[...document.querySelectorAll('#acct-chips .chip')].map(c => c.textContent)") == ["有利差異", "不利差異"]
    ev(p, "__t.chip('不利差異')")
    assert ev(p, "document.querySelector('#sheet-miss').classList.contains('on')")
    ev(p, "document.querySelector('#miss-retry').click(); __t.chip('有利差異'); __t.cta(); __t.keys('50000'); __t.press('OK'); __t.cta(); __t.chip('不利差異')")
    assert ev(p, "document.querySelector('#b-fb-title').textContent") == "完答！"
    ev(p, "goHome()"); p.wait_for_function("mode === 'home'")
    assert ev(p, "document.querySelectorAll('#h-collect .fig.on').length") == 2

@test("タブ・次の未踏論点・戻る操作（履歴）・設定・リセット確認")
def t_nav(ctx):
    p = fresh_page(ctx)
    ev(p, "document.querySelector('#tabbar button[data-tab=\"map\"]').click(); document.querySelector('#btn-next-topic').click()")
    assert ev(p, "mode") == "quiz" and ev(p, "history.state.v") == "quiz"
    p.go_back(); p.wait_for_function("mode === 'home'")
    assert ev(p, "tab") == "map", "開始元のタブに戻っていない"
    ev(p, "document.querySelector('#tabbar button[data-tab=\"record\"]').click()")
    assert ev(p, "document.querySelectorAll('#h-week .day').length") == 7
    ev(p, "document.querySelector('.seg[data-set=\"theme\"] button[data-v=\"dark\"]').click()")
    assert ev(p, "document.documentElement.getAttribute('data-theme')") == "dark"
    ev(p, "document.querySelector('.seg[data-set=\"n\"] button[data-v=\"3\"]').click()")
    assert "新規 3" in ev(p, "document.querySelector('#btn-today').textContent")
    ev(p, "document.querySelector('#btn-reset').click()")
    assert ev(p, "[...document.querySelectorAll('#acct-chips .chip')].map(c => c.textContent)") == ["リセットする", "やめる"]
    ev(p, "__t.chip('やめる')")
    ev(p, "document.querySelector('#btn-reset').click(); __t.chip('リセットする')")
    assert ev(p, "Object.keys(progress).length") == 0
    ev(p, "document.querySelector('.seg[data-set=\"theme\"] button[data-v=\"system\"]').click()")

@test("復習ロジック：期日前の問題を混ぜない・全問学習済みなら弱点から")
def t_srs(ctx):
    p = fresh_page(ctx)
    ev(p, "const t = todayStr(); PROBLEMS.forEach(q => progress[q.id] = {box:3, due:addDays(t,7), seen:1, wrong:0}); store.set('progress', progress); renderHome()")
    assert "もう一周" in ev(p, "document.querySelector('#btn-today').textContent")
    ev(p, "document.querySelector('#btn-today').click()"); assert ev(p, "queue.length") == 10
    ev(p, "goHome()"); p.wait_for_function("mode === 'home'")
    ev(p, "['S01','S02','S03'].forEach(id => progress[id].due = todayStr()); store.set('progress', progress); renderHome(); document.querySelector('#btn-today').click()")
    assert sorted(ev(p, "queue")) == ["S01", "S02", "S03"]

@test("壊れた保存データでも起動する")
def t_corrupt(ctx):
    p = fresh_page(ctx)
    ev(p, "localStorage.setItem('bokitore:progress', 'null'); localStorage.setItem('bokitore:days', '[1,2]'); localStorage.setItem('bokitore:session', '{\"v\":2,\"queue\":\"x\"}'); localStorage.setItem('bokitore:settings', '{\"n\":\"x\",\"cat\":1}')")
    p.reload(); p.wait_for_function("typeof PROBLEMS !== 'undefined'")
    assert ev(p, "settings.n") == 10 and ev(p, "settings.cat") == "both"
    assert ev(p, "document.querySelector('#btn-resume').hidden")
    assert not p._errors, p._errors

@test("小さい画面（320×568）でも横スクロールが出ずタブバーが見える")
def t_small(ctx):
    p = fresh_page(ctx)
    p.set_viewport_size({"width": 320, "height": 568})
    ev(p, "renderHome()")
    assert ev(p, "document.scrollingElement.scrollWidth <= window.innerWidth")
    r = ev(p, "(() => { const b = document.querySelector('#tabbar').getBoundingClientRect(); return b.bottom <= window.innerHeight && b.width > 0; })()")
    assert r, "タブバーが画面内に収まっていない"

@test("模試データ：満点100・設問配点と欄配点が一致・答案用紙の欄と解答が1対1")
def t_exam_data(ctx):
    p = fresh_page(ctx)
    bad = ev(p, """(() => {
      const ng = [];
      for(const ex of EXAMS){
        let tot = 0;
        ex.sections.forEach((sec, si) => {
          tot += sec.pt;
          if(sec.blocks.reduce((a,b)=>a+b.pt,0) !== sec.pt) ng.push(ex.id+' '+sec.name+' ブロック配点');
          sec.blocks.forEach((b, bi) => {
            if(!b.expl) ng.push(ex.id+' '+sec.name+' 解説なし');
            if(b.kind === 'je'){
              const d = b.debit.reduce((s,l)=>s+l[1],0), c = b.credit.reduce((s,l)=>s+l[1],0);
              if(d !== c) ng.push(ex.id+' '+sec.name+' 貸借不一致');
              if(b.debit.length > b.rows || b.credit.length > b.rows) ng.push(ex.id+' '+sec.name+' 行数不足');
              for(const l of [...b.debit, ...b.credit]) if(!b.cands.includes(l[0])) ng.push(ex.id+' '+sec.name+' 候補に無い科目 '+l[0]);
            } else {
              if(b.fields.reduce((a,f)=>a+f.pt,0) !== b.pt) ng.push(ex.id+' '+sec.name+' 欄配点');
              const inSheet = (b.sheet.match(/data-f="/g) || []).length;
              if(inSheet !== b.fields.length) ng.push(ex.id+' '+sec.name+' 欄数 '+inSheet+'≠'+b.fields.length);
              for(const f of b.fields){
                if(b.sheet.split('data-f="'+f.k+'"').length !== 2) ng.push(ex.id+' '+sec.name+' 欄 '+f.k);
                if(f.kind === 'choice' && !f.opts.includes(f.a)) ng.push(ex.id+' '+sec.name+' 選択肢 '+f.k);
              }
            }
          });
        });
        if(tot !== 100) ng.push(ex.id+' 満点'+tot);
      }
      return ng;
    })()""")
    assert bad == [], bad

@test("模試：UIで仕訳と穴埋めを入力→大問ナビの記入数と保留🚩が動く")
def t_exam_ui(ctx):
    p = fresh_page(ctx)
    ev(p, "setTab('exam'); document.querySelector('#h-exams .examcard').click()")
    assert ev(p, "mode") == "exam"
    assert ev(p, "exRemain") == 90 * 60
    assert ev(p, "document.body.classList.contains('wide')")
    assert ev(p, "document.querySelectorAll('#e-nav button').length") == 6   # 第1〜5問＋見直し
    # 第1問(1)を答案用紙どおりに入力（借方2行・貸方2行）
    ev(p, "__t.jeSet(0,0,'debit',0,'前受金',800000)")
    ev(p, "__t.jeSet(0,0,'debit',1,'役務原価',560000)")
    assert ev(p, "document.querySelector('#e-nav button .n').textContent") == "0/5", "貸方が空なら未記入のまま"
    ev(p, "__t.jeSet(0,0,'credit',0,'役務収益',800000)")
    ev(p, "__t.jeSet(0,0,'credit',1,'仕掛品',560000)")
    assert ev(p, "document.querySelector('#e-nav button .n').textContent") == "1/5"
    assert ev(p, "exAns['S0B0_d0a']") == "前受金"
    # 保留マーク
    ev(p, "document.querySelector('#e-flag').click()")
    assert ev(p, "document.querySelectorAll('#e-nav button.flag').length") == 1
    # 第5問の選択欄（有利／不利）と金額欄
    ev(p, "__t.examGo(4)")
    ev(p, "__t.setNum('S4B0_e1', 120000)")
    ev(p, "__t.setChip('S4B0_e2', '有利差異')")
    assert ev(p, """document.querySelector('#e-body .fld[data-k="S4B0_e2"]').textContent""") == "有利差異"
    assert ev(p, "secStat(4)[0]") == 2
    assert not p._errors, p._errors

@test("模試：中断して戻ると答案と残り時間が復元される")
def t_exam_resume(ctx):
    p = fresh_page(ctx)
    ev(p, "startExam('M1'); __t.examClock(4200); __t.setNum('S0B0_d0m', 800000); saveExam(); goHome()")
    p.wait_for_function("mode === 'home'", timeout=3000)
    assert ev(p, "exTimer === null"), "ホームに戻っても時計が動いている"
    assert 4199 <= ev(p, "savedExam().remain") <= 4200, ev(p, "savedExam().remain")
    assert "中断中" in ev(p, "document.querySelector('#h-exams .badge.hold').textContent")
    ev(p, "startExam('M1')")
    assert ev(p, "exAns['S0B0_d0m']") == 800000
    assert 4199 <= ev(p, "exRemain") <= 4200
    # 「最初からやり直す」で消える
    ev(p, "startExam('M1', true)")
    assert ev(p, "exAns['S0B0_d0m']") is None
    assert ev(p, "exRemain") == 90 * 60
    assert not p._errors, p._errors

@test("模試：全問正解で100点・合格、白紙は0点、部分点は欄単位")
def t_exam_score(ctx):
    p = fresh_page(ctx)
    ev(p, "startExam('M1'); __t.examFill(true); submitExam(true)")
    assert ev(p, "mode") == "examresult"
    assert ev(p, "exResult.total") == 100, ev(p, "exResult.secs")
    assert "合格ライン" in ev(p, "document.querySelector('#er-judge').textContent")
    assert ev(p, "exResult.secs.map(s => s.got)") == [20, 20, 20, 28, 12]
    assert ev(p, "examLog.M1.score") == 100 and ev(p, "examLog.M1.best") == 100
    assert ev(p, "localStorage.getItem('bokitore:exam')") is None, "提出後も中断データが残っている"
    # 白紙
    ev(p, "startExam('M1', true); submitExam(true)")
    assert ev(p, "exResult.total") == 0
    assert ev(p, "examLog.M1.best") == 100, "最高点が下書きされてしまう"
    # 部分点：第3問の1欄だけ正解＝2点、第1問(1)は貸方1行欠けで0点（部分点なし）
    ev(p, """startExam('M1', true);
             exAns['S2B0_p1'] = 7187000;
             exAns['S0B0_d0a'] = '前受金'; exAns['S0B0_d0m'] = 800000;
             exAns['S0B0_d1a'] = '役務原価'; exAns['S0B0_d1m'] = 560000;
             exAns['S0B0_c0a'] = '役務収益'; exAns['S0B0_c0m'] = 800000;
             submitExam(true)""")
    assert ev(p, "exResult.total") == 2, ev(p, "exResult.secs.map(s => s.got)")
    assert not p._errors, p._errors

@test("模試：時間切れで自動提出される")
def t_exam_timeup(ctx):
    p = fresh_page(ctx)
    ev(p, "startExam('M1'); __t.examFill(true); __t.examClock(2)")
    p.wait_for_function("mode === 'examresult'", timeout=6000)
    assert ev(p, "exResult.total") == 100
    assert ev(p, "exTimer === null")
    assert ev(p, "exSubmitted")
    assert not p._errors, p._errors

@test("模試：残り時間は経過した実時間で減る（裏に回っても巻き戻らない）")
def t_exam_clock(ctx):
    p = fresh_page(ctx)
    ev(p, "startExam('M1'); __t.examClock(600); exDeadline -= 30000")   # 30秒ぶん裏に回った状態を作る
    p.wait_for_function("exRemain <= 571", timeout=3000)
    assert ev(p, "exRemain") <= 571, "tick回数で数えていて、止まっていた時間が試験時間から抜けている"
    ev(p, "goHome()"); p.wait_for_function("mode === 'home'")   # 「←」は履歴経由で非同期（WebKitで顕在化）
    assert ev(p, "exDeadline") == 0 and ev(p, "exTimer === null")
    assert ev(p, "savedExam().remain") <= 571, "中断時の残り時間が実時間と合っていない"
    assert not p._errors, p._errors

@test("模試：書きかけの行は不正解・同じ側に同じ科目は選べない")
def t_exam_je_strict(ctx):
    p = fresh_page(ctx)
    # 借方2行目に科目だけ書いてある状態（金額なし）は「無視して正解」にしない
    ev(p, """startExam('M1', true);
             exAns['S0B0_d0a'] = '前受金';   exAns['S0B0_d0m'] = 800000;
             exAns['S0B0_d1a'] = '役務原価'; exAns['S0B0_d1m'] = 560000;
             exAns['S0B0_c0a'] = '役務収益'; exAns['S0B0_c0m'] = 800000;
             exAns['S0B0_c1a'] = '仕掛品';   exAns['S0B0_c1m'] = 560000;
             exAns['S0B0_d2a'] = '現金';
             submitExam(true)""")
    assert ev(p, "exResult.secs[0].got") == 0, "科目だけの書きかけ行が無視されている"
    # 金額だけの行も同じ
    ev(p, """startExam('M1', true);
             exAns['S0B0_d0a'] = '前受金';   exAns['S0B0_d0m'] = 800000;
             exAns['S0B0_d1a'] = '役務原価'; exAns['S0B0_d1m'] = 560000;
             exAns['S0B0_c0a'] = '役務収益'; exAns['S0B0_c0m'] = 800000;
             exAns['S0B0_c1a'] = '仕掛品';   exAns['S0B0_c1m'] = 560000;
             exAns['S0B0_d2m'] = 1;
             submitExam(true)""")
    assert ev(p, "exResult.secs[0].got") == 0, "金額だけの書きかけ行が無視されている"
    # 同じ側で使用済みの科目は選択肢に出ない
    ev(p, "startExam('M1', true); __t.setChip('S0B0_d0a', '前受金'); __t.fld('S0B0_d1a')")
    opts = ev(p, "[...document.querySelectorAll('#acct-chips .chip')].map(c => c.textContent)")
    assert "前受金" not in opts, "同じ側に同じ科目を2回書けてしまう"
    assert "（空欄）" in opts and "役務原価" in opts, opts
    ev(p, "closeSheet(); __t.fld('S0B0_c0a')")   # 貸方は制限を受けない
    assert "前受金" in ev(p, "[...document.querySelectorAll('#acct-chips .chip')].map(c => c.textContent)")
    assert not p._errors, p._errors

@test("模試：提出後は答案を書き換えられず、二重提出もしない")
def t_exam_after_submit(ctx):
    p = fresh_page(ctx)
    ev(p, "startExam('M1'); __t.examFill(true); submitExam(true)")
    before = ev(p, "days[todayStr()]")
    ev(p, "setField('S0B0_d0m', 1); openField('S0B0_d0m')")
    assert ev(p, "exAns['S0B0_d0m']") == 800000, "提出後に答案を書き換えられる"
    assert not ev(p, "document.querySelector('#sheet-num').classList.contains('on')"), "提出後に入力シートが開く"
    ev(p, "submitExam(true); submitExam(false)")
    assert ev(p, "days[todayStr()]") == before, "二重提出で学習回数が二重計上される"
    assert ev(p, "examLog.M1.score") == 100
    assert not p._errors, p._errors

@test("模試：壊れた中断データを読み込んでも起動する")
def t_exam_corrupt(ctx):
    p = fresh_page(ctx)
    ev(p, "localStorage.setItem('bokitore:exam', JSON.stringify({v:2, id:'M1', sec:99, ans:{a:{}, b:-1, c:'ok'}, flag:'x', remain:-5}))")
    p.reload(); p.wait_for_function("typeof EXAMS !== 'undefined'")
    assert ev(p, "savedExam()") is None, "残り0以下の中断データを拾ってしまう"
    ev(p, "localStorage.setItem('bokitore:exam', JSON.stringify({v:2, id:'M1', sec:99, ans:{a:{}, b:-1, c:'ok'}, flag:'x', remain:600}))")
    p.reload(); p.wait_for_function("typeof EXAMS !== 'undefined'")
    sv = ev(p, "savedExam()")
    assert sv["sec"] == 0 and sv["ans"] == {"c": "ok"} and sv["flag"] == {}, sv
    ev(p, "startExam('M1')")
    assert ev(p, "mode") == "exam"
    assert not p._errors, p._errors


@test("現在地：タブごとに見出しが変わり、画面遷移には方向付きの動きが付く。きょうの主ボタンが最初に見える")
def t_wayfinding(ctx):
    p = fresh_page(ctx)
    assert ev(p, "document.querySelector('#h-title').textContent") == "きょう"
    assert ev(p, "document.querySelector('#btn-today').getBoundingClientRect().top < document.querySelector('#h-journey').getBoundingClientRect().top"), "主ボタンが最初に無い"
    ev(p, "document.querySelector('#tabbar button[data-tab=\"drills\"]').click()")
    assert ev(p, "document.querySelector('#h-title').textContent") == "計算ドリル"
    assert ev(p, "document.querySelector('#pane-drills').classList.contains('anim-tab')"), "タブ切替に動きが無い"
    ev(p, "startDrill('D1')")
    assert ev(p, "document.querySelector('#scr-drill').classList.contains('anim-push')"), "奥へ進む動きが無い"
    assert "平均法" in ev(p, "document.querySelector('#b-title').textContent")
    ev(p, "goHome()"); p.wait_for_function("mode === 'home'")
    assert ev(p, "document.querySelector('#h-title').textContent") == "計算ドリル", "戻ったのに開始元のタブ見出しでない"
    ev(p, "document.querySelector('#tabbar button[data-tab=\"today\"]').click(); document.querySelector('#btn-today').click()")
    assert ev(p, "document.querySelector('#q-title').textContent").startswith("仕訳 · ")
    assert not p._errors, p._errors

# ---------------- 実行 ----------------
def main():
    if not os.path.exists(os.path.join(HERE, "bokitore.html")):
        print("bokitore.html がありません。先に python build.py を実行してください。"); sys.exit(2)
    httpd = serve()
    failed = 0
    with sync_playwright() as pw:
        browser = getattr(pw, os.environ.get("BOKI_BROWSER", "chromium")).launch()
        for fn in results:
            ctx = browser.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ja-JP")
            try:
                fn(ctx); print("PASS ", fn._test_name)
            except Exception as e:
                failed += 1; print("FAIL ", fn._test_name); print("      ", type(e).__name__, str(e)[:300])
            finally:
                ctx.close()
        browser.close()
    httpd.shutdown()
    print("----"); print(f"{len(results) - failed} / {len(results)} passed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
