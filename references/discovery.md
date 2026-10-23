# Stage 0 — Discovery

Goal: a brief the user agrees with, in under five minutes of their time.

## Read before you ask
Look for what already exists and reuse it — users hate re-explaining what's written down:
- Design docs (`design*.md`, brand docs, `README`), business docs (who the product serves, tone).
- Existing logo/icon files (`public/`, `assets/`, `favicon.*`), the current logo component, CSS tokens
  (`index.css`, `globals.css`, `tailwind.config.*`, `theme.*`).
- The tech stack (see `implement.md` §1) — note it now; it shapes stage 5.
Note contradictions (e.g. a design doc says one palette, the CSS still has an older one) and mention them.

## Ask at most 4 questions, in one go
Prefer multiple-choice with your best guess first. Typical ones:
1. Scope — new logo / redesign current / document only / apply to code.
2. Literal or not — must the mark show the obvious subject (e.g. a crab), or can it be abstract/letter-based?
3. Mood — 2–3 options drawn from what you read (e.g. "playful game HUD / trustworthy fintech / streetwise").
4. Language — only if the docs and market don't settle it: which language should the brand book and copy use?
Skip questions whose answers are already in the docs.

## Brief (show it, keep it short)
```
Name (exact spelling) · what it does · audience
Language — what the audience reads (deliverables use it; the chat stays in the user's language)
Adjectives (3–5) — these become visual cues
Constraints — existing palette/fonts, where it must work (16 px favicon, stream overlay, print…)
Category clichés to avoid — e.g. tipping: coffee cups, hearts, tip jars, up-arrows
Lookalike risks — famous marks in the same space (e.g. Rust's crab mascot for crab marks)
Stack — framework, styling, component library
```
