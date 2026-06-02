#!/bin/bash
# ApplyKit — commit all changes and push to GitHub
# Run from the applykit project root:
#   cd /path/to/applykit && bash commit_and_push.sh

set -e

echo "=== Removing stale git lock ==="
rm -f .git/index.lock

echo "=== Staging all changes ==="
git add -A

echo "=== Changes to be committed ==="
git status --short

echo ""
echo "=== Committing ==="
git commit -m "feat: overnight pipeline v1, scoring config, feedback loop, review scripts

New files:
- config/defaults.yml: tracked scoring dimensions (9 dims, no gov_adjacency, location 10%)
- scripts/read_scores.py: read evaluations + feedback as JSON (immutable DB mode)
- scripts/write_feedback.py: persist feedback (copy-to-tmp write pattern for mount safety)
- output/.gitkeep: output directory for generated morning briefs

Modified:
- applykit/config.py: deep-merge defaults.yml -> config.yml via load_config()
- .gitignore: added output/*.html, output/*.json, *.db-journal
- All prior session changes: full applykit package, tests, docs, skill files

Removed:
- launch-skill/ (superseded by skill/)"

echo ""
echo "=== Pushing ==="
git push origin main

echo ""
echo "=== Done ==="
git log --oneline -3
