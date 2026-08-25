# Feature: Polish Pass Based on Recruiter/Hiring-Manager Review

## Context
This app is being used as a portfolio piece to send to hiring managers and
startups (crypto/fintech/AI). The overall structure and narrative arc is
already strong - this pass is about closing specific gaps that would help it
land harder in a 30-second first impression, not a redesign.

Work through the items below roughly in the priority order listed. Before
changing anything, inspect the current code to find the exact components
referenced (the AI % headline, the sidebar diagnostics panel, the footer
credit line, etc.) rather than assuming file/variable names.

---

## 1. Add a "so what" line under the AI % headline number (highest priority)

Right now the headline shows something like "58% AI - effectively AI" with
no interpretation. Add one short, clearly-labeled line directly under/beside
the number that gives the viewer context, for example:
- A comparison benchmark, e.g. "That's higher than the Nasdaq 100's AI
  weighting" (only include this if you can back it with a real, defensible
  number - do not fabricate a benchmark figure; if no reliable comparison
  number is available, use the risk-band option below instead).
- A simple risk-flag band (e.g. green under ~25%, yellow ~25-50%, red above
  ~50%) rendered as a small colored label or badge next to the number, with
  a one-line caption explaining what the band means.

Keep this to one line of text plus/or one small visual badge - this is meant
to make the number legible at a glance, not add another paragraph.

## 2. Surface the methodology caveat near the headline, not buried in small text

The existing methodology note (e.g. "Linear projection: beta_AI x AI_shock +
beta_rest x rest_shock, no alpha term") is currently small gray text at the
bottom of a chart. This is a genuine strength (it signals real understanding
of model limitations) and is currently invisible to a quick reader.

- Add a small info icon / "i" badge or expandable tooltip directly next to
  the headline AI % number or the stress-test chart title.
- On hover/click, show the existing methodology text - reuse the exact
  existing wording, don't rewrite the substance, just relocate/surface it.
- Do not remove the original caption where it already exists; this is an
  additional, more visible pointer to the same information for readers who
  won't scroll to the fine print.

## 3. Fix the "Gate check: PASS" sidebar diagnostic panel

Currently sits permanently visible in the sidebar with no explanation of
what it is or why it matters, which reads like leftover debug output.
Choose one of the following (inspect how much space/precedent the sidebar
already has for collapsible sections before deciding):

- **Option A (preferred if simple):** Add a one-line plain-language caption
  under the existing "Gate check: PASS" line, e.g. "Confirms the 100-ticker
  price data is complete and internally consistent." Keep the existing
  PASS/FAIL indicator as-is.
- **Option B:** Move the entire diagnostics block (Gate check, SPY 2022
  drawdown, universe size, source) into a collapsed expander, e.g. labeled
  "Data diagnostics (for the curious)", collapsed by default.

Either is acceptable; pick whichever fits the existing sidebar layout with
the least disruption to other sidebar elements (Quick presets, Supported
universe, Browse by category).

## 4. Add a downloadable or shareable summary (highest-leverage addition)

This is the single most valuable addition for outreach purposes - it turns
the app from something people click once into something that can be
attached to an email or LinkedIn message directly.

Implement at least one of the following, in order of preference:

- **Shareable link with portfolio state pre-loaded.** If the app doesn't
  already encode portfolio state in the URL (check existing routing/query
  param handling first), add a "Copy shareable link" button that serializes
  the current ticker/weight selection into URL query parameters, and have
  the app read those params on load to restore that exact portfolio. This
  is the more valuable of the two options because it keeps the recipient
  inside the interactive app.
- **Downloadable PDF/PNG summary.** A "Download my portfolio X-ray" button
  that exports a single-page summary containing: the donut chart, the
  headline AI % (with the "so what" line from item 1), the backtest chart,
  and the stress-test bar chart. Check what's already available in the
  environment for exporting Streamlit charts/layouts to PDF or image before
  introducing a new heavy dependency - prefer a lightweight approach (e.g.
  exporting the existing Plotly figures directly) over building a new
  templating system.

Only implement both if the first one is straightforward; don't over-invest
here if the shareable-link approach alone covers the main use case.

## 5. Mobile layout check

Given this link will often be opened from a phone (e.g. from a cold email),
verify the following don't break on a narrow viewport (test at roughly
375-390px width):
- The ticker/weight table in the portfolio builder step.
- The donut chart and its legend (check that labels don't overlap or get
  clipped).
- The stress-test bar chart and its scenario labels.
- The sidebar (confirm it collapses sensibly rather than squeezing the main
  content).

Fix any overflow, clipping, or overlap issues found, matching the existing
responsive patterns already used elsewhere in the app rather than
introducing a new breakpoint system.

## 6. Move the name/credit line up from the footer

Currently "Built by Ilan Niraev, 2026 (github link)" sits as small gray text
at the very bottom of the page, after a long scroll - most visitors will
never see it. Add the name and a link (GitHub and/or LinkedIn, whichever is
preferred - check if a LinkedIn URL is available to include alongside the
existing GitHub link) near the top hero section (next to or under "The
Portfolio X-Ray" title), styled consistently with the existing hero design
(don't make it visually loud - a small byline is enough). Leave the existing
footer credit line in place as well; this is additive, not a replacement.

---

## Non-goals / constraints
- Do not restructure the existing step order (Why this exists -> Build ->
  Headline number -> Backtest -> Stress test) - it already works well.
- Do not change the existing dark theme, color logic (lime/gray/sage), or
  overall visual identity.
- Do not fabricate benchmark numbers (e.g. a Nasdaq 100 AI-weighting figure)
  if a reliable source/calculation isn't available - use the risk-band
  alternative in that case instead.
- Keep changes additive and low-risk to the existing working flow; this is a
  polish pass, not a rewrite.

## Suggested order of work
1. Item 1 (headline "so what" line) - highest visibility, lowest effort.
2. Item 3 (Gate check panel) - quick fix, removes a "debug output" smell.
3. Item 6 (name/link near the top) - quick fix, high trust value.
4. Item 2 (surface methodology near headline) - moderate effort.
5. Item 4 (shareable link or download) - highest effort, highest leverage;
   do this once the quick wins above are done.
6. Item 5 (mobile check) - do last, as a pass across everything above once
   the new elements from items 1-4 exist, since they also need mobile
   verification.
