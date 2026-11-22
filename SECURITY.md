# Security Notes

Home File Hub V3 is a development/foundation project and has not undergone an independent security audit. Use it only in a controlled environment and with folders you intentionally choose to share.

## Before publishing to GitHub

Never commit or publish:

- `data/` or any SQLite database, including `*.db`, `*.db-wal` and `*.db-shm`
- `.venv/`, `venv/`, Python bytecode or compiled extension files
- Passwords, API keys, session cookies, CSRF tokens or other credentials
- Logs, backups, exports or screenshots containing private account information
- Machine-specific absolute paths if they disclose information you do not want public

If a real credential or token has ever been committed, removing it in a later commit is not enough. Revoke or rotate it, then follow GitHub's guidance for removing sensitive data from repository history.

## Network exposure

- Keep the application bound to `127.0.0.1` when using Tailscale Serve.
- Use the HTTPS URL provided by Tailscale Serve.
- Do not use Tailscale Funnel or public router port forwarding for this project.
- Do not bind to `0.0.0.0` unless you have deliberately designed and secured the network exposure.

## Storage boundaries

Only configure directories that should be available to authenticated Home File Hub users. Do not add the whole Windows system drive as a convenience. Use a separate non-admin test account and verify its permissions before sharing important data.

## Operational cautions

- Back up the database before upgrades.
- Stop the application before manually copying its SQLite database, or use a SQLite-consistent backup procedure.
- Use unique passwords and protect the Windows host account.
- Review code changes and test them with non-sensitive sample files before using important data.
