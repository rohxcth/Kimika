---
name: update-spec
description: Record a design decision change in kimika-spec.md (and CLAUDE.md or docs/ if a rule or template changes), keeping all files consistent. Use when Rohith changes how Kimika should work or look, or invokes /update-spec.
---

# Update the spec

1. **Restate the change** in one line and confirm it with Rohith if it's ambiguous.

2. **Find every place it touches.** Search `kimika-spec.md`, `CLAUDE.md` and `docs/` for related wording. A change often appears in several places (e.g. a report section appears in the spec summary, `docs/report-templates.md` and the PDF format).

3. **Edit consistently.**
   - Design and layout changes go in `kimika-spec.md`
   - Rule changes (sources, tone, free-tier limits, verification) go in `CLAUDE.md`
   - Report structure changes go in `docs/report-templates.md`
   - Source changes go in `docs/sources.md`

   Change only what the decision requires. Keep the existing structure and wording style.

4. **Check for contradictions.** Re-read the edited sections and search for leftover old wording. No two files should disagree.

5. **Flag knock-on work.** If already-built code no longer matches the spec, list what needs changing, but don't change code in this skill.

6. **Report** a short before → after summary per file.
