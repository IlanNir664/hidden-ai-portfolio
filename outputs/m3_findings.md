# Module 3 Findings -- Scenario Projection

If a dot-com-style repricing occurred, QQQ's projected loss (-72%)
is the largest of the portfolios tested, versus RSP's (-54%) --
but QQQ's projected no-bubble gain (33%) is also the largest,
against RSP's (11%). SPY and the synthetic 60/40 sit between
the two: -57%/22% and
-39%/14%
respectively (Chart 6). Every portfolio in this study sits somewhere on the same
upside-kept-versus-downside-risked line -- none dominates the others on both axes at
once, and this project does not recommend a weight. These are conditional projections
built from today's measured betas and historical shock sizes, not forecasts that any
scenario will happen -- see `m3_methodology.md` and `LIMITATIONS.md` for why real
crash losses likely run worse than the linear numbers shown here.

**A third scenario, 2008-style, tells a different kind of story -- and it is not the
milder one.** The synthetic 60/40's projected outcome if a 2008-style repricing
occurred is -41%, *worse* than its -39% dot-com-style
projection, even though the 2008 AI_shock itself (-53.4%, QQQ) is smaller in
magnitude than the dot-com AI_shock (-77.9%, Nasdaq Composite). The reason is the
rest_shock: 2008's (-59.8%, value/IWD) is far deeper than dot-com's (-34.1%, also
value/IWD, different era) -- because 2008 was systemic, "the rest of the market"
fell almost as hard as the epicenter, whereas in the dot-com crash it barely fell at
all. A portfolio like 60/40, with meaningful exposure to both factors (`beta_ai`
0.32, `beta_rest` 0.41), takes the hit on both sides at once in the 2008 scenario in
a way it doesn't in the dot-com one. This projection likely still *understates* the
real difference: the two-factor model only "sees" bonds through `beta_rest` applied
to an equity rest-of-market shock -- it has no way to represent TLT's actual 2008
behavior, a +26% *gain* (Module 2's flight-to-quality finding), so a real 60/40
investor's 2008-style outcome would likely have been meaningfully better than even
this worse-than-dot-com number shows. See `LIMITATIONS.md`, Module 3 section.
