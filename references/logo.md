# Stages 1–2 — Logo: explore, then finalize

## 1. Exploration rounds
- Max 6 concepts per board (one image, ~1.5k tokens to view). For 7–15 ideas, make two or three boards.
- Round 1: 3 different **ideas** (different mark types: letterform, pictorial, emblem…), each a one-sentence idea.
  Write the one-liners first; a concept that needs a paragraph won't read in a glance.
- Build each as a rough black-on-white SVG (viewBox 256), render it, look, fix what reads wrong, then put all on a
  `contact_sheet.py` board: `--brand` (shown in the tab and nav bar), `--names`, `--notes` (the idea),
  `--risks` (the honest problem, if any), and `--lang` + `--labels` for the product's language. Expect to throw
  away 1 of 3 after looking — say so and replace it.
- Later rounds follow the user's reaction:
  - "X bagus, explore lagi" → 6–9 **variants of X** (proportion, size of the key detail, position, line weight,
    container/tile version).
  - "cari konsep lain" → 7–15 **new ideas** across types; fix the ones that misread before showing.
  - "bisa jadi kayak huruf CC?" → take the request literally first, then show a few interpretations.
- Notes per option: one neutral line + an honest risk ("reads as ∞ at 16 px", "looks like a sofa").
- Never put a "recommended" badge in exploration (contact_sheet.py has none on purpose).
- Draw roughs in pure black: the board's reversed tile and dark app icon invert the SVG with CSS.

Useful idea generators: fuse the product noun with the name's letters (claw → C), turn a product action into a
shape (pinch, catch, drop a coin), local idiom/slang puns (Indonesian "mata duitan" = coin eyes), the category's
reward/arcade/craft metaphors. Avoid clip-art literalism and category clichés unless there's a twist.

## 2. Choosing a direction
When the user picks, restate what they picked and what will change in finalization (e.g. "fix hidden claw tips,
real gaps instead of white strokes"). Don't redesign the idea they approved — finalization makes it clean, it does
not make it different. If a "cleaner" construction changes the character, show it side by side with their sketch.

## 3. Finalize the geometry (geometry.py)
Write a small construction script that imports `scripts/geometry.py`. Lessons that cost iterations:
- **Real gaps, never white strokes.** Fake gaps break on coloured/dark backgrounds and in one-colour versions. Use
  `knockout(back, front, gap)`; one gap size for the whole mark.
- **Tangents.** Where a Bézier leaves a circle, its control point must lie on the circle's tangent; otherwise you
  get a visible bump ("shoulder"). Check by rendering at 700 px.
- **Pointed tips.** A tip is two edges meeting; if both edges curve the same way you get a crescent that can turn
  an open C into an O. Keep the aperture readable.
- **Layer order is a design decision.** Which shape sits in front changes which details are visible (claw tips vs a
  clean seam). Render both orders and choose with the user's original sketch in mind.
- **Slivers and nubs.** Where two cuts meet, tiny wedges survive. Find them numerically (list outline points near
  the cutter), then fill the crevice with `bridge()` or grow the front shape so its halo swallows the wedge;
  finish with `drop_islands()`.
- Tag paths with roles (`main`, `accent`) via `write_svg`, so recolouring keeps the accent (e.g. the coin amber).
- Make a **small cut** for < 24 px (one simple element of the mark): wide or detailed marks collapse at 16 px.

## 4. Build the kit (make_kit.py)
Wordmark: outline the brand's display font with `outline_text.py` (download the TTF, check OFL). Lockup defaults
that worked: cap height 0.60 × mark height, gap 0.30 × mark height; stacked 0.46 / 0.26. Colour roles:
`main` (ink / sand on dark), `accent` (brand colour). Run `make_kit.py kit.json`, then render an overview board:
lockups on light + dark, app icon, sizes 96→16, one-colour on the accent colour. Check the PWA icons keep the accent
(generic exporters often flatten everything to one colour — don't accept that).

Mobile comes from the same run (`files/mobile/`, skip with `"mobile": false`): iOS app icon with dark and tinted
variants, Android adaptive icon (vector foreground + monochrome for themed icons) with legacy mipmaps, splash icon,
vector logos for in-app use, and 1024 PNGs + Expo / Flutter config snippets. Check them on **one** composite image:
iOS light/dark/tinted, the Android foreground under a circle and a squircle mask (the launcher shows only the centre
72 of 108 dp), the themed (monochrome) icon, and the splash icon on its background. Wide marks hit the mask first —
lower `mobile.android_fill` if anything nears the edge. iOS 26 Liquid Glass layered icons (Icon Composer `.icon`)
are not generated; the 1024 set still works there.

## 5. Deliver
`files/` (all SVG + `web/` + `mobile/`), a short `GUIDELINES.md` (files table, colour table, clear space = a mark element such
as the coin Ø, minimum sizes, don'ts, open items like trademark search), and an overview PNG. Don't touch the
user's repo here — offer stage 5 instead.
