# Design skills

Third-party Claude Code skills used for the app interface, copied verbatim (MIT). Each folder
keeps its upstream `LICENSE`. Read before installing: no scripts, no network access.

| Skill | Source | Commit |
| --- | --- | --- |
| better-typography | [jakubkrehel/skills](https://github.com/jakubkrehel/skills) | 4c66b1f |
| better-accessibility | jakubkrehel/skills | 4c66b1f |
| better-writing | jakubkrehel/skills | 4c66b1f |
| better-interface | jakubkrehel/skills (needed by interface-review) | 4c66b1f |
| interface-review | jakubkrehel/skills | 4c66b1f |
| break-ui | [emilkowalski/skills](https://github.com/emilkowalski/skills) | 2d22863 |

The skills assume web stacks with CDNs and Tailwind in places; the rules in `CLAUDE.md` win:
no remote assets at runtime, vanilla HTML/CSS/JS, Italian UI copy.
