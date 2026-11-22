from pathlib import Path
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .db import get_conn, init_db
from .security import verify_password, new_session, hash_token, hash_password

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "home_file_hub.db"
COOKIE_NAME = "hfh_session"
SESSION_SECONDS = 8 * 60 * 60

app = FastAPI(title="Home File Hub V3", version="3.0.0")
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")

@app.on_event("startup")
def startup():
    init_db(DB_PATH)

class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

class UserBody(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern=r"^(admin|editor|viewer|custom)$")

class StorageBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    path: str = Field(min_length=1, max_length=1024)

class PermissionBody(BaseModel):
    user_id: int
    can_list: bool = False
    can_download: bool = False
    can_upload: bool = False
    can_rename: bool = False
    can_delete: bool = False

def log_action(conn, user_id, action, target=""):
    conn.execute(
        "INSERT INTO activity_logs(user_id,action,target,created_at) VALUES(?,?,?,datetime('now'))",
        (user_id, action, target),
    )

def current_user(request: Request):
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(401, "Please sign in")
    with get_conn(DB_PATH) as conn:
        row = conn.execute("""
            SELECT u.id,u.username,u.role,u.is_active,s.csrf_token,s.expires_at
            FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token_hash=?
        """, (hash_token(raw),)).fetchone()
        if not row or not row["is_active"] or row["expires_at"] < int(time.time()):
            raise HTTPException(401, "Session expired. Please sign in again.")
        return dict(row)

def require_csrf(request: Request, user=Depends(current_user)):
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not secrets_compare(supplied, user["csrf_token"]):
        raise HTTPException(403, "CSRF validation failed")
    return user

def secrets_compare(a, b):
    import hmac
    return hmac.compare_digest(a, b)

def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator permission required")
    return user

def effective_permissions(conn, user, storage_id):
    # Fail closed: non-admin users receive no storage access until an
    # administrator explicitly assigns permissions for this location.
    if user["role"] == "admin":
        return dict(can_list=1, can_download=1, can_upload=1, can_rename=1, can_delete=1)
    row = conn.execute(
        "SELECT can_list, can_download, can_upload, can_rename, can_delete "
        "FROM folder_permissions WHERE user_id=? AND storage_id=?",
        (user["id"], storage_id),
    ).fetchone()
    if row:
        return dict(row)
    return dict(can_list=0, can_download=0, can_upload=0, can_rename=0, can_delete=0)

def authorized_storage(conn, user, storage_id, permission="can_list"):
    loc = conn.execute(
        "SELECT * FROM storage_locations WHERE id=? AND is_active=1", (storage_id,)
    ).fetchone()
    if not loc:
        raise HTTPException(404, "Storage location not found")
    perms = effective_permissions(conn, user, storage_id)
    if not perms.get(permission):
        raise HTTPException(403, "You do not have permission for this storage location")
    root = Path(loc["root_path"]).resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(409, "Configured storage folder is unavailable")
    return loc, root

def safe_child(root: Path, relative: str) -> Path:
    relative = (relative or "").replace("\\", "/")
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(400, "Invalid path")
    return candidate

@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/health")
def health():
    return {"status": "ok", "app": "Home File Hub", "version": "3.0.0"}

@app.post("/api/login")
def login(body: LoginBody, response: Response):
    with get_conn(DB_PATH) as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1", (body.username,)
        ).fetchone()
        if not user or not verify_password(user["password_hash"], body.password):
            raise HTTPException(401, "Incorrect username or password")
        raw, token_hash, csrf, expires_at = new_session()
        conn.execute(
            "INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES(?,?,?,?)",
            (token_hash, user["id"], csrf, expires_at),
        )
        log_action(conn, user["id"], "login", "web")
        conn.commit()
    response.set_cookie(
        COOKIE_NAME, raw, max_age=SESSION_SECONDS, httponly=True,
        secure=True, samesite="strict", path="/"
    )
    return {"ok": True, "username": user["username"], "role": user["role"], "csrf_token": csrf}

@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"id": user["id"], "username": user["username"], "role": user["role"],
            "csrf_token": user["csrf_token"]}

@app.post("/api/logout")
def logout(request: Request, response: Response, user=Depends(require_csrf)):
    raw = request.cookies.get(COOKIE_NAME, "")
    with get_conn(DB_PATH) as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (hash_token(raw),))
        log_action(conn, user["id"], "logout", "web")
        conn.commit()
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return {"ok": True}

