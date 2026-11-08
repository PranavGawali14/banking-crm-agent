"""Data-access layer (Repository pattern).

Tools never write SQL themselves; they call this repository. Swapping SQLite for a real
core-banking / CRM API (Salesforce FSC, Dynamics, Finacle…) means re-implementing this one
class while every tool and the agent stay untouched.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional

from crm_agent.config import get_settings
from crm_agent.models import CustomerFilters


class CustomerRepository:
    def __init__(self, db_path: Path | str | None = None, auto_seed: bool = True):
        self.db_path = Path(db_path or get_settings().db_path)
        if auto_seed and not self.db_path.exists():
            from crm_agent.data.seed import seed_database

            seed_database(self.db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    # -- helpers ---------------------------------------------------------------------
    def _rows(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return [self._decode(dict(r)) for r in self._conn.execute(sql, tuple(params)).fetchall()]

    @staticmethod
    def _decode(row: dict) -> dict:
        if "existing_products" in row and isinstance(row["existing_products"], str):
            row["existing_products"] = [p for p in row["existing_products"].split(",") if p]
        for flag in ("whatsapp_opt_in", "sms_opt_in", "email_opt_in", "dnd"):
            if flag in row:
                row[flag] = bool(row[flag])
        return row

    # -- metadata --------------------------------------------------------------------
    @property
    def as_of_date(self) -> date:
        """Reference 'today' of the dataset (stored at seed time, so analysis stays consistent)."""
        try:
            row = self._conn.execute("SELECT value FROM meta WHERE key='as_of_date'").fetchone()
            if row:
                return date.fromisoformat(row[0])
        except sqlite3.Error:
            pass
        return get_settings().as_of_date

    def distinct_values(self, column: str) -> list[str]:
        if column not in {"city", "segment", "employment_type", "preferred_language"}:
            raise ValueError(f"column not allowed: {column}")
        return [r[0] for r in self._conn.execute(f"SELECT DISTINCT {column} FROM customers ORDER BY 1")]

    def customer_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    # -- customers -------------------------------------------------------------------
    def search_customers(self, filters: CustomerFilters | None = None, limit: int | None = None) -> list[dict]:
        f = filters or CustomerFilters()
        clauses, params = [], []
        if f.cities:
            clauses.append(f"LOWER(city) IN ({','.join('?' * len(f.cities))})")
            params += [c.lower() for c in f.cities]
        if f.segments:
            clauses.append(f"LOWER(segment) IN ({','.join('?' * len(f.segments))})")
            params += [s.lower() for s in f.segments]
        if f.employment_types:
            clauses.append(f"employment_type IN ({','.join('?' * len(f.employment_types))})")
            params += f.employment_types
        for col, op, val in (("annual_income", ">=", f.min_income), ("annual_income", "<=", f.max_income),
                             ("age", ">=", f.min_age), ("age", "<=", f.max_age),
                             ("credit_score", ">=", f.min_credit_score)):
            if val is not None:
                clauses.append(f"{col} {op} ?")
                params.append(val)
        sql = "SELECT * FROM customers"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY customer_id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self._rows(sql, params)

    def get_customer(self, customer_id: str) -> Optional[dict]:
        rows = self._rows("SELECT * FROM customers WHERE customer_id = ?", (customer_id.upper(),))
        return rows[0] if rows else None

    def find_customers_by_name(self, name: str) -> list[dict]:
        like = f"%{name.strip().lower()}%"
        return self._rows("SELECT * FROM customers WHERE LOWER(full_name) LIKE ? OR LOWER(first_name) = ? ORDER BY customer_id",
                          (like, name.strip().lower()))

    def get_customers(self, customer_ids: list[str]) -> list[dict]:
        if not customer_ids:
            return []
        return self._rows(f"SELECT * FROM customers WHERE customer_id IN ({','.join('?' * len(customer_ids))})", customer_ids)

    # -- transactions ----------------------------------------------------------------
    def get_transactions(self, customer_ids: list[str], since: date) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {cid: [] for cid in customer_ids}
        if not customer_ids:
            return out
        # chunk to stay under SQLite's parameter limit
        for i in range(0, len(customer_ids), 500):
            chunk = customer_ids[i:i + 500]
            rows = self._rows(
                f"SELECT * FROM transactions WHERE txn_date >= ? AND customer_id IN ({','.join('?' * len(chunk))})",
                [since.isoformat(), *chunk])
            for r in rows:
                out[r["customer_id"]].append(r)
        return out

    def get_balance_snapshots(self, customer_ids: list[str]) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {cid: [] for cid in customer_ids}
        for i in range(0, len(customer_ids), 500):
            chunk = customer_ids[i:i + 500]
            rows = self._rows(
                f"SELECT * FROM balance_snapshots WHERE customer_id IN ({','.join('?' * len(chunk))}) ORDER BY month_end",
                chunk)
            for r in rows:
                out[r["customer_id"]].append(r)
        return out

    # -- training data ---------------------------------------------------------------
    def get_campaign_history(self, product_id: str) -> list[dict]:
        return self._rows("SELECT * FROM campaign_history WHERE product_id = ?", (product_id,))
