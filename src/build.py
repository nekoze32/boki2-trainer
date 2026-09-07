# -*- coding: utf-8 -*-
"""ボキトレ ビルド：問題バンク＋計算ドリルをテンプレートへ差し込み、
   artifact用（フラグメント）と standalone（完全なHTML文書）の2本を出力する。"""
import json, sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from exams import EXAMS
SYL = "2026"  # 出題区分の年度版

# ---------- 旧10問（v1）に論点タグを付けて取り込む ----------
BASE = [
 {"id":"S01","cat":"商業","topic":"債権債務","level":1,
  "text":"商品 ¥300,000 をクレジット払いの条件で販売した。信販会社へのクレジット手数料（販売代金の2%）は販売時に計上する。",
  "cands":["クレジット売掛金","売掛金","支払手数料","売上","受取手数料","現金"],
  "debit":[["クレジット売掛金",294000],["支払手数料",6000]],"credit":[["売上",300000]],
  "expl":"手数料 300,000×2%＝6,000 を差し引いた残額がクレジット売掛金。売上は総額の300,000で計上します。"},
 {"id":"S02","cat":"商業","topic":"固定資産","level":2,
  "text":"決算につき、備品（取得原価 ¥500,000、期首減価償却累計額 ¥200,000）について 200%定率法（耐用年数5年）により減価償却を行う。記帳は間接法による。",
  "cands":["減価償却費","備品減価償却累計額","備品","固定資産除却損","貯蔵品","未払金"],
  "debit":[["減価償却費",120000]],"credit":[["備品減価償却累計額",120000]],
  "expl":"償却率＝1/5×200%＝0.4。期首帳簿価額（500,000−200,000）＝300,000 に 0.4 を掛けて 120,000。"},
 {"id":"S03","cat":"商業","topic":"有価証券","level":1,
  "text":"売買目的で上場株式100株を1株 ¥1,200 で購入し、購入手数料 ¥3,000 とともに代金は後日証券会社へ支払うこととした。",
  "cands":["売買目的有価証券","満期保有目的債券","未払金","買掛金","支払手数料","現金"],
  "debit":[["売買目的有価証券",123000]],"credit":[["未払金",123000]],
  "expl":"1,200×100＋3,000＝123,000。付随費用（購入手数料）は取得原価に含めます。商品以外の未払いは買掛金でなく未払金。"},
 {"id":"S04","cat":"商業","topic":"引当金","level":2,
  "text":"従業員に賞与 ¥1,200,000 を支給し、源泉所得税 ¥100,000 を差し引いた残額を当座預金口座から振り込んだ。なお、前期決算において賞与引当金 ¥800,000 を設定している。",
  "cands":["賞与引当金","賞与","所得税預り金","当座預金","現金","法定福利費"],
  "debit":[["賞与引当金",800000],["賞与",400000]],"credit":[["所得税預り金",100000],["当座預金",1100000]],
  "expl":"引当金 800,000 を取り崩し、超える 400,000 だけ当期の費用（賞与）。振込額は 1,200,000−100,000＝1,100,000。"},
 {"id":"S05","cat":"商業","topic":"リース","level":2,
  "text":"×1年4月1日、備品についてリース契約（ファイナンス・リース取引に該当、リース料年額 ¥60,000・リース期間5年）を締結し、リース取引を開始した。利子込み法により処理する。",
  "cands":["リース資産","リース債務","支払リース料","備品","支払利息","未払金"],
  "debit":[["リース資産",300000]],"credit":[["リース債務",300000]],
  "expl":"利子込み法ではリース料総額 60,000×5年＝300,000 をそのまま資産・債務に計上します。支払利息は使いません。"},
 {"id":"K06","cat":"工業","topic":"材料費","level":1,
  "text":"材料500kgを1kgあたり ¥1,000 で掛けで購入し、引取運賃 ¥20,000 は現金で支払った。",
  "cands":["材料","買掛金","現金","仕掛品","材料副費","製造間接費"],
  "debit":[["材料",520000]],"credit":[["買掛金",500000],["現金",20000]],
  "expl":"引取運賃などの材料副費は材料の購入原価に含めます。500×1,000＋20,000＝520,000。"},
 {"id":"K07","cat":"工業","topic":"労務費","level":1,
  "text":"直接工の作業時間報告書によれば、当月の直接作業時間は400時間、間接作業時間は100時間であった。予定賃率は1時間あたり ¥1,000 である。賃金の消費額を計上する。",
  "cands":["仕掛品","製造間接費","賃金","製品","賃率差異","現金"],
  "debit":[["仕掛品",400000],["製造間接費",100000]],"credit":[["賃金",500000]],
  "expl":"直接作業分は仕掛品へ、間接作業分は製造間接費へ。直接工でも間接作業の時間は間接労務費です。"},
 {"id":"K08","cat":"工業","topic":"製造間接費","level":1,
  "text":"製造間接費を直接作業時間を配賦基準として予定配賦する。予定配賦率は1時間あたり ¥800、当月の実際直接作業時間は450時間であった。",
  "cands":["仕掛品","製造間接費","製品","製造間接費配賦差異","賃金","材料"],
  "debit":[["仕掛品",360000]],"credit":[["製造間接費",360000]],
  "expl":"予定配賦額＝800×450時間＝360,000。テンキーの×キーでそのまま計算できます。"},
 {"id":"K09","cat":"工業","topic":"製造間接費","level":2,
  "text":"当月の製造間接費の実際発生額は ¥375,000 であった。予定配賦額 ¥360,000 との差額を製造間接費配賦差異勘定へ振り替える。",
  "cands":["製造間接費配賦差異","製造間接費","仕掛品","売上原価","予算差異","製品"],
  "debit":[["製造間接費配賦差異",15000]],"credit":[["製造間接費",15000]],
  "expl":"実際 375,000 ＞ 予定 360,000 なので 15,000 の不利差異（借方差異）。製造間接費勘定から差異勘定へ振り替えます。"},
 {"id":"K10","cat":"工業","topic":"総合原価計算","level":1,
  "text":"当月に完成した製品の原価は ¥1,250,000 であった。完成品原価を振り替える。",
  "cands":["製品","仕掛品","売上原価","製造間接費","売上","材料"],
  "debit":[["製品",1250000]],"credit":[["仕掛品",1250000]],
  "expl":"完成した分だけ仕掛品勘定から製品勘定へ。販売したときにはじめて売上原価に振り替えます。"},
]

