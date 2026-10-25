---
name: lesson
description: Record a mistake as a rule in docs/lessons.md so it isn't repeated, and add a regression test where possible. Use when Rohith corrects an error or invokes /lesson.
---

# Record a lesson

1. **Pin down the mistake.** Restate in one line what went wrong and why (e.g. "Extractor read '$45m' as 45 because the m suffix wasn't handled"). If the cause is unclear, ask Rohith before writing anything.

2. **Write the rule** and append it to `docs/lessons.md` in this exact format:

   ```
   - **[YYYY-MM-DD] <What went wrong>** → **<Rule going forward>**
   ```

   Keep it to one line, specific and testable. "Be more careful" is not a rule; "Convert m/bn/k suffixes to full numbers before validation" is.

3. **Prevent it in code where possible.** If the mistake can be caught automatically, add a pytest regression test (synthetic data, no network) and make it pass. Mention the test name in the lesson line.

4. **Check for duplicates.** If a similar lesson already exists, update that line instead of adding a new one.

5. **Report** the line you added (and the test, if any) in two lines. Suggest a DEVLOG entry for Rohith to write in his own words.
