"""Stage 4 기대효과·페르소나 재구매 가치 계산 스크립트.
- 가격: 올리브영 정가(2026-10-30, research/brand-product.md 2장, decisions.md 가격 기준)
- 모든 가정값은 [미확인] 추천값이다(output/리포트/가정값-목록.md). 값을 바꾸면 A 블록만 고치고 다시 실행한다.
- 금액은 '거래액 기준'. 무신사 수수료가 '협의'라 마진·수익률은 계산하지 않는다.
실행: python3 -I stage4_estimates.py > stage4_estimates_output.txt
"""

# ---------------- A. 가정값 (모두 [미확인]) ----------------
A = dict(
    disc=0.20,            # A01 무신사 실결제 할인율(정가 대비)
    cream_ml_day=1.0,     # A02 크림 일 사용량(ml): 1회 0.5ml × 아침·저녁
    lotion_ml_day=1.5,    # A03 로션 일 사용량(ml)
    cleanser_ml_day=1.5,  # A04 포밍 클렌저 일 사용량(ml)
    sun_ml_day=0.5,       # A05 선크림 일 사용량(ml), 3~8월만
    p_repeat={"봄 러너": 0.30, "겨울 산행러": 0.15, "환절기 민감러": 0.30},  # A06 12개월 내 2회 이상 구매 확률
    w_scen={"보수": 0.50, "기본": 0.35, "낙관": 0.15},  # A07 재구매자 안의 시나리오 비중
    persona_mix={"봄 러너": 0.35, "겨울 산행러": 0.25, "환절기 민감러": 0.40},  # A08 첫 구매 고객 페르소나 구성
    duo_share=0.20,       # A09 주문 중 듀오 세트 비중
    kit_share=0.10,       # A10 주문 중 시즌 기획세트 비중
    popup_days=14,        # A11 팝업 기간(일)
    popup_daily_visit=300,  # A12 팝업 일 방문객
    popup_trial=0.50,     # A13 체험 참여율
    popup_cvr=0.15,       # A14 현장 구매 전환율(방문객 대비)
    popup_online_4w=0.10, # A15 체험자 중 4주 내 온라인 구매 비율
    popup_lift=0.35,      # A16 팝업 후 4주 온라인 일평균 거래액 상승률(기준값 성수 3주 +35%)
    season_switch=0.15,   # A17 시즌 교체 재구매율(3~8월 수딩 구매자 중 9~12월 인텐시브 구매)
)
SPRING_SUMMER = 184  # 3/1~8/31
FALL_WINTER = 181    # 9/1~2/28

# ---------------- B. 가격(올리브영 정가, 원) ----------------
P = {
    "수딩 크림 80ml": (30000, 80), "수딩 로션 160ml": (30000, 160),
    "인텐시브 크림 80ml": (32000, 80), "인텐시브 로션 160ml 기획": (32000, 160),
    "인텐시브 오인트 크림 80ml": (35000, 80), "인텐시브 크림 미스트 100ml": (23000, 100),
    "포밍 클렌저 240ml": (24000, 240), "데일리 선크림 50ml": (32000, 50),
    "수딩 세럼 마스크 5매": (30000, None),
    "듀오 크림 세트(80+80)": (62000, 160), "듀오 대용량(130+130)": (78000, 260),
}
def won(x): return f"{x:,.0f}원"

def use(item, days, ml_day):
    price, vol = P[item]
    ml = days * ml_day
    units = ml / vol
    return dict(item=item, days=days, ml=ml, cycle=vol / ml_day, units=units, amt=units * price)

def fixed(item, n):
    price, _ = P[item]
    return dict(item=item, days=None, ml=None, cycle=None, units=n, amt=n * price)

c, l = A["cream_ml_day"], A["lotion_ml_day"]
personas = {
    "봄 러너": dict(first=("수딩 로션 160ml", 30000), scen={
        "보수": [use("수딩 로션 160ml", SPRING_SUMMER, l)],
        "기본": [use("수딩 로션 160ml", SPRING_SUMMER, l), use("인텐시브 로션 160ml 기획", FALL_WINTER, l)],
        "낙관": [use("수딩 로션 160ml", SPRING_SUMMER, l), use("인텐시브 로션 160ml 기획", FALL_WINTER, l),
                 use("포밍 클렌저 240ml", 365, A["cleanser_ml_day"]), use("데일리 선크림 50ml", SPRING_SUMMER, A["sun_ml_day"])],
    }),
    "겨울 산행러": dict(first=("인텐시브 크림 80ml", 32000), scen={
        "보수": [use("인텐시브 크림 80ml", FALL_WINTER, c)],
        "기본": [use("인텐시브 크림 80ml", FALL_WINTER, c), use("수딩 크림 80ml", SPRING_SUMMER, c)],
        "낙관": [use("인텐시브 크림 80ml", 91, c), use("인텐시브 오인트 크림 80ml", 90, c),
                 use("수딩 크림 80ml", SPRING_SUMMER, c), fixed("인텐시브 크림 미스트 100ml", 2)],
    }),
    "환절기 민감러": dict(first=("듀오 크림 세트(80+80)", 62000), scen={
        "보수": [use("듀오 크림 세트(80+80)", SPRING_SUMMER, c)],
        "기본": [use("듀오 대용량(130+130)", 365, c)],
        "낙관": [use("듀오 대용량(130+130)", 365, c), use("포밍 클렌저 240ml", 365, A["cleanser_ml_day"]),
                 fixed("수딩 세럼 마스크 5매", 1)],
    }),
}

