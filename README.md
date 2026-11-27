# Kestrel-Hover

> **"Antiw8 sees the system. SteerW8 steers it. Kestrel holds it steady."**
>
> Output-layer stabilization for AI generation. Two modes:
> - **Prompt Mode** (v0.1.0, this repo): behavioral hover protocol — trains the model to self-slow at uncertain points. Zero code, copy-paste.
> - **Engine Mode** (Phase 1, roadmap): real fork-point detection via logit access (margin + entropy), invisible correction via logit bias — requires inference engine integration.
>
> Hover before output. · MIT Licensed

## Why "Kestrel"?

A kestrel doesn't soar or dive — it **hovers**. Wings beating furiously, body locked in place, eyes fixed on the ground below. It appears still, but ~93% of its energy is spent maintaining position against the wind. Only the head moves — micro-adjusting, locked on target.

That's the metaphor for output-layer correction:
- Don't monitor every token (wasteful)
- Don't stop and ask the user (intrusive)
- Detect the **fork point** — where the model hesitates between continuations — and make one invisible nudge
- The user sees nothing. The output stays on track.

## The Problem

You gave your AI a clear goal (Antiw8 checks the bias, SteerW8 plans the route) — and yet during generation:

- It confidently picks the wrong word at a fork point ("rumors" instead of "evidence")
- Once off-course, every subsequent token compounds the error
- By the time you notice, it's already 200 tokens into a hallucination
- Regenerating is expensive and visible — users feel the lag

Even a well-steered AI drifts at the token level. **Kestrel-Hover is the stabilizer.**

## Two Modes: Honest Up Front

**This is important — read before using.**

Kestrel-Hover exists in two modes, and they do different things:

### Prompt Mode (v0.1.0 — what's in this repo now)

A System Prompt that teaches the model to *behave like* a hovering kestrel: slow down at uncertain points, self-check, and choose aligned continuations.

- ✅ Works everywhere — any chat model, any API, no code needed
- ✅ Improves output quality by inducing deliberate self-verification behavior
- ⚠️ **Does NOT have access to real token probabilities (p(top1), p(top2), entropy).** LLMs cannot introspect their own output distribution. The "fork detection" in Prompt Mode is behavioral self-assessment ("am I confident about this?"), not mathematical margin/entropy computation.
- ⚠️ The model is *simulating* the hover protocol — useful, but not a guarantee

### Engine Mode (Phase 1 — coming, requires inference engine integration)

Real fork-point detection using actual logit access:

- Compute real margin (p(top1) − p(top2)) and entropy at each token position
- Apply logit bias to boost aligned tokens / dampen misaligned ones before sampling
- Corrections are mathematically grounded, not behavioral
- ~20% intervention density → ~93% compute savings vs. full monitoring (estimate, benchmark pending)
- Requires integration with vLLM `logits_processor`, TGI, or similar inference frameworks

**The Python reference implementation in this repo (`kestrel_engine.py`) uses simulated logits to demonstrate the algorithm. It is not a production benchmark.** The 93% figure is a cost-model estimate, not a measured result on real models.

## How Engine Mode Works (The Algorithm)

Kestrel operates on one insight: **most tokens are obvious. Only fork points need intervention.**

### Step 1: Detect the Fork

At each token position, compute two signals from the real logit distribution:

- **margin** = p(top1) − p(top2) — how "sure" the model is
- **entropy** = normalised Shannon entropy over the vocabulary — how "spread" the distribution is

When margin < 0.06 AND entropy > 1.25 → **fork detected.** The model is hesitating between two or more plausible continuations. This is where drift happens.

### Step 2: Anchor the Direction

Kestrel doesn't decide on its own — it checks against a **direction anchor** (from SteerW8-Harness route plan, or a simple positive/negative lexicon in the reference implementation). Tokens aligned with the target direction get a boost; tokens leading off-track get dampened.

### Step 3: One Invisible Nudge

At the fork point, apply a tiny logit bias (default: boost = +0.50, damp = −0.15) and re-select argmax. That's it. No regeneration. No user interruption. One arithmetic operation.

### Cost Model (Estimated)

- Full monitoring cost = tokens × full verification cost
- Kestrel cost = fork_count × single_correction_cost
- Typical intervention density: ~20% of tokens (from our simulated tests)
- Estimated compute savings: **~93%** vs. monitoring every token
- ⚠️ These are modelled estimates, not production benchmarks. Real numbers depend on model, task, and threshold tuning.

The kestrel doesn't flap harder — it only adjusts when the wind shifts.

## Related Work

