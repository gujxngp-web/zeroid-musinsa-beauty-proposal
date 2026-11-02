"""Round 1 추정 예산안 계산 스크립트 (총괄이사 피드백 P1: #001 #002 #004~#013 #017 #023 #030)

- 근거 결정: research/decisions.md 2026-11-02 Q1~Q11
- 가격: 올리브영 실판매가(Q3). 패리티 = 2026-10-30 평시 판매가(기록 없는 SKU는 정가×0.9 [가정],
        기획 상품은 수딩 기획의 10-30 할인율 21.3% [가정]), 행사 = 2026-11-02 행사가(output/리뷰/round1/리서치.md 1-2)
- 모든 금액은 (추정). 가정값은 output/리포트/가정값-목록.md 'Round 1 (B 블록)'과 같다. 사용자 확인 전 [미확인].
- 거래액 = 고객 실결제 판매가 기준. 무신사 수익 = 거래액 × 수수료율 − 무신사 부담 판촉비.
- 2026-11-02 2단계 수정: 인텐시브 기획 패리티 가정, 구성안 이름을 기획 14-2(A/B/C)와 맞춤, LTV·CAC 정의를 #006과 맞춤,
  하방 주문 수를 근사(×0.75) 대신 모델로 계산, 하방에 팝업 방문 하단 반영, G3·G4 북극성을 시점 가중으로,
  무신사 인일을 승인 항목 1~5별로 분해, 쿠폰 할인액 근거화(5,000원), 체험단 원가 구성 반영, 14절 미사용 변수(Z, disc) 제거,
  15~22절(승인 항목별 부담·시점, 게이트 하한·최대 손실, 가격표·가드레일, 재고, CRM 발송일, 후기, 팝업 대안, ROAS) 추가.
실행: python3 -I round1_budget.py > round1_budget_output.txt
"""
import copy

# ============ A. 가격 (원) ============
# (정가, 패리티 평시가, 패리티 출처, 행사가 11-02, 용량ml)
KIT_PAR = 29900 / 38000  # 수딩 크림 기획 10-30 평시가 비율(할인 21.3%)
PRICE = {
    "수딩 크림 80ml":            (30000, 27000, "가정 정가×0.9", 24300, 80),
    "수딩 로션 160ml":           (30000, 27000, "가정 정가×0.9", 24300, 160),
    "인텐시브 크림 80ml":        (32000, 28800, "10-30 기록",    25920, 80),
    "인텐시브 로션 160ml 기획":  (32000, 28800, "가정 정가×0.9", 22400, 160),
    "인텐시브 오인트 크림 80ml": (35000, 31500, "가정 정가×0.9", 27720, 80),
    "인텐시브 크림 미스트 100ml":(23000, 20700, "가정 정가×0.9", 18630, 100),
    "포밍 클렌저 240ml":         (24000, 21600, "가정 정가×0.9", 19440, 240),
    "데일리 선크림 50ml":        (32000, 28800, "가정 정가×0.9", 25920, 50),
    "수딩 세럼 마스크 5매":      (30000, 27000, "가정 정가×0.9(정가는 공식몰)", 24300, None),  # 행사가도 가정(정가×0.81)
    "수딩 크림 기획 80+50ml":    (38000, 29900, "10-30 기록",    28900, 130),
    "인텐시브 크림 기획 80+50ml":(40000, round(40000 * KIT_PAR, -2), "가정 수딩 기획 할인율 21%", 30900, 130),
    "핌프로브 젤 클렌저 180ml":  (32000, 28800, "가정 정가×0.9", 25920, 180),
    "핌프로브 레드 컨트롤 크림 80ml": (33000, 27900, "10-30 기록", 26730, 80),
}
def combo(name, parts):
    PRICE[name] = (sum(PRICE[p][0] for p in parts), sum(PRICE[p][1] for p in parts), "구성품 합",
                   sum(PRICE[p][3] for p in parts),
                   sum(PRICE[p][4] or 0 for p in parts) or None)
combo("듀오 크림 세트(80+80)", ["수딩 크림 80ml", "인텐시브 크림 80ml"])
combo("듀오 대용량(130+130)", ["수딩 크림 기획 80+50ml", "인텐시브 크림 기획 80+50ml"])
combo("봄 러너 키트", ["포밍 클렌저 240ml", "수딩 로션 160ml", "데일리 선크림 50ml"])
combo("겨울 산행 키트", ["인텐시브 크림 80ml", "인텐시브 크림 미스트 100ml"])
combo("여름 땀 시즌 키트", ["핌프로브 젤 클렌저 180ml", "핌프로브 레드 컨트롤 크림 80ml"])

def price(item, mode):
    lst, par, _, ev, _ = PRICE[item]
    return {"정가": lst, "패리티": par, "행사": ev, "하방30": lst * 0.70, "구20": lst * 0.80}[mode]

# ============ B. 가정값 ============
LV = ("저", "기본", "고")
B = dict(
    # 기존 확정 가정(2026-10-30)
    cream=1.0, lotion=1.5, cleanser=1.5, sun=0.5,
    p_repeat={"봄 러너": 0.30, "겨울 산행러": 0.15, "환절기 민감러": 0.30},
    w_scen={"보수": 0.50, "기본": 0.35, "낙관": 0.15},
    mix={"봄 러너": 0.35, "겨울 산행러": 0.25, "환절기 민감러": 0.40},
    # B01 수수료율 3안(Q1, 기본값 없음)
    rates={"저 9.4%": 0.094, "중 18.6%": 0.186, "고 27.8%": 0.278},
    # B02 행사 거래액 비중: 행사 37일(3월 페스타 11 + 5월 페스타 11 + 8월 무뷰페 온라인 15) × 일평균 2.5배(+150%)
    event_days=37, event_lift=1.5, event_split={"3월 페스타": 11, "5월 페스타": 11, "8월 무뷰페": 15},
    # B03 무신사 행사 쿠폰·후기 적립 분담률(Q4: 50% 이하) → 상한 50%로 계산
    mss_share=0.50,
    # B04 증분율 구성: 무신사 뷰티 첫 구매 비율 a, 기존 뷰티 고객 중 무신사 내 대체율 s
    incr={"저": (0.20, 0.80), "기본": (0.30, 0.65), "고": (0.40, 0.50)},
    # B05 1년차 첫 구매자 수 규모 시나리오(Q8, 목표 아님)
    scale={"저": 3000, "기본": 6000, "고": 12000},
    # B06 월별 첫 구매자 분포(3월~2월)
    month_share=[0.14, 0.08, 0.12, 0.07, 0.06, 0.09, 0.08, 0.08, 0.09, 0.07, 0.06, 0.06],
    review_rate=0.20,          # B07 주문당 후기 작성률
    review_point=1000,         # B08 후기 건당 적립금(원)
    # 팝업 (Q7)
    popup_days=14, visit={"하단·기본": 120, "상단": 300}, cvr={"하단": 0.10, "기본": 0.15, "상단": 0.20},
    popup_duo=0.40,            # B09 팝업 듀오 비중
    pyeong_sales={"저": 50000, "기본": 80000, "고": 130000},   # B10 뷰티존 평당 일 거래액(정상 상태). 개장 3일 9억÷3일÷2,000평=15만 원
    area={"저": 10, "기본": 15, "고": 20},                       # B11 팝업 면적(평). 뷰티존 약 146평 [미확인]
    lift={"저": 0.15, "기본": 0.25, "고": 0.35},                 # B12 팝업 후 4주 온라인 일평균 상승률(이중차분, 가정)
    # B13 무신사 인일: 승인 항목 1~5별 (Q6)
    mandays_item={
        "1 입점·단독 구성(MD 등록·검수·게이트 4회)": {"저": 7, "기본": 10, "고": 14},
        "2 페스타 슬롯(MD·마케팅 지면 운영)":       {"저": 3, "기본": 5, "고": 8},
        "3 팝업 공간(오프라인팀 협의·점검·POS·보안)": {"저": 10, "기본": 20, "고": 30},
        "4 집계 통계 공유(데이터팀 셋업+월 1회)":   {"저": 8, "기본": 12, "고": 18},
        "5 시즌 교체 CRM(CRM팀 추출·설정·집계)":     {"저": 4, "기본": 6, "고": 10},
    },
    manday_cost={"저": 250000, "기본": 350000, "고": 500000},    # B14 인일 단가 = 연봉 5천만·7천만·1억 × 1.2 ÷ 240일
    media={"저": 0, "기본": 5_000_000, "고": 15_000_000},       # B15 노출 지면 기회비용(페스타 60% + 팝업 앱 안내 40%)
    media_popup=0.40,
    # 쿠폰 2종 (Q5)
    crm_target=0.35, crm_optin=0.60, holdout=0.10, crm_use=0.15, crm_amt=5000, crm_base_buy=0.09,  # B16~B20
    card_take=0.60, card_use=0.10, card_amt=5000,                # B21~B23
    # 제로이드 측(참고)
    trial_n={"일반(듀오)": 60, "크루(봄 러너 키트)": 40}, cogs=0.30, ship=4000, trial_post=0.70,  # B24~B26
    safety_weeks=2,            # B27 안전재고 주수
)
SS, FW = 184, 181
MS = B["month_share"]

