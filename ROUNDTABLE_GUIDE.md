# The Roundtable â Silent Honor Decision-Review Guide

**TL;DR:** The Roundtable is a decision-review process for calls that are expensive or
slow to undo for Silent Honor â program changes, partnerships, hiring, platform
architecture picks. Instead of asking Claude one question and getting one confident
paragraph, it fact-checks every checkable claim first, then runs five fixed advisor
personas (a Contrarian, a First-Principles Thinker, an Expansionist, an Outsider, and an
Executor) who each answer completely independently and blind to one another, cross-examine
each other's answers for blind spots, and converge on a single verdict: where they agree,
where they clash (as a vote, not a paragraph of hedging), what the cross-review caught
that no one lens saw alone, and one concrete action with an owner and a date to check back
in. Every verdict gets logged so it's possible to see later whether it held up.

---

## Where this came from

This process was adapted from a shared, org-wide "panel of 5 advisors â cross-review â
verdict" pattern, reworked for Silent Honor's own repo and workflow:

- Each seat is a genuinely separate, parallel call that **cannot see the others' answers**
  until an explicit cross-review stage. Independence is structural, not just instructed.
- A **fact-check stage runs first, every time** â every checkable claim in the decision
  gets verified (confirmed / corrected / flagged unverifiable) before any seat argues.
- The verdict states disagreement as a **vote** (e.g. "3-of-5 favor A") â scannable in
  seconds, not buried in hedged prose.
- Same 5 personas by default, **plus** optional 6th/7th seats (Compliance, Security,
  Brand, Financial) added â never substituted â when the decision calls for it. For
  Silent Honor, a **Compliance/PII** extra seat is worth reaching for often, given how
  much of what this org handles is sensitive financial and DD-214 data.
- The final call always includes one concrete Monday-morning action, an owner, and a date
  to revisit if it turns out wrong.
- Every verdict is appended to a running ledger (`ROUNDTABLE_LOG.md` at the repo root),
  and each new run checks it for past revisit dates that never got closed out.

## Quick start (Claude Code, working in `silenthonor-website`)

Nothing to install â the skill lives in this repo at
`.claude/skills/roundtable/SKILL.md`. Just say:

> "Roundtable this: should we open a second counselor role for financial counseling
> specifically?"

or

> "Council this."
> "Run the panel on this decision."

Claude runs the full 4-stage process (fact-check â independent â cross-review â verdict),
logs the result, and hands back:

```
### ROUNDTABLE VERDICT â <decision, one line>

Where the Roundtable agrees
Where it clashes           (stated as a vote, e.g. "3-of-5 favor A")
Blind spots caught
Final call                 (one action + owner + a date to revisit)
```

## When to actually use it

Use it for decisions that are **expensive or slow to reverse**:
- Program or policy changes affecting members
- A launch or go/no-go call for a new feature (e.g. Battle Buddy going live for a new
  role, a new pipeline stage)
- A hire, a role change, an org decision
- An architecture or build-vs-buy pick with real switching cost
- Anything touching how member financial data or DD-214s are handled or stored

Don't use it for small reversible stuff â "should this button be blue or navy" doesn't
need five advisors arguing. Overusing it on trivial calls trains people to skim past the
verdict, which defeats the point.

## The fact-check stage (runs before the seats, every time)

Before any seat answers, Claude pulls every checkable claim out of the decision â
numbers, dates, comparisons, "we have X members enrolled," "this costs $Y" â and
verifies each one. Each claim comes back confirmed, corrected with the real number, or
flagged unverifiable, and that block gets handed to all 5 seats as shared ground truth
before they start arguing. If a decision genuinely has no checkable claims (a pure
judgment call), Claude says so explicitly and skips straight to the panel.

**Why this matters:** five sharp advisors can still build an airtight-sounding case on a
shared wrong premise. Cross-review between seats won't catch a wrong number none of them
had right in the first place â only checking the number itself does.

## The five seats

| Seat | Job |
|---|---|
| **The Contrarian** | Finds the single fatal flaw â not a balanced pros/cons list |
| **The First-Principles Thinker** | Challenges whether you're even solving the right problem |
| **The Expansionist** | Argues the upside case as hard as the Contrarian argues the downside |
| **The Outsider** | Zero-context reaction â catches curse-of-knowledge blind spots |
| **The Executor** | Only cares what you do Monday morning â one action, one owner, one date |

Situational extra seats (added, never substituted) when relevant: **Compliance/Risk**
(reach for this one often at Silent Honor), **Security**, **Brand/Voice**,
**Financial/runway**.

## The ledger â every verdict gets logged

Every verdict is appended to `ROUNDTABLE_LOG.md` at the repo root â one entry per
decision, never edited except to fill in the outcome once a revisit date arrives. This is
what makes "what did we decide, and did it hold up" answerable months later instead of
buried in a chat nobody can find. Each new Roundtable run checks the ledger first for any
past revisit date that's passed with no outcome recorded, and flags it before starting
the new one.

Entry format:

```markdown
### Verdict N â <YYYY-MM-DD>

- **Decision:** <one line>
- **Facts checked:** <what was verified/corrected, or "none â no checkable claims in this one">
- **Where it agreed:** <one line>
- **Where it clashed:** <vote, e.g. "3-of-5 favor A">
- **Blind spots caught:** <one line>
- **Final call:** <recommendation + Monday-morning action + owner>
- **Revisit by:** <date>
- **Revisit outcome:** pending
```

## Reading a verdict â one red flag to know

If a verdict comes back **unanimous with zero real tension**, that's not proof the
decision is safe â it's a signal to check that the independent stage actually ran blind.
A Roundtable that agrees 5-for-5 every single time either found something genuinely
uncontroversial, or collapsed back into "one opinion wearing five hats." Ask for a re-run
if that keeps happening.

---

## FAQ

**Does this replace asking the person whose call it genuinely is?** No. If the verdict
surfaces something that's really someone's call to make, ask them directly â the
Executor seat doesn't decide it on their behalf.

**Does a Roundtable Verdict grant merge/deploy/spend authority?** No. It's a
recommendation only.

**Can I add my own seat permanently?** No â the 5 fixed seats stay fixed so verdicts stay
comparable across decisions. Add situational 6th/7th seats per-decision instead.

**What if I think a verdict missed something?** Re-run it and say so explicitly in the
cross-review stage â that's exactly the loop this is built to catch.

**Where do past verdicts live?** `ROUNDTABLE_LOG.md` at the repo root â every verdict
ever run, appended in order, with its revisit date and outcome. Check there before
re-litigating a decision that was already made.

**Can I skip the fact-check stage to save time?** Only if the decision genuinely has no
checkable claims, and even then it should say so explicitly rather than silently
skipping. "We already know the numbers" is the exact trap this stage exists to catch.
