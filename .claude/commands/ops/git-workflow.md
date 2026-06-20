# /ops:git-workflow — Team Branching Guide

Two people working safely on Pipes.QA.
The rule: **never commit directly to `main` or `dev`**.
Always branch → work → PR → review → merge.

---

## Branch structure

```
main   ← stable, production-ready only
dev    ← shared integration branch (PR target)
feature/<name>   ← your working branch
```

---

## Starting new work (do this every time)

```bash
git checkout dev
git pull origin dev                        # get latest from teammate
git checkout -b feature/your-feature-name  # create your branch
```

Good branch names:
- `feature/lite-khomp-provider`
- `feature/dnc-bot-autostart`
- `fix/resume-progress-key`

---

## During work

```bash
git add <specific-files>     # never: git add .
git commit -m "what and why"
git push origin feature/your-feature-name
```

---

## Done — open a Pull Request

On GitHub: **feature/your-feature-name → dev**
The other person reviews before it merges.
Never merge your own PR without the other person seeing it.

---

## After teammate merges to dev

```bash
git checkout dev
git pull origin dev    # get their changes
uv sync               # if pyproject.toml changed
```

---

## Merging dev → main (releases only)

Only when dev is fully tested and stable:
```bash
git checkout main
git pull origin main
git merge dev
git push origin main
```

---

## Golden rules

| Rule | Why |
|------|-----|
| Always `git pull origin dev` before starting | Avoid conflicts |
| One branch per feature | Keeps changes isolated |
| Never edit `.env` in git | Credentials stay local |
| Run `uv sync` after pulling if `pyproject.toml` changed | Get new packages |
| PR to `dev`, not direct push | Someone reviews first |
| Never force-push to `main` or `dev` | Protects shared history |

---

## If you get a merge conflict

```bash
git checkout dev
git pull origin dev
git checkout feature/your-branch
git merge dev              # pull dev into your branch
# fix conflicts in VS Code, then:
git add <resolved-files>
git commit -m "merge dev into feature branch"
git push origin feature/your-branch
```

---

## Quick reference

```bash
# Where am I?
git status
git branch

# What changed?
git log --oneline -10
git diff

# Undo last commit (keep changes)
git reset HEAD~1
```
