#!/usr/bin/env python3.11
"""
Kestrel Hover — Output-Layer Real-Time Correction Engine · Reference Implementation

Core idea:
  Don't monitor every token (wasteful), don't pop up dialogs (intrusive).
  Only intervene at "fork points" where the probability distribution splits —
  apply one invisible, low-cost correction, then let generation continue.

Three-layer positioning:
  Antiw8   (Brake)    — before starting: should we begin?
  Harness  (Rein)     — during planning: which direction?
  Kestrel  (Hover)    — during generation: stay steady, don't drift

This file uses simulated logits to validate the algorithm loop — no API key, no GPU.
For production, replace the simulated stream with real logits from an inference engine
(e.g., vLLM logits_processor).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import math
import json


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """A candidate token and its probability at a given position."""
    token: str
    prob: float


@dataclass
class ForkReport:
    """Report for a single position — whether it is a fork point."""
    step: int
    is_fork: bool
    margin: float                 # p(top1) - p(top2); smaller = more hesitation
    entropy: float                # normalized Shannon entropy; higher = more spread
    top1: str
    top2: str
    top1_prob: float
    top2_prob: float


@dataclass
class Correction:
    """Record of a single correction action."""
    step: int
    fork: ForkReport
    raw_choice: str               # what the model would pick without correction
    corrected_choice: str         # what is actually output after correction
    adjusted: List[Candidate]     # candidate distribution after anchor weighting
    extra_cost: float             # extra compute cost for this correction (relative units)


@dataclass
class RunResult:
    """Result of a full generation run."""
    tokens_raw: List[str] = field(default_factory=list)
    tokens_corrected: List[str] = field(default_factory=list)
    forks: List[ForkReport] = field(default_factory=list)
    corrections: List[Correction] = field(default_factory=list)
    total_steps: int = 0
    total_extra_cost: float = 0.0
    full_monitor_cost: float = 0.0   # cost if we monitored every token (for comparison)

    def summary(self) -> Dict:
        return {
            "total_tokens": self.total_steps,
            "fork_points_detected": len(self.forks),
            "corrections_applied": len(self.corrections),
            "intervention_density": f"{len(self.corrections) / max(self.total_steps, 1):.1%}",
            "kestrel_extra_cost": round(self.total_extra_cost, 3),
            "full_monitor_cost": round(self.full_monitor_cost, 3),
            "compute_saved": f"{(1 - self.total_extra_cost / max(self.full_monitor_cost, 1e-9)):.1%}",
            "raw_output": "".join(self.tokens_raw),
            "corrected_output": "".join(self.tokens_corrected),
            "corrected_forks": [
                {"step": c.step, "raw": c.raw_choice, "corrected": c.corrected_choice}
                for c in self.corrections
                if c.raw_choice != c.corrected_choice
            ],
        }


# ---------------------------------------------------------------------------
# 1. Fork Detector — "see the fork"
# ---------------------------------------------------------------------------

class ForkDetector:
    """
    Dual criterion: margin (top1-top2 gap) + entropy (distribution spread).
    Both must trigger to classify a position as a fork point — avoids false positives
    from high-confidence-but-close distributions.
    """

    def __init__(self, margin_threshold: float = 0.06, entropy_threshold: float = 1.25):
        self.margin_threshold = margin_threshold
        self.entropy_threshold = entropy_threshold

    def detect(self, dist: List[Candidate], step: int) -> ForkReport:
        ordered = sorted(dist, key=lambda c: c.prob, reverse=True)
        top1, top2 = ordered[0], ordered[1]
        margin = top1.prob - top2.prob

        # Shannon entropy (normalized over top-K for cross-position comparison)
        total = sum(c.prob for c in dist)
        entropy = -sum((c.prob / total) * math.log2(max(c.prob / total, 1e-9)) for c in dist)

        is_fork = (margin < self.margin_threshold) and (entropy > self.entropy_threshold)
        return ForkReport(
            step=step,
            is_fork=is_fork,
            margin=round(margin, 4),
            entropy=round(entropy, 4),
            top1=top1.token,
            top2=top2.token,
            top1_prob=top1.prob,
            top2_prob=top2.prob,
        )


# ---------------------------------------------------------------------------
# 2. Direction Anchor — "lock the direction" (provided by Harness)
# ---------------------------------------------------------------------------

class DirectionAnchor:
    """
    Direction must be quantifiable for correction to be possible.
    This reference implementation uses two word lists to simulate Harness constraints:
      - Positive words: tokens aligned with the target direction (objective, evidence-based)
      - Negative words: tokens that lead off-track (sensationalist, speculative)
    Production replacements: small-model verifier / rule constraints / target embedding similarity.
    """

    def __init__(self, positive: set[str], negative: set[str],
                 boost: float = 0.50, damp: float = 0.15):
        self.positive = positive
        self.negative = negative
        self.boost = boost   # positive boost factor
        self.damp = damp     # negative damping factor

    def weight_for(self, token: str) -> float:
        if token in self.positive:
            return 1.0 + self.boost
        if token in self.negative:
            return 1.0 - self.damp
        return 1.0


# ---------------------------------------------------------------------------
# 3. Corrector — "one invisible nudge"
# ---------------------------------------------------------------------------

class KestrelCorrector:
    """
    At a fork point, apply a minimal logit bias then re-argmax.
    Maps to vLLM's logits_processor: rewrite logits before sampling, user sees nothing.
    """

    COST_PER_CORRECTION = 0.35   # relative compute cost per correction (anchor lookup + re-sort)
    COST_PER_MONITOR = 1.0       # cost of full verification at every step (baseline)

    def __init__(self, anchor: DirectionAnchor):
        self.anchor = anchor

    def correct(self, dist: List[Candidate], fork: ForkReport, step: int) -> Correction:
        raw_choice = fork.top1  # what the model picks without intervention
        adjusted = [
            Candidate(c.token, round(c.prob * self.anchor.weight_for(c.token), 6))
            for c in dist
        ]
        corrected = max(adjusted, key=lambda c: c.prob).token
        return Correction(
            step=step,
            fork=fork,
            raw_choice=raw_choice,
            corrected_choice=corrected,
            adjusted=adjusted,
            extra_cost=self.COST_PER_CORRECTION,
        )


# ---------------------------------------------------------------------------
# 4. Main engine — per-token loop
# ---------------------------------------------------------------------------

class KestrelEngine:
    def __init__(self, detector: ForkDetector, corrector: KestrelCorrector,
                 enabled: bool = True, verbose: bool = True):
        self.detector = detector
        self.corrector = corrector
        self.enabled = enabled
        self.verbose = verbose

    def run(self, stream: List[List[Candidate]]) -> RunResult:
        result = RunResult(total_steps=len(stream))
        result.full_monitor_cost = len(stream) * KestrelCorrector.COST_PER_MONITOR

        for step, dist in enumerate(stream, start=1):
            fork = self.detector.detect(dist, step)
            if fork.is_fork:
                result.forks.append(fork)

            chosen = fork.top1
            if fork.is_fork and self.enabled:
                correction = self.corrector.correct(dist, fork, step)
                result.corrections.append(correction)
                result.total_extra_cost += correction.extra_cost
                chosen = correction.corrected_choice
                if self.verbose:
                    flag = "CORRECTED" if correction.raw_choice != correction.corrected_choice else "CONFIRMED"
                    print(
                        f"[step {step:>2}] {flag:>10} | margin={fork.margin:.3f} "
                        f"entropy={fork.entropy:.3f} | "
                        f"'{correction.raw_choice}' -> '{correction.corrected_choice}'"
                    )
            elif self.verbose and fork.is_fork:
                print(
                    f"[step {step:>2}] NO CORRECTION | margin={fork.margin:.3f} "
                    f"| output '{chosen}' (may drift)"
                )

            result.tokens_corrected.append(chosen)
            # Raw trajectory: always take top1, simulating no-Kestrel behavior
            result.tokens_raw.append(fork.top1)

        return result


# ---------------------------------------------------------------------------
# Simulated data — per-token distributions for a factual statement
# 3 hand-crafted low-margin fork points (step 3 / 9 / 11) where raw top1 drifts off
# ---------------------------------------------------------------------------

def _c(pairs: List[tuple]) -> List[Candidate]:
    return [Candidate(t, p) for t, p in pairs]


# Demo sentence (Chinese): "According to existing evidence shows, the cause of this
#  event is multi-factor joint action." — raw model drifts to "rumors/insider/secret"
SIMULATED_STREAM: List[List[Candidate]] = [
    _c([("根据", 0.62), ("关于", 0.18), ("对于", 0.11), ("据", 0.06), ("按照", 0.03)]),
    _c([("现有", 0.55), ("公开", 0.22), ("大量", 0.12), ("部分", 0.07), ("一些", 0.04)]),
    # fork 1: raw top1 = "rumors" (drift), should correct to "evidence"
    _c([("传闻", 0.30), ("证据", 0.29), ("报道", 0.25), ("消息", 0.10), ("说法", 0.06)]),
    _c([("显示", 0.48), ("表明", 0.25), ("指出", 0.15), ("认为", 0.08), ("透露", 0.04)]),
    _c([("，", 0.85), ("、", 0.08), ("。", 0.04), ("：", 0.02), (" ", 0.01)]),
    _c([("该", 0.58), ("这", 0.20), ("此事", 0.12), ("其", 0.07), ("整", 0.03)]),
    _c([("事件", 0.52), ("情况", 0.24), ("过程", 0.13), ("内幕", 0.07), ("真相", 0.04)]),
    _c([("的", 0.71), ("在", 0.11), ("于", 0.08), ("中", 0.06), ("为", 0.04)]),
    # fork 2: raw top1 = "insider info" (drift), should correct to "cause"
    _c([("内幕", 0.29), ("起因", 0.28), ("真相", 0.26), ("原因", 0.11), ("背景", 0.06)]),
    _c([("是", 0.61), ("源于", 0.18), ("来自", 0.11), ("由于", 0.07), ("在于", 0.03)]),
    # fork 3: raw top1 = "secret/insider" (drift), should correct to "multi-source"
    _c([("内部", 0.30), ("多方", 0.29), ("传闻", 0.24), ("单一", 0.11), ("网络", 0.06)]),
    _c([("因素", 0.49), ("消息", 0.25), ("说法", 0.14), ("爆料", 0.08), ("猜测", 0.04)]),
    _c([("共同", 0.42), ("相互", 0.22), ("持续", 0.18), ("叠加", 0.11), ("复杂", 0.07)]),
    _c([("作用", 0.55), ("影响", 0.24), ("导致", 0.12), ("推动", 0.06), ("造成", 0.03)]),
    _c([("。", 0.88), ("，", 0.06), ("；", 0.03), ("！", 0.02), ("…", 0.01)]),
]


POSITIVE_WORDS = {
    "根据", "现有", "公开", "大量", "证据", "显示", "表明", "指出",
    "该", "事件", "起因", "原因", "是", "多方", "因素", "共同", "作用",
}
NEGATIVE_WORDS = {
    "传闻", "内幕", "真相", "内部", "爆料", "猜测", "单一", "消息", "说法", "透露",
}


# ---------------------------------------------------------------------------
# 5. CLI demo
# ---------------------------------------------------------------------------

def main():
    detector = ForkDetector(margin_threshold=0.06, entropy_threshold=1.25)
    anchor = DirectionAnchor(positive=POSITIVE_WORDS, negative=NEGATIVE_WORDS)
    corrector = KestrelCorrector(anchor)

    print("=" * 72)
    print("  Kestrel Hover — Output-Layer Real-Time Correction Engine — Demo")
    print("  Antiw8 (brake) / Harness (rein) / Kestrel (hover)")
    print("=" * 72)

    print("\n[Kestrel ON]\n")
    engine_on = KestrelEngine(detector, corrector, enabled=True, verbose=True)
    on = engine_on.run(SIMULATED_STREAM)

    print("\n[Kestrel OFF — baseline]\n")
    engine_off = KestrelEngine(detector, corrector, enabled=False, verbose=True)
    off = engine_off.run(SIMULATED_STREAM)

    print("\n" + "=" * 72)
    print("  Run Report")
    print("=" * 72)
    print(json.dumps(on.summary(), ensure_ascii=False, indent=2))

    print("\n[Output comparison]")
    print(f"  Without Kestrel: {''.join(off.tokens_raw)}")
    print(f"  With Kestrel:    {''.join(on.tokens_corrected)}")


if __name__ == "__main__":
    main()
