"""3단계: SQLite 기반 사용자/프로필/레시피 저장 및 인증 유틸.

추가 의존성 없이 표준 라이브러리(sqlite3, hashlib, secrets)만 사용한다.
- 비밀번호: PBKDF2-HMAC-SHA256 (솔트 포함) 해시로 저장, 평문 저장 안 함.
- 세션: 랜덤 토큰을 sessions 테이블에 저장, Authorization: Bearer <token> 로 인증.
"""
import hashlib
import json
import secrets
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "app.db"
PBKDF2_ITERATIONS = 200_000


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """테이블이 없으면 생성."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nickname TEXT NOT NULL,
                diet TEXT DEFAULT 'none',
                allergies TEXT DEFAULT '[]',          -- JSON 배열 문자열
                default_servings INTEGER DEFAULT 2,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                data TEXT NOT NULL,                    -- 레시피 전체 JSON
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


# --- 비밀번호 해시 ---
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS)
    return secrets.compare_digest(dk.hex(), hash_hex)


# --- 사용자 / 세션 ---
def create_user(email: str, password: str, nickname: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, nickname) VALUES (?, ?, ?)",
            (email, hash_password(password), nickname),
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    with get_conn() as conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    return token


def delete_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def user_for_token(token: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT u.* FROM users u
            JOIN sessions s ON s.user_id = u.id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()


# --- 프로필 ---
def update_profile(user_id: int, diet: str, allergies: list[str], default_servings: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET diet = ?, allergies = ?, default_servings = ? WHERE id = ?",
            (diet, json.dumps(allergies, ensure_ascii=False), default_servings, user_id),
        )


# --- 레시피 ---
def save_recipe(user_id: int, recipe: dict) -> sqlite3.Row:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO recipes (user_id, title, data) VALUES (?, ?, ?)",
            (user_id, recipe.get("title", "무제"), json.dumps(recipe, ensure_ascii=False)),
        )
        rid = cur.lastrowid
        return conn.execute("SELECT * FROM recipes WHERE id = ?", (rid,)).fetchone()


def list_recipes(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM recipes WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()


def delete_recipe(user_id: int, recipe_id: int) -> bool:
    """본인 소유 레시피만 삭제. 삭제되면 True."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, user_id)
        )
        return cur.rowcount > 0
