# Founder Implementation Principles v1.0

> Founder-ratified 2026-07-21. **These are founder operating rules, not runtime rules.**
> They govern how the founder personally runs implementation sessions — the third
> governance layer:
>
> | Layer | Governs | Document |
> |---|---|---|
> | Kernel | the system | `spec/PAEOS-4-v1.1.md` |
> | Constitutional Execution Rules (CER) | the runtime + its agents | `operations/ENGINEERING_LIFECYCLE.md` |
> | **Founder Implementation Principles** | **the founder** | this document |
>
> The runtime cannot enforce these on the founder (parchment clause, H2 — enforcement
> against the sovereign is convention, not prevention). This document *is* that convention,
> written down so it is not lost to conversation (A2). Discipline the founder keeps here is
> what keeps the constitution's guarantees real in practice.

## The seven principles

### FP-1 — One roadmap task per session
Never carry more than **one roadmap task to completion (merge) per session.** You MAY
dispatch parallel *generation* (the backlog's parallel tracks), but you personally shepherd
**one** task through integration at a time.
*Why:* keeps every session's diff reviewable, keeps failures unentangled, and keeps the repo
releasable after each. This is the founder-behavior analog of **K8** (single-threaded
integration): coherence is the property that fragments under parallelism — including the
founder's own attention.

### FP-2 — Every merged task leaves the repository releasable
After any merge, the trunk MUST be in a **releasable state** — conformance green, nothing
half-integrated, no broken build. If a task cannot land releasable, it is not done; split it
or file the shortfall as Debt (CER-3), do not merge a broken trunk.
*Why:* prevents big-bang integration and silent debt accumulation. Grounding: L16 promotion +
the conformance suite (§12.4); trunk-always-green is the deployability invariant a solo
founder cannot afford to lose.

### FP-3 — Every implementation ends with the Constitutional Review
No task closes without the L17 Constitutional Review (the six questions: weaknesses,
invalidated assumptions, what got stronger, proposals created, debt recorded, strategy
change).
*Why:* this is your personal enforcement of **CER-4**. The runtime produces the review; you
confirm it exists before you consider the task done.

### FP-4 — Every implementation produces passing evidence
"Done" means **passing evidence in the store**, never assertion. No merge on "it should
work" — only on live, signed, independent evidence satisfying the task's evidence spec.
*Why:* your enforcement of **K1** (evidence-gated promotion) and L13. Verification is the
scarce resource; assertion is not evidence.

### FP-5 — Every implementation is independently reviewed
Every task passes an **independent audit by a different model family** than the builder
before you merge (L14 / A-08). You do not merge builder-self-approved work.
*Why:* your enforcement of **I3/A-08** decorrelation. Same-family (or self-) review is
verification theater; this is the one check whose skipping is invisible until it's expensive.

### FP-6 — Every improvement proposal is logged
Every improvement you or the runtime discovers becomes a `proposals/PAEOS-IP-NNNN.md` — never
a silent change, never left in the chat.
*Why:* your enforcement of **CER-2**. The founder is the only one who can ratify a proposal,
so the founder is the one who must ensure it's logged and reaches the decision queue.

### FP-7 — No architecture changes during roadmap execution without founder ratification
While executing the roadmap, the kernel, lifecycle, authority, invariants, and constitutional
law do **not** change except by an explicit **founder-ratified amendment**. A discovered
improvement is logged (FP-6) and deferred; it does not divert the current task.
*Why:* your enforcement of **CER-5 / §14.5**. This is the discipline that lets you think
freely about improvements (FP-6) without destabilizing implementation — recommend now,
ratify deliberately, never mid-flight.

## Session ritual (operationalizes the seven)

**Open a session:**
- [ ] Pick **exactly one** roadmap task whose dependencies are all integrated (FP-1).
- [ ] Confirm the trunk is currently releasable (FP-2) — you're starting from green.
- [ ] Confirm the task's classification / ceremony depth (which lifecycle states apply).

**During (the founder acts only through the ABI — never edits work products directly):**
- [ ] Dispatch per the lifecycle; resolve gates and Decisions as they escalate.
- [ ] Log any discovered improvement as a Proposal (FP-6); log any deliberate compromise as
      Debt (CER-3). Do not act on architecture changes (FP-7).

**Close a session (merge only when ALL hold):**
- [ ] Passing evidence in the store (FP-4).
- [ ] Independent audit clean, different model family (FP-5).
- [ ] Constitutional Review written (FP-3).
- [ ] Proposals / Debt logged (FP-6).
- [ ] Repository is releasable after the merge (FP-2).
- [ ] Exactly one task completed this session (FP-1).

If any box is unchecked, **do not merge.** Stop, or file the gap as Debt, and resume next
session from green.

## Relationship to the rest of the corpus

FP-3..FP-7 are the founder's personal enforcement of rules the runtime already carries (CER-4,
K1, A-08, CER-2, CER-5). **FP-1 and FP-2 are the genuinely new founder discipline** — session
scope and trunk-releasability — which no runtime rule imposes because they are about the
founder's own cadence and risk tolerance, not the system's mechanics. Together they are the
operating rhythm that keeps a solo founder's implementation disciplined, reviewable, and always
one green step at a time.

*Version 1.0. Amendable by the founder (these are the founder's own rules); changes are
recorded here, append-only in spirit like the rest of the corpus.*