def persona_values(A):
    out = {}
    for name, p in personas.items():
        tot = {s: sum(x["amt"] for x in items) for s, items in p["scen"].items()}
        rep = sum(A["w_scen"][s] * tot[s] for s in tot)
        pr = A["p_repeat"][name]
        first = p["first"][1]
        ev = (1 - pr) * first + pr * rep
        out[name] = dict(tot=tot, rep=rep, first=first, ev=ev, ev_gmv=ev * (1 - A["disc"]),
                         first_gmv=first * (1 - A["disc"]))
    return out

print("# Stage 4 계산 결과 (모든 값 (추정), 가정은 [미확인])\n")
print("## 1. 사용 주기 (용량 ÷ 일 사용량)")
for item, ml_day in [("수딩 크림 80ml", c), ("인텐시브 크림 80ml", c), ("수딩 로션 160ml", l),
                     ("인텐시브 로션 160ml 기획", l), ("포밍 클렌저 240ml", A["cleanser_ml_day"]),
                     ("데일리 선크림 50ml", A["sun_ml_day"]), ("듀오 크림 세트(80+80)", c), ("듀오 대용량(130+130)", c)]:
    price, vol = P[item]
    print(f"- {item}: {vol}ml ÷ {ml_day}ml/일 = {vol/ml_day:.0f}일(약 {vol/ml_day/30.4:.1f}개월), ml당 {price/vol:.1f}원")

V = persona_values(A)
print("\n## 2. 페르소나별 연간 구매액(올리브영 정가) / 무신사 거래액(할인 반영)")
for name, p in personas.items():
    print(f"\n### {name} (첫 구매: {p['first'][0]} {won(p['first'][1])})")
    for s, items in p["scen"].items():
        for x in items:
            extra = f"{x['days']}일 × 사용 → {x['units']:.2f}개" if x["days"] else f"{x['units']}개(고정)"
            print(f"  [{s}] {x['item']}: {extra} = {won(x['amt'])}")
        t = V[name]["tot"][s]
        print(f"  [{s}] 합계 정가 {won(t)} / 무신사 거래액 {won(t*(1-A['disc']))} / 첫 구매 대비 {t/p['first'][1]:.1f}배")
    v = V[name]
    print(f"  재구매자 가중 평균(정가) {won(v['rep'])}, 재구매 확률 {A['p_repeat'][name]:.0%}")
    print(f"  ▶ 신규 고객 1명 기대 연간 가치: 정가 {won(v['ev'])} / 무신사 거래액 {won(v['ev_gmv'])} (1회 구매만 할 때 {won(v['first_gmv'])}의 {v['ev']/v['first']:.2f}배)")

print("\n## 3. 첫 구매 고객 1,000명 코호트 (페르소나 구성 A08)")
mix = A["persona_mix"]
rep_n = sum(1000 * mix[n] * A["p_repeat"][n] for n in mix)
ev_tot = sum(1000 * mix[n] * V[n]["ev_gmv"] for n in mix)
once_tot = sum(1000 * mix[n] * V[n]["first_gmv"] for n in mix)
print(f"- 2회 이상 구매 고객(북극성): {rep_n:.0f}명 ({rep_n/10:.1f}%)")
print(f"- 12개월 거래액: {won(ev_tot)} vs 첫 구매만 {won(once_tot)} → 재구매가 더하는 거래액 {won(ev_tot-once_tot)} (+{(ev_tot/once_tot-1):.0%})")
sw = sum(1000 * mix[n] * A["p_repeat"][n] * (A["w_scen"]["기본"] + A["w_scen"]["낙관"]) for n in mix)
print(f"- 시즌 교체(기본·낙관) 고객: {sw:.0f}명 ({sw/10:.1f}%)")

