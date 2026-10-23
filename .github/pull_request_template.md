<!-- PR title: a Conventional Commit, e.g. "feat: Android splash for Expo" or "fix: overflow in the colour table".
     Release notes are built from it, so describe the change, not the work. -->

## What and why

<!-- What changes for someone using the skill, and why. Link the issue: Closes #123 -->

## How you checked it

<!-- Scripts you ran and on which brand. For anything visual, add before / after screenshots
     (light and dark, and a phone width for the brand book). -->

## Checklist

- [ ] Title follows Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`)
- [ ] Ran the changed scripts on a real brand and looked at the output
- [ ] Visual changes: screenshots attached (light, dark, phone width where relevant)
- [ ] `SKILL.md`, `references/` and the README match the new behaviour
- [ ] No generated files or media committed (examples go in the release, not the repo)
- [ ] Doesn't make the agent read more: no new large files to read back, images stay targeted (`render.py --only`)
- [ ] The user still picks; no new "recommended" defaults in exploration
