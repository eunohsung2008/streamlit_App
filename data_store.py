"""Persistence layer for the 3-11 classroom website.

The deployed app uses Supabase. A SQLite implementation is included so the
project can be previewed locally before cloud credentials are configured.
"""

from __future__ import annotations

import base64
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")


class DataStoreError(RuntimeError):
    """Raised when a persistence operation cannot be completed."""


def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


class LocalStore:
    """SQLite-backed store for local previews and automated tests."""

    backend_name = "local"

    def __init__(self, db_path: str | Path = "data/classroom.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS notices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author_role TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    lookup_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT '접수',
                    reply TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS study_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    title TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    problem TEXT NOT NULL,
                    solution TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    author_alias TEXT NOT NULL DEFAULT '익명',
                    problem_image_url TEXT NOT NULL DEFAULT '',
                    problem_image_path TEXT NOT NULL DEFAULT '',
                    solution_image_url TEXT NOT NULL DEFAULT '',
                    solution_image_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_notices_created
                    ON notices(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_suggestions_created
                    ON suggestions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_study_created
                    ON study_posts(created_at DESC);
                """
            )

    def healthcheck(self) -> bool:
        with self._connect() as conn:
            return conn.execute("SELECT 1").fetchone()[0] == 1

    def add_notice(
        self, title: str, content: str, author_role: str, pinned: bool
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notices(title, content, author_role, pinned, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, content, author_role, int(pinned), now_iso()),
            )

    def list_notices(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM notices
                ORDER BY pinned DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_notice(self, notice_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM notices WHERE id = ?", (notice_id,))

    def add_suggestion(
        self,
        category: str,
        title: str,
        content: str,
        lookup_hash: str,
    ) -> None:
        timestamp = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO suggestions(
                    category, title, content, lookup_hash, status,
                    reply, created_at, updated_at
                ) VALUES (?, ?, ?, ?, '접수', '', ?, ?)
                """,
                (category, title, content, lookup_hash, timestamp, timestamp),
            )

    def get_suggestion_by_hash(self, lookup_hash: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM suggestions WHERE lookup_hash = ?",
                (lookup_hash,),
            ).fetchone()
        return dict(row) if row else None

    def list_suggestions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM suggestions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_suggestion(
        self, suggestion_id: int, status: str, reply: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE suggestions
                SET status = ?, reply = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, reply, now_iso(), suggestion_id),
            )

    def delete_suggestion(self, suggestion_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))

    def save_image(
        self, data: bytes, content_type: str, prefix: str
    ) -> tuple[str, str]:
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{content_type};base64,{encoded}", ""

    def add_study_post(self, post: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO study_posts(
                    subject, title, difficulty, problem, solution, source,
                    author_alias, problem_image_url, problem_image_path,
                    solution_image_url, solution_image_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post["subject"],
                    post["title"],
                    post["difficulty"],
                    post["problem"],
                    post["solution"],
                    post.get("source", ""),
                    post.get("author_alias", "익명"),
                    post.get("problem_image_url", ""),
                    post.get("problem_image_path", ""),
                    post.get("solution_image_url", ""),
                    post.get("solution_image_path", ""),
                    now_iso(),
                ),
            )

    def list_study_posts(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM study_posts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_study_post(self, post_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM study_posts WHERE id = ?", (post_id,))


class SupabaseStore:
    """Supabase-backed store used by the deployed Streamlit app."""

    backend_name = "supabase"

    def __init__(self, url: str, key: str, bucket: str = "study-images") -> None:
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise DataStoreError("supabase 패키지가 설치되어 있지 않습니다.") from exc

        self.client = create_client(url, key)
        self.bucket = bucket

    @staticmethod
    def _data(response: Any) -> list[dict[str, Any]]:
        return list(response.data or [])

    def healthcheck(self) -> bool:
        self.client.table("notices").select("id").limit(1).execute()
        return True

    def add_notice(
        self, title: str, content: str, author_role: str, pinned: bool
    ) -> None:
        self.client.table("notices").insert(
            {
                "title": title,
                "content": content,
                "author_role": author_role,
                "pinned": pinned,
            }
        ).execute()

    def list_notices(self, limit: int = 50) -> list[dict[str, Any]]:
        response = (
            self.client.table("notices")
            .select("*")
            .order("pinned", desc=True)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return self._data(response)

    def delete_notice(self, notice_id: int) -> None:
        self.client.table("notices").delete().eq("id", notice_id).execute()

    def add_suggestion(
        self,
        category: str,
        title: str,
        content: str,
        lookup_hash: str,
    ) -> None:
        self.client.table("suggestions").insert(
            {
                "category": category,
                "title": title,
                "content": content,
                "lookup_hash": lookup_hash,
            }
        ).execute()

    def get_suggestion_by_hash(self, lookup_hash: str) -> dict[str, Any] | None:
        response = (
            self.client.table("suggestions")
            .select("*")
            .eq("lookup_hash", lookup_hash)
            .limit(1)
            .execute()
        )
        rows = self._data(response)
        return rows[0] if rows else None

    def list_suggestions(self, limit: int = 200) -> list[dict[str, Any]]:
        response = (
            self.client.table("suggestions")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return self._data(response)

    def update_suggestion(
        self, suggestion_id: int, status: str, reply: str
    ) -> None:
        self.client.table("suggestions").update(
            {"status": status, "reply": reply, "updated_at": now_iso()}
        ).eq("id", suggestion_id).execute()

    def delete_suggestion(self, suggestion_id: int) -> None:
        self.client.table("suggestions").delete().eq("id", suggestion_id).execute()

    def save_image(
        self, data: bytes, content_type: str, prefix: str
    ) -> tuple[str, str]:
        path = f"{prefix}/{uuid4().hex}.webp"
        self.client.storage.from_(self.bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": content_type, "upsert": "false"},
        )
        public_url = self.client.storage.from_(self.bucket).get_public_url(path)
        return str(public_url), path

    def add_study_post(self, post: dict[str, Any]) -> None:
        payload = {
            "subject": post["subject"],
            "title": post["title"],
            "difficulty": post["difficulty"],
            "problem": post["problem"],
            "solution": post["solution"],
            "source": post.get("source", ""),
            "author_alias": post.get("author_alias", "익명"),
            "problem_image_url": post.get("problem_image_url", ""),
            "problem_image_path": post.get("problem_image_path", ""),
            "solution_image_url": post.get("solution_image_url", ""),
            "solution_image_path": post.get("solution_image_path", ""),
        }
        self.client.table("study_posts").insert(payload).execute()

    def list_study_posts(self, limit: int = 100) -> list[dict[str, Any]]:
        response = (
            self.client.table("study_posts")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return self._data(response)

    def delete_study_post(self, post_id: int) -> None:
        response = (
            self.client.table("study_posts")
            .select("problem_image_path, solution_image_path")
            .eq("id", post_id)
            .limit(1)
            .execute()
        )
        rows = self._data(response)
        if rows:
            paths = [
                value
                for value in (
                    rows[0].get("problem_image_path"),
                    rows[0].get("solution_image_path"),
                )
                if value
            ]
            if paths:
                try:
                    self.client.storage.from_(self.bucket).remove(paths)
                except Exception:
                    # The database post should still be removable if an old image
                    # was already deleted from Storage.
                    pass
        self.client.table("study_posts").delete().eq("id", post_id).execute()

