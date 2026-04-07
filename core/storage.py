"""
Storage - SQLite database layer for macros and history
"""
import sqlite3
import json
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field, asdict


DB_PATH = Path.home() / ".automate_anything" / "macros.db"


@dataclass
class MacroAction:
    type: str                    # click_image | type_text | wait | scroll | key_press
    params: dict = field(default_factory=dict)
    # type-specific:
    # click_image: {image_b64, confidence, fallback_coords, retry_count}
    # type_text:   {text, delay_between_keys}
    # wait:        {seconds}
    # scroll:      {direction, amount, x, y}
    # key_press:   {keys}  e.g. ["ctrl","c"]

    def to_dict(self) -> dict:
        return {"type": self.type, "params": self.params}

    @classmethod
    def from_dict(cls, d: dict) -> "MacroAction":
        return cls(type=d["type"], params=d.get("params", {}))


@dataclass
class Macro:
    id: Optional[int]
    name: str
    prompt: str
    summary: str
    actions: List[MacroAction]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def actions_to_json(self) -> str:
        return json.dumps([a.to_dict() for a in self.actions])

    @classmethod
    def from_row(cls, row: tuple) -> "Macro":
        id_, name, prompt, summary, actions_json, created_at, updated_at = row
        actions = [MacroAction.from_dict(d) for d in json.loads(actions_json)]
        return cls(
            id=id_,
            name=name,
            prompt=prompt,
            summary=summary,
            actions=actions,
            created_at=created_at,
            updated_at=updated_at,
        )


class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS macros (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                prompt      TEXT NOT NULL,
                summary     TEXT NOT NULL DEFAULT '',
                actions     TEXT NOT NULL DEFAULT '[]',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS run_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                macro_id    INTEGER NOT NULL,
                ran_at      REAL NOT NULL,
                success     INTEGER NOT NULL DEFAULT 1,
                error_msg   TEXT,
                FOREIGN KEY(macro_id) REFERENCES macros(id) ON DELETE CASCADE
            )
        """)
        conn.commit()

    def save_macro(self, macro: Macro) -> Macro:
        conn = self._get_conn()
        now = time.time()
        if macro.id is None:
            cur = conn.execute(
                "INSERT INTO macros (name, prompt, summary, actions, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (macro.name, macro.prompt, macro.summary, macro.actions_to_json(), now, now),
            )
            macro.id = cur.lastrowid
        else:
            macro.updated_at = now
            conn.execute(
                "UPDATE macros SET name=?, prompt=?, summary=?, actions=?, updated_at=? WHERE id=?",
                (macro.name, macro.prompt, macro.summary, macro.actions_to_json(), now, macro.id),
            )
        conn.commit()
        return macro

    def list_macros(self) -> List[Macro]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, name, prompt, summary, actions, created_at, updated_at FROM macros ORDER BY updated_at DESC"
        ).fetchall()
        return [Macro.from_row(tuple(r)) for r in rows]

    def get_macro(self, macro_id: int) -> Optional[Macro]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, name, prompt, summary, actions, created_at, updated_at FROM macros WHERE id=?",
            (macro_id,),
        ).fetchone()
        return Macro.from_row(tuple(row)) if row else None

    def delete_macro(self, macro_id: int):
        conn = self._get_conn()
        conn.execute("DELETE FROM macros WHERE id=?", (macro_id,))
        conn.commit()

    def log_run(self, macro_id: int, success: bool, error_msg: str = ""):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO run_history (macro_id, ran_at, success, error_msg) VALUES (?,?,?,?)",
            (macro_id, time.time(), 1 if success else 0, error_msg),
        )
        conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