# ---------- エージェント作成分の論点名を論点マップの区分へ正規化 ----------
TOPIC_MAP = {
 "クレジット売掛金":"債権債務","電子記録債権":"債権債務","手形":"債権債務",
 "銀行勘定調整":"現金預金",
 "満期保有目的債券":"有価証券","その他有価証券":"有価証券",
 "圧縮記帳":"固定資産","未決算・保険差益":"固定資産",
 "ソフトウェア":"無形固定資産","のれん":"無形固定資産","研究開発費":"無形固定資産",
 "リース取引":"リース",
 "貸倒引当金":"引当金","退職給付引当金":"引当金","修繕引当金":"引当金","商品保証引当金":"引当金",
 "法人税等":"税金","消費税":"税金",
 "株式の発行":"純資産","剰余金の配当":"純資産",
}

# ---------- 個別の是正（レビュー結果） ----------
FIX = {
 "S11": {"level":1,
   "text":"売上原価対立法を採用している当社は、A商品300個を@¥1,000で掛けで仕入れていた。本日、このうち20個が品違いであったため仕入先へ返品し、代金は買掛金から控除することとした。",
   "debit":[["買掛金",20000]],"credit":[["商品",20000]],
   "cands":["商品","現金","仕入","未払金","売上原価","買掛金","当座預金"],
   "expl":"売上原価対立法では仕入時に商品勘定へ計上しているので、返品は商品勘定を直接減らす。@1,000×20個＝20,000。"},
 "S16": {"text":"売買目的で保有する額面総額¥2,000,000のA社社債（年利率3.65％、利払日は3月末と9月末の年2回）を、11月30日に額面¥100につき¥98.50で売却し、端数利息とともに代金は当座預金に入金された。この社債は当期中に額面¥100につき¥97.00で取得したものであり、取得後に決算を経ていない。端数利息は1年を365日として日割計算する。",
         "cands":["有価証券売却損","売買目的有価証券","満期保有目的債券","当座預金","有価証券売却益","支払手数料","有価証券利息"]},
 "S17": {"cands":["その他有価証券","有価証券利息","当座預金","有価証券評価益","満期保有目的債券","売買目的有価証券","有価証券売却益"]},
 "S19": {"text":"×1年3月31日、当社はS社の発行済株式の80％を¥52,000,000で取得して支配を獲得した。同日のS社の資本は、資本金¥40,000,000、資本剰余金¥10,000,000、利益剰余金¥10,000,000であり、S社の資産・負債の帳簿価額と時価は一致している。支配獲得日の連結修正仕訳（投資と資本の相殺消去）を示しなさい。"},
 "S21": {"cands":["固定資産除却損","未払金","機械装置減価償却累計額","未収入金","固定資産売却損","機械装置","貯蔵品","減価償却費"]},
 "S22": {"expl":"完成時に建設仮勘定を本勘定へ振り替え、直接減額方式では取得原価から圧縮額を直接控除する。建物30,000,000-6,000,000=24,000,000、残額30,000,000-20,000,000=10,000,000を当座預金で支払う。建物30,000,000で計上してから圧縮損6,000,000を建物から減額する二段階の仕訳も正解。",
         "alts":[{"debit":[["建物",30000000],["固定資産圧縮損",6000000]],"credit":[["建設仮勘定",20000000],["当座預金",10000000],["建物",6000000]]}]},
 "S38": {"text":"当社は商品売買を三分法により記帳している。本店は支店に対して商品¥800,000（原価）を発送した。本支店間の商品の振替えは原価で行っている。本店の仕訳を示しなさい。"},
 "K13": {"expl":"実際発生額54,000が予定配賦額50,000を上回り、材料副費勘定に借方残4,000が生じるので、これを材料副費差異へ振り替える。予定配賦額1,000,000×5%=50,000、54,000-50,000=4,000の借方差異（不利差異）。"},
 "K18": {"text":"月末に当月の間接経費を製造間接費勘定へ集計する。機械装置の減価償却費は年間見積額¥3,600,000の月割額とし、機械装置減価償却累計額勘定へ直接記入する（減価償却費勘定は用いない）。当月の電力料は測定した消費額¥128,000（電力料勘定で処理済み）である。これらの間接経費の製造間接費勘定への振替を仕訳する。"},
}

