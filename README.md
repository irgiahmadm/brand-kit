# brand-kit

<a href="https://github.com/irgiahmadm/brand-kit/releases/latest/download/brand-kit-intro.mp4">
  <img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/intro.gif" width="100%" alt="brand-kit intro: logo exploration, brand book, tokens for web and mobile">
</a>
<p align="center"><sub>🔊 <a href="https://github.com/irgiahmadm/brand-kit/releases/latest/download/brand-kit-intro.mp4">Watch with sound (0:19, MP4)</a></sub></p>

An AI agent skill that takes a product from **"we need a brand"** to **"the brand is live in our codebase"**, with
you choosing at every step.

Works with any coding agent that supports [Agent Skills](https://agentskills.io) (`SKILL.md`): Claude Code, Codex,
Cursor, Gemini CLI, GitHub Copilot, OpenCode and others.

## How it works

| # | Stage | What you get | You decide |
|:-:|---|---|---|
| 0 | **Discovery** | A short brief: product, audience, personality, and your tech stack (detected from the repo). | Confirm the brief |
| 1 | **Explore** | Concept rounds on review boards: each idea on light and reversed, tried in a browser tab, app icon and nav bar. No "recommended" badge. | Pick a direction |
| 2 | **Finalize** | A clean master mark with real knockout gaps, plus the full kit: colourways, small cut, horizontal and stacked lockups, app icon, favicons, PWA icons and manifest, plus mobile: iOS icon (light/dark/tinted), Android adaptive and themed icon, splash, Expo and Flutter configs. | Approve the logo |
| 3 | **Extend** | Mascot, loaders and UI gimmicks drawn from the logo's own shapes. | Choose which to keep |
| 4 | **Brand book** | One self-contained HTML page: logo, colour with contrast checks, typography, shape, live motion examples (easing, durations, enter/exit/press/stagger), voice, and components with code. Light and dark. | Review the page |
| 5 | **Implement** | Design tokens for web (CSS variables, Tailwind v4/v3, shadcn/ui) and mobile (Flutter, SwiftUI, Jetpack Compose, React Native), then components written in your stack's conventions. | Check it matches the book |

Start at any stage. Already have a logo? Jump to the brand book. Only need tokens in your repo? Go straight to stage 5.

## Install

**With the skills CLI.** Name your agent with `-a`, so the skill lands in the folder that agent actually reads:

```bash
# Claude Code  → .claude/skills/brand-kit
npx skills add irgiahmadm/brand-kit -a claude-code

# Several agents at once
npx skills add irgiahmadm/brand-kit -a claude-code -a cursor -a codex

# Every supported agent
npx skills add irgiahmadm/brand-kit -a '*'
```

Add `-g` to install for your user (every project) instead of the current repo.

> [!IMPORTANT]
> Without `-a`, the CLI may only write to `.agents/skills/`. Claude Code doesn't read that folder, so the skill
> won't show up there. Re-run with `-a claude-code`.

**Or copy this folder by hand:**

| Agent | You, every project | One repo (shared with the team) |
|---|---|---|
| Claude Code | `~/.claude/skills/brand-kit/` | `.claude/skills/brand-kit/` |
| Cursor, Gemini CLI, Copilot, OpenCode, Codex | see your agent's docs | `.agents/skills/brand-kit/` |
| Anything else | — | Add to your agent's rules file: *"For branding work, follow `path/to/brand-kit/SKILL.md`."* |

Start a new agent session after installing, so it picks up the skill.

### Requirements

- Python 3 with `pip install skia-pathops fonttools pillow`
- Chrome, Edge or Chromium (used headless for rendering and screenshots)

## Usage

### Call it by name

| Agent | Type |
|---|---|
| Claude Code | `/brand-kit` followed by what you want, e.g. `/brand-kit make a logo for this app` |
| Other agents | Mention it: *"Use the brand-kit skill to …"* |

You can also just describe the job. The skill loads by itself on requests like "make a logo", "set up our brand",
"build a style guide" or "apply our brand colours to this repo". If it doesn't, name it explicitly as above.

### Example prompts

Pick the one that matches where you are. You don't have to start at stage 0.

| You have | Prompt |
|---|---|
| Nothing yet | `/brand-kit Build a brand for this app from scratch. Read the repo first to understand the product.` |
| A product idea, no repo | `/brand-kit Brand for "Kopi Kilat", a 15-minute coffee delivery app for office workers. Friendly, fast, a bit playful.` |
| A direction in mind | `/brand-kit Logo concepts for Kopi Kilat: monogram or a lightning-bolt cup. Show at least 6 options.` |
| A logo you like | `/brand-kit Finalize logo/draft.svg into a full logo kit: lockups, colourways, favicon and app icons.` |
| A finished logo | `/brand-kit Make a mascot and loading animations from our logo in brand/logo/.` |
| Logo + colours + fonts | `/brand-kit Build a brand book from our logo in brand/ and the colours and fonts in DESIGN.md.` |
| A brand book already | `/brand-kit Apply our brand book to this repo: tokens, theme and the main components.` |
| A change to make | `/brand-kit Add a dark-mode accent colour to our brand book and update the tokens.` |

### What a session looks like

1. The agent asks a few questions (or reads your repo) and writes a short brief. You confirm it.
2. It shows options as images: logo concepts, loaders, layouts. Reply in plain words: "#3 and #5", "more like #2 but
   rounder", "none of these, try letterforms".
3. After each step you approve, it builds the files and refreshes the brand book.
4. At the end you get the logo kit, `brand-book.html` and, if you asked, the brand applied to your codebase on a new
   branch.

The agent runs every script itself. You never have to type a command.

### Token usage

> [!NOTE]
> Rough **new tokens per stage**, estimated from the skill's file sizes and the image cost each render prints. They
> are not measured on a full run. More rounds or more changes cost more, and your agent re-sends the conversation
> each turn (prompt caching makes that cheaper).

| Stage | Typical | What it spends tokens on |
|---|---|---|
| Load the skill | ~2k | `SKILL.md`; each stage then loads one ~0.5–1k guide |
| 0 Discovery | 2–8k | Reading your docs and repo for the brief |
| 1 Explore, per round | 4–10k | Writing rough SVGs and viewing one review board (~1.5k per board of up to 6) |
| 2 Finalize | 10–25k | Construction script, kit generation, a few checks at real size |
| 3 Extend | 10–25k | Mascot, loaders and gimmicks on one lab page |
| 4 Brand book | 10–25k | Writing `brand.json`, then one section screenshot per change (~1–1.5k each) |
| 5 Implement | 15–60k | Depends on your repo: how many components and call sites change |
| **Full run** | **~60–180k** | Everything above, with two or three exploration rounds |

How the skill keeps this down (enforced in the scripts as well as the instructions):

- Generated files are never read back. The brand book embeds every asset (the Scrimpanzee one is ~125k tokens), so the
  agent relies on each script's one-line summary and on screenshots.
- Checks are targeted. `render.py shot … --only color` captures one section for ~1.5k tokens instead of ~20k for
  the whole page. A full look-through happens once, at the end, after the agent tells you what it costs.
- Every screenshot is trimmed and sized to what the model actually sees, and the script prints its cost
  (`~1532 tokens to view`), so the agent can pick the cheaper check.
- One image per question: a single board per exploration round, at most 6 concepts on it.

To spend less: start at the stage you need (a finished logo can skip stages 1–2), give direction in your replies
("B, rounder") so rounds converge, and ask for the full-page review only once.

### Language

The agent chats in your language, but the deliverables (review boards, brand book, copy examples) use the
**product's** language: whatever its audience reads. It settles this in discovery and asks if it isn't clear. Any
language works; say it up front if you already know, e.g. *"the app is for Brazil, write the brand book in
Portuguese"*.

## What's inside

```
SKILL.md                 workflow, checkpoints, tools
references/              one guide per stage (discovery, logo, extend, book, implement)
scripts/
  geometry.py            boolean path ops: unions, uniform knockout gaps, sliver cleanup, role-tagged SVG
  outline_text.py        wordmark text → outlined paths (variable fonts supported)
  contact_sheet.py       exploration review board (light + reversed, tried in a browser tab, app icon, nav bar)
  make_kit.py            master mark → full logo kit, web icons, iOS / Android icons and splash
  render.py              screenshots, SVG → PNG, slicing, real mobile check, overflow finder, .ico
  build_book.py          brand.json (+ optional plugin) → one-page brand book
  export_tokens.py       brand.json → tokens (DTCG), CSS, Tailwind v4/v3, shadcn, Flutter, SwiftUI, Compose, React Native
```

## Example: Scrimpanzee

A full run for Scrimpanzee, tactical training and matchmaking for competitive teams: a strategist chimp, dark canopy,
one bioyellow signal. Everything below was generated by the skill.

📖 **[Download the brand book](https://github.com/irgiahmadm/brand-kit/releases/latest/download/scrimpanzee-brand-book.html)**: one self-contained HTML page, open it in any browser.

### Explore — round 1 review board

Each concept on light and reversed, tried in a browser tab, as an app icon and in a nav bar, with an honest risk.
The user picked **C · Facet** and refined it in round 2.

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-round1.png" width="80%" alt="Round 1 review board: six concepts">

### Logo kit — lockups, variants, clear space, misuse

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-logo.png" width="80%" alt="Logo section: lockups, variants, clear space, misuse">

### Mobile icons — iOS, Android adaptive and themed, splash

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-app-icons.png" width="100%" alt="iOS light, dark and tinted icons; Android adaptive and themed icons; splash">

### Brand book — light and dark shell

<p>
  <img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-hero.png" width="62%" alt="Brand book cover, light shell">
  <img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-mobile.png" width="22%" alt="Brand book on a phone">
</p>
<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-hero-dark.png" width="62%" alt="Brand book cover, dark shell">

### Colour — palette, shells, contrast checks

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-color.png" width="80%" alt="Colour section">

### Typography

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-type.png" width="80%" alt="Typography section">

### Shape and elevation

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-shape.png" width="80%" alt="Shape and elevation section">

### Motion — easing, durations, live examples

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-motion.png" width="80%" alt="Motion section: easing curves, duration bars, live examples">

### Mascot and loaders

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-mascot.png" width="80%" alt="Mascot and loaders section">

### Components with code

<img src="https://github.com/irgiahmadm/brand-kit/releases/latest/download/scz-components.png" width="80%" alt="Components section">

## Contributing

Issues and pull requests are welcome: bugs, new stacks for stage 5, better review boards, more motion presets,
translations of the UI labels.

**Report something.** Use the [bug report](https://github.com/irgiahmadm/brand-kit/issues/new?template=bug_report.yml)
or [feature request](https://github.com/irgiahmadm/brand-kit/issues/new?template=feature_request.yml) form. Say which
agent and stage, and add a screenshot for anything visual.

**Change something.**

1. Fork and clone, then install the script dependencies:
   ```bash
   pip install skia-pathops fonttools pillow   # plus Chrome, Edge or Chromium for rendering
   ```
2. Point your agent at your clone instead of an installed copy, so you test your changes. For Claude Code, link it
   into a scratch project: `mkdir -p .claude/skills && ln -s /path/to/brand-kit .claude/skills/brand-kit` (on Windows,
   `mklink /J .claude\skills\brand-kit C:\path\to\brand-kit`).
3. Run the skill once in that scratch project for any product. Its `brand/` folder is your test bed: re-run the
   scripts you changed against it, for example
   ```bash
   python scripts/build_book.py brand/brand.json -o out/brand-book.html
   python scripts/render.py shot out/brand-book.html -o out/motion.png --only motion
   ```
4. Look at what you changed, in light and dark and at phone width (`render.py mobile`). Visual bugs only show up in
   screenshots.
5. Open a PR with a [Conventional Commit](https://www.conventionalcommits.org) title (`feat:`, `fix:`, `docs:`, …)
   and fill in the template. Release notes are generated from these titles.

**House rules**, so the skill stays what it is:

- The user picks. No "recommended" option in exploration unless they ask for an opinion.
- Keep it light on tokens. The agent never reads generated files back; checks use targeted screenshots
  (`render.py --only`), and scripts print short summaries.
- Deliverables follow the product's language. New UI text goes into the label tables (`--print-labels`), not
  hard-coded.
- Python 3 standard library plus `skia-pathops`, `fonttools` and `pillow`; nothing else without a good reason.
- Don't commit generated files or media. README examples are attached to the release.
- Update `SKILL.md` and the matching `references/` guide whenever behaviour changes.

## Notes

- No trademark clearance is performed. Run a professional search before launching a mark.
- Check that the fonts used in a logo allow it (SIL OFL fonts do).
- Scrimpanzee is a real product's identity, shown here only as an example of the output. Don't reuse its visuals
  for another brand.

## Credits

Inspired by [logo-design-skill](https://github.com/kaankiziltug/logo-design-skill) by
[@kaankiziltug](https://github.com/kaankiziltug) (MIT), which shaped the brief-first process, testing logos at
small sizes, and showing honest notes on each concept. brand-kit carries that idea on into the brand book and the
codebase.
