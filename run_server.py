from pathlib import Path
import argparse
import getpass
import sys

from app.db import init_db, get_conn
from app.security import hash_password

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "home_file_hub.db"

def initialize_admin():
    init_db(DB_PATH)
    with get_conn(DB_PATH) as conn:
        exists = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if exists:
            print("An admin account already exists.")
            return
        print("\nCreate the first Home File Hub administrator.")
        password = getpass.getpass("Admin password (minimum 12 characters): ")
        confirm = getpass.getpass("Confirm password: ")
        if len(password) < 12:
            print("Password must be at least 12 characters.")
            sys.exit(1)
        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)
        conn.execute(
            "INSERT INTO users(username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,datetime('now'))",
            ("admin", hash_password(password), "admin", 1),
        )
        conn.commit()
    print("Administrator created. Keep this password private.")

def main():
    parser = argparse.ArgumentParser(description="Home File Hub V3")
    parser.add_argument("--init-admin", action="store_true", help="Create the first administrator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    ROOT.joinpath("data").mkdir(exist_ok=True)
    init_db(DB_PATH)
    if args.init_admin:
        initialize_admin()
        return

    import uvicorn
    print("Home File Hub V3 starting")
    print(f"Database: {DB_PATH}")
    print(f"Listening on: http://{args.host}:{args.port}")
    print("Use Tailscale Serve for private HTTPS access. Do not expose this port publicly.")
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