def ev_share(B):
    e = B["event_days"] * (1 + B["event_lift"])
    return e / (e + (365 - B["event_days"]))

def mandays(B, lvl):
    return sum(v[lvl] for v in B["mandays_item"].values())

# ============ C. 페르소나 모델 ============
def personas(B, uf=1.0):
    c, l, cl, s = B["cream"] * uf, B["lotion"] * uf, B["cleanser"] * uf, B["sun"] * uf
    def use(item, days, ml):
        return (item, days * ml / PRICE[item][4])
    def fixed(item, n):
        return (item, n)
    return {
        "봄 러너": dict(first="수딩 로션 160ml", scen={
            "보수": [use("수딩 로션 160ml", SS, l)],
            "기본": [use("수딩 로션 160ml", SS, l), use("인텐시브 로션 160ml 기획", FW, l)],
            "낙관": [use("수딩 로션 160ml", SS, l), use("인텐시브 로션 160ml 기획", FW, l),
                     use("포밍 클렌저 240ml", 365, cl), use("데일리 선크림 50ml", SS, s)]}),
        "겨울 산행러": dict(first="인텐시브 크림 80ml", scen={
            "보수": [use("인텐시브 크림 80ml", FW, c)],
            "기본": [use("인텐시브 크림 80ml", FW, c), use("수딩 크림 80ml", SS, c)],
            "낙관": [use("인텐시브 크림 80ml", 91, c), use("인텐시브 오인트 크림 80ml", 90, c),
                     use("수딩 크림 80ml", SS, c), fixed("인텐시브 크림 미스트 100ml", 2)]}),
        "환절기 민감러": dict(first="듀오 크림 세트(80+80)", scen={
            "보수": [use("듀오 크림 세트(80+80)", SS, c)],
            "기본": [use("듀오 대용량(130+130)", 365, c)],
            "낙관": [use("듀오 대용량(130+130)", 365, c), use("포밍 클렌저 240ml", 365, cl),
                     fixed("수딩 세럼 마스크 5매", 1)]}),
    }

def values(B, mode, uf=1.0, rf=1.0):
    P = personas(B, uf)
    out = {}
    for n, p in P.items():
        tot = {s: sum(u * price(i, mode) for i, u in items) for s, items in p["scen"].items()}
        rep = sum(B["w_scen"][s] * tot[s] for s in tot)
        pr = min(1.0, B["p_repeat"][n] * rf)
        first = price(p["first"], mode)
        out[n] = dict(tot=tot, rep=rep, first=first, ev=(1 - pr) * first + pr * rep, pr=pr)
    w = sum(B["mix"][n] * out[n]["ev"] for n in out)
    w1 = sum(B["mix"][n] * out[n]["first"] for n in out)
    return out, w, w1

def won(x): return f"{x:,.0f}원"
def man(x): return f"{x/10000:,.0f}만 원"

print("# Round 1 추정 예산안 계산 결과 (모든 금액 (추정), 가정값 [미확인])\n")

# ---------- 1. 가격 기준 ----------
print("## 1. 가격 기준 (Q3: 올리브영 실판매가)")
print("| 품목 | 정가 | 패리티(평시) | 패리티 할인율 | 패리티 출처 | 행사(11-02) | 행사 할인율 |")
print("|---|---|---|---|---|---|---|")
for k, (lst, par, src, ev, vol) in PRICE.items():
    print(f"| {k} | {lst:,} | {par:,.0f} | {1-par/lst:.0%} | {src} | {ev:,} | {1-ev/lst:.0%} |")
es = ev_share(B)
print(f"\n- 행사 거래액 비중 = 행사 {B['event_days']}일 × {1+B['event_lift']:.1f}배 ÷ (그 값 + 평시 {365-B['event_days']}일) = {es:.1%}")

# ---------- 2. 페르소나 가치 ----------
print("\n## 2. 페르소나 1명 12개월 기대 거래액 (재구매 확률 반영)")
modes = [("구20", "이전 기준(정가×0.8)"), ("패리티", "패리티(평시가)"), ("행사", "행사(11-02)")]
res = {m: values(B, m) for m, _ in modes}
print("| 페르소나 | 첫 구매만(이전) | 기대(이전) | 첫 구매만(패리티) | 기대(패리티) | 기대(행사) | 패리티 배수 |")
print("|---|---|---|---|---|---|---|")
for n in B["mix"]:
    o_, p, e = res["구20"][0][n], res["패리티"][0][n], res["행사"][0][n]
    print(f"| {n} | {won(o_['first'])} | {won(o_['ev'])} | {won(p['first'])} | {won(p['ev'])} | {won(e['ev'])} | {p['ev']/p['first']:.2f}배 |")
for m, lab in modes:
    print(f"- 가중 평균 [{lab}] 기대 {won(res[m][1])} / 첫 구매만 {won(res[m][2])} / +{res[m][1]/res[m][2]-1:.0%}")
EVp, EVe = res["패리티"][1], res["행사"][1]
EVb = (1 - es) * EVp + es * EVe
print(f"- 예산용 혼합 기대 거래액 = 패리티 {1-es:.0%} + 행사 {es:.0%} = {won(EVb)}")
print("\n### 2-1. 시나리오별 연간 거래액(패리티) — 재구매자 안에서만")
for n in B["mix"]:
    t = res["패리티"][0][n]["tot"]; t0 = res["구20"][0][n]["tot"]; tl = values(B, "정가")[0][n]["tot"]
    print(f"- {n}: " + " / ".join(f"{s} {won(t[s])}(정가 {won(tl[s])}, 이전 {won(t0[s])})" for s in t))