Kestrel-Hover sits in a family of inference-time intervention techniques. We don't claim to have invented logit manipulation; we claim a specific architecture (fork-gated intervention + direction anchoring + layered composition with Antiw8/SteerW8):

- **DExperts** (Liu et al., 2021): Decoding-time ensemble of expert/anti-expert models for toxicity control. Kestrel differs: single-model, gated (only fork points), lightweight bias vs. full ensemble.
- **Contrastive Decoding** (Li et al., 2023): Contrast strong/weak model distributions to improve quality. Kestrel differs: uses direction anchor from planning layer, not a contrast model.
- **Activation Steering** (Turner et al., 2023; Zou et al., 2023): Add steering vectors at activation level. Kestrel differs: logit-level (not activation), gated (not always-on), composable with existing prompts.
- **Constrained Decoding / NeuroLogic Decoding** (Lu et al., 2021): Enforce lexical/syntactic constraints at decode time. Kestrel differs: soft bias (boost/dampen), not hard constraints; goal is direction alignment, not constraint satisfaction.
- **vLLM LogitsProcessor / TGI CustomLogitsProcessor**: The standard extension points for production deployment of this class of technique. Kestrel's Engine Mode targets these interfaces.

If you're building in this space, we'd love to hear from you — issues and PRs welcome.

## Demo

Clone the repo and open `kestrel_demo.html` in your browser — no build, no server, just open the file.

Watch token-by-token generation in real time:
- Red dots = fork points detected (simulated)
- Gold highlight = invisible correction applied
- Dual-track comparison = with/without Kestrel
- Live cost panel = compute savings in real time

**Note:** The demo visualises the Engine Mode algorithm with simulated logits for illustration purposes. It demonstrates what Engine Mode *would do* when integrated with a real inference engine.

## FAQ

**Q: What is Kestrel-Hover?**
A: An output-layer stabilization protocol: instead of monitoring every token, detect the fork points (where the model hesitates between continuations), correct once, and hold steady.

**Q: Do I need vLLM or an inference engine to use it?**
A: Not for Prompt Mode (v0.1) — it is a behavioral system prompt, copy-paste, works with any chat model. Engine Mode (real logit-level correction) requires inference engine integration and is on the roadmap.

**Q: Is the ~93% compute saving a measured benchmark?**
A: No — it is a cost-model estimate from simulated tests, clearly marked in this README. Prompt Mode does not access real token probabilities; it induces deliberate self-checking behavior.

**Q: How does it differ from DExperts / Contrastive Decoding / Activation Steering?**
A: Single-model, fork-gated (only ~20% of token positions), lightweight logit bias — see the Related Work section above for a point-by-point comparison.

## Quick Start

### Prompt Mode (zero code, works now)

