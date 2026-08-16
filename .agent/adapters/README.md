# Agent adapters

`.agent/` is the tracked canonical source. `.agents/` and `CLAUDE.md` are
generated from `.agent/adapters/targets/` and gitignored — edit `.agent/`, never
the output.

```bash
python tools/sync-agent-resources.py --prune
```