# 하방
dn, EVd, EVd1 = values(B, "하방30", uf=0.6, rf=0.5)
dn_p, EVdp, _ = values(B, "패리티", uf=0.6, rf=0.5)
print(f"\n- 하방(재구매×0.5, 사용량×0.6, 할인 30%) 기대 거래액 {won(EVd)} (패리티 기본 대비 {EVd/EVp-1:+.0%}), 첫 구매만 {won(EVd1)}")
for n in B["mix"]:
    print(f"  · {n}: {won(dn[n]['ev'])}")

print("\n### 2-2. 민감도 (패리티 가중 기대 거래액)")
for lab, kw in [("재구매×0.5", dict(rf=0.5)), ("재구매×1.5", dict(rf=1.5)), ("사용량×0.6", dict(uf=0.6)), ("사용량×1.5", dict(uf=1.5))]:
    v = values(B, "패리티", **kw)[1]; print(f"- {lab}: {won(v)} ({v/EVp-1:+.0%})")
for lab, m in [("전량 행사가", "행사"), ("할인 30%", "하방30"), ("이전 20%", "구20")]:
    v = values(B, m)[1]; print(f"- {lab}: {won(v)} ({v/EVp-1:+.0%})")
for mix in ({"봄 러너": .45, "겨울 산행러": .30, "환절기 민감러": .25}, {"봄 러너": .30, "겨울 산행러": .20, "환절기 민감러": .50}):
    BB = copy.deepcopy(B); BB["mix"] = mix; v = values(BB, "패리티")[1]
    print(f"- 고객 구성 {list(mix.values())}: {won(v)} ({v/EVp-1:+.0%})")

# ---------- 3. 듀오 비중·객단가 (#023) ----------
print("\n## 3. 듀오 비중 정합 (#023) — 첫 구매 1,000명 기준 12개월 주문 (1개 = 1주문 [가정])")
DUO, KITS = {"듀오 크림 세트(80+80)"}, {"듀오 대용량(130+130)", "봄 러너 키트", "겨울 산행 키트"}
def orders(B, mix, mode="패리티", uf=1.0, rf=1.0):
    P = personas(B, uf); o = dict(total=0, duo=0, kit=0, first=0, first_duo=0, gmv=0)
    for n, p in P.items():
        N = 1000 * mix[n]; pr = min(1.0, B["p_repeat"][n] * rf)
        o["first"] += N; o["first_duo"] += N * (p["first"] in DUO)
        o["total"] += N * (1 - pr); o["duo"] += N * (1 - pr) * (p["first"] in DUO)
        o["kit"] += N * (1 - pr) * (p["first"] in KITS); o["gmv"] += N * (1 - pr) * price(p["first"], mode)
        for s, items in p["scen"].items():
            w = N * pr * B["w_scen"][s]
            for i, u in items:
                o["total"] += w * u; o["duo"] += w * u * (i in DUO); o["kit"] += w * u * (i in KITS)
                o["gmv"] += w * u * price(i, mode)
    return o
o = orders(B, B["mix"])
OPC = o["total"] / 1000
AOV = o["gmv"] / o["total"]
print(f"- 첫 주문 듀오 비중: {o['first_duo']/o['first']:.1%} (= 환절기 민감러 구성)")
print(f"- 전체 주문 {o['total']:,.0f}건 중 듀오 {o['duo']:,.0f}건 = {o['duo']/o['total']:.1%}, 기획세트 {o['kit']/o['total']:.1%}")
print(f"- 1인당 12개월 주문 수 {OPC:.2f}건, 주문당 객단가(패리티) {won(AOV)}")
single = (price("수딩 크림 80ml", "패리티") + price("인텐시브 크림 80ml", "패리티")) / 2
duo = price("듀오 크림 세트(80+80)", "패리티")
kit = sum(price(k, "패리티") for k in KITS) / 3
print(f"- 주문당 객단가 / 크림 단품 평균({won(single)}) = {AOV/single-1:+.0%}")
for d, k in [(0.20, 0.10), (o['duo']/o['total'], o['kit']/o['total'])]:
    a = single * (1 - d - k) + duo * d + kit * k
    print(f"- 객단가 모델(단품 {single:,.0f}·듀오 {duo:,.0f}·세트 {kit:,.0f}) 듀오 {d:.1%} 세트 {k:.1%} → {won(a)} (단품만 대비 {a/single-1:+.0%})")
lo, hi = 0.0, 0.40
for _ in range(40):
    m = (lo + hi) / 2
    rest = 1 - m; mix2 = {"봄 러너": rest * 35/60, "겨울 산행러": rest * 25/60, "환절기 민감러": m}
    oo = orders(B, mix2)
    if oo["duo"] / oo["total"] > 0.20: hi = m
    else: lo = m
BB = copy.deepcopy(B); BB["mix"] = mix2
print(f"- 전체 주문 듀오 20%에 맞추려면 민감러 비중 {m:.1%} → 가중 기대 거래액(패리티) {won(values(BB,'패리티')[1])} ({values(BB,'패리티')[1]/EVp-1:+.0%})")

# ---------- 4. 듀오 ml당 (#013) ----------
print("\n## 4. 듀오·기획 ml당 가격 (#013)")
rows = [("무신사 계절 듀오 80+80(본품)", "듀오 크림 세트(80+80)", 160),
        ("올리브영 기획 2개(80+50 ×2)", "듀오 대용량(130+130)", 260),
        ("수딩 크림 단품 80", "수딩 크림 80ml", 80), ("인텐시브 크림 단품 80", "인텐시브 크림 80ml", 80)]
for lab, it, ml in rows:
    print(f"- {lab}: 정가 {price(it,'정가')/ml:.0f} / 패리티 {price(it,'패리티')/ml:.0f} / 행사 {price(it,'행사')/ml:.0f} 원/ml")
oy_p = price("듀오 대용량(130+130)", "패리티") / 260; oy_e = price("듀오 대용량(130+130)", "행사") / 260
print(f"- 에스트라 무신사 단독 크림 80ml 2개 47,520원 = {47520/160:.0f}원/ml (리서치 2-1)")
print(f"- 계절 듀오 본품이 올리브영 기획 패리티 ml당({oy_p:.0f}원)과 같으려면 160ml에 {oy_p*160:,.0f}원 (정가 62,000 대비 {1-oy_p*160/62000:.0%} 할인) → 단품 패리티 깨짐")
MINI = 20  # 무신사 전용 미니 용량 [가정]
for lab, ml, pr in [(f"A안 듀오 80+80 + 전용 미니 {MINI}ml @ 패리티 합 {duo:,.0f}", 160 + MINI, duo),
                    ("B안 계절 크림 80 1개(수딩) + 다른 라인 미니 10ml @ 27,000", 90, price("수딩 크림 80ml", "패리티")),
                    (f"C안 80+50 ×2 @ 올리브영 기획 평시가 합 {price('듀오 대용량(130+130)','패리티'):,.0f}", 260, price("듀오 대용량(130+130)", "패리티"))]:
    print(f"- {lab}: {pr/ml:.0f}원/ml (올리브영 기획 패리티 대비 {pr/ml/oy_p-1:+.0%}, 행사 대비 {pr/ml/oy_e-1:+.0%}, 에스트라 단독 대비 {pr/ml/(47520/160)-1:+.0%})")

