"""Evidence Gap — 건강 주장의 '주장 강도 vs 실제 근거' 차이를 보여주는 Streamlit 앱.

실행:  streamlit run app.py
"""
import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit Cloud의 secrets → 환경변수 (core 모듈들이 os.getenv로 읽음)
try:
    for k, v in st.secrets.items():
        if isinstance(v, str):
            os.environ.setdefault(k, v)
except Exception:
    pass

from core import llm, pubmed
from core.claim import STRENGTH_LABELS, analyze_claim, judge_stances, suggest_rewrite
from core.evidence import classify
from core.scoring import compute_gap

st.set_page_config(page_title="Evidence Gap", page_icon="🔬", layout="wide")
EXAMPLES = json.loads((Path(__file__).parent / "data/examples.json").read_text("utf-8"))
STANCE_KO = {"supports": "✅ 지지", "contradicts": "❌ 반박", "mixed": "➖ 혼재",
             "irrelevant": "· 무관", "unknown": "? 미판정"}


@st.cache_data(ttl=3600, show_spinner=False)
def cached_search(query: str, n: int, min_year: int):
    return pubmed.search_and_fetch(query, retmax=n, min_year=min_year)


# ---------------- 사이드바 ----------------
with st.sidebar:
    st.header("⚙️ 설정")
    prov = llm.provider()
    if prov == "none":
        st.warning("데모 모드: LLM 키가 없어 예시 문장 + 규칙 기반으로만 동작합니다.")
    else:
        st.success(f"LLM: {prov}")
    n_papers = st.slider("검색할 논문 수", 5, 30, 12)
    min_year = st.slider("이 연도 이후 논문만", 1990, 2026, 2005)
    st.divider()
    st.caption("예시 문장")
    for ex in EXAMPLES:
        if st.button(ex["text"], use_container_width=True):
            st.session_state.claim = ex["text"]

# ---------------- 메인 입력 ----------------
st.title("🔬 Evidence Gap")
st.caption("건강 정보의 '말의 세기'와 '연구 근거의 세기' 사이 차이를 보여드립니다.")

claim_text = st.text_input("확인하고 싶은 건강 주장을 입력하세요",
                           key="claim", placeholder="예: 커피를 마시면 치매가 예방된다")
go = st.button("근거 확인하기", type="primary", disabled=not claim_text)

if go:
    example_query = next((e["query"] for e in EXAMPLES if e["text"] == claim_text), "")

    # 1) 주장 분석
    with st.status("분석 중...", expanded=True) as status:
        st.write("① 주장의 강도와 과장 표현을 분석하는 중")
        claim = analyze_claim(claim_text, fallback_query=example_query)
        if not claim.pubmed_query:
            st.error("데모 모드에서는 사이드바의 예시 문장만 분석할 수 있어요. LLM 키를 설정해 주세요.")
            st.stop()

        # 2) 논문 검색
        st.write(f"② PubMed 검색: `{claim.pubmed_query}`")
        try:
            papers = cached_search(claim.pubmed_query, n_papers, min_year)
        except Exception as e:
            st.error(f"PubMed 검색에 실패했어요: {e}")
            st.stop()

        # 3) 근거 수준 분류 + 지지/반박 판정
        st.write(f"③ 논문 {len(papers)}편의 연구 설계와 결과를 판정하는 중")
        stances = judge_stances(claim, papers)
        rows = []
        for p in papers:
            lv = classify(p)
            s = stances.get(p.pmid, {"stance": "unknown", "finding_ko": ""})
            rows.append({"paper": p, "level": lv.score, "lv": lv,
                         "stance": s.get("stance", "unknown"),
                         "finding": s.get("finding_ko", "")})

        # 4) Gap 계산 + 바른 문장
        result = compute_gap(claim.strength, rows)
        summary = (f"지지 {result.n_support}편, 반박 {result.n_contra}편, "
                   f"최고 근거 수준 {result.evidence_strength}/5")
        rewrite = suggest_rewrite(claim, summary)
        status.update(label="분석 완료", state="complete", expanded=False)

    # ---------------- 결과 ----------------
    c1, c2, c3 = st.columns(3)
    c1.metric("주장 강도", f"{claim.strength} / 5", STRENGTH_LABELS[claim.strength],
              delta_color="off")
    c2.metric("근거 강도", f"{result.evidence_strength} / 5", summary, delta_color="off")
    c3.metric("Evidence Gap", f"{result.gap}%", result.verdict,
              delta_color="inverse" if result.gap >= 45 else "normal")
    st.progress(result.gap / 100)

    if claim.hype_words:
        st.markdown("**과장 표현:** " + " ".join(f"`{w}`" for w in claim.hype_words))
    st.caption(claim.reasoning)

    st.info(f"**이렇게 말하는 게 정확해요**\n\n{rewrite}")

    left, right = st.columns([1, 2])
    with left:
        st.subheader("근거 피라미드")
        cnt = Counter(r["lv"].label for r in rows if r["stance"] != "irrelevant")
        order = sorted({r["lv"] for r in rows}, key=lambda l: -l.score)
        st.bar_chart(pd.DataFrame({"논문 수": [cnt.get(l.label, 0) for l in order]},
                                  index=[l.label for l in order]), horizontal=True)
    with right:
        st.subheader("찾은 논문")
        for r in sorted(rows, key=lambda r: (-r["level"], r["stance"] == "irrelevant")):
            p = r["paper"]
            with st.expander(f'{r["lv"].emoji} {STANCE_KO.get(r["stance"], r["stance"])} · '
                             f'{p.title[:90]} ({p.year})'):
                st.markdown(f'**{r["lv"].label}** · {p.journal} · [PubMed {p.pmid}]({p.url})')
                if r["finding"]:
                    st.write(r["finding"])
                st.caption(p.abstract[:700] + ("…" if len(p.abstract) > 700 else ""))

st.divider()
st.caption("⚠️ 이 도구는 연구 근거의 수준을 보여주는 교육용 서비스이며 의학적 진단·처방을 대신하지 않습니다.")
