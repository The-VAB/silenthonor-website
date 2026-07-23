/* ═══════════════════════════════════════════════════════════════════════════
   SILENT HONOR — JOURNEY SELF-SELECT (client-side eligibility + emphasis)

   A scoped, honest implementation of the Situational Personalization
   Standard's Step 1 (eligibility: suppress what doesn't apply) and Step 2
   (emphasis: rank/frame what remains) for a static site with no CDP behind
   it. The signal source is the "declared / zero-party" tier only — one
   optional tap, framed as personalization the visitor controls, never a
   gate — everything else in the real directive (behavioral inference,
   identity resolution, ML scoring) requires the intelligence stack this
   site doesn't have yet.

   Content is tagged in HTML with:
     data-applies-to="veteran business supporter all"   (space-separated)
     data-emphasize-for="veteran"                        (single key)
   Confidence rule honored: with no selection, nothing is suppressed —
   every applies-to item stays visible (the "graceful default").
   ═══════════════════════════════════════════════════════════════════════════ */

const JOURNEY_KEY = 'sh-journey';
const JOURNEY_VALUES = ['veteran', 'business', 'supporter'];

function applyJourney(journey) {
  const body = document.body;

  if (journey) {
    body.setAttribute('data-journey', journey);
  } else {
    body.removeAttribute('data-journey');
  }

  // Eligibility: suppress content that explicitly doesn't apply.
  document.querySelectorAll('[data-applies-to]').forEach(el => {
    const tags = el.getAttribute('data-applies-to').split(/\s+/);
    const eligible = !journey || tags.includes('all') || tags.includes(journey);
    el.classList.toggle('journey-hidden', !eligible);
  });

  // Emphasis: highlight + reorder the match for the active journey.
  document.querySelectorAll('[data-emphasize-for]').forEach(el => {
    const match = journey && el.getAttribute('data-emphasize-for') === journey;
    el.classList.toggle('journey-emphasis', !!match);
  });

  // Reflect selection in the pill UI.
  document.querySelectorAll('.journey-pill').forEach(pill => {
    pill.classList.toggle('active', pill.dataset.journey === journey);
  });
}

function setJourney(journey) {
  const next = JOURNEY_VALUES.includes(journey) ? journey : null;
  try {
    if (next) localStorage.setItem(JOURNEY_KEY, next);
    else localStorage.removeItem(JOURNEY_KEY);
  } catch (e) {}
  applyJourney(next);
}

document.addEventListener('DOMContentLoaded', () => {
  let saved = null;
  try { saved = localStorage.getItem(JOURNEY_KEY); } catch (e) {}
  if (JOURNEY_VALUES.includes(saved)) applyJourney(saved);

  document.querySelectorAll('.journey-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const current = pill.dataset.journey;
      const isActive = pill.classList.contains('active');
      setJourney(isActive ? null : current); // tap again to clear — correction is one tap away
    });
  });
});

window.SilentHonorJourney = { setJourney, applyJourney };
