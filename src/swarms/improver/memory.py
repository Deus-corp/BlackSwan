from __future__ import annotations

import dataclasses
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.swarms.improver.models import ImprovementResult, MemoryHit
from src.swarms.improver.validation import fingerprint_text


class MemoryStore:
    """
    Persistent memory layer for the ImproverAgent, based on SQLite.

    Stores:
    - episodes of improvement attempts
    - success/failure patterns
    - file-specific history
    - strategy performance stats

    Retrieval prefers FTS5 when available and falls back to a robust token search
    with recency and score weighting.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = False
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA wal_autocheckpoint=1000;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    original_path TEXT NOT NULL,
                    proposed_path TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    summary TEXT DEFAULT '',
                    critique TEXT DEFAULT '',
                    risk REAL DEFAULT 0.0,
                    score REAL DEFAULT 0.0,
                    success INTEGER DEFAULT NULL,
                    validation_json TEXT DEFAULT '{}',
                    tags_json TEXT DEFAULT '[]',
                    fingerprint TEXT DEFAULT '',
                    meta_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    pattern_key TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_score REAL DEFAULT 0.0,
                    extra_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS file_stats (
                    path TEXT PRIMARY KEY,
                    ts INTEGER NOT NULL,
                    fingerprint TEXT DEFAULT '',
                    last_score REAL DEFAULT 0.0,
                    successful_edits INTEGER NOT NULL DEFAULT 0,
                    failed_edits INTEGER NOT NULL DEFAULT 0,
                    total_edits INTEGER NOT NULL DEFAULT 0,
                    last_strategy TEXT DEFAULT '',
                    meta_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS strategy_stats (
                    strategy TEXT PRIMARY KEY,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    total_score REAL NOT NULL DEFAULT 0.0,
                    last_used_ts INTEGER NOT NULL DEFAULT 0,
                    last_success_ts INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(ts);
                CREATE INDEX IF NOT EXISTS idx_episodes_strategy ON episodes(strategy);
                CREATE INDEX IF NOT EXISTS idx_patterns_ts ON patterns(ts);
                CREATE INDEX IF NOT EXISTS idx_file_stats_ts ON file_stats(ts);
                """
            )

            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
                    USING fts5(
                        original_path,
                        proposed_path,
                        strategy,
                        summary,
                        critique,
                        tags_json,
                        validation_json,
                        content='',
                        tokenize='porter'
                    )
                    """
                )
                self._fts_available = True
            except sqlite3.OperationalError:
                self._fts_available = False

            conn.commit()

    def get_file_fingerprint(self, path: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT fingerprint FROM file_stats WHERE path = ?", (path,)).fetchone()
        return row["fingerprint"] if row and row["fingerprint"] else None

    def _episode_meta(self, result: ImprovementResult) -> Dict[str, Any]:
        return {
            "changed_lines_ratio": result.changed_lines_ratio,
            "strategy": result.strategy,
            "memory_tags": list(result.memory_tags),
            "fallback_used": result.fallback_used,
            "validation": dataclasses.asdict(result.validation),
        }

    def record_episode(self, result: ImprovementResult) -> None:
        success = bool(
            result.validation.syntactically_valid
            and result.validation.compile_ok
            and (result.score >= 15.0)
            and ("changed_too_much" not in result.validation.notes)
        )
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO episodes (
                    ts, original_path, proposed_path, strategy, summary,
                    critique, risk, score, success, validation_json, tags_json,
                    fingerprint, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(time.time()),
                    result.original_path,
                    result.proposed_path,
                    result.strategy,
                    result.summary or "",
                    result.critique or "",
                    float(result.risk),
                    float(result.score),
                    1 if success else 0,
                    json.dumps(dataclasses.asdict(result.validation), ensure_ascii=False),
                    json.dumps(result.memory_tags, ensure_ascii=False),
                    fingerprint_text(result.code),
                    json.dumps(self._episode_meta(result), ensure_ascii=False),
                ),
            )
            episode_id = cur.lastrowid
            if self._fts_available:
                conn.execute(
                    """
                    INSERT INTO episodes_fts (
                        rowid, original_path, proposed_path, strategy, summary,
                        critique, tags_json, validation_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode_id,
                        result.original_path,
                        result.proposed_path,
                        result.strategy,
                        result.summary or "",
                        result.critique or "",
                        json.dumps(result.memory_tags, ensure_ascii=False),
                        json.dumps(dataclasses.asdict(result.validation), ensure_ascii=False),
                    ),
                )
            conn.commit()

    def record_pattern(
        self,
        pattern_key: str,
        description: str,
        score: float,
        success: bool,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT pattern_key FROM patterns WHERE pattern_key = ?", (pattern_key,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO patterns (ts, pattern_key, description, success_count, failure_count, last_score, extra_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(time.time()),
                        pattern_key,
                        description,
                        1 if success else 0,
                        0 if success else 1,
                        float(score),
                        json.dumps(extra or {}, ensure_ascii=False),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE patterns
                    SET ts = ?, description = ?,
                        success_count = success_count + ?,
                        failure_count = failure_count + ?,
                        last_score = ?,
                        extra_json = ?
                    WHERE pattern_key = ?
                    """,
                    (
                        int(time.time()),
                        description,
                        1 if success else 0,
                        0 if success else 1,
                        float(score),
                        json.dumps(extra or {}, ensure_ascii=False),
                        pattern_key,
                    ),
                )
            conn.commit()

    def record_file_outcome(
        self,
        path: str,
        score: float,
        success: bool,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        fingerprint = meta.get("new_fingerprint") if meta else None
        with self._connect() as conn:
            row = conn.execute("SELECT path FROM file_stats WHERE path = ?", (path,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO file_stats (
                        path, ts, fingerprint, last_score,
                        successful_edits, failed_edits, total_edits,
                        last_strategy, meta_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        path,
                        int(time.time()),
                        fingerprint,
                        float(score),
                        1 if success else 0,
                        0 if success else 1,
                        1,
                        str(meta.get("strategy", "")) if meta else "",
                        json.dumps(meta or {}, ensure_ascii=False),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE file_stats
                    SET ts = ?, fingerprint = ?, last_score = ?,
                        successful_edits = successful_edits + ?,
                        failed_edits = failed_edits + ?,
                        total_edits = total_edits + 1,
                        last_strategy = ?,
                        meta_json = ?
                    WHERE path = ?
                    """,
                    (
                        int(time.time()),
                        fingerprint,
                        float(score),
                        1 if success else 0,
                        0 if success else 1,
                        str(meta.get("strategy", "")) if meta else "",
                        json.dumps(meta or {}, ensure_ascii=False),
                        path,
                    ),
                )
            conn.commit()

    def record_strategy_outcome(self, strategy: str, score: float, success: bool) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT strategy FROM strategy_stats WHERE strategy = ?", (strategy,)).fetchone()
            now = int(time.time())
            if row is None:
                conn.execute(
                    """
                    INSERT INTO strategy_stats (
                        strategy, success_count, failure_count, total_score,
                        last_used_ts, last_success_ts
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        strategy,
                        1 if success else 0,
                        0 if success else 1,
                        float(score),
                        now,
                        now if success else 0,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE strategy_stats
                    SET success_count = success_count + ?,
                        failure_count = failure_count + ?,
                        total_score = total_score + ?,
                        last_used_ts = ?,
                        last_success_ts = CASE WHEN ? = 1 THEN ? ELSE last_success_ts END
                    WHERE strategy = ?
                    """,
                    (
                        1 if success else 0,
                        0 if success else 1,
                        float(score),
                        now,
                        1 if success else 0,
                        now,
                        strategy,
                    ),
                )
            conn.commit()

    def _fallback_search(self, query: str, limit: int) -> List[MemoryHit]:
        tokens = [t for t in re.split(r"\W+", query.lower()) if t and len(t) > 1]
        if not tokens:
            return []

        hits: List[MemoryHit] = []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM episodes
                ORDER BY ts DESC
                LIMIT 500
                """
            ).fetchall()

        now = time.time()
        for row in rows:
            haystack = " ".join(
                [
                    str(row["original_path"] or ""),
                    str(row["proposed_path"] or ""),
                    str(row["strategy"] or ""),
                    str(row["summary"] or ""),
                    str(row["critique"] or ""),
                    str(row["tags_json"] or ""),
                    str(row["validation_json"] or ""),
                    str(row["meta_json"] or ""),
                ]
            ).lower()

            token_hits = sum(1 for t in tokens if t in haystack)
            if token_hits == 0:
                continue

            age_seconds = max(0.0, now - float(row["ts"] or now))
            recency_bonus = 1.0 / (1.0 + age_seconds / 86_400.0)
            score = float(token_hits) + recency_bonus + min(float(row["score"] or 0.0) / 20.0, 2.0)
            if int(row["success"] or 0) == 1:
                score += 0.5

            hits.append(MemoryHit(kind="episode", score=score, payload=dict(row)))

        hits.sort(key=lambda h: (h.score, h.payload.get("ts", 0)), reverse=True)
        return hits[:limit]

    def _fts_search(self, query: str, limit: int) -> List[MemoryHit]:
        if not self._fts_available:
            return self._fallback_search(query, limit)

        tokens = [t for t in re.split(r"\W+", query.lower()) if t and len(t) > 1]
        if not tokens:
            return []

        fts_query = " ".join(f"{token}*" for token in tokens[:12])

        hits: List[MemoryHit] = []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    e.*,
                    bm25(episodes_fts) AS fts_rank
                FROM episodes_fts
                JOIN episodes e ON e.id = episodes_fts.rowid
                WHERE episodes_fts MATCH ?
                ORDER BY fts_rank ASC, e.ts DESC
                LIMIT ?
                """,
                (fts_query, limit * 4),
            ).fetchall()

        now = time.time()
        for row in rows:
            age_seconds = max(0.0, now - float(row["ts"] or now))
            recency_bonus = 1.0 / (1.0 + age_seconds / 86_400.0)
            fts_rank = float(row["fts_rank"] or 0.0)
            score = (3.0 / (1.0 + max(0.0, fts_rank))) + recency_bonus + min(float(row["score"] or 0.0) / 25.0, 2.0)
            if int(row["success"] or 0) == 1:
                score += 0.5

            hits.append(MemoryHit(kind="episode", score=score, payload=dict(row)))

        hits.sort(key=lambda h: (h.score, h.payload.get("ts", 0)), reverse=True)
        return hits[:limit]

    def search_episodes(self, query: str, limit: int = 5) -> List[MemoryHit]:
        return self._fts_search(query, limit)

    def get_strategy_stats(self) -> Dict[str, Dict[str, float]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM strategy_stats").fetchall()

        out: Dict[str, Dict[str, float]] = {}
        for row in rows:
            success_count = int(row["success_count"])
            failure_count = int(row["failure_count"])
            total = success_count + failure_count
            total_score = float(row["total_score"])
            out[row["strategy"]] = {
                "success_count": float(success_count),
                "failure_count": float(failure_count),
                "total": float(total),
                "avg_score": total_score / max(1.0, float(total)),
                "last_used_ts": float(row["last_used_ts"]),
                "last_success_ts": float(row["last_success_ts"] if "last_success_ts" in row.keys() else 0),
            }
        return out

    def get_recent_success_patterns(self, limit: int = 8) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM patterns
                ORDER BY (success_count - failure_count) DESC, last_score DESC, ts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_failure_patterns(self, limit: int = 8) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM patterns
                ORDER BY (failure_count - success_count) DESC, last_score ASC, ts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_file_history(self, path: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM file_stats WHERE path = ?", (path,)).fetchone()
        return dict(row) if row else None
