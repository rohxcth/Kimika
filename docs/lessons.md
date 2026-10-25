# Lessons learned

Rules added after real mistakes during the build. Each lesson follows one format so it stays short and actionable. This file is the harness's memory: Claude reads it every session.

Format:
- **[date] What went wrong** → **Rule going forward**

- **2026-10-26 UI preferences confirmed by Rohith** → Header: wordmark only (no date, no dropdown). No sticky nav tabs. Report cards in a 2-column grid (side by side). No deal wrap on the page. No em dashes anywhere in report prose or titles; use a colon or plain hyphen instead. These rules apply to templates, sample data, and LLM prompts.

- **2026-10-26 Starlette 0.41+ changed `TemplateResponse` signature** — old call `TemplateResponse("page.html", {"request": request, ...})` silently passed the context dict as the template *name*, causing `TypeError: unhashable type 'dict'`. → Always call `TemplateResponse(request=request, name="page.html", context={...})` with keyword args; the new API adds `request` to context automatically.
