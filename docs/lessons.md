# Lessons learned

Rules added after real mistakes during the build. Each lesson follows one format so it stays short and actionable. This file is the harness's memory: Claude reads it every session.

Format:
- **[date] What went wrong** → **Rule going forward**

- **2026-10-26 UI preferences confirmed by Rohith** → Header: wordmark only (no date, no dropdown). No sticky nav tabs. Report cards in a 2-column grid (side by side). No deal wrap on the page. No em dashes anywhere in report prose or titles; use a colon or plain hyphen instead. These rules apply to templates, sample data, and LLM prompts.

- **2026-10-26 Context window overuse burns credits** — Long sessions accumulate context from file reads, test output, and large diffs, exhausting the token budget and requiring top-ups. → Read only files needed for the current sub-task. Prefer targeted Grep/Glob over reading whole files. Commit at each natural checkpoint rather than batching a full step into one message. Avoid re-reading files already known this session.

- **2026-10-26 Starlette 0.41+ changed `TemplateResponse` signature** — old call `TemplateResponse("page.html", {"request": request, ...})` silently passed the context dict as the template *name*, causing `TypeError: unhashable type 'dict'`. → Always call `TemplateResponse(request=request, name="page.html", context={...})` with keyword args; the new API adds `request` to context automatically.

- **2026-10-26 Stale uvicorn process silently hides new routes** — After adding a new FastAPI route, the already-running uvicorn server (even with `--reload`) did not pick up the change mid-session, returning Starlette's default `{"detail":"Not Found"}` JSON 404 instead of the new HTML response. → After adding any new route, verify it is reachable via `TestClient` in a test (see `test_report_page_200`) before declaring it done. When running the dev server interactively, kill and restart it fresh rather than relying on reload after session-level code changes.
