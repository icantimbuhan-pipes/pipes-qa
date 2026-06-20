# /ops:push — Save and push your work

Run this skill whenever you want to save your work and push it to GitHub.

---

## Step 1 — Check where you are

```bash
git status
git branch
```

Tell the user:
- What branch they're on
- What files have changed (modified/untracked)

---

## Step 2 — If they are on `main` or `dev` directly

Warn them:
```
⚠️  You are on 'dev' (or 'main') directly.
You should work on a feature branch to stay safe.

Run this first:
  git checkout -b feature/your-feature-name

Then come back and run /ops:push again.
```

Stop here and wait for them to create a branch.

---

## Step 3 — If they are on a feature branch, stage and commit

Ask: **"What did you work on? (one short sentence)"**

Use their answer as the commit message. Then run:

```bash
git add <only the files that changed — list them specifically, never git add .>
git commit -m "<their answer>"
git push origin <current-branch>
```

Show the output so they can see it worked.

---

## Step 4 — Remind them to open a PR

```
✅ Pushed to GitHub.

Next step: open a Pull Request on GitHub
  feature/<your-branch>  →  dev

URL: https://github.com/icantimbuhan-pipes/pipes-qa/pulls
Ask your teammate to review before merging.
```

---

## Starting fresh (new day, new task)

If the user says they want to start new work (not push existing work), run:

```bash
git checkout dev
git pull origin dev
```

Then ask: **"What are you working on today?"**
Use their answer to create a branch name (lowercase, dashes):

```bash
git checkout -b feature/<kebab-case-name>
```

Confirm:
```
✅ Ready. You are now on feature/<name>.
Do your work, then run /ops:push when done.
```
