---
name: review-report
description: Review a generated Kimika report (JSON and PDF) against the report rules and templates, and list every problem found. Use after the pipeline produces a report, or when Rohith invokes /review-report with a report path or slug.
---

# Review a report

Input: a report folder, e.g. `reports/2026-10-26/<slug>/`. If none is given, review the most recent reports in `reports/`.

Read `report.json`, render or open `report.pdf`, and check against `CLAUDE.md` (report content rules) and `docs/report-templates.md`.

## Checklist

**Content**
- [ ] All template sections present, in order (deal reports: snapshot → rationale → process & negotiations → valuation → structure & financing → advisers → Market view → Outlook & scenarios → Bibliography; Economy & Markets: Economy → Equities → Commodities → Debt → Currencies → Bibliography)
- [ ] Economy section analyses the macro landscape and policy (monetary, fiscal, trade, regulation), not just data releases
- [ ] Market view and outlook reflect consensus from **multiple** sources; split views show both sides
- [ ] Outlook & scenarios present; forecasts and probabilities come from sources or market pricing, not invented
- [ ] Nothing speculative presented as fact; undisclosed items say "Not publicly disclosed"

**Tone and style**
- [ ] Neutral and professional; no "Kimika thinks", no recommendations, no hype
- [ ] Written for IB analysts: dense, precise, no basic explanations or educational asides
- [ ] **No in-text citations** (no [1], footnote numbers or source names in the prose)
- [ ] Bibliography at the end, grouped (Filings & announcements · Central banks & official data · Market data · Commentary & news)
- [ ] Paraphrased: no copied passages

**Numbers**
- [ ] Every figure in the body appears in the verification log with a status
- [ ] Derived figures (premium, multiples, implied value, dilution, tenor) were computed in `app/finance.py`. Spot-check two by recomputing
- [ ] Currency always explicit; % to 1 decimal place; spreads in bps; reference prices dated
- [ ] Market figures have ≥2 sources, or are marked ❓ Single source

**PDF**
- [ ] A4, 11pt body, clean headings and tables, page numbers, disclaimer on the last page
- [ ] Deal report 1–2 pages; Economy & Markets 2–4 pages
- [ ] File name follows `Kimika_<Type>_<Title>_<YYYY-MM-DD>.pdf`

## Output
A short list grouped by **Must fix** / **Should fix** / **OK**, each with the exact location (section or page) and a suggested fix. Then ask Rohith whether to fix them now. For any mistake that could recur, suggest running `/lesson`.
