# Stage 5 — Implement in the user's stack

The brand book stores **what** (tokens, component specs, rules), not framework code. Implementation translates that
into the conventions of the repo in front of you.

## 1. Detect, don't assume
Read `package.json` (and lockfile), framework config (`vite.config.*`, `next.config.*`, `nuxt.config.*`,
`svelte.config.*`, `app.json`/`pubspec.yaml` for mobile), styling (`tailwind` version — v4 has `@import "tailwindcss"`
/ `@theme` in CSS, v3 has `tailwind.config.*`), component library (`components.json` = shadcn, MUI, Chakra, Vuetify…),
and the project's own rules files (AGENTS.md, CLAUDE.md, .cursor/rules, CONVENTIONS, design docs). A user saying "Next.js" may be on
TanStack Start + Vite — check.

## 2. Tokens via adapters (`export_tokens.py`)
| Stack | Use | Where it goes |
|---|---|---|
| any web | `tokens.css` | global stylesheet |
| Tailwind v4 | `tokens.css` + `tailwind4.css` (`@theme inline`, `@utility` for elevation/blob) | main CSS after `@import "tailwindcss"` |
| shadcn/ui | `shadcn.css` (maps to `--background`, `--primary`, `--radius`, …) + `tailwind4.css` | replace the `:root`/`.dark` blocks in the global CSS |
| Tailwind v3 | `tokens.css` + spread `tailwind3.js` into `theme.extend` | `tailwind.config.js` |
| CSS-in-JS (MUI/Chakra/styled) | map `tokens.json` roles into the theme object | theme file |
| Flutter | `brand_theme.dart` (`BrandTheme.light/dark`, `BrandColors`, `BrandRadius`, `BrandFonts`) | `lib/theme/`, pass to `MaterialApp(theme:, darkTheme:)` |
| SwiftUI (iOS) | `BrandTheme.swift` (`Color.brand*` roles switch with dark mode, `Color.palette*`, `BrandRadius`, `BrandFont`) | app target |
| Jetpack Compose | `BrandTheme.kt` (`BrandTheme { }`, light/dark `ColorScheme`, `BrandPalette`, `BrandRadius`) | `ui/theme/`, fix the `package` line |
| React Native / Expo | `theme.ts` (`palette`, `colors.light/dark`, `radius`, `fonts`, `elevation`) | `src/theme/`, pick the mode with `useColorScheme()` |
| Other | `tokens.json` (W3C DTCG) → Style Dictionary, or map by hand | theme module |
Keep the brand's fonts loading the way the project already loads fonts (native files only carry family names).

### Mobile assets (`files/mobile/` from make_kit.py)
| Stack | Icons and splash |
|---|---|
| Native iOS | copy `ios/AppIcon.appiconset` and `ios/BrandMark.imageset` into `Assets.xcassets` |
| Native Android | merge `android/res/` into `app/src/main/res/`; splash: `windowSplashScreenAnimatedIcon=@drawable/splash_icon`, `windowSplashScreenBackground=@color/splash_background`; Play Store: `play-store-512.png` |
| Expo | copy `store/*.png` to `assets/brand/`, merge `store/expo-app.json` into `app.json`, then `npx expo prebuild` |
| Flutter | copy `store/*.png` to `assets/brand/`, add `store/flutter_launcher_icons.yaml` and `flutter_native_splash.yaml` config, run both generators |
| React Native CLI | use the native iOS and Android steps above |
Don't overwrite existing icons without saying so; show before/after on the composite check image.

## 3. Components as specs
For each component in the book: anatomy, states (default/hover/pressed/loading/disabled/error), tokens used, rules
(e.g. "amounts: mono + tabular, never animated"; "one primary CTA per screen"). Then:
1. Find the existing equivalent in the repo and restyle it through tokens before creating new ones.
2. Respect the library's boundaries (e.g. shadcn: don't hand-edit generated primitives if the project forbids it —
   remap via CSS variables; custom brand components in the project's shared folder).
3. Logo component: inline SVG paths from the master with `currentColor` for `main` and a CSS variable for the
   accent; a `size`/`small` variant switches to the small cut below 24 px. Keep the existing component name and props
   so call sites don't change.
4. Loaders/gimmicks: port the CSS keyframes as-is (they are framework-free); wrap in a component; honour
   `prefers-reduced-motion`.
5. Icons: favicon set + manifest from `files/web/`, `<head>` snippet adapted to the framework's head API.

### Lessons from the first real run (TanStack Start + Tailwind v4 + shadcn)
- **Generate, don't paste.** Write a small script that reads the master SVGs / path data and emits the components
  (`BrandMark.tsx`, `BrandLoaders.tsx`, its CSS). Path data copied by hand drifts from the master; a generator can
  be re-run whenever the logo changes. Convert SVG → JSX in that script (`class`→`className`, `stroke-width`→
  `strokeWidth`, `style="a:b"`→`style={{ a: 'b' }}`, colours → `currentColor` / CSS variables).
- **Prefix keyframes and classes** (`cc-leg`, `cc-bob`…): names like `.leg`/`.bob` collide in a real app.
- **Check call sites before changing a mark's aspect ratio.** Existing `w-8 h-6` boxes letterbox a wider mark (it
  shrinks, it doesn't squash) — tell the user, and switch 16 px call sites to the small cut.
- **Existing colouring decides the look.** If every call site sets the mark to the brand colour, the two-tone mark
  renders one-colour; expose the accent as a CSS variable (`--crab-coin`) and say how to get two-tone.
- **Don't touch token files the user is mid-way through** (uncommitted theme work) — implement around them and say so.
- **Headless screenshots of marketing pages can look empty** when sections animate in on scroll; that's not proof of a
  bug — say it's unverified and ask the user to check in a real browser.

## 4. Verify
Run the app (or its preview), screenshot the same screens in light/dark and at phone width, compare with the brand
book, list differences and fix. Run the project's lint/typecheck/tests. Work on a branch; never mix with unrelated
uncommitted changes — ask first.