# ---------- 5. 비용 함수 ----------
def promo_var(B, N, EVp_, EVe_, opc=None):
    """N에 비례하는 무신사 판촉비: 행사 쿠폰 분담, CRM 쿠폰, 후기 적립금"""
    es = ev_share(B)
    festa = N * es * (EVp_ - EVe_) * B["mss_share"]
    crm_issue = N * sum(MS[:6]) * B["crm_target"] * B["crm_optin"] * (1 - B["holdout"])
    crm = crm_issue * B["crm_use"] * B["crm_amt"] * B["mss_share"]
    opc = opc if opc else OPC
    review = N * opc * B["review_rate"] * B["review_point"] * B["mss_share"]
    return dict(festa=festa, crm=crm, crm_issue=crm_issue, review=review)

def fixed_cost(B, r, lvl, visit):
    space_gmv = B["pyeong_sales"][lvl] * B["area"][lvl] * B["popup_days"]
    space = space_gmv * r
    md = mandays(B, lvl) * B["manday_cost"][lvl]
    media = B["media"][lvl]
    card_issue = visit * B["popup_days"] * B["card_take"]
    card = card_issue * B["card_use"] * B["card_amt"] * B["mss_share"]
    return dict(space_gmv=space_gmv, space=space, man=md, media=media, card=card, card_issue=card_issue)

def incr_rate(B, k):
    a, s = B["incr"][k]; return a + (1 - a) * (1 - s)

print("\n## 5. 증분율 (Q9)")
for k in B["incr"]:
    a, s = B["incr"][k]
    print(f"- {k}: 무신사 뷰티 첫 구매 {a:.0%} + 기존 뷰티 고객 {1-a:.0%} × (1 − 무신사 내 대체율 {s:.0%}) = {incr_rate(B,k):.1%}")

print("\n## 6. 무신사 비용 항목 (규모 기본 6,000명, 팝업 일 120명, 중 수수료 18.6%로 공간 기회비용 환산)")
N0 = B["scale"]["기본"]
COST = {}
for lvl in LV:
    pv = promo_var(B, N0, EVp, EVe)
    for rk, r in B["rates"].items():
        f = fixed_cost(B, r, lvl, 120)
        tot = f["space"] + f["man"] + f["media"] + f["card"] + pv["festa"] + pv["crm"] + pv["review"]
        cash = f["card"] + pv["festa"] + pv["crm"] + pv["review"]
        COST[(lvl, rk)] = (tot, cash)
        if rk == "중 18.6%":
            print(f"- [{lvl}] 공간 기회비용 거래액 {man(f['space_gmv'])} → 수수료 손실 {man(f['space'])} / 인일 {mandays(B,lvl)}×{B['manday_cost'][lvl]/1e4:.0f}만 = {man(f['man'])} / 지면 {man(f['media'])} / 퇴장 카드 {man(f['card'])} / 행사 쿠폰 분담 {man(pv['festa'])} / CRM {man(pv['crm'])}(발행 {pv['crm_issue']:,.0f}장) / 후기 적립 {man(pv['review'])} → 합계 {man(tot)} (현금성 판촉비 {man(cash)}, 나머지는 인일·공간·지면 기회비용)")
lo_c = min(v[0] for v in COST.values()); hi_c = max(v[0] for v in COST.values())
print(f"- 무신사 부담 합계 범위(비용 저~고 × 수수료 3안): {man(lo_c)} ~ {man(hi_c)}, 기본(비용 기본·중 수수료) {man(COST[('기본','중 18.6%')][0])}")

def econ(B, N, r, ik, lvl, visit, EVp_, EVe_, EVb_, opc=None):
    pv = promo_var(B, N, EVp_, EVe_, opc)
    f = fixed_cost(B, r, lvl, visit)
    cost = f["space"] + f["man"] + f["media"] + f["card"] + pv["festa"] + pv["crm"] + pv["review"]
    gmv = N * EVb_
    i = incr_rate(B, ik)
    gross = gmv * r - (pv["festa"] + pv["crm"] + pv["review"] + f["card"])
    incr_margin = gmv * r * i
    net = incr_margin - cost
    F = f["space"] + f["man"] + f["media"] + f["card"]
    v = (pv["festa"] + pv["crm"] + pv["review"]) / N
    unit = EVb_ * r * i - v
    be = F / unit if unit > 0 else float("inf")
    ltv = EVb_ * r * i          # #006: 1인 기대 거래액 × 수수료율 × 증분율
    cac = cost / N              # #006: 무신사 비용 ÷ 첫 구매자 수
    return dict(cost=cost, gmv=gmv, gross=gross, incr=incr_margin, net=net, ratio=ltv / cac, be=be, cac=cac,
                ltv=ltv, F=F, v=v, pv=pv, f=f)

print("\n## 7. 무신사 수익 = 거래액 × 수수료율 − 무신사 부담 판촉비 (12개월 코호트, 규모 시나리오는 목표 아님)")
print("| 규모 | 첫 구매자 | 거래액 | 수수료율 | 수수료 수익 | 판촉비 | 무신사 수익(총) | 증분 기준 수수료(증분 기본) |")
print("|---|---|---|---|---|---|---|---|")
for sk, N in B["scale"].items():
    for rk, r in B["rates"].items():
        e = econ(B, N, r, "기본", "기본", 120, EVp, EVe, EVb)
        promo = e["pv"]["festa"] + e["pv"]["crm"] + e["pv"]["review"] + e["f"]["card"]
        print(f"| {sk} | {N:,} | {man(e['gmv'])} | {rk} | {man(e['gmv']*r)} | {man(promo)} | {man(e['gross'])} | {man(e['incr'])} |")

print("\n## 8. LTV/CAC (12개월) 판정 — 비용 기본, 팝업 일 120명. LTV = 1인 기대 거래액 × 수수료율 × 증분율, CAC = 무신사 비용 ÷ 첫 구매자 수")
print("| 규모 | 수수료율 | 증분율 | LTV | CAC | LTV÷CAC | 판정 | 증분 순익 |")
print("|---|---|---|---|---|---|---|---|")
for sk, N in B["scale"].items():
    for rk, r in B["rates"].items():
        for ik in B["incr"]:
            e = econ(B, N, r, ik, "기본", 120, EVp, EVe, EVb)
            print(f"| {sk} | {rk} | {ik} {incr_rate(B,ik):.0%} | {won(e['ltv'])} | {won(e['cac'])} | {e['ratio']:.2f} | {'≥1 통과' if e['ratio']>=1 else '<1 미달'} | {man(e['net'])} |")

print("\n## 9. 손익분기 첫 구매자 수 (증분 기준, 증분 기본)")
BE = {}
for lvl in LV:
    for rk, r in B["rates"].items():
        e = econ(B, N0, r, "기본", lvl, 120, EVp, EVe, EVb)
        BE[(lvl, rk)] = e["be"]
        be = "도달 불가" if e["be"] == float("inf") else f"{e['be']:,.0f}명"
        print(f"- 비용 {lvl} / {rk}: 고정비 {man(e['F'])}, 1인 증분 수수료 {won(EVb*r*incr_rate(B,'기본'))} − 1인 판촉비 {won(e['v'])} → 손익분기 첫 구매자 {be}")

