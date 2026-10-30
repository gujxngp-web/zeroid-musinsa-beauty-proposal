"""리뷰 정량분석 계산 스크립트 (올리브영 기준).
원자료: oy_sku_overall.csv(상품 전체 표기), oy_sample50.csv(최근 50개 표본), oy_sample300.csv(확장 300개 표본)
출처: research/reviews/oliveyoung-*.md, research/reviews/summary.md (수집일 2026-10-30)
실행: python3 -I review_stats.py > review_stats_output.txt
"""
import csv
from collections import defaultdict

def load(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def num(x):
    return float(x) if x not in ("", None) else None

LINES = ["인텐시브", "수딩", "핌프로브"]
ov = load("oy_sku_overall.csv")
s50 = load("oy_sample50.csv")
s300 = load("oy_sample300.csv")

print("## A. 라인별 리뷰 수 가중 평균 (상품 전체 표기, 확인한 SKU만)")
for ln in LINES:
    rows = [r for r in ov if r["line"] == ln]
    n = sum(num(r["total_reviews"]) for r in rows)
    def w(col):
        vals = [(num(r[col]), num(r["total_reviews"])) for r in rows if num(r[col]) is not None]
        tw = sum(b for _, b in vals)
        return sum(a * b for a, b in vals) / tw if tw else None
    print(f"{ln}: SKU {len(rows)}개, 리뷰 {n:,.0f}, 평점 {w('avg_rating'):.2f}, 5점 {w('r5'):.1f}%, 4점 {w('r4'):.1f}%, 3점 {w('r3'):.1f}%, 1~2점 {w('r2')+w('r1'):.1f}%, "
          f"건성 {w('survey_skin_dry'):.1f}% 복합 {w('survey_skin_combo'):.1f}% 지성 {w('survey_skin_oily'):.1f}%, "
          f"보습 {w('survey_effect_moist'):.1f}% 진정 {w('survey_effect_soothe'):.1f}% (클렌저 제외), 순해요 {w('survey_mild'):.1f}%")

print("\n## B. 최근 50개 표본 라인 합계 (n=150/라인)")
tot = defaultdict(float)
for ln in LINES:
    rows = [r for r in s50 if r["line"] == ln]
    agg = defaultdict(float)
    for r in rows:
        for k, v in r.items():
            if k not in ("line", "sku", "period") and v != "":
                agg[k] += float(v)
    for k, v in agg.items():
        tot[k] += v
    n = 50 * len(rows)
    avg = (5*agg['s5']+4*agg['s4']+3*agg['s3']+2*agg['s2']+agg['s1'])/n
    print(f"{ln}: 평균 {avg:.2f}, 5점 {agg['s5']:.0f}, 4점 {agg['s4']:.0f}, 3점 {agg['s3']:.0f}, 2점 {agg['s2']:.0f}, 1점 {agg['s1']:.0f} | "
          f"매장구매 {agg['store']:.0f} ({agg['store']/n*100:.1f}%), 재구매표시 {agg['repurchase']:.0f} ({agg['repurchase']/n*100:.1f}%), 포토 {agg['photo']:.0f}, 한달이상 {agg['month_plus']:.0f} ({agg['month_plus']/n*100:.1f}%) | "
          f"프로필 공개 {agg['profile_n']:.0f}: 건성 {agg['p_dry']:.0f} 복합 {agg['p_combo']:.0f} 지성 {agg['p_oily']:.0f} 민감 {agg['p_sensitive']:.0f} 트러블성 {agg['p_trouble']:.0f}")
    kws = {k: agg[k] for k in agg if k.startswith("kw_")}
    print("   키워드(언급 리뷰 수): " + ", ".join(f"{k[3:]} {v:.0f}" for k, v in sorted(kws.items(), key=lambda x: -x[1])))
n = 450
print(f"전체 450: 매장구매 {tot['store']:.0f} ({tot['store']/n*100:.1f}%), 재구매표시 {tot['repurchase']:.0f} ({tot['repurchase']/n*100:.1f}%), 한달이상 {tot['month_plus']:.0f} ({tot['month_plus']/n*100:.1f}%), 계절 {tot['kw_season']:.0f} ({tot['kw_season']/n*100:.1f}%), 야외 {tot['kw_outdoor']:.0f}")
print("SKU별 매장구매 비율: " + ", ".join(f"{r['sku']} {int(r['store'])*2}%" for r in s50))

print("\n## C. 계절 듀오 비교: 확장 300개 표본 (크림·로션)")
grp = defaultdict(lambda: defaultdict(float))
for r in s300:
    for k, v in r.items():
        if k not in ("line", "sku", "period") and v != "":
            grp[r["line"]][k] += float(v)
for ln in ("인텐시브", "수딩"):
    g = grp[ln]; n = 600
    winter = g['season_winter'] + g['season_coldwind'] + g['season_heating']
    summer = g['season_summer']
    print(f"{ln} (n=600): 재구매배지 {g['repurchase_badge']:.0f} ({g['repurchase_badge']/n*100:.1f}%), 본문 재구매/정착 {g['kw_repurchase_text']:.0f} ({g['kw_repurchase_text']/n*100:.1f}%), "
          f"계절 언급 {g['kw_season']:.0f} ({g['kw_season']/n*100:.1f}%), 겨울계열(겨울+찬바람+난방) {winter:.0f} ({winter/n*100:.1f}%), 여름 {summer:.0f} ({summer/n*100:.1f}%), "
          f"겨울계열:여름 = {winter/summer:.2f}:1, 환절기 {g['season_transition']:.0f}, 가을 {g['season_autumn']:.0f}, "
          f"장벽 {g['kw_barrier']:.0f} ({g['kw_barrier']/n*100:.1f}%), 끈적/무거움 불만 {g['kw_heavy']:.0f} ({g['kw_heavy']/n*100:.1f}%), 순함 {g['kw_mild']:.0f} ({g['kw_mild']/n*100:.1f}%), 보습 {g['kw_moist']:.0f} ({g['kw_moist']/n*100:.1f}%), "
          f"1~2점 {g['s2']+g['s1']:.0f} ({(g['s2']+g['s1'])/n*100:.1f}%), 평균 {(5*g['s5']+4*g['s4']+3*g['s3']+2*g['s2']+g['s1'])/n:.2f}")
ri = grp['인텐시브']['repurchase_badge']/600; rs = grp['수딩']['repurchase_badge']/600
print(f"수딩/인텐시브 재구매배지 배수: {rs/ri:.2f}배")
si = grp['인텐시브']['season_summer']/600; ss = grp['수딩']['season_summer']/600
print(f"여름 언급 비율 수딩/인텐시브: {ss/si:.2f}배")
for r in s300:
    n = 300
    print(f"  {r['sku']}: 재구매배지 {int(r['repurchase_badge'])/n*100:.1f}%, 계절 {int(r['kw_season'])/n*100:.1f}%, 겨울 {r['season_winter']} 여름 {r['season_summer']}")

print("\n## D. 객단가 기준값(올리브영 정가, 2026-10-30)")
print("수딩 크림 80ml 30,000 + 인텐시브 크림 80ml 32,000 = 62,000원 (단품 듀오)")
print("수딩 크림 80+50 기획 38,000 + 인텐시브 크림 80+50 기획 40,000 = 78,000원 (기획 듀오)")
print(f"듀오 단품 합 vs 단품 평균(31,000): {62000/31000:.1f}배")