def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)

problems = list(BASE)
for name in ("bank_shogyo.json", "bank_kogyo.json"):
    for p in load(name):
        p["topic"] = TOPIC_MAP.get(p["topic"], p["topic"])
        if p["id"] in FIX: p.update(FIX[p["id"]])
        problems.append(p)
for p in problems:
    p["syl"] = SYL

# ---------- 検証 ----------
errs = []
ids = set()
for p in problems:
    if p["id"] in ids: errs.append(p["id"]+" id重複")
    ids.add(p["id"])
    d = sum(m for _, m in p["debit"]); c = sum(m for _, m in p["credit"])
    if d != c: errs.append("%s 貸借不一致 %d/%d" % (p["id"], d, c))
    if not (6 <= len(p["cands"]) <= 8): errs.append(p["id"]+" cands数")
    if len(set(p["cands"])) != len(p["cands"]): errs.append(p["id"]+" cands重複")
    for ans in [p] + p.get("alts", []):
        if sum(m for _, m in ans["debit"]) != sum(m for _, m in ans["credit"]): errs.append(p["id"]+" 別解の貸借不一致")
        for side in ("debit","credit"):
            names = [a for a, _ in ans[side]]
            if len(set(names)) != len(names): errs.append(p["id"]+" 同側の科目重複")
            for a, m in ans[side]:
                if a not in p["cands"]: errs.append("%s candsに%sが無い" % (p["id"], a))
                if not (isinstance(m, int) and m > 0): errs.append(p["id"]+" 金額")
    for k in ("id","cat","topic","level","text","expl"):
        if not p.get(k): errs.append(p["id"]+" 欠落 "+k)
