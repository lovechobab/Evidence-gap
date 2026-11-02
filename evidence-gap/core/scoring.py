"""Evidence Gap 점수 = 주장 강도 - 근거 강도.

근거 강도(1~5)는 '주장을 지지하는' 논문들로 계산한다.
 - 가장 높은 설계 수준(best)을 기본으로
 - 반박 논문 비율이 높으면 감점 (일관성)
 - 지지 논문이 2편 미만이면 감점 (재현성)
Gap(0~100) = (주장 강도 - 근거 강도) / 3, 인과 단정 + 실험 근거 없음이면 +20.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GapResult:
    claim_strength: int
    evidence_strength: float
    gap: float           # 0~100 (높을수록 과장)
    verdict: str
    n_support: int
    n_contra: int


def compute_gap(claim_strength: int, rows: list[dict]) -> GapResult:
    """rows: [{"level": int, "stance": str}, ...]"""
    relevant = [r for r in rows if r["stance"] != "irrelevant"]
    support = [r for r in relevant if r["stance"] in ("supports", "mixed", "unknown")]
    contra = [r for r in relevant if r["stance"] == "contradicts"]

    if not support:
        ev = 1.0
    else:
        ev = float(max(r["level"] for r in support))
        if len(support) < 2:
            ev -= 0.5
        if relevant:
            ev -= 1.5 * len(contra) / len(relevant)
    ev = max(1.0, min(5.0, ev))

    gap = max(0.0, claim_strength - ev) / 3 * 100
    # 핵심 규칙: 인과를 단정(강도 4 이상)했는데 지지 근거에 RCT·메타분석이 없으면 가산
    best_support = max((r["level"] for r in support), default=0)
    if claim_strength >= 4 and best_support < 4:
        gap += 20
    gap = min(100.0, gap)
    verdict = ("근거에 맞는 표현" if gap < 20 else
               "약간 과장" if gap < 40 else
               "과장됨" if gap < 65 else "심하게 과장됨")
    return GapResult(claim_strength, round(ev, 1), round(gap), verdict,
                     len(support), len(contra))
