# Stage 4 — Brand book (`brand.json` → one page)

`python scripts/build_book.py brand.json -o brand-book.html` builds one self-contained page: sticky sidebar with
sub-menus (scrollspy), top tabs on mobile, light/dark shell toggle (remembered), copy buttons, code snippets, logo
downloads embedded. Only fonts load from the network.

The build prints the section ids. Check a change with `render.py shot brand-book.html -o x.png --only <id>` (also
works for sub-section ids, add `--dark` for the dark shell). Never open the HTML as text.

## brand.json — sections render only when their data exists
Start small (meta, logo, colors, theme, fonts, shape) and grow.

Write all content (summary, notes, rules, voice, component copy) in the product's language from discovery, set
`meta.lang`, and put translated UI labels in `meta.labels` (`python scripts/build_book.py --print-labels` lists all
of them in English). Any language works; nothing is built in.

| Key | What | Notes |
|---|---|---|
| `meta` | name, title, tagline, system, lang, updated, summary, `labels` | `labels` overrides UI text (English defaults in `DEFAULT_LABELS` of build_book.py — section names, sub-titles, states, buttons). Translate them for non-English brands. |
| `logo` | `dir` (relative to brand.json), idea, `primary.light/dark`, `lockups[]`, `marks[]`, clearspace, `clearspace_ratio`, `minsize[]`, `donts[]` | tile `bg`: light / dark / white / accent. Don't effects: stretch, rotate, recolor, shadow, outline, busy |
| `colors.groups[].items[]` | name, token, `oklch` [L,C,h] or `hex`, role | OKLCH preferred (wide gamut, matches modern CSS); hex is derived |
| `colors.contrast[]` | fg, bg (colour names), use | WCAG ratio + verdict computed |
| `colors.rules[]` | strings | |
| `theme` | light/dark `{bg, fg, muted}`, card, card_fg, primary(_fg), secondary(_fg), destructive(_fg), optional accent/success/pending/achievement | values are colour names or hex. Cards keep one colour in both shells |
| `fonts` | `css` (Google Fonts URL), display/body/mono `{family, fallback, use, sample}` | |
| `type_scale[]`, `type_rules[]` | role, font, size, weight, sample, note, `upper`, `tabular` | |
| `shape` | `radius[]`, `blob`, `elevation {style: offset\|soft, levels[{name, radius, border, offset, use}], press{translate, offset, ms}, never[]}` | levels are picked by shape: pill = radius ≥ 500, cards = largest radius |
| `motion` | `durations {name: ms}`, `easings {name: [x1,y1,x2,y2]}`, `examples[{preset, duration, easing, name?, use?, step?}]`, principles[], tokens[{name, code}], never[] | Optional: without it the book still shows easing curves, duration bars and live examples from defaults (fast 150 / base 240 / slow 420; standard, enter, exit, overshoot). Presets: fade-up, pop, slide-in, stagger, press, exit, shimmer — each loops on the brand's own cards and buttons, with copyable CSS, and stops under reduced motion. Durations and easings also export as `--duration-*` / `--ease-*` |
| `voice` | traits[], terms[{concept, use, avoid}], pairs[{do, dont}], microcopy[], gamified | |
| `components` | button, input, statuses, achievement, card, wallet, stats, avatar, toast, empty, table, tabs, dialog | each optional; copy is the brand's real UI text; `code` = snippet in the user's stack |
| `extras` | path to a brand plugin (file or package folder) | optional |

## Brand plugin (optional) — `extend(book) -> dict`
For brand-specific material (mascot, loaders, gimmicks). Keys: `css`, `js`, `sections` (new top-level sections with
`after: "<core id>"`), `into` (`{"motion": [subsections]}` appended to a core section), `hooks` (`hero_art`,
`inline_loader`, `empty_art`). Core ids: overview, logo, color, type, shape, motion, voice, components. Scope plugin
CSS under a wrapper class so it can't leak into the book. Keep the plugin self-contained (own folder, own data).

## Review checklist before showing
Render (`render.py shot … --h 18000`, `slice`), then look at every slice in light **and** `--dark`, and at
`render.py mobile`. Common catches: reversed logo on a light card (use the ink version on cards), assets overflowing
tiles, plugin buttons inheriting the wrong style, nav labels, horizontal overflow on phones.