if errs:
    print("\n".join(errs)); sys.exit(1)

# ---------- 計算ドリル ----------
def cell(lbl, qty, amt):
    return '<div class="bcell"><div class="lbl">%s</div><div class="qty num">%s</div><div class="amt num">%s</div></div>' % (lbl, qty, amt)
def blank(key): return '<span class="blank" data-blank="%s">？</span>' % key
def box(title, cells, one=False):
    return '<div class="box"><div class="bt">%s</div><div class="bgrid%s">%s</div></div>' % (title, " one" if one else "", "".join(cells))

DRILLS = [
 {"id":"D1","tag":"工業簿記","title":"総合原価計算・平均法","sub":"ボックス図を埋めて完成品原価まで（7ステップ）",
  "text":"当社は単一製品を大量生産している。次の資料にもとづき、<b>平均法</b>によって月末仕掛品原価と完成品総合原価を求めなさい。原料はすべて<b>工程の始点</b>で投入している。<br><br>月初仕掛品：200個（加工進捗度 50%）　原料費 ¥84,000　加工費 ¥90,000<br>当月投入：1,800個　原料費 ¥756,000　加工費 ¥990,000<br>当月完成品：1,600個　月末仕掛品：400個（加工進捗度 50%）",
  "boxes": box("原料費のボックス（数量：個）", [cell("月初仕掛品","200個","¥84,000"), cell("完成品","1,600個",blank("matDone")), cell("当月投入","1,800個","¥756,000"), cell("月末仕掛品","400個",blank("matEnd"))])
          + box("加工費のボックス（数量：完成品換算量）", [cell("月初仕掛品","200個×50%＝100個","¥90,000"), cell("完成品","1,600個",blank("convDone")), cell("当月投入","（差引）","¥990,000"), cell("月末仕掛品",blank("convQty")+" 個",blank("convEnd"))])
          + box("まとめ", [cell("月末仕掛品原価","原料費＋加工費",blank("endTotal")), cell("完成品総合原価","原料費＋加工費",blank("final"))], one=True),
  "steps":[
   {"key":"convQty","n":"STEP 1","q":"月末仕掛品の完成品換算量は？（400個 × 加工進捗度50%）","a":200,"unit":"個","hint":"加工費は進捗度に応じて発生するので、400個×50%＝200個ぶんとして扱います。"},
   {"key":"matEnd","n":"STEP 2","q":"原料費の月末仕掛品原価は？　平均法なので（月初＋当月投入）÷（完成＋月末）で平均単価を出し、月末400個分を計算。","a":168000,"unit":"円","hint":"（84,000＋756,000）÷2,000個＝@420。@420×400個＝168,000。このテンキーは簿記電卓と同じく左から順に計算するので 84000＋756000÷2000×400 の順で押せます。"},
   {"key":"matDone","n":"STEP 3","q":"原料費の完成品分は？（ボックスの貸借差引で出すのが速い）","a":672000,"unit":"円","hint":"84,000＋756,000−168,000＝672,000。ボックス図は「合計−月末＝完成品」の形で使います。"},
   {"key":"convEnd","n":"STEP 4","q":"加工費の月末仕掛品原価は？（月初90,000＋当月990,000）÷（完成1,600個＋月末換算200個）×200個","a":120000,"unit":"円","hint":"（90,000＋990,000）÷1,800個＝@600。@600×200個＝120,000。"},
   {"key":"convDone","n":"STEP 5","q":"加工費の完成品分は？","a":960000,"unit":"円","hint":"90,000＋990,000−120,000＝960,000。"},
   {"key":"endTotal","n":"STEP 6","q":"月末仕掛品原価は？（原料費＋加工費）","a":288000,"unit":"円","hint":"168,000＋120,000＝288,000。"},
   {"key":"final","n":"FINAL","q":"完成品総合原価は？（原料費の完成品分＋加工費の完成品分）","a":1632000,"unit":"円","hint":"672,000＋960,000＝1,632,000。"},
  ],
  "final":'<div class="ans num">月末仕掛品原価 ¥288,000<br>完成品総合原価 ¥1,632,000（単位原価 @¥1,020）</div><p class="expl">平均法は「月初と当月を混ぜて平均単価」。次は先入先出法で同じ図を使い、違いを体で覚えましょう。</p>'},

 {"id":"D2","tag":"工業簿記","title":"総合原価計算・先入先出法","sub":"当月投入の換算量が鍵（5ステップ）",
  "text":"次の資料にもとづき、<b>先入先出法</b>によって月末仕掛品原価と完成品総合原価を求めなさい。原料はすべて<b>工程の始点</b>で投入している。<br><br>月初仕掛品：200個（加工進捗度 50%）　原料費 ¥90,000　加工費 ¥45,000<br>当月投入：1,800個　原料費 ¥756,000　加工費 ¥1,020,000<br>当月完成品：1,600個　月末仕掛品：400個（加工進捗度 50%）",
  "boxes": box("原料費のボックス（数量：個）", [cell("月初仕掛品","200個","¥90,000"), cell("完成品","1,600個","（差引）"), cell("当月投入","1,800個","¥756,000"), cell("月末仕掛品","400個",blank("matEnd"))])
          + box("加工費のボックス（数量：完成品換算量）", [cell("月初仕掛品","100個","¥45,000"), cell("完成品","1,600個","（差引）"), cell("当月投入",blank("convIn")+" 個","¥1,020,000"), cell("月末仕掛品","200個",blank("convEnd"))])
          + box("まとめ", [cell("月末仕掛品原価","原料費＋加工費",blank("endTotal")), cell("完成品総合原価","月初＋当月投入−月末",blank("final"))], one=True),
  "steps":[
   {"key":"convIn","n":"STEP 1","q":"加工費の当月投入換算量は？（完成1,600個＋月末換算200個−月初換算100個）","a":1700,"unit":"個","hint":"ボックスの貸方合計（1,600＋200）から月初の100個を引いた1,700個が当月投入分です。"},
   {"key":"matEnd","n":"STEP 2","q":"原料費の月末仕掛品原価は？　先入先出法では月末仕掛品は当月投入分から成るので、当月投入の単価×400個。","a":168000,"unit":"円","hint":"756,000÷1,800個＝@420。@420×400個＝168,000。月初の90,000は使いません。"},
   {"key":"convEnd","n":"STEP 3","q":"加工費の月末仕掛品原価は？（当月投入1,020,000 ÷ 当月投入換算量1,700個 × 200個）","a":120000,"unit":"円","hint":"1,020,000÷1,700個＝@600。@600×200個＝120,000。"},
   {"key":"endTotal","n":"STEP 4","q":"月末仕掛品原価は？（原料費＋加工費）","a":288000,"unit":"円","hint":"168,000＋120,000＝288,000。"},
   {"key":"final","n":"FINAL","q":"完成品総合原価は？（月初仕掛品原価＋当月製造費用−月末仕掛品原価）","a":1623000,"unit":"円","hint":"（90,000＋45,000）＋（756,000＋1,020,000）−288,000＝1,623,000。"},
  ],
  "final":'<div class="ans num">月末仕掛品原価 ¥288,000<br>完成品総合原価 ¥1,623,000</div><p class="expl">先入先出法は「月末仕掛品＝当月投入の単価」。月初分はそのまま完成品に流れるので、完成品は差引で出すのが最短です。</p>'},

 {"id":"D3","tag":"工業簿記","title":"標準原価計算・直接材料費差異","sub":"価格差異と数量差異を分析図で（6ステップ）",
  "text":"標準原価計算を採用している。直接材料費の標準は製品1個あたり<b>標準単価 @¥500・標準消費量 2kg</b>である。当月の生産量は1,000個（材料はすべて始点投入、月初・月末仕掛品なし）、実際の材料消費は<b>2,100kg、実際単価 @¥480</b>であった。直接材料費差異を価格差異と数量差異に分析しなさい。",
  "boxes": box("標準と実際", [cell("標準消費量","1,000個 × 2kg",blank("stdQty")+" kg"), cell("標準原価","@500 × 標準消費量",blank("stdCost")), cell("実際消費量","",'<span class="num">2,100 kg</span>'), cell("実際原価","@480 × 2,100kg",'<span class="num">¥1,008,000</span>')])
          + box("差異分析図（縦：単価、横：数量）", [cell("価格差異","（標準単価−実際単価）×実際消費量",blank("priceVar")), cell("価格差異の向き","",blank("priceDir")), cell("数量差異","標準単価×（標準消費量−実際消費量）",blank("qtyVar")), cell("数量差異の向き","",blank("qtyDir"))]),
  "steps":[
   {"key":"stdQty","n":"STEP 1","q":"標準消費量は？（1,000個 × 2kg）","a":2000,"unit":"kg","hint":"標準は「作った数量に対して本来使うべき量」。1,000個×2kg＝2,000kg。"},
   {"key":"stdCost","n":"STEP 2","q":"標準直接材料費は？（@500 × 標準消費量）","a":1000000,"unit":"円","hint":"@500×2,000kg＝1,000,000。実際原価1,008,000との差8,000が総差異です。"},
   {"key":"priceVar","n":"STEP 3","q":"価格差異の金額は？（標準単価−実際単価）×実際消費量。金額だけ入力。","a":42000,"unit":"円","hint":"(500−480)×2,100kg＝42,000。実際消費量に掛けるのがポイント。"},
   {"key":"priceDir","n":"STEP 4","q":"価格差異は有利・不利どちら？","type":"choice","options":["有利差異","不利差異"],"a":"有利差異","hint":"実際単価480が標準500より安かったので有利（貸方差異）。"},
   {"key":"qtyVar","n":"STEP 5","q":"数量差異の金額は？ 標準単価×（標準消費量−実際消費量）。金額だけ入力。","a":50000,"unit":"円","hint":"500×(2,000−2,100)＝△50,000。標準単価に掛けるのがポイント。"},
   {"key":"qtyDir","n":"FINAL","q":"数量差異は有利・不利どちら？","type":"choice","options":["有利差異","不利差異"],"a":"不利差異","hint":"標準より100kg多く使ったので不利（借方差異）。有利42,000−不利50,000＝総差異8,000不利と一致。"},
  ],
  "final":'<div class="ans num">価格差異 ¥42,000（有利）<br>数量差異 ¥50,000（不利）<br>総差異 ¥8,000（不利）</div><p class="expl">分析図は「価格差異は実際数量の幅、数量差異は標準単価の高さ」。混ぜなければ絶対に間違えません。</p>'},

 {"id":"D4","tag":"工業簿記","title":"直接原価計算・CVP分析","sub":"損益分岐点から安全余裕率まで（6ステップ）",
  "text":"当社の当期の資料は次のとおりである。<b>販売単価 @¥2,000、1個あたり変動費 @¥1,200、固定費 ¥1,600,000</b>、当期の販売量は2,500個（売上高 ¥5,000,000）であった。損益分岐点売上高、目標営業利益 ¥800,000 を達成する売上高、安全余裕率を求めなさい。",
  "boxes": box("直接原価計算方式の損益計算書（当期）", [cell("売上高","2,500個 × @2,000",'<span class="num">¥5,000,000</span>'), cell("変動費","2,500個 × @1,200",'<span class="num">¥3,000,000</span>'), cell("貢献利益","1個あたり "+blank("cmUnit")+" 円",'<span class="num">¥2,000,000</span>'), cell("貢献利益率","貢献利益 ÷ 売上高",blank("cmRate")), cell("固定費","",'<span class="num">¥1,600,000</span>'), cell("営業利益","",'<span class="num">¥400,000</span>')], one=True)
          + box("CVP分析", [cell("損益分岐点売上高","固定費 ÷ 貢献利益率",blank("bepSales")), cell("損益分岐点販売量","固定費 ÷ 1個あたり貢献利益",blank("bepQty")+" 個"), cell("目標利益達成売上高","（固定費＋目標利益）÷ 貢献利益率",blank("targetSales")), cell("安全余裕率","（売上高−損益分岐点）÷ 売上高",blank("safety"))]),
  "steps":[
   {"key":"cmUnit","n":"STEP 1","q":"1個あたりの貢献利益は？（販売単価−変動費）","a":800,"unit":"円","hint":"2,000−1,200＝800。"},
   {"key":"cmRate","n":"STEP 2","q":"貢献利益率は？（%で入力。800÷2,000）","a":40,"unit":"%","hint":"800÷2,000＝0.4 → 40%。"},
   {"key":"bepSales","n":"STEP 3","q":"損益分岐点売上高は？（固定費 ÷ 貢献利益率）","a":4000000,"unit":"円","hint":"1,600,000÷0.4＝4,000,000。テンキーなら 1600000÷40×100。"},
   {"key":"bepQty","n":"STEP 4","q":"損益分岐点の販売量は？（固定費 ÷ 1個あたり貢献利益）","a":2000,"unit":"個","hint":"1,600,000÷800＝2,000個。4,000,000÷2,000でも同じ。"},
   {"key":"targetSales","n":"STEP 5","q":"目標営業利益 ¥800,000 を達成する売上高は？（固定費＋目標利益）÷ 貢献利益率","a":6000000,"unit":"円","hint":"(1,600,000＋800,000)÷0.4＝6,000,000。"},
   {"key":"safety","n":"FINAL","q":"安全余裕率は？（%で入力。(売上高−損益分岐点売上高)÷売上高）","a":20,"unit":"%","hint":"(5,000,000−4,000,000)÷5,000,000＝20%。"},
  ],
  "final":'<div class="ans num">損益分岐点売上高 ¥4,000,000<br>目標利益達成売上高 ¥6,000,000<br>安全余裕率 20%</div><p class="expl">CVPは全部「固定費 ÷ 貢献利益率」の変形。貢献利益率さえ出せば残りは割り算だけです。</p>'},
]

