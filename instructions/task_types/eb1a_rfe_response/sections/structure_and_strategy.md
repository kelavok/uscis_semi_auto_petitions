# RFE structure and strategy

Do not draft final prose. Build a practical working plan.

Return `draft_text` containing:

1. RFE metadata found or missing.
2. Issue matrix: issue id, USCIS concern, status, initial filing evidence, new evidence, response strategy.
3. Recommended order of sections.
4. Suggested `episode_id` / `episode_folder` values for `rfe_issue_response` prompts.
5. Questions for the user if strategy, facts, or documents are missing.

If RFE text is missing, ask for it. If initial filing text is missing, say which sections are needed.