print("\n## 4. 듀오·기획세트 → 객단가")
single = (30000 + 32000) / 2 * (1 - A["disc"])
duo = 62000 * (1 - A["disc"])
kit = (86000 + 55000 + 78000) / 3 * (1 - A["disc"])
d, k = A["duo_share"], A["kit_share"]
aov0 = single
aov1 = single * (1 - d) + duo * d
aov2 = single * (1 - d - k) + duo * d + kit * k
print(f"- 단품만: {won(aov0)} / 듀오 {d:.0%}: {won(aov1)} (+{aov1/aov0-1:.0%}) / 듀오 {d:.0%}+기획세트 {k:.0%}: {won(aov2)} (+{aov2/aov0-1:.0%})")
print(f"- 거래액 중 듀오 비중: {duo*d/aov2:.0%}, 기획세트 비중: {kit*k/aov2:.0%}, 단품 {single*(1-d-k)/aov2:.0%}")
for dd in (0.10, 0.20, 0.30):
    a = single * (1 - dd - k) + duo * dd + kit * k
    print(f"  · 듀오 {dd:.0%}일 때 객단가 {won(a)} (+{a/aov0-1:.0%})")

print("\n## 5. 4~5월 팝업")
vis = A["popup_days"] * A["popup_daily_visit"]
buy = vis * A["popup_cvr"]
trial = vis * A["popup_trial"]
onl = trial * A["popup_online_4w"]
popup_aov = duo + 6000 * (1 - A["disc"]) * 2  # 듀오 + 마스크 2매
print(f"- 방문객 {vis:,.0f}명 = {A['popup_days']}일 × {A['popup_daily_visit']}명")
print(f"- 현장 구매 {buy:,.0f}명(전환 {A['popup_cvr']:.0%}), 팝업 객단가 {won(popup_aov)} → 방문객 1,000명당 현장 거래액 {won(1000*A['popup_cvr']*popup_aov)}")
print(f"- 체험 {trial:,.0f}명 → 4주 내 온라인 구매 {onl:,.0f}명. 오프라인 접점 신규 구매자 합 {buy+onl:,.0f}명")
print(f"- 온라인 파급: 팝업 후 4주 추가 거래액 = 팝업 전 일평균 거래액 × {A['popup_lift']:.0%} × 28일 = 팝업 전 일평균의 {A['popup_lift']*28:.1f}일분")
for lift in (0.20, 0.35, 0.50):
    print(f"  · 상승률 {lift:.0%} → {lift*28:.1f}일분")

print("\n## 6. 9~10월 시즌 교체 캠페인 (3~8월 수딩 구매자 1,000명당)")
for r in (0.10, 0.15, 0.25):
    g = 1000 * r * 32000 * (1 - A["disc"])
    print(f"- 전환율 {r:.0%}: 인텐시브 구매 {1000*r:.0f}명, 첫 인텐시브 크림 1통 거래액 {won(g)}, 겨울 한 시즌 지속 시 {won(1000*r*FALL_WINTER/80*32000*(1-A['disc']))}")

print("\n## 7. 1년차 월별 성장률 기준 (경쟁 더마 무신사 연 성장률의 월 환산)")
for nm, g in [("셀퓨전씨", 0.69), ("코스알엑스", 0.72), ("에스트라", 1.93), ("일리윤", 2.89)]:
    print(f"- {nm} +{g:.0%}/년 → 월 {((1+g)**(1/12)-1):.1%}")

print("\n## 8. 민감도: 신규 고객 1명 기대 연간 가치(무신사 거래액, 3명 가중 평균)")
def wavg(A):
    V = persona_values(A)
    return sum(A["persona_mix"][n] * V[n]["ev_gmv"] for n in V)
base = wavg(A)
print(f"- 기본: {won(base)}")
import copy
# 재구매 확률 ×0.5 / ×1.5
for f in (0.5, 1.5):
    B = copy.deepcopy(A); B["p_repeat"] = {k: x * f for k, x in A["p_repeat"].items()}
    print(f"- 재구매 확률 ×{f}: {won(wavg(B))} ({wavg(B)/base-1:+.0%})")
for dsc in (0.10, 0.30):
    B = copy.deepcopy(A); B["disc"] = dsc
    print(f"- 할인율 {dsc:.0%}: {won(wavg(B))} ({wavg(B)/base-1:+.0%})")
for w in ({"보수": 0.7, "기본": 0.25, "낙관": 0.05}, {"보수": 0.3, "기본": 0.45, "낙관": 0.25}):
    B = copy.deepcopy(A); B["w_scen"] = w
    print(f"- 시나리오 비중 {w}: {won(wavg(B))} ({wavg(B)/base-1:+.0%})")
# 사용량 ±50%: 재구매자 연간액이 사용량에 비례(고정 품목 제외 근사)
for f in (0.6, 1.5):
    B = copy.deepcopy(A)
    V2 = {}
    for n, p in personas.items():
        tot = {s: sum(x["amt"] * (f if x["days"] else 1) for x in items) for s, items in p["scen"].items()}
        rep = sum(A["w_scen"][s] * tot[s] for s in tot)
        pr = A["p_repeat"][n]
        V2[n] = ((1 - pr) * p["first"][1] + pr * rep) * (1 - A["disc"])
    val = sum(A["persona_mix"][n] * V2[n] for n in V2)
    print(f"- 일 사용량 ×{f}: {won(val)} ({val/base-1:+.0%})")
