# Publishing Home File Hub V3 to GitHub

This guide assumes you have reviewed the project and created a new, empty GitHub repository.

## 1. Prepare a clean project folder

Keep the application source and documentation, for example:

```text
HomeFileHub_V3/
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── main.py
│   ├── security.py
│   └── static/
│       └── index.html
├── run_server.py
├── requirements.txt
├── README.md
├── SECURITY.md
└── .gitignore
```

Do not copy `.venv/`, `data/`, SQLite database files, logs, backups or credentials into the public repository. Keep your full local backup separately.

Replace the project's existing `.gitignore` with the provided GitHub-ready `.gitignore`.

## 2. Create the GitHub repository

1. Sign in at https://github.com/.
2. Select **New repository**.
3. Enter a repository name, such as `Home-File-Hub-V3`.
4. Add a short description, such as `A self-hosted Windows file hub with FastAPI, SQLite and private Tailscale access.`
5. Choose **Public** only if you are comfortable making the source code public. Otherwise choose **Private**.
6. Do not initialize it with a README, license or `.gitignore` if you already have those files locally.
7. Create the repository.

## 3. Upload with GitHub Desktop (recommended for beginners)

1. Install GitHub Desktop from https://desktop.github.com/.
2. Sign in to your GitHub account.
3. Choose **File → Add Local Repository** if your cleaned project folder is already a Git repository; otherwise choose **File → New Repository** and set the local path to the cleaned project folder.
4. Review the changed files. Confirm that `.venv/`, `data/`, database files and secrets are not listed.
5. Enter a commit summary such as `Initial public release of Home File Hub V3`.
6. Select **Commit to main**.
7. Select **Publish repository** and choose Public or Private.
8. Visit the repository on GitHub and check that the README renders correctly.

## 4. Upload with Git commands (alternative)

Open PowerShell in the cleaned project folder:

```powershell
git init
git add .
git status
```

**Stop here and inspect the staged file list.** If you see `.venv`, `data`, `*.db`, logs or secrets, fix `.gitignore` and unstage/remove those files before continuing.

Then:

```powershell
git commit -m "Initial release: Home File Hub V3"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/Home-File-Hub-V3.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username and use the exact repository URL shown by GitHub.

## 5. Final repository check

On GitHub, verify:

- README describes only features that exist in the code.
- `requirements.txt` is present.
- `.gitignore` is present.
- No database, virtual environment, credentials, logs or private paths were uploaded.
- The repository visibility is what you intended.
- A license is added only if you have chosen one.

## Important

The complete ZIP supplied for private inspection is not the file to publish. It includes the local virtual environment and database. Publish a cleaned source-only project folder instead.