print("\n## 10. 동시 악화 하방 (Q10: 재구매×0.5, 사용량×0.6, 할인 30%, 팝업 방문 하단 120명·전환 10%)")
opc_d = orders(B, B["mix"], uf=0.6, rf=0.5)["total"] / 1000
N_d = N0 - 120 * B["popup_days"] * (0.15 - 0.10)   # 팝업 전환 15%→10%로 줄어든 구매자
print(f"- 하방 1인 주문 수 {opc_d:.2f}건(기본 {OPC:.2f}), 첫 구매자 {N_d:,.0f}명(팝업 전환 하단 반영)")
DOWN = {}
for rk, r in B["rates"].items():
    for lvl in ("기본", "고"):
        e = econ(B, N_d, r, "기본", lvl, 120, EVdp, EVd, EVd, opc_d)
        DOWN[(rk, lvl)] = e
        print(f"- {rk} / 비용 {lvl} / 규모 기본 / 증분 기본: 증분 수수료 {man(e['incr'])} − 무신사 비용 {man(e['cost'])} = {man(e['net'])} (LTV÷CAC {e['ratio']:.2f})")
WORST = {}
for rk, r in B["rates"].items():
    e = econ(B, B["scale"]["저"] - 84, r, "저", "고", 120, EVdp, EVd, EVd, opc_d)
    WORST[rk] = e["net"]
    print(f"- 최악 조합(게이트 없이 12개월 집행) {rk} / 비용 고 / 규모 저 / 증분 저: {man(e['net'])}")

# ---------- 11. 팝업 ----------
print("\n## 11. 팝업 (Q7)")
pop_single = (price("수딩 로션 160ml", "패리티") + price("인텐시브 크림 80ml", "패리티") + price("수딩 크림 80ml", "패리티")) / 3
pop_aov = B["popup_duo"] * duo + (1 - B["popup_duo"]) * pop_single
print(f"- 팝업 객단가(패리티, 무신사 POS) = 듀오 {B['popup_duo']:.0%} × {duo:,.0f} + 단품 {1-B['popup_duo']:.0%} × {pop_single:,.0f} = {won(pop_aov)}")
first_aov = sum(B["mix"][n] * res["패리티"][0][n]["first"] for n in B["mix"])
for sk, N in B["scale"].items():
    base_daily = N * MS[1] * first_aov / 30
    print(f"- 규모 {sk}: 기준선(4월) 온라인 일평균 {man(base_daily)} → 4주 이중차분 +15~35%p = {man(base_daily*28*0.15)}~{man(base_daily*28*0.35)}")
print("| 방문/일 | 전환 | 방문객 | 구매자 | 현장 거래액 | 무신사 수수료(중) | 퇴장 카드 발행 |")
print("|---|---|---|---|---|---|---|")
for vk, vv in B["visit"].items():
    for ck, cc in B["cvr"].items():
        V = vv * B["popup_days"]; b = V * cc
        print(f"| {vv} | {cc:.0%} | {V:,} | {b:,.0f} | {man(b*pop_aov)} | {man(b*pop_aov*0.186)} | {V*B['card_take']:,.0f}장 |")

def popup_cost(B, lvl, r, vv):
    f = fixed_cost(B, r, lvl, vv)
    md = B["mandays_item"]["3 팝업 공간(오프라인팀 협의·점검·POS·보안)"][lvl] * B["manday_cost"][lvl]
    return dict(space=f["space"], man=md, media=B["media"][lvl] * B["media_popup"], card=f["card"],
                total=f["space"] + md + B["media"][lvl] * B["media_popup"] + f["card"])

print("\n### 11-1. 팝업만 떼어 본 무신사 손익 (중 수수료, 증분 기본, 규모 기본; 비용 단계와 상승률 단계를 함께 움직임)")
r = 0.186; i = incr_rate(B, "기본")
base_daily0 = N0 * MS[1] * first_aov / 30
POP = {}
for lvl in LV:
    for vv, cc, lab in [(120, 0.15, "기본 120명·15%"), (120, 0.10, "하단 120명·10%"), (300, 0.15, "상단 300명·15%")]:
        V = vv * B["popup_days"]; sales = V * cc * pop_aov
        spill = base_daily0 * 28 * B["lift"][lvl]
        pc = popup_cost(B, lvl, r, vv)
        mrev = (sales + spill) * r * i
        need_v = (pc["total"] - spill * r * i) / (cc * pop_aov * r * i) / B["popup_days"] if pc["total"] > spill * r * i else 0
        POP[(lvl, lab)] = dict(sales=sales, spill=spill, cost=pc["total"], roas=(sales + spill) / pc["total"])
        print(f"- 비용 {lvl} / {lab}: 현장 {man(sales)} + 온라인 파급 {man(spill)} → 무신사 증분 수수료 {man(mrev)} vs 무신사 팝업 비용 {man(pc['total'])} → {man(mrev-pc['total'])} / 손익분기 일 방문객 {need_v:,.0f}명 / 무신사 비용 기준 ROAS {(sales+spill)/pc['total']:.2f}")

# ---------- 12. 쿠폰 ----------
print("\n## 12. 쿠폰 2종 (Q5) 예산 — 기본 규모")
pv = promo_var(B, N0, EVp, EVe)
ic = price("인텐시브 크림 80ml", "패리티")
print(f"- 할인액 근거: 인텐시브 크림 80ml 평시 {won(ic)} − {B['crm_amt']:,}원 = {won(ic-B['crm_amt'])} = 정가 대비 {1-(ic-B['crm_amt'])/32000:.1%} → Q3 행사 시나리오(20~30%) 안. 30% 상한까지 여유 {won(ic-22400-B['crm_amt'])}")
print(f"- ① 시즌 교체 CRM: 발행 = {N0:,} × 3~8월 첫 구매 비중 {sum(MS[:6]):.0%} × 수딩 단품 첫 구매(봄 러너) {B['crm_target']:.0%} × 수신 동의 {B['crm_optin']:.0%} × (1 − 홀드아웃 {B['holdout']:.0%}) = {pv['crm_issue']:,.0f}장")
print(f"  비용 = {pv['crm_issue']:,.0f} × 사용률 {B['crm_use']:.0%} × {B['crm_amt']:,}원 × 무신사 {B['mss_share']:.0%} = {won(pv['crm'])} (총 쿠폰액 {won(pv['crm']/B['mss_share'])})")
inc_buy = pv["crm_issue"] * (B["crm_use"] - B["crm_base_buy"])
inc_gmv = inc_buy * ic * FW / 80
print(f"  증분 구매자 = 발행 × (사용률 {B['crm_use']:.0%} − 홀드아웃 구매율 {B['crm_base_buy']:.0%}) = {inc_buy:,.0f}명 → 겨울 시즌 지속 거래액 {won(inc_gmv)} → 쿠폰 1원당 증분 거래액 {inc_gmv/(pv['crm']/B['mss_share']):.1f}원")
for sk in ("저", "고"):
    p2 = promo_var(B, B["scale"][sk], EVp, EVe)
    print(f"  (규모 {sk}) 발행 {p2['crm_issue']:,.0f}장, 무신사 부담 {won(p2['crm'])}")