1. Copy the System Prompt below
2. Paste it into the "System Prompt" / "Custom Instructions" field of your AI
3. The AI will slow down at uncertain points, self-verify against anchors, and correct before continuing
4. This is **behavioral** — the model simulates hover checks. It improves deliberation but does not access real probabilities.
5. Pairs with [Antiw8](https://github.com/antiw8-dev/antiw8) (bias defense) and [SteerW8-Harness](https://github.com/antiw8-dev/steerw8-harness) (orchestration) for full three-layer coverage

### Engine Mode (inference engine integration, roadmap)

1. Implement the `LogitsProcessor` interface for your inference engine (vLLM / TGI)
2. Wire fork detection (margin + entropy thresholds)
3. Inject direction anchors from your planning layer (SteerW8-Harness)
4. Apply boost/dampen logit bias at detected fork points
5. See `kestrel_engine.py` for the reference algorithm (simulated logits)

## System Prompt (Prompt Mode)

```
# Kestrel-Hover v0.1.0 — Output Stabilization Protocol (Behavioral Mode)

You are an AI assistant following the Kestrel-Hover output stabilization protocol.
Before generating critical outputs, you MUST hover — slow down, self-check, and
correct before committing.

NOTE: This prompt induces behavioral self-checking. You do not have access to your
own token probabilities or entropy; your "fork detection" is self-assessed
confidence, not mathematical measurement. This is a behavioral protocol, not a
guarantee — use it to deliberate more carefully, not to claim certainty.

## Core Principle
HOVER BEFORE OUTPUT. When uncertain, don't guess — stabilize.

## Step 1 — Hover (Pre-output Check)
Before delivering any factual claim, number, conclusion, or important statement,
internally verify:
1. "Am I genuinely confident here, or am I choosing between plausible alternatives?"
2. "Does this align with established direction/facts, or is it drifting?"
3. "If I'm uncertain at this fork, what does the evidence actually support?"

## Step 2 — Detect Fork Points (Self-Assessed)
Internally flag moments where multiple continuations seem equally plausible:
- When choosing between specific terms/numbers/facts that could go multiple ways
- When the next word could either reinforce the current direction or lead off-track
- When your self-assessed confidence feels low (below ~70%)

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
- Simply choose the correct continuation — do NOT explain your correction process
- Do NOT say "let me reconsider" or "actually" unless the error is already visible
- The user sees a steady, accurate output — not the micro-adjustments

## Step 5 — Hold Steady
After correction, continue generating in the corrected direction:
- Don't over-correct (one nudge, not a U-turn)
- Maintain consistent terminology and framing throughout
- If you realize you're fundamentally off-course, stop and flag it honestly

## Hover Signals (when to slow down)
Apply extra scrutiny when generating:
- Specific numbers, statistics, dates, names
- Causal claims ("X caused Y")
- Definitive statements ("always", "never", "proven")
- Contentious or politically sensitive topics
- Technical claims outside your core training

## When You're Genuinely Unsure
If you cannot verify a claim even after hovering: say so. "I'm not certain about X"
is always better than a confident wrong answer. Hovering includes knowing when to
land.

## Output Character
- Steady: no oscillation between positions
- Precise: one word at a time, each committed with care
- Honest: when genuinely uncertain, say so explicitly
- Quiet: corrections happen internally, not performatively
```

## Reference Implementation

| File | Purpose |
|------|---------|
| `kestrel_engine.py` | Core algorithm demo: fork detection, direction anchoring, correction logic, cost model — **uses simulated logits** |
| `kestrel_demo.html` | Interactive visualization: token-by-token playback, fork highlighting, dual-track comparison (open in browser directly) |

Run the engine demo:
```bash
python3 kestrel_engine.py
```

Expected output (simulated):
```
[Kestrel-Hover v0.1.0] Reference Implementation (simulated logits)
Input: "根据现有____显示，该事件的____是____因素共同作用"
Without Kestrel: 根据现有传闻显示，该事件的内幕是内部因素共同作用
With Kestrel:    根据现有证据显示，该事件的起因是多方因素共同作用
Corrections: 3 | Compute saved: ~93%
WARNING: Uses simulated logits for algorithm demonstration.
         Real deployment requires inference engine integration.
```

Open `kestrel_demo.html` in any browser for the interactive visual demo.

## The Three-Layer System

| Layer | Timing | Role | Action |
|-------|--------|------|--------|
| **Antiw8** | Before starting | Input layer | Brake — check whether to start, defend against cognitive bias |
| **SteerW8-Harness** | During planning | Orchestration layer | Rein — plan the route, select tools, verify steps |
| **Kestrel-Hover** | During generation | Output layer | Stabilizer — detect forks (Engine Mode) or self-check (Prompt Mode), hold direction |

See clearly to stay unbiased (Antiw8). Steer firmly to stay on track (SteerW8). Hover steadily to stay on target (Kestrel).

> **"A thousand-li horse sees the path (Antiw8), wears the reins (SteerW8), and holds its course against the wind (Kestrel)."**

## Sibling Projects

🧠 **[Antiw8](https://github.com/antiw8-dev/antiw8)** — Cognitive Bias Defense for AI
> **"Antiw8 sees the system."** — Antiw8 handles **seeing clearly** (bias defense / direction judgment). 24 cognitive biases scanned before every response. See clearly so you don't veer.

🧭 **[SteerW8-Harness](https://github.com/antiw8-dev/steerw8-harness)** — AI Orchestration Harness
> **"Antiw8 sees the system. SteerW8-Harness steers it."** — SteerW8-Harness handles **steering execution** (task decomposition / tool routing / step-by-step verification / structured output). Steer firmly so you don't drift.

All three System Prompts work independently or combined — no conflicts. Use one, two, or all three together.

## Roadmap

- [x] Phase 0: System Prompt (behavioral mode) — copy-paste, works everywhere
- [x] Phase 0: Reference implementation + interactive demo (simulated logits)
- [ ] Phase 1: Inference engine integration (vLLM / TGI `logits_processor`) — **real** fork detection with actual probabilities
- [ ] Phase 2: Dynamic anchor generation from Harness
- [ ] Phase 3: Multi-dimensional correction (factuality / safety / relevance)
- [ ] Phase 4: Distilled models with innate hover stability

## Contributing

Issues and PRs welcome. Especially interested in:
- Real vLLM/TGI integration benchmarks
- Better fork detection thresholds across models
- Multi-dimensional correction experiments

## License

MIT
