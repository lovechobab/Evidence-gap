"""① 주장 분석 (강도·인과 표현·검색어)  ② 논문별 지지/반박 판정  ③ 바른 문장 제안.

LLM이 없을 때는 키워드 규칙으로 대신하는 데모 모드가 동작한다.
중요: LLM은 '실제로 검색된 초록'만 판단한다. 논문을 새로 만들어내지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import llm
from .pubmed import Paper

# 주장 강도 척도 (1~5)
STRENGTH_LABELS = {
    1: "가능성 제시 (~일 수도 있다)",
    2: "연관성 (~와 관련 있다)",
    3: "위험 감소/증가 (~하면 위험이 줄어든다)",
    4: "인과 단정 (~하면 예방된다/생긴다)",
    5: "효능 과장 (완치·특효·100%)",
}


@dataclass
class ClaimAnalysis:
    original: str
    exposure: str               # 원인 (예: 커피)
    outcome: str                # 결과 (예: 치매)
    claim_type: str             # association | causal | efficacy
    strength: int               # 1~5
    hype_words: list[str] = field(default_factory=list)
    pubmed_query: str = ""
    reasoning: str = ""


CLAIM_SYSTEM = """너는 건강 정보의 과장 표현을 분석하는 역학 전문가다.
입력된 한국어 건강 주장을 분석해 아래 JSON만 출력하라.
{
 "exposure": "원인/노출 (한국어)",
 "outcome": "결과/질병 (한국어)",
 "claim_type": "association | causal | efficacy",
 "strength": 1~5 정수,
 "hype_words": ["인과·과장 표현 원문 그대로"],
 "pubmed_query": "영어 PubMed 검색식 (MeSH 용어와 AND/OR 사용)",
 "reasoning": "강도 판단 이유 한 문장"
}
강도 기준: 1=가능성 제시, 2=연관성, 3=위험 감소/증가, 4=인과 단정(예방된다, 생긴다), 5=완치·특효·100% 등 효능 과장."""


def analyze_claim(text: str, fallback_query: str = "") -> ClaimAnalysis:
    if llm.provider() == "none":
        return _heuristic_claim(text, fallback_query)
    d = llm.chat_json(CLAIM_SYSTEM, text)
    return ClaimAnalysis(original=text, **{k: d.get(k) for k in (
        "exposure", "outcome", "claim_type", "strength", "hype_words",
        "pubmed_query", "reasoning")})


# ---------- 논문별 지지/반박 판정 (한 번의 호출로 일괄 처리) ----------
STANCE_SYSTEM = """너는 의학 논문 초록을 읽고 특정 주장과의 관계를 판정한다.
각 논문에 대해 JSON 배열만 출력하라:
[{"pmid": "...", "stance": "supports | contradicts | mixed | irrelevant",
  "finding_ko": "핵심 결과 한 문장 (한국어, 수치 있으면 포함)"}]
초록에 없는 내용을 추측하지 말 것. 연관성만 보였으면 그렇다고 쓸 것."""


def judge_stances(claim: ClaimAnalysis, papers: list[Paper]) -> dict[str, dict]:
    if llm.provider() == "none" or not papers:
        return {p.pmid: {"stance": "unknown", "finding_ko": ""} for p in papers}
    body = f"주장: {claim.original}\n\n" + "\n\n".join(
        f"[PMID {p.pmid}] {p.title}\n{p.abstract[:1500]}" for p in papers)
    rows = llm.chat_json(STANCE_SYSTEM, body, max_tokens=3000)
    return {str(r["pmid"]): r for r in rows}


# ---------- 바르게 고친 문장 ----------
REWRITE_SYSTEM = """건강 주장과 실제 근거 요약을 보고, 근거 수준에 맞게 정확히 고친
한국어 문장 하나를 제안하라. 일반인이 이해하기 쉽게. JSON: {"rewrite": "..."}"""


def suggest_rewrite(claim: ClaimAnalysis, evidence_summary: str) -> str:
    if llm.provider() == "none":
        return (f"{claim.exposure}와(과) {claim.outcome} 사이에 관련이 있다는 연구가 있지만, "
                f"그 원인이라고 단정할 근거는 아직 부족합니다.")
    d = llm.chat_json(REWRITE_SYSTEM,
                      f"주장: {claim.original}\n근거 요약: {evidence_summary}")
    return d["rewrite"]


# ---------- 데모 모드용 규칙 ----------
_HYPE = [
    (5, r"완치|특효|만병|100\s*%|기적|무조건"),
    (4, r"예방된다|예방한다|낫는다|고친다|치료된다|막아준다|생긴다|걸린다|유발한다"),
    (3, r"줄어든다|낮춘다|높인다|감소|증가"),
    (2, r"관련|연관|상관"),
    (1, r"수도 있|가능성"),
]


def _heuristic_claim(text: str, query: str) -> ClaimAnalysis:
    levels, words = [], []
    for level, pat in _HYPE:
        found = re.findall(pat, text)
        if found:
            words += found
            levels.append(level)
    strength = max(levels) if levels else 2
    return ClaimAnalysis(
        original=text, exposure="(원인)", outcome="(결과)",
        claim_type="efficacy" if strength == 5 else "causal" if strength == 4 else "association",
        strength=strength, hype_words=words, pubmed_query=query,
        reasoning="데모 모드: 키워드 규칙으로 판단했습니다.",
    )