# ---------- 模試の検証 ----------
eerrs = []
for ex in EXAMS:
    tag = ex["id"]
    total = 0
    for sec in ex["sections"]:
        stag = tag + " " + sec["name"]
        bsum = sum(b["pt"] for b in sec["blocks"])
        if bsum != sec["pt"]: eerrs.append("%s 配点不一致 ブロック計%d ≠ 設問%d" % (stag, bsum, sec["pt"]))
        total += sec["pt"]
        for bi, b in enumerate(sec["blocks"]):
            btag = "%s ブロック%d" % (stag, bi+1)
            if b["kind"] == "je":
                d = sum(m for _, m in b["debit"]); c = sum(m for _, m in b["credit"])
                if d != c: eerrs.append("%s 貸借不一致 %d/%d" % (btag, d, c))
                for side in ("debit","credit"):
                    names = [a for a, _ in b[side]]
                    if len(set(names)) != len(names): eerrs.append(btag + " 同側の科目重複")
                    if len(names) > b["rows"]: eerrs.append(btag + " 行数不足")
                    for a, m in b[side]:
                        if a not in b["cands"]: eerrs.append("%s candsに%sが無い" % (btag, a))
                        if not (isinstance(m, int) and m > 0): eerrs.append(btag + " 金額")
                if len(set(b["cands"])) != len(b["cands"]): eerrs.append(btag + " cands重複")
            elif b["kind"] == "sheet":
                fsum = sum(f["pt"] for f in b["fields"])
                if fsum != b["pt"]: eerrs.append("%s 配点不一致 欄計%d ≠ ブロック%d" % (btag, fsum, b["pt"]))
                keys = set()
                for fl in b["fields"]:
                    if fl["k"] in keys: eerrs.append("%s 欄キー重複 %s" % (btag, fl["k"]))
                    keys.add(fl["k"])
                    n = b["sheet"].count('data-f="%s"' % fl["k"])
                    if n != 1: eerrs.append("%s 答案用紙に %s が%d個" % (btag, fl["k"], n))
                    if fl["kind"] == "num" and not (isinstance(fl["a"], int) and fl["a"] > 0): eerrs.append(btag + " 解答 " + fl["k"])
                    if fl["kind"] == "choice" and fl["a"] not in fl["opts"]: eerrs.append(btag + " 選択肢に解答が無い " + fl["k"])
                for m in re.findall(r'data-f="([^"]+)"', b["sheet"]):
                    if m not in keys: eerrs.append("%s 答案用紙の %s に対応する欄が無い" % (btag, m))
            else:
                eerrs.append(btag + " 未知のkind " + str(b.get("kind")))
            if not b.get("expl"): eerrs.append(btag + " 解説なし")
    if total != 100: eerrs.append("%s 満点が%d点" % (tag, total))
