# Local Setup (Phase 0)

Run these in VS Code's integrated terminal (Terminal > New Terminal), with this folder open. One-time setup.

## 1. Confirm Python + git are installed

```
py --version
git --version
```

Note: on this machine, plain `python` sometimes hits a Microsoft Store stub instead of the real install. Use `py` instead of `python` for every command below — it reliably finds the real interpreter, and it also correctly respects an activated venv.

## 2. Create and activate a virtual environment

A venv has to be created locally (it's OS-specific — one built in a sandbox won't run on your machine).

```
py -m venv venv
```

Activate it (PowerShell):
```
.\venv\Scripts\Activate.ps1
```
(If PowerShell blocks the script, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.)

Or Command Prompt:
```
venv\Scripts\activate.bat
```

You'll know it worked because your terminal prompt gets a `(venv)` prefix.

## 3. Install dependencies

```
py -m pip install -r requirements.txt
```

Sanity check it worked:
```
py -c "import pandas, requests, nfl_data_py; print('ok')"
```

## 4. Initialize git

(I tried to do this step from my end but the connection between Cowork and this folder doesn't support git's file-locking operations reliably — this one's quick to run yourself.)

```
git init -b main
git add -A
git commit -m "chore: initial project scaffold (docs, folder structure, gitignore, requirements)"
```

## 5. Connect to GitHub

1. On github.com, create a **new empty repository** (no README/.gitignore/license — we already have those).
2. Copy the repo URL it gives you, then:

```
git remote add origin <the-url-you-copied>
git branch -M main
git push -u origin main
```

## 6. Request FantasyPros API access

Takes a few days to get approved, so start it now even though we don't need it until Phase 1:
https://support.fantasypros.com/hc/en-us/articles/49749297704475-How-do-I-request-access-to-the-FantasyPros-API

## 7. Create your `.env` file

In the project root, create a file named `.env` (already gitignored, will never get committed):

```
ANTHROPIC_API_KEY=your-key-here
```

We'll add FantasyPros' key here too once it's approved.

---

Once all 7 are done, Phase 0 is complete and we can start Phase 1 (data ingest scripts).
