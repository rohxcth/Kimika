---
name: next-step
description: Run the next step of Kimika's build end to end. Find the step, plan, build, test, call the right subagents and skills automatically, fix what they find, report back, then stop. Use when Rohith says "next step", "continue the build", or invokes /next-step.
---

# Next build step (end to end)

Rohith only needs to type `/next-step`. You handle the checks, reviews and lessons yourself.

## 1. Find the step
- Read `kimika-spec.md` section 9, `DEVLOG.md`, and `git log --oneline -20`, and look at which files in `app/` and `tests/` already exist.
- The next step is the first one in the current tier that isn't done. If the sources disagree, say what you see and ask Rohith which step he's on. Never skip ahead to a later tier.

## 2. Plan (big steps only)
For steps 5, 6, 7, 9 and 10, or any step touching several files: show a short plan (files, approach, what "done" looks like, anything Rohith must do first, e.g. add a key or design screenshots), then **wait for his OK**. For other steps, state the plan in 2–3 lines and continue.

## 3. Build
Follow `CLAUDE.md`: small readable functions, finance logic commented, finance figures in `app/finance.py`, network access only via `app/fetch.py`, never read or write `.env`, free tiers only. Use Context7 for current library docs (FastAPI, WeasyPrint, APScheduler, google-genai, yfinance, pdfplumber).

## 4. Test
Add or update pytest tests (synthetic data, no network). Run `pytest -q`. Fix failures before moving on.

## 5. Run the checks this step needs (automatically)

| If the step... | Do this |
|---|---|
| Adds or changes any finance calculation (`finance.py`, premiums, multiples, ranking by US$ value) | Run the **finance-reviewer** subagent on the changed code. Fix every "Error"; add the "Missing tests" |
| Introduces any data source not already in `docs/sources.md` | Run the **source-scout** subagent on it **before** writing code that depends on it. If the verdict is "Don't use", stop and tell Rohith. If "Use", add its row to `docs/sources.md` |
| Produces reports (pipeline runs, prompts, templates, PDF) | Run the pipeline with `--now` (or on fixtures), then run the **review-report** skill on the outputs, then the **report-critic** subagent on the best and the worst report. Fix all "Must fix" and "Top 3 fixes" |
| Builds or changes the web page or PDF layout | Render it (page at desktop and phone width; PDF to images) and check it against `kimika-spec.md` sections 2 and 6 and anything in `docs/design/` |
| Uses Gemini | Show the request count per model from the quota log and confirm it's within the caps in `config.yaml` |

If a check finds a mistake that could recur, apply the **lesson** skill: add the rule to `docs/lessons.md` and a regression test.

If Rohith changed a design decision during the step, apply the **update-spec** skill so all files stay consistent.

## 6. End of tier
If this was the last step of a tier, check every item in the definition of done (`kimika-spec.md` section 10) that applies to the tier. List anything missing, and don't declare the tier complete until it's done.

## 7. Report back, then stop
Use exactly this format:

```
Step N done: <one-line summary>
Files: <created/changed>
Tests: <X passed>
Checks run: <subagents/skills used, and what they found and what was fixed>
Lessons added: <none, or the lines>
Finance logic: <1–2 sentences with a concrete example, if any>
Worth understanding: <1–2 questions an interviewer could ask about this step, with short answers>
Suggested DEVLOG line: <for Rohith to rewrite in his own words>
Commit: git add -A && git commit -m "Step N: <summary>"
Next: Step N+1: <name> (<anything Rohith must prepare first>)
```

Do not start the next step until Rohith confirms. Do not commit for him unless he asks.
