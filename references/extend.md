# Stage 3 — Extend: mascot, loaders, gimmicks

Build these from the **logo's own geometry** (reuse the master paths), so everything reads as one family. Put them
on an interactive "lab" page (plain HTML + CSS keyframes + a little JS), give each a card with a code tag
(L1, L2…), one honest note, and let the user pick.

## Loaders — offer a spread
- Character walking (with a prop, e.g. carrying the coin) — section/page loading.
- **Logo animation** variants (piece drops in / pieces slide together / accent spins while the mark "breathes") —
  splash, first load, replaces a full-page spinner. If a character version of the logo looks odd (legs on letters),
  replace it with a pure logo animation.
- Tiny inline loader (a part of the mark that pinches/rotates) — inside buttons.
- Progress-style (character eats tokens along a track) — uploads, multi-step.
- Skeleton companion (character peeks from behind skeleton bars) — keeps skeletons as the real loading pattern.

## Gimmicks — group them
Celebrations (stream alert, success, milestone, leaderboard crown) · Empty & error (sleeping, lost/404, search) ·
Micro-interactions (hover on logo, easter egg after N clicks, button press, rotating loading copy, sounds) ·
Seasonal (costumes paired with alternate app icons). Icon set: one consistent stroke grid with a brand signature
(e.g. one accent-coloured coin per icon).

## Rules that keep gimmicks classy
- Read the design doc's motion rules first and obey them (e.g. money amounts never animate; celebrations are rare;
  no glow/blur). Say in the card note how the gimmick respects them.
- Every animation stops under `prefers-reduced-motion`.
- No emoji standing in for brand assets — draw them.
- Sounds: synthesize placeholders with WebAudio, default off.
- Favicon can change at runtime (e.g. a badge with a count); PWA icons cannot — say so when offering "app icon
  alternates" for a web app.

## Checking animations
Pages honour `?t=<ms>` (freeze) and `?dark=1`. Screenshot 2–3 times per animation; look for clipped elements, props
covering the face, labels overlapping. Headless browsers can't reach `#anchors` reliably — screenshot tall and slice.
