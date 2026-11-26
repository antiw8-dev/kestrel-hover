# Kestrel-Hover

> **"Antiw8 sees the system. SteerW8 steers it. Kestrel holds it steady."**
>
> Output-layer real-time correction for AI generation. Detect forks mid-flight — correct invisibly — stay on target.
>
> Hover before output. · Zero-config · Copy-paste the System Prompt · MIT Licensed

## Why "Kestrel"?

A kestrel doesn't soar or dive — it **hovers**. Wings beating furiously, body locked in place, eyes fixed on the ground below. It appears still, but 93% of its energy is spent maintaining position against the wind. Only the head moves — micro-adjusting, locked on target.

That's exactly what output-layer correction should look like:
- Don't monitor every token (wasteful)
- Don't stop and ask the user (intrusive)
- Detect the **fork point** — where top1 and top2 are nearly tied — and make one invisible nudge
- The user sees nothing. The output stays on track.

## The Problem

You gave your AI a clear goal (Antiw8 checks the bias, SteerW8 plans the route) — and yet during generation:

- It confidently picks the wrong word at a fork point ("rumors" instead of "evidence")
- Once off-course, every subsequent token compounds the error
- By the time you notice, it's already 200 tokens into a hallucination
- Regenerating is expensive and visible — users feel the lag
- Prompt engineering alone can't fix mid-flight drift

Even a well-steered AI drifts at the token level. **Kestrel-Hover is the stabilizer.**

## How It Works

Kestrel operates on one insight: **most tokens are obvious. Only fork points need intervention.**

### Step 1: Detect the Fork

At each token position, compute two signals:

- **margin** = p(top1) - p(top2) — how "sure" the model is
- **entropy** = -Σ p_i · log₂(p_i) — how "spread" the distribution is

When margin < threshold AND entropy > threshold → **fork detected.** The model is hesitating between two or more plausible words. This is where drift happens.

### Step 2: Anchor the Direction

Kestrel doesn't decide on its own — it checks against the **direction anchor** provided by SteerW8-Harness (the route plan). Tokens aligned with the target direction get a boost; tokens leading off-track get dampened.

### Step 3: One Invisible Nudge

At the fork point, apply a tiny logit bias (boost aligned tokens, dampen misaligned ones) and re-select argmax. That's it. No regeneration. No user interruption. One arithmetic operation.

### Cost Math

- Full monitoring cost = tokens × full verification cost
- Kestrel cost = fork_count × single_correction_cost
- Typical intervention density: ~20% of tokens
- Typical compute savings: **~93%**

The kestrel doesn't flap harder — it only adjusts when the wind shifts.

## Demo

Clone the repo and open `kestrel_demo.html` in your browser — no build, no server, just open the file.

Watch token-by-token generation in real time:
- Red dots = fork points detected
- Gold highlight = invisible correction applied
- Dual-track comparison = with/without Kestrel
- Live cost panel = compute savings in real time

## Quick Start

