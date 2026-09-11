# Copilot Instructions

This project uses `.structure/` for AI development state management.

Before making changes:
1. Read `.structure/state.json` for current phase
2. Read the target module's `.structure/STATUS.md` for boundaries
3. Check `.structure/coupling.md` for cross-module constraints

Key rules:
- One module lock at a time
- Always update `.structure/` alongside code changes
- Check "不要假设" (wrong assumptions) section in STATUS.md before coding
- `yang/jsonl.py` and `web/src/yangdata.js` must stay in sync

Full contract: `.structure/AGENT.md`