for lab, vv in [("기본 120명", 120), ("상단 300명", 300)]:
    f = fixed_cost(B, 0.186, "기본", vv)
    print(f"- ② 팝업 퇴장 카드({lab}): 발행 {f['card_issue']:,.0f}장(방문객 × 수령 {B['card_take']:.0%}) × 사용률 {B['card_use']:.0%} × {B['card_amt']:,}원 × {B['mss_share']:.0%} = {won(f['card'])}")
print(f"- (행사) 페스타·무뷰페 쿠폰 공동 분담: {man(pv['festa'])} = 첫 구매자 × 행사 비중 {es:.0%} × (패리티 − 행사 기대 거래액 {won(EVp-EVe)}) × {B['mss_share']:.0%}")
for k, d in B["event_split"].items():
    print(f"  · {k} {d}일분 {man(pv['festa']*d/B['event_days'])}")
print(f"- (후기) 후기 적립금 분담: {man(pv['review'])} = 주문 {N0*OPC:,.0f}건 × 작성률 {B['review_rate']:.0%} × {B['review_point']:,}원 × {B['mss_share']:.0%}")

# ---------- 13. 게이트 ----------
print("\n## 13. 게이트 기준선·하한 (기준선 = 규모 기본 경로, 하한 = Q10 동시 악화 하방 또는 규모 저 경로)")
def repeaters(N, months, rf=1.0):
    """시점 가중 북극성: 월 m 첫 구매자는 (months − m − 0.5)개월 경과, 12개월 재구매 확률이 경과 개월에 비례해 쌓인다고 가정"""
    pr = sum(B["mix"][n] * min(1.0, B["p_repeat"][n] * rf) for n in B["mix"])
    return sum(N * MS[m] * pr * min(1.0, max(0.0, months - m - 0.5) / 12) for m in range(min(months, 12)))
pr_w = sum(B["mix"][n] * B["p_repeat"][n] for n in B["mix"])
trial_posts = sum(B["trial_n"].values()) * B["trial_post"]
g1_buy, g1_buy_lo = N0 * MS[0], B["scale"]["저"] * MS[0]
g1_gmv = g1_buy * first_aov
g1_gmv_lo = g1_buy_lo * values(B, "하방30")[2]
print(f"- G1 4주 첫 구매자: 기준선 {g1_buy:,.0f}명 / 하한 {g1_buy_lo:,.0f}명(규모 저 경로)")
print(f"- G1 4주 거래액: 기준선 {man(g1_gmv)} / 하한 {man(g1_gmv_lo)}(규모 저 × 할인 30%)")
rev2 = g1_buy * 0.5 * B["review_rate"] * 0.5 + trial_posts
rev2_lo = g1_buy_lo * 0.5 * B["review_rate"] * 0.5 * 0.5 + trial_posts * 0.5
rev4 = g1_buy * B["review_rate"] + trial_posts
rev4_lo = g1_buy_lo * B["review_rate"] * 0.5 + trial_posts * 0.5
print(f"- 후기 2주: 기준선 {rev2:,.0f}건(첫 2주 주문 × 작성률 {B['review_rate']:.0%} × 사용 지연 50% + 체험단 {trial_posts:.0f}건) / 하한 {rev2_lo:,.0f}건")
print(f"- G1 후기 4주: 기준선 {rev4:,.0f}건 / 하한 {rev4_lo:,.0f}건")
for rk in B["rates"]:
    be = BE[("기본", rk)]
    print(f"- 참고: 손익분기 경로({rk}, 비용 기본) 3월 첫 구매자 {be*MS[0]:,.0f}명" if be != float("inf") else f"- 참고: {rk} 손익분기 도달 불가")
kit_q = round(g1_buy * B["mix"]["봄 러너"], -2)
print(f"- V2 봄 러너 테스트 키트 한정 수량 = 3월 첫 구매자 {g1_buy:,.0f} × 봄 러너 {B['mix']['봄 러너']:.0%} ≈ {kit_q:,.0f}세트, 소진율 기준선 60%({kit_q*0.6:,.0f}세트) / 하한 30%({kit_q*0.3:,.0f}세트)")
g3 = repeaters(N0, 6); g3_lo = repeaters(N0, 6, 0.5)
g4 = repeaters(N0, 12); g4_lo = repeaters(N0, 12, 0.5)
print(f"- G3 6개월 북극성(2회 이상 구매 고객 수, 시점 가중): 기준선 {g3:,.0f}명 / 하한 {g3_lo:,.0f}명 (첫 구매자 누적 {N0*sum(MS[:6]):,.0f}명)")
print(f"- G4 12개월 북극성: 기준선 {g4:,.0f}명 / 하한 {g4_lo:,.0f}명 (첫 구매 후 12개월 기준 비율은 {pr_w:.1%} / {pr_w*0.5:.1%})")
orders6 = N0 * sum(MS[:6]) + g3 * 1.0
rev6 = orders6 * B["review_rate"] + trial_posts
rev6_lo = (B["scale"]["저"] * sum(MS[:6]) + repeaters(B["scale"]["저"], 6, 0.5)) * B["review_rate"] * 0.5 + trial_posts * 0.5
print(f"- G3 6개월 후기 누적(브랜드 전체): 기준선 {rev6:,.0f}건 / 하한 {rev6_lo:,.0f}건. 듀오 SKU만: 약 {rev6*o['duo']/o['total']:,.0f}건 → 기존 '대표 SKU 6개월 1,000건'은 규모 기본에서 도달 어려움")
R = EVd / EVp
print(f"- 하방 거래액 수준 = 기본의 {R:.0%} → 6개월에 나눠 월 {R**(1/6)-1:+.1%} (G3 월 성장률 하한: 카테고리 대비 이만큼 낮음)")
print(f"- 시즌 교체 재구매율: 기준선 15%(2026-10-30 확정, 도전 25%) / 하한 7.5%(재구매×0.5). CRM 증분: 기준선 +{(B['crm_use']-B['crm_base_buy'])*100:.0f}%p / 하한 0%p")
print(f"- 증분 대리 지표(제로이드 첫 구매자 중 최근 12개월 무신사 더마 구매 이력 없는 비율): 기준선 {incr_rate(B,'기본'):.0%} / 하한 {incr_rate(B,'저'):.0%}")

