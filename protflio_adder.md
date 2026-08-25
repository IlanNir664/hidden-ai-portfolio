# Feature: Sector Preset Portfolio Gallery

## Goal
Add a visual gallery of preset, sector-themed portfolios that the user can pick
from with one click to instantly load into the portfolio builder, instead of
only building a portfolio manually or picking from the existing text-only
"Quick presets" dropdown.

Reference for the visual style (screenshot provided separately, from an
unrelated raffle-wheel site - only the layout/card style is the reference,
not the content or language): a grid of cards, each showing a small donut
chart, a short title, a one-word category tag, and a legend of the
tickers/weights inside it. Cards sit in a responsive grid (3 per row on
desktop).

## Where it goes
Directly under the existing "Portfolio at a glance" donut chart / AI-exposure
table in Step 1-2 of the app (i.e. right after the user sees their own
portfolio's AI % breakdown, before they move on to the backtest/stress-test
steps). Before touching layout, inspect the current app's file(s) (likely
`app.py` or a `steps/` module) to find exactly where the "Portfolio at a
glance" donut and the AI % headline number are rendered, and insert the new
section immediately after that block, with its own step-like header, e.g.:

```
### Try a themed sector portfolio instead
See how a portfolio concentrated in one sector compares - pick a card below
to swap it in and re-run the numbers.
```

## Functional requirements

1. **Preset portfolios by sector.** Define 5-7 preset portfolios, each with
   3-6 tickers and weights that sum to 100%, drawn only from the app's
   existing supported 100-ticker universe (check `data/prices.db` or the
   existing ticker list/category mapping already used by the "Browse by
   category" sidebar control - reuse that mapping, don't invent a new one).
   Suggested sectors to cover, adjust based on what's actually available in
   the 100-ticker universe:
   - Healthcare (e.g. UNH, PFE, JNJ, MRK, ABBV)
   - Financials (e.g. V, BAC, JPM)
   - Consumer staples / "basics" (e.g. WMT, PG, KO)
   - Energy
   - Media / Communication
   - Broad market index (e.g. VOO or SPY-tracking fund alone, as a neutral
     baseline card)
   - Optionally an "AI basket" sector card if not already obviously covered
     by the main flow, using the same AI-basket tickers the rest of the app
     already tags as AI exposure.

2. **Card layout.** Each preset renders as a card containing:
   - A small donut chart (reuse the existing donut chart component/styling
     used for "Portfolio at a glance" - same color logic: lime for AI-basket
     tickers, gray for bonds/no-equity-exposure, sage/muted for other
     equity - do not invent a new palette).
   - A short title (sector name) and a one-line category label underneath
     the title.
   - A small legend below the donut listing each ticker and its weight %.
   - Cards arranged in a responsive grid, 3 per row on desktop, stacking to
     1 per row on narrow/mobile widths (check how the rest of the app
     already handles Streamlit's column layout at narrow widths, and match
     that approach - likely `st.columns` with a check for mobile via
     existing patterns, if any).

3. **Selection behavior.** Clicking/selecting a card should:
   - Replace the current portfolio builder's tickers and weights with that
     preset's tickers and weights (same effect as the existing "Load preset"
     button already used for the "Quick presets" dropdown - reuse that same
     underlying function/state update rather than writing a new one).
   - Scroll or otherwise return the user's attention to the portfolio
     builder / AI % results above, or re-run the AI % calculation
     automatically so the user immediately sees the new portfolio's AI %,
     donut, and (if already calculated) backtest and stress-test numbers
     update without extra clicks.
   - Visually indicate which preset (if any) is currently active, e.g. a
     highlighted border on the selected card.

4. **Consistency.** Match existing app conventions exactly:
   - Same dark theme, same lime/gray/sage color logic already used elsewhere.
   - Same font, spacing, and card/border styling as any existing bordered
     containers in the app (e.g. the "Portfolio at a glance" container).
   - Same caveats/limitations language style as the rest of the app - if a
     preset's weights are illustrative/simplified, note it briefly the same
     way the rest of the app flags assumptions (e.g. the existing
     "fixed-weight, daily-rebalanced" disclaimer pattern).

## Non-goals / constraints
- Do not fetch any new ticker data live - only use tickers already present
  in the existing 100-ticker cached universe.
- Do not change the existing manual portfolio builder, "Quick presets"
  dropdown, or any downstream step (backtest, stress test) - this feature
  only adds a new way to populate the same portfolio state that already
  feeds those steps.
- Do not add a new color palette, new fonts, or a different visual style
  from the rest of the app - the screenshot is a layout/interaction
  reference only, not a design system to copy wholesale (ignore its exact
  colors, its Hebrew text, and its RTL layout).

## Suggested implementation steps
1. Locate the existing "Portfolio at a glance" section and the existing
   preset-loading logic (`Load preset` button / `Quick presets` dropdown) in
   the codebase - reuse, don't duplicate.
2. Locate the existing ticker category mapping used by "Browse by category"
   in the sidebar, and use it to build the sector preset definitions so
   sector labels stay consistent with the rest of the app.
3. Build a small reusable "preset card" render function that takes a preset
   name, category label, and {ticker: weight} dict, and renders the donut +
   legend using the existing donut chart component.
4. Lay out the cards in a responsive grid under the existing AI % section.
5. Wire card selection to the existing portfolio-state update function used
   by "Load preset," and trigger a rerun so downstream numbers update.
6. Test with at least 2 presets end-to-end (select a card -> confirm
   ticker/weight table, AI %, and donut update correctly) before adding the
   rest.
