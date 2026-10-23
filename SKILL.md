---
name: brand-kit
description: >-
  End-to-end brand identity pipeline: discovery → logo exploration → finalized logo kit → mascot/loaders/gimmicks →
  a single-page interactive brand book (style guide + components) → design tokens and implementation in the user's own
  tech stack. Use this skill whenever someone wants a logo, a new or refreshed brand identity, a style guide, brand
  guidelines, a design system or brand book page, design tokens, loading animations or UI gimmicks that match a brand,
  app icons/favicons from a logo, or wants to apply their brand (colours, fonts, components) to a codebase — even if
  they only say things like "bikin logo", "rapihin branding", "style guide-nya mana", "theme-in pakai warna brand",
  or "jadiin design system". Also use it to extend or update an existing brand book built with it.
---

# Brand Kit

Take a product from "we need a brand" to "the brand is live in our codebase", with the **user deciding at every
checkpoint**. You explore widely, build cleanly, document everything in one shareable page, and implement it in
whatever stack the user has.

Keep messages short: show images/pages, one line per option, then ask.

## Two languages, never assumed

- **Chat** is in whatever language the user writes to you.
- **Deliverables** (review sheets, brand book, voice and copy examples, component text) are in the product's
  language: the one its audience reads. That can differ from the chat (a team chatting in Indonesian may ship a
  Japanese product) and a brand may have more than one. Settle it in discovery from the creator's preference and the
  product's market; ask if the docs don't make it clear. Record it as `meta.lang` (BCP 47, e.g. `en`, `id`,
  `pt-BR`, `ja`) and translate the UI labels (`--print-labels` on `build_book.py` and `contact_sheet.py`) into that
  language. Never default to English or to any other language just because the scripts are written in it.

## The one rule that shapes everything: the user picks

Every stage ends at a checkpoint where the user chooses. Show **options without a "recommended" badge** unless they
ask for your opinion — people who build brands want to own the choice, and an early recommendation anchors them. When
they react ("bagus", "aneh banget", "cari konsep lain"), treat it as direction, not as a request for a new round of
explanation: explore more in that direction and show again. If they ask for "minimal N", give at least N.

Be honest in the notes on each option: say what reads wrong ("looks like a tulip", "turns into ∞ at 16 px"). That
honesty is what makes the options useful.

## Stages (start wherever the user is)

| # | Stage | Output | Checkpoint | Read |
|---|---|---|---|---|
| 0 | Discovery | short brief + detected stack | user confirms brief | `references/discovery.md` |
| 1 | Explore | concept rounds on contact sheets | user picks a direction | `references/logo.md` §1–2 |
| 2 | Finalize | clean master mark + full kit (lockups, colourways, favicon, PWA icons) | user approves logo | `references/logo.md` §3–5 |
| 3 | Extend | mascot / loaders / gimmicks lab page | user picks which to use | `references/extend.md` |
| 4 | Document | `brand.json` → one-page brand book (sidebar + sub-menus, light/dark, live motion examples) | user reviews page | `references/book.md` |
| 5 | Implement | tokens + components in their codebase | screenshots match the book | `references/implement.md` |

Skip what exists: an existing logo jumps to 3 or 4; "just document our design doc" is stage 4; "apply our brand to
this repo" is stage 5 (build `brand.json` first if there is none — it is the source of truth for tokens).

## Tools (scripts/)

All Python 3; install once: `pip install skia-pathops fonttools pillow`. A Chromium browser (Chrome/Edge) is used
for rendering. Run with `python` (on Windows `python3` is often a store stub).

| Script | Use it to |
|---|---|
| `geometry.py` | Boolean path ops for clean marks: union/subtract, uniform knockout gaps (`knockout`), crevice bridges, sliver removal, role-tagged SVG output |
| `outline_text.py` | Set the wordmark in a (variable) font and convert it to outlines |
| `contact_sheet.py` | Exploration review board: one row per concept, light + reversed, tried in a 16 px browser tab, app icon and nav bar; honest risk line; labels in any language; no recommendation badge |
| `make_kit.py` | Master mark (role-tagged) → every logo file: colourways, small cut, horizontal/stacked lockups, wordmark, app icon, adaptive favicon.svg, favicon.ico, PWA icons, manifest, `<head>` snippet, and `mobile/`: iOS app icon (light/dark/tinted), Android adaptive + themed icon, splash, vector logos, Expo/Flutter configs |
| `render.py` | Look at your work: SVG→PNG, page screenshots (`--t` freezes animations, `--dark`), `slice` tall shots, real `mobile` check (375 px iframe), `overflow` finder |
| `build_book.py` | `brand.json` (+ optional brand plugin) → single self-contained brand book HTML |
| `export_tokens.py` | `brand.json` → W3C DTCG `tokens.json`, `tokens.css`, `tailwind4.css`, `shadcn.css`, `tailwind3.js`, Flutter `brand_theme.dart`, SwiftUI `BrandTheme.swift`, Compose `BrandTheme.kt`, React Native `theme.ts` |

## Look at everything you make

You write SVG and HTML without seeing them, so a render is the only way to know what you made. After every build,
render it, open the PNG and look. Check light and dark, 16 px, and a phone width before showing anything, using the
section shots above rather than whole pages. Most bugs in this pipeline only showed up in a
screenshot (a logo invisible on a dark card, cards rendered as circles, a page wider than the phone). When you find a
problem, say what it was and fix it rather than hoping the user won't notice.

## Token budget (hard rules)

Images and generated files are where a run gets expensive; the instructions themselves are cheap. Every script
prints what you need, and `render.py` prints what each image costs to view ("~N tokens"). Follow these:

1. **Never read generated files.** Brand book HTML (~100k+ tokens, it embeds every asset), review boards, token
   outputs, kit SVGs. The script's one-line summary is your confirmation; screenshots are your check.
2. **Never read script source.** Each script's usage is in its first lines (`head -25`) or `--help`.
3. **Check only what changed.** After a book edit: `render.py shot book.html -o x.png --only <section-id>`
   (~1–1.5k tokens) instead of slicing the whole page (~20k). A full slice-through is for the final review only —
   tell the user it costs ~20k tokens before you do it.
4. **One image per question.** One board per exploration round (max 6 concepts per board), one kit sheet, one
   section shot. Don't view the same image twice; don't render "just to be sure" without looking.
5. **Edit, don't rewrite.** Change `brand.json`, scripts and components with targeted edits; don't re-read a file
   you just wrote.
6. **Load one reference at a time,** for the stage you're in.

## Finish with the book, not a command

Run every script yourself; never hand the user a command to type. Whenever a stage changes the brand (new logo,
colours, loaders, tokens), rebuild the brand book at the end of that turn and give them the file path (and a
screenshot if your environment can show images). The book is the deliverable people open and share.

## Works in any agent

This is a plain Agent Skill (`SKILL.md` + `references/` + `scripts/`). Nothing here depends on one vendor: any agent
that can read files, run Python and open a headless Chromium can follow it. If your agent cannot display images,
still render and inspect the PNGs yourself, then give the user the file paths.

## Honesty and limits

- No trademark clearance: recommend a professional search before launch.
- Font licences must allow logo use (SIL OFL fonts do); say which fonts were used.
- Don't claim tests or renders you didn't run. If a browser isn't available, say so and keep geometry simple.
- In stage 5, ask before touching a repo with uncommitted changes, and work on a new branch.
