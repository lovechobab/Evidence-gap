"""논문의 연구 설계 → 근거 수준(1~5) 분류.

LLM을 쓰지 않는 규칙 기반이라 결과가 항상 같고, 발표에서 "왜 이 등급인지" 설명하기 쉽다.
1) PubMed PublicationType 태그  2) 제목/초록 키워드  순서로 판단.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .pubmed import Paper


@dataclass(frozen=True)
class Level:
    score: float
    label: str
    emoji: str


LEVELS = {
    "meta":     Level(5, "메타분석·체계적 문헌고찰", "🟢"),
    # 관찰연구를 모은 메타분석은 아무리 많아도 '연관성'까지만 보여준다 → 인과 주장 근거로는 3.5
    "meta_obs": Level(3.5, "관찰연구 메타분석", "🟡"),
    "rct":      Level(4, "무작위 대조시험(RCT)", "🟢"),
    "cohort":   Level(3, "코호트·환자-대조군 (관찰연구)", "🟡"),
    "cross":    Level(2, "단면연구·증례보고", "🟠"),
    "preclin":  Level(1, "동물·세포 실험", "🔴"),
    "review":   Level(1, "서술적 리뷰·의견", "⚪"),
    "unknown":  Level(2, "설계 불명확", "⚪"),
}

_PUBTYPE_RULES = [
    ({"Meta-Analysis", "Systematic Review"}, "meta"),
    ({"Randomized Controlled Trial"}, "rct"),
    ({"Observational Study", "Multicenter Study"}, "cohort"),
    ({"Case Reports"}, "cross"),
    ({"Review", "Editorial", "Comment", "Letter"}, "review"),
]

_KEYWORD_RULES = [
    (r"meta-analys|systematic review", "meta"),
    (r"randomi[sz]ed|placebo-controlled", "rct"),
    (r"cohort|case-control|prospective|longitudinal|follow-up", "cohort"),
    (r"cross-sectional|case report|survey", "cross"),
    (r"\b(mice|mouse|rats?|murine|in vitro|cell line|zebrafish)\b", "preclin"),
]


def _meta_level(text: str) -> Level:
    observational = re.search(r"cohort|observational|case-control|prospective", text)
    randomized = re.search(r"randomi[sz]ed|\brcts?\b", text)
    return LEVELS["meta_obs"] if observational and not randomized else LEVELS["meta"]


def classify(paper: Paper) -> Level:
    types = set(paper.pub_types)
    text = f"{paper.title} {paper.abstract}".lower()
    for tags, key in _PUBTYPE_RULES[:4]:      # 강한 설계 태그 우선
        if types & tags:
            return _meta_level(text) if key == "meta" else LEVELS[key]
    for pattern, key in _KEYWORD_RULES:
        if re.search(pattern, text):
            return _meta_level(text) if key == "meta" else LEVELS[key]
    if types & _PUBTYPE_RULES[4][0]:
        return LEVELS["review"]
    return LEVELS["unknown"]