# ---------- 14. 제로이드 비용 (참고) ----------
print("\n## 14. 제로이드 비용 항목 (팝업·론칭, 저/기본/고, 참고)")
BUILD = {"저": 1_500_000, "기본": 2_000_000, "고": 3_000_000}   # 평당 시공·집기·철거
BA = {"저": 150000, "기본": 180000, "고": 220000}; LEAD = {"저": 250000, "기본": 300000, "고": 350000}
ZP = {}
trial = (B["trial_n"]["일반(듀오)"] * 62000 + B["trial_n"]["크루(봄 러너 키트)"] * 86000) * B["cogs"] + sum(B["trial_n"].values()) * B["ship"]
for lvl in LV:
    build = B["area"][lvl] * BUILD[lvl]
    ba = (3 * 14 + 1 * 4) * BA[lvl] + 14 * LEAD[lvl]       # 상시 3명×14일 + 주말 1명×4일, 책임자 14일
    content = {"저": 10_000_000, "기본": 20_000_000, "고": 30_000_000}[lvl]
    sample = {"저": 120, "기본": 120, "고": 300}[lvl] * 14 * 0.5 * {"저": 1000, "기본": 1500, "고": 2000}[lvl]
    ins = {"저": 500_000, "기본": 1_000_000, "고": 2_000_000}[lvl]
    run = {"저": 1_000_000, "기본": 2_000_000, "고": 3_000_000}[lvl]
    ZP[lvl] = build + ba + sample + ins + run
    tot = ZP[lvl] + trial + content
    print(f"- [{lvl}] 시공 {man(build)} / BA·책임자 {man(ba)} / 체험단 {man(trial)} / 콘텐츠 {man(content)} / 샘플 {man(sample)} / 보험 {man(ins)} / 출발 런 운영 {man(run)} → 합계 {man(tot)} (그중 팝업분 {man(ZP[lvl])})")
lst_ev = values(B, "정가")[1]
for sk, N in B["scale"].items():
    print(f"- 상시 할인 부담(정가 대비 패리티 차액, 제로이드) 규모 {sk}: {man(N*(lst_ev-EVp)*(1-es))} + 행사 쿠폰 제로이드 분담 {man(N*es*(EVp-EVe)*(1-B['mss_share']))}")

# ---------- 15. 승인 항목별 무신사 부담과 시점 ----------
print("\n## 15. 승인 항목 1~5별 무신사 부담 (규모 기본, 중 수수료, 팝업 일 120명)")
def items(lvl, r=0.186, N=N0):
    pv = promo_var(B, N, EVp, EVe); f = fixed_cost(B, r, lvl, 120); c = B["manday_cost"][lvl]
    mi = {k: v[lvl] * c for k, v in B["mandays_item"].items()}
    k1, k2, k3, k4, k5 = list(mi)
    return {
        "1 입점·단독 구성": dict(man=mi[k1], cash=pv["review"], opp=0, note="MD 인일 + 후기 적립 분담"),
        "2 페스타 슬롯": dict(man=mi[k2], cash=pv["festa"], opp=B["media"][lvl] * (1 - B["media_popup"]), note="인일 + 행사 쿠폰 분담(연 3회) + 지면"),
        "3 성수 팝업 공간": dict(man=mi[k3], cash=f["card"], opp=f["space"] + B["media"][lvl] * B["media_popup"], note="오프라인팀 인일 + 퇴장 카드 + 공간·앱 안내 지면"),
        "4 집계 통계 공유": dict(man=mi[k4], cash=0, opp=0, note="데이터팀 인일"),
        "5 시즌 교체 CRM": dict(man=mi[k5], cash=pv["crm"], opp=0, note="CRM팀 인일 + CRM 쿠폰 분담"),
    }
print("| 승인 항목 | 인일(저/기본/고) | 저 | 기본 | 고 | 기본 내역 |")
print("|---|---|---|---|---|---|")
IT = {lvl: items(lvl) for lvl in LV}
for k in IT["기본"]:
    md = list(B["mandays_item"].values())[int(k[0]) - 1]
    vals = [sum(IT[l][k][x] for x in ("man", "cash", "opp")) for l in LV]
    d = IT["기본"][k]
    print(f"| {k} | {md['저']}/{md['기본']}/{md['고']} | {man(vals[0])} | {man(vals[1])} | {man(vals[2])} | 인일 {man(d['man'])} + 현금성 {man(d['cash'])} + 기회비용 {man(d['opp'])} |")
tots = [sum(sum(v.values()) if False else v["man"] + v["cash"] + v["opp"] for v in IT[l].values()) for l in LV]
print(f"| 합계 | {mandays(B,'저')}/{mandays(B,'기본')}/{mandays(B,'고')} | {man(tots[0])} | {man(tots[1])} | {man(tots[2])} | 6절 중 수수료 합계와 같음 |")

print("\n### 15-1. 게이트 시점별 누적 무신사 비용과 그 시점까지의 누적 순손익 (Q10 동시 악화 하방 수익 반영)")
def stages(lvl, r):
    c = B["manday_cost"][lvl]; mi = {k: v[lvl] for k, v in B["mandays_item"].items()}
    k1, k2, k3, k4, k5 = list(mi)
    pvb = promo_var(B, N0, EVp, EVe)
    fm = {k: pvb["festa"] * d / B["event_days"] for k, d in B["event_split"].items()}
    pc = popup_cost(B, lvl, r, 120)
    d_m = (mi[k4] - 2) * c / 12        # 데이터팀 월 운영분(셋업 2인일 제외)
    st = {
        "G1 이전(~3월)": mi[k1] * 0.6 * c + mi[k2] * c + B["media"][lvl] * (1 - B["media_popup"]) + fm["3월 페스타"] + 2 * c + d_m + pvb["review"] * MS[0],
        "G1~G2(4~6월)": mi[k1] * 0.1 * c + pc["total"] + fm["5월 페스타"] + 3 * d_m + pvb["review"] * sum(MS[1:4]),
        "G2~G3(7~8월)": mi[k1] * 0.1 * c + fm["8월 무뷰페"] + 2 * d_m + pvb["review"] * sum(MS[4:6]),
        "G3~G4(9~2월)": mi[k1] * 0.2 * c + mi[k5] * c + pvb["crm"] + 6 * d_m + pvb["review"] * sum(MS[6:]),
    }
    # G1에서 중단할 때 12개월: 팝업·CRM·추가 지면 없음, 단품 상시 운영(MD 유지·데이터·행사 쿠폰·후기 적립은 계속)
    g1stop = st["G1 이전(~3월)"] + mi[k1] * 0.4 * c + fm["5월 페스타"] + fm["8월 무뷰페"] + 11 * d_m + pvb["review"] * sum(MS[1:])
    return st, g1stop
cum_share = {"G1 이전(~3월)": MS[0] * 0.5, "G1~G2(4~6월)": sum(MS[:4]) * 0.6, "G2~G3(7~8월)": sum(MS[:6]) * 0.7, "G3~G4(9~2월)": 1.0}
STOP = {}
for lvl, rk in [("기본", "중 18.6%"), ("고", "중 18.6%"), ("기본", "저 9.4%")]:
    r = B["rates"][rk]
    st, g1stop = stages(lvl, r)
    inc_d = econ(B, N_d, r, "기본", lvl, 120, EVdp, EVd, EVd, opc_d)["incr"]
    inc_d_nopop = econ(B, N0 - 168, r, "기본", lvl, 120, EVdp, EVd, EVd, opc_d)["incr"]
    acc = 0
    print(f"- [비용 {lvl} / {rk}]")
    for k, v in st.items():
        acc += v
        STOP[(lvl, rk, k)] = inc_d * cum_share[k] - acc
        print(f"  · {k}: 구간 비용 {man(v)}, 누적 {man(acc)} / 하방 증분 수수료 누적 약 {man(inc_d*cum_share[k])} → 시점 누적 순손익 {man(STOP[(lvl, rk, k)])}")
    STOP[(lvl, rk, "G1중단12")] = inc_d_nopop - g1stop
    print(f"  · G1에서 팝업·CRM을 멈추고 단품 운영만 할 때 12개월: 비용 {man(g1stop)} vs 하방 증분 수수료 {man(inc_d_nopop)} → {man(inc_d_nopop-g1stop)}")
    print(f"  · (검산) 구간 합 {man(acc)} vs 6절 합계 {man(COST[(lvl, rk)][0])}")