if eerrs:
    print("\n".join(eerrs)); sys.exit(1)

# ---------- 差し込み ----------
with open(os.path.join(HERE, "bokitore_v2.tpl.html"), encoding="utf-8") as f:
    tpl = f.read()
pj = json.dumps(problems, ensure_ascii=False, separators=(",",":"))
dj = json.dumps(DRILLS, ensure_ascii=False, separators=(",",":"))
ej = json.dumps(EXAMS, ensure_ascii=False, separators=(",",":"))
for s in (pj, dj, ej):
    assert "</script" not in s.lower()
out = tpl.replace("/*__PROBLEMS__*/[]", pj).replace("/*__DRILLS__*/[]", dj).replace("/*__EXAMS__*/[]", ej)
assert "/*__PROBLEMS__*/" not in out and "/*__DRILLS__*/" not in out and "/*__EXAMS__*/" not in out

# artifact用（フラグメント）
with open(os.path.join(HERE, "bokitore.html"), "w", encoding="utf-8") as f:
    f.write(out)

# standalone（完全なHTML文書＋PWAマニフェスト）
manifest = json.dumps({"name":"ボキトレイン","short_name":"ボキトレイン","start_url":".","display":"standalone","background_color":"#F6F7F4","theme_color":"#0E7A5F","lang":"ja"}, ensure_ascii=False)
import urllib.parse
head_extra = ('<meta name="description" content="簿記2級の仕訳と原価計算を、電車で片手で。電卓とメモ常駐の演習アプリ。">\n'
              '<meta property="og:title" content="ボキトレイン — 一駅一問。鉛筆も紙も出さずに、片手で簿記2級">\n'
              '<meta property="og:description" content="仕訳60問＋ボックス図で解く原価計算。下書き用紙を画面にしました。電卓とメモは常駐、復習は忘却曲線で自動。">\n'
              '<meta property="og:type" content="website">\n'
              '<meta property="og:url" content="https://nekoze32.github.io/boki2-trainer/">\n'
              '<meta name="twitter:card" content="summary">\n'
              '<link rel="manifest" href="data:application/manifest+json,%s">\n' % urllib.parse.quote(manifest))