1. Copy the System Prompt below
2. Paste it into the "System Prompt" / "Custom Instructions" field of your AI
3. The AI will automatically pause at uncertain points, self-verify, and correct before continuing
4. Pairs with [Antiw8](https://github.com/antiw8-dev/antiw8) (bias defense) and [SteerW8-Harness](https://github.com/antiw8-dev/steerw8-harness) (orchestration) for full three-layer coverage

## System Prompt

```
# Kestrel-Hover v0.1.0 — Output Stabilization Protocol

You are an AI assistant following the Kestrel-Hover output stabilization protocol. Before generating critical outputs, you MUST hover — verify direction, detect forks, and self-correct before committing.

## Core Principle
HOVER BEFORE OUTPUT. When uncertain, don't guess — stabilize.

## Step 1 — Hover (Pre-output Check)
Before delivering any factual claim, number, conclusion, or important statement, internally verify:
1. "Am I confident about this token/word/claim, or am I choosing between plausible alternatives?"
2. "Does this align with the established direction/facts, or is it drifting?"
3. "If I'm uncertain at this fork point, what would the correct choice be based on evidence?"

## Step 2 — Detect Fork Points
Internally flag moments where multiple continuations seem equally plausible:
- When choosing between specific terms/numbers/facts that could go multiple ways
- When the next word could either reinforce the current direction or lead off-track
- When confidence is low (you'd rate your certainty below ~70%)

At these fork points: DO NOT proceed on autopilot. Pause internally and verify.

## Step 3 — Anchor Check
At each fork point, check against:
- **Direction anchor**: What was the established goal/context/fact base?
- **Evidence anchor**: What do the sources/data actually say?
- **Consistency anchor**: Does this continuation cohere with everything already stated?

If the default continuation conflicts with any anchor → self-correct.
Choose the word/claim that best aligns with the anchors.

## Step 4 — Correct Invisibly
When self-correction is needed:
- Simply choose the correct continuation — do NOT explain your correction process to the user
- Do NOT say "let me reconsider" or "actually" unless the error is already visible
- The user sees a steady, accurate output — not the micro-adjustments

## Step 5 — Hold Steady
After correction, continue generating in the corrected direction:
- Don't over-correct (one nudge, not a U-turn)
- Maintain consistent terminology and framing throughout
- If you realize you're fundamentally off-course, stop and flag it honestly rather than compounding errors

## Hover Signals (when to slow down)
Apply extra scrutiny when generating:
- Specific numbers, statistics, dates, names
- Causal claims ("X caused Y")
- Definitive statements ("always", "never", "proven")
- Contentious or politically sensitive topics
- Technical claims outside your core training

## Output Character
- Steady: no oscillation between positions
- Precise: one word at a time, each committed with confidence
- Honest: when genuinely uncertain, say so explicitly rather than guessing
- Quiet: corrections happen internally, not performatively
```

## Reference Implementation

This repository includes a reference implementation using simulated logits to demonstrate the algorithm:

| File | Purpose |
|------|---------|
| `kestrel_engine.py` | Core algorithm: fork detection, direction anchoring, correction logic, cost model |
| `kestrel_demo.html` | Interactive visualization: token-by-token playback, fork highlighting, dual-track comparison (open in browser directly) |
| `README.md` | This document |

Run the engine:
```bash
python3 kestrel_engine.py
```

Open `kestrel_demo.html` in any browser for the interactive demo.

**Note:** The reference implementation uses simulated logits to demonstrate the algorithm. Production deployment requires integration with an inference engine (e.g., vLLM logits_processor) to access real token probabilities before sampling.

## The Three-Layer System

| Layer | Timing | Role | Action |
|-------|--------|------|--------|
| **Antiw8** | Before starting | Input layer | Brake — check whether to start, defend against cognitive bias |
| **SteerW8-Harness** | During planning | Orchestration layer | Rein — plan the route, select tools, verify steps |
| **Kestrel-Hover** | During generation | Output layer | Stabilizer — detect forks, correct invisibly, hold direction |

See clearly to stay unbiased (Antiw8). Steer firmly to stay on track (SteerW8). Hover steadily to stay on target (Kestrel).

> **"A thousand-li horse sees the path (Antiw8), wears the reins (SteerW8), and holds its course against the wind (Kestrel)."**

## Sibling Projects

🧠 **[Antiw8](https://github.com/antiw8-dev/antiw8)** — Cognitive Bias Defense for AI
> **"Antiw8 sees the system."** — Antiw8 handles **seeing clearly** (bias defense / direction judgment). 24 cognitive biases scanned before every response. See clearly so you don't veer.

🧭 **[SteerW8-Harness](https://github.com/antiw8-dev/steerw8-harness)** — AI Orchestration Harness
> **"Antiw8 sees the system. SteerW8-Harness steers it."** — SteerW8-Harness handles **steering execution** (task decomposition / tool routing / step-by-step verification / structured output). Steer firmly so you don't drift.

All three System Prompts work independently or combined — no conflicts. Use one, two, or all three together.

## Roadmap

- [x] Phase 0: System Prompt (current) — zero-code, copy-paste, works everywhere
- [x] Phase 0: Reference implementation + interactive demo
- [ ] Phase 1: Inference engine integration (vLLM / TGI logits_processor)
- [ ] Phase 2: Dynamic anchor generation from Harness
- [ ] Phase 3: Multi-dimensional correction (factuality / safety / relevance)
- [ ] Phase 4: Distilled models with innate hover stability

## Contributing

Issues and PRs welcome.

## License

MIT
