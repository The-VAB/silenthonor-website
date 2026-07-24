---
name: roundtable
description: >-
  Structured decision-review for expensive or slow-to-reverse calls — pricing,
  launches, hires, architecture/build-vs-buy picks. Fact-checks every checkable
  claim first, then runs five advisor seats (Contrarian, First-Principles,
  Expansionist, Outsider, Executor) as genuinely independent parallel subagents
  that are blind to each other, cross-reviews their answers for blind spots, and
  returns ONE voted verdict with a concrete action + owner + revisit date — then
  appends it to ROUNDTABLE_LOG.md. Invoke when the user says "roundtable this",
  "council this", or "run the panel on this decision".
---

# The Roundtable

A decision-review process for calls that are **expensive or slow to undo**. Its
whole point is to force a real argument *before* a recommendation reaches a person,
because the biggest failure of "just ask the AI" is that it validates whatever
framing it was handed. Run the four stages below in order. Do not shortcut them.

## When to run it
Use for: pricing/monetization changes, launch or go/no-go calls, hires/role/org
decisions, architecture or build-vs-buy picks with real switching cost.
Do NOT use for small reversible things (button color, copy tweaks). If the user
triggers it on something trivial, say so and offer a normal quick answer instead —
overusing it trains people to skim the verdict.

## Stage 0 — Check the ledger first
Read `ROUNDTABLE_LOG.md` at the repo root (create it from the template at the end
if missing). If any past entry has a **Revisit by** date that has passed and
**Revisit outcome: pending**, surface it to the user in one line before starting —
an unclosed past decision may bear on this one.

## Stage 1 — Fact-check (every time, before any seat argues)
Pull every checkable claim out of the decision — numbers, dates, comparisons,
"we have X users", "this costs $Y", "competitor does Z". Verify each with the
tools available (web search, the codebase, files). Mark each: **confirmed**,
**corrected** (give the real value), or **unverifiable** (say why). Assemble this
into a short "shared ground truth" block that every seat receives.
- If the decision genuinely has no checkable claims (a pure judgment call), say so
  explicitly and skip to Stage 2. Never skip silently — "we already know the
  numbers" is the exact trap this stage exists to catch.

## Stage 2 — Five independent seats (run BLIND and in PARALLEL)
Spawn the five seats as **separate subagents in a single batch** (one message,
five `Agent` tool calls) so they run concurrently and none can see another's
answer. Give each the decision + the Stage-1 ground-truth block and nothing else.
Independence must be *structural*, not just instructed.
- For a heavyweight decision, use the `Workflow` tool instead: a parallel stage of
  five seats → a cross-review stage → a synthesis stage.
- If no parallel tooling is available, fall back to writing all five out in one
  pass without revising earlier seats — and note that independence was weaker.

Seats (fixed — never substitute one):

| Seat | Its one job |
|---|---|
| **Contrarian** | Name the single fatal flaw — the one reason this fails. Not a pros/cons list. |
| **First-Principles Thinker** | Is this even the right problem? Challenge the framing before the solution. |
| **Expansionist** | Argue the upside as hard as the Contrarian argued the downside. What if it works better than planned? |
| **Outsider** | Zero-context reaction, like a stranger seeing it cold. What jargon/assumed context/internal logic doesn't hold up outside the room? |
| **Executor** | Ignore the debate — what do you literally do Monday? One action, one owner, one date. |

Situational extra seats, **added never substituted**, when the decision calls for
it: **Compliance/Risk**, **Security**, **Brand/Voice**, **Financial/runway**.

## Stage 3 — Cross-review, then verdict
Only after all five answers exist: cross-review them against each other. Where do
they agree? Where do they clash (state it as a **vote**, e.g. "3-of-5 favor A")?
What blind spot did the cross-review catch that no single seat saw alone?

Then output exactly:

```
### ROUNDTABLE VERDICT — <decision, one line>

Where the Roundtable agrees:
Where it clashes:            (as a vote, e.g. "3-of-5 favor A")
Blind spots caught:
Final call:                  <recommendation> + <Monday-morning action> + <owner> + <revisit date>
```

Red flag: if the verdict is **unanimous with zero real tension**, don't treat that
as safety — flag that the independent stage may not have run truly blind, and offer
a re-run. A panel that agrees 5-for-5 every time has collapsed into one opinion
wearing five hats.

## Stage 4 — Log it
Append one entry to `ROUNDTABLE_LOG.md` (never edit past entries except to fill in
the outcome once a revisit date arrives):

```markdown
### Verdict N — <YYYY-MM-DD>

- **Decision:** <one line>
- **Facts checked:** <verified/corrected, or "none — no checkable claims">
- **Where it agreed:** <one line>
- **Where it clashed:** <vote>
- **Blind spots caught:** <one line>
- **Final call:** <recommendation + Monday-morning action + owner>
- **Revisit by:** <date>
- **Revisit outcome:** pending
```

## Boundaries
- A verdict is a **recommendation only** — it grants no merge/deploy/spend authority.
- It does **not** replace the person whose call it genuinely is. If the verdict
  surfaces something that's really a founder's/lead's/owner's decision, tell the
  user to ask them directly.