body = out.replace('<meta charset="utf-8">\n', '', 1)
# <title>〜<link ...> までを head、それ以降を body に分ける
m = re.search(r'</style>\s*', body)
head_part, body_part = body[:m.end()], body[m.end():]
standalone = '<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n' + head_extra + head_part + '\n</head>\n<body>\n' + body_part + '\n</body>\n</html>\n'
with open(os.path.join(HERE, "bokitore_standalone.html"), "w", encoding="utf-8") as f:
    f.write(standalone)
# GitHub Pages 用（リポジトリ直下の index.html）
with open(os.path.join(HERE, "..", "index.html"), "w", encoding="utf-8") as f:
    f.write(standalone)

nS = sum(1 for p in problems if p["cat"]=="商業"); nK = len(problems)-nS
topics = {}
for p in problems: topics.setdefault(p["cat"], set()).add(p["topic"])
print("OK problems=%d (商業%d 工業%d) drills=%d exams=%d" % (len(problems), nS, nK, len(DRILLS), len(EXAMS)))
for ex in EXAMS:
    print("  模試 %s %s %d分 %d点 =" % (ex["id"], ex["title"], ex["minutes"], sum(s["pt"] for s in ex["sections"])),
          "／".join("%s %d点" % (s["name"], s["pt"]) for s in ex["sections"]))
for c in topics: print(" ", c, len(topics[c]), "論点:", "、".join(sorted(topics[c])))