@app.get("/api/users")
def list_users(user=Depends(require_admin)):
    with get_conn(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id,username,role,is_active,created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/users")
def create_user(body: UserBody, user=Depends(require_csrf)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator permission required")
    with get_conn(DB_PATH) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users(username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,datetime('now'))",
                (body.username, hash_password(body.password), body.role, 1),
            )
            log_action(conn, user["id"], "user_created", body.username)
            conn.commit()
            return {"id": cur.lastrowid, "username": body.username, "role": body.role}
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise HTTPException(409, "Username already exists")
            raise

@app.patch("/api/users/{user_id}/active")
def set_user_active(user_id: int, active: bool, user=Depends(require_csrf)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator permission required")
    if user_id == user["id"] and not active:
        raise HTTPException(400, "You cannot disable your own administrator account")
    with get_conn(DB_PATH) as conn:
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (1 if active else 0, user_id))
        if not active:
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        log_action(conn, user["id"], "user_status_changed", str(user_id))
        conn.commit()
    return {"ok": True}

@app.get("/api/storage")
def list_storage(user=Depends(current_user)):
    with get_conn(DB_PATH) as conn:
        rows = conn.execute("SELECT * FROM storage_locations WHERE is_active=1 ORDER BY name").fetchall()
        result = []
        for row in rows:
            perms = effective_permissions(conn, user, row["id"])
            if perms.get("can_list"):
                result.append({"id": row["id"], "name": row["name"], "path": row["root_path"],
                               "permissions": {k: bool(perms.get(k)) for k in
                                ("can_list","can_download","can_upload","can_rename","can_delete")}})
    return result

@app.post("/api/storage")
def add_storage(body: StorageBody, user=Depends(require_csrf)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator permission required")
    path = Path(body.path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except Exception:
        raise HTTPException(400, "Folder path does not exist")
    if not resolved.is_dir():
        raise HTTPException(400, "Storage path must be a folder")
    with get_conn(DB_PATH) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO storage_locations(name,root_path,is_active,created_at) VALUES(?,?,1,datetime('now'))",
                (body.name, str(resolved)),
            )
            log_action(conn, user["id"], "storage_added", body.name)
            conn.commit()
            return {"id": cur.lastrowid, "name": body.name, "path": str(resolved)}
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise HTTPException(409, "A storage location with that name already exists")
            raise

@app.post("/api/storage/{storage_id}/permissions")
def set_permissions(storage_id: int, body: PermissionBody, user=Depends(require_csrf)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator permission required")
    with get_conn(DB_PATH) as conn:
        if not conn.execute("SELECT id FROM storage_locations WHERE id=?", (storage_id,)).fetchone():
            raise HTTPException(404, "Storage location not found")
        if not conn.execute("SELECT id FROM users WHERE id=?", (body.user_id,)).fetchone():
            raise HTTPException(404, "User not found")
        conn.execute("""
            INSERT INTO folder_permissions(user_id,storage_id,can_list,can_download,can_upload,can_rename,can_delete)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(user_id,storage_id) DO UPDATE SET
            can_list=excluded.can_list,can_download=excluded.can_download,
            can_upload=excluded.can_upload,can_rename=excluded.can_rename,can_delete=excluded.can_delete
        """, (body.user_id, storage_id, int(body.can_list), int(body.can_download),
              int(body.can_upload), int(body.can_rename), int(body.can_delete)))
        log_action(conn, user["id"], "permissions_updated", f"storage:{storage_id},user:{body.user_id}")
        conn.commit()
    return {"ok": True}

@app.get("/api/files")
def list_files(storage_id: int, path: str = "", user=Depends(current_user)):
    with get_conn(DB_PATH) as conn:
        loc, root = authorized_storage(conn, user, storage_id, "can_list")
        folder = safe_child(root, path)
        if not folder.is_dir():
            raise HTTPException(404, "Folder not found")
        items = []
        for p in sorted(folder.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                resolved = p.resolve()
                if resolved != root and root not in resolved.parents:
                    continue
                stat = p.stat()
                items.append({"name": p.name, "is_dir": p.is_dir(),
                              "size": None if p.is_dir() else stat.st_size})
            except OSError:
                continue
        return {"location": loc["name"], "path": path, "items": items}

@app.post("/api/files/upload")
async def upload_file(storage_id: int = Form(...), path: str = Form(""),
                      file: UploadFile = File(...), user=Depends(current_user)):
    with get_conn(DB_PATH) as conn:
        loc, root = authorized_storage(conn, user, storage_id, "can_upload")
        folder = safe_child(root, path)
        if not folder.is_dir():
            raise HTTPException(404, "Destination folder not found")
        name = Path(file.filename or "").name
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise HTTPException(400, "Invalid filename")
        target = safe_child(root, f"{path}/{name}" if path else name)
        if target.exists():
            raise HTTPException(409, "A file with that name already exists")
        written = 0
        try:
            with target.open("xb") as out:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > 2 * 1024 * 1024 * 1024:
                        raise HTTPException(413, "File exceeds the 2 GB upload limit")
                    out.write(chunk)
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        log_action(conn, user["id"], "file_uploaded", f"{loc['name']}/{path}/{name}")
        conn.commit()
    return {"ok": True, "filename": name, "bytes": written}

@app.get("/api/files/download")
def download_file(storage_id: int, path: str, user=Depends(current_user)):
    with get_conn(DB_PATH) as conn:
        loc, root = authorized_storage(conn, user, storage_id, "can_download")
        target = safe_child(root, path)
        if not target.is_file():
            raise HTTPException(404, "File not found")
        log_action(conn, user["id"], "file_downloaded", f"{loc['name']}/{path}")
        conn.commit()
    return FileResponse(target, filename=target.name)

@app.get("/api/activity")
def activity(limit: int = 100, user=Depends(require_admin)):
    limit = max(1, min(limit, 500))
    with get_conn(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT a.id,u.username,a.action,a.target,a.created_at
            FROM activity_logs a LEFT JOIN users u ON u.id=a.user_id
            ORDER BY a.id DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]