# ---------- 16. 판매가표·가드레일 ----------
print("\n## 16. 무신사 판매가 제안(패리티)·행사 시나리오·가격 가드레일")
SKUS = [("계절 듀오 크림 세트(히어로, +전용 미니)", "듀오 크림 세트(80+80)"), ("봄 러너 키트", "봄 러너 키트"),
        ("겨울 산행 키트", "겨울 산행 키트"), ("환절기 대용량(단독 아님)", "듀오 대용량(130+130)"),
        ("여름 땀 시즌 키트", "여름 땀 시즌 키트"), ("인텐시브 크림 80ml", "인텐시브 크림 80ml"), ("수딩 크림 80ml", "수딩 크림 80ml")]
print("| 상품 | 정가(합) | 평시 판매가(패리티) | 행사 20% | 행사 30%(하한) | 평시 ml당 |")
print("|---|---|---|---|---|---|")
for lab, it in SKUS:
    lst = price(it, "정가"); par = price(it, "패리티"); vol = PRICE[it][4]
    if it == "듀오 크림 세트(80+80)": vol = 160 + MINI
    e20, e30 = min(par, lst * 0.8), min(par, lst * 0.7)   # 기획 상품은 평시가가 이미 20% 넘게 할인돼 있어 평시가보다 높게 두지 않음
    print(f"| {lab} | {lst:,} | {par:,.0f} | {e20:,.0f} | {e30:,.0f} | {par/vol:.0f}원 |" if vol else f"| {lab} | {lst:,} | {par:,.0f} | {e20:,.0f} | {e30:,.0f} | — |")
print("- 가드레일 ① 평시: 무신사 단품 판매가 = 다른 채널 평시 판매가(10-30 기준 정가 대비 약 10%) ±1,000원")
print("- 가드레일 ② 행사 하한: 쿠폰·적립 포함 고객 실결제가 ≥ 정가 × 70% (인텐시브 크림 22,400원, 수딩 크림 21,000원, 계절 듀오 43,400원)")
print("- 가드레일 ③ 역전 신호: 다른 채널 실판매가가 무신사 판매가보다 10% 이상 낮은 날이 7일 연속 → 리스크 1 대응 착수")

# ---------- 17. 재고 ----------
print("\n## 17. 재고 (위탁 + 직배송)")
wk = N0 * OPC / 52
peak = N0 * MS[0] * 1.0 / 4.3
print(f"- 평균 주간 주문 {wk:,.0f}건, 3월(입점·페스타) 주간 {peak:,.0f}건")
print(f"- 안전재고 {B['safety_weeks']}주분 = 평시 {wk*B['safety_weeks']:,.0f}건분 (3월은 {peak*B['safety_weeks']:,.0f}건분)")
ev_extra = B["event_lift"] * 11 / 7
print(f"- 행사 전 추가 = 행사 일평균 +{B['event_lift']:.0%} × 11일(페스타) ÷ 7 = {ev_extra:.1f}주분 → 3주분 추가 추천(여유 포함). 팝업 현장 재고 = 14일 구매자 252명 × 1.2개 ≈ 300개(상단 300명 시 750개)")

# ---------- 18. CRM 발송일 ----------
print("\n## 18. 시즌 교체 CRM 발송일 = 구매일 + 용량 ÷ 일 사용량 − 14일")
for lab, ml, u in [("수딩 크림 80ml", 80, 1.0), ("수딩 로션 160ml", 160, 1.5), ("수딩 크림 기획 130ml", 130, 1.0)]:
    d = ml / u - 14
    lo_, hi_ = ml / 1.5 - 14 if "크림" in lab else ml / 2.0 - 14, ml / 0.6 - 14 if "크림" in lab else ml / 1.0 - 14
    import datetime as _dt
    a = _dt.date(2027, 9, 1) - _dt.timedelta(days=round(d)); b_ = _dt.date(2027, 10, 31) - _dt.timedelta(days=round(d))
    print(f"- {lab}(일 {u}ml): 구매 후 {d:.0f}일(사용량 범위 {lo_:.0f}~{hi_:.0f}일). 소진 기준 발송 대상 구매일 {a:%m.%d}~{b_:%m.%d}, 그 전 구매자는 9월 첫 주 일괄 발송, 그 뒤 구매자는 발송 없음(10.31 사용 종료)")

# ---------- 19. 팝업 대안 비교 ----------
print("\n## 19. 팝업 대안 A/B/C 무신사 비용 (중 수수료, 일 120명)")
for lvl in LV:
    pc = popup_cost(B, lvl, 0.186, 120)
    print(f"- 비용 {lvl}: A(4~5월 성수) {man(pc['total'])} / B(9~10월 성수) 같은 산식 {man(pc['total'])} / C(홍대) 같은 산식 {man(pc['total'])} [홍대 평당 거래액·면적 미확인, 성수 값 준용]")

# ---------- 20. 팝업 ROAS (G2 보조) ----------
print("\n## 20. 팝업 ROAS (G2 보조) = (현장 거래액 + 4주 증분 온라인 거래액) ÷ 팝업 비용")
for lvl in LV:
    for lab in ("기본 120명·15%", "하단 120명·10%"):
        p = POP[(lvl, lab)]
        tot_cost = p["cost"] + ZP[lvl]
        print(f"- 비용 {lvl} / {lab}: 무신사 비용 기준 {p['roas']:.2f} / 무신사+제로이드 팝업비 기준 {(p['sales']+p['spill'])/tot_cost:.2f}")

# ---------- 21. 결재 요약 숫자 ----------
print("\n## 21. 결재 요약·한 장 요약용 숫자")
print(f"- ③ 1,000명당 12개월 2회 이상 구매 {pr_w*1000:,.0f}명 / 1인 12개월 기대 거래액 {won(EVp)}(첫 구매만 {won(res['패리티'][2])}의 {EVp/res['패리티'][2]:.2f}배) / 주문당 객단가 {won(AOV)}(크림 단품 평균 대비 {AOV/single-1:+.0%})")
print(f"- COST 무신사 부담 {man(lo_c)}~{man(hi_c)}(기본 {man(COST[('기본','중 18.6%')][0])}, 현금성 {man(COST[('기본','중 18.6%')][1])})")
print(f"- 손익분기 첫 구매자(비용 기본, 증분 기본) 저 {BE[('기본','저 9.4%')]:,.0f} / 중 {BE[('기본','중 18.6%')]:,.0f} / 고 {BE[('기본','고 27.8%')]:,.0f}명")
print(f"- 하방(게이트 없이 12개월, 비용 기본·중) {man(DOWN[('중 18.6%','기본')]['net'])} / 누적 손실 최저점(G2 직후) {man(STOP[('기본','중 18.6%','G1~G2(4~6월)')])} / G1 중단 후 12개월 {man(STOP[('기본','중 18.6%','G1중단12')])} / 최악 조합(비용 고·규모 저·증분 저) {man(WORST['중 18.6%'])}")
