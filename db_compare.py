#!/usr/bin/env python3
"""Compare SQLite database objects and version metadata."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class DbObject:
    """Represents a database object definition from sqlite_master."""

    obj_type: str
    name: str
    sql: str


def _normalize_sql(sql: str) -> str:
    """Normalize SQL for stable comparisons across formatting differences.

    Note: this performs case-insensitive matching by lowercasing SQL text.
    """

    if not sql:
        return ""
    compact = re.sub(r"\s+", " ", sql).strip().rstrip(";")
    return compact.lower()


def _load_objects(connection: sqlite3.Connection) -> Dict[Tuple[str, str], DbObject]:
    """Load user-defined schema objects keyed by (type, name)."""

    cursor = connection.execute(
        """
        SELECT type, name, COALESCE(sql, '')
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
          AND type IN ('table', 'view', 'trigger', 'index')
        """
    )
    objects: Dict[Tuple[str, str], DbObject] = {}
    for obj_type, name, sql in cursor.fetchall():
        objects[(obj_type, name)] = DbObject(obj_type=obj_type, name=name, sql=sql)
    return objects


def _load_versions(connection: sqlite3.Connection) -> Dict[str, int]:
    """Load key SQLite PRAGMA version metadata values."""

    user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    schema_version = connection.execute("PRAGMA schema_version").fetchone()[0]
    application_id = connection.execute("PRAGMA application_id").fetchone()[0]
    return {
        "user_version": int(user_version),
        "schema_version": int(schema_version),
        "application_id": int(application_id),
    }


def compare_databases(source_db: str, target_db: str) -> Dict[str, object]:
    """Compare two SQLite databases and return object and version differences."""

    with sqlite3.connect(source_db) as source_conn, sqlite3.connect(target_db) as target_conn:
        source_objects = _load_objects(source_conn)
        target_objects = _load_objects(target_conn)
        source_versions = _load_versions(source_conn)
        target_versions = _load_versions(target_conn)

    missing_in_target: List[Dict[str, str]] = []
    missing_in_source: List[Dict[str, str]] = []
    definition_mismatches: List[Dict[str, str]] = []

    source_keys = set(source_objects.keys())
    target_keys = set(target_objects.keys())

    for key in sorted(source_keys - target_keys):
        obj = source_objects[key]
        missing_in_target.append({"type": obj.obj_type, "name": obj.name})

    for key in sorted(target_keys - source_keys):
        obj = target_objects[key]
        missing_in_source.append({"type": obj.obj_type, "name": obj.name})

    for key in sorted(source_keys & target_keys):
        source_obj = source_objects[key]
        target_obj = target_objects[key]
        if _normalize_sql(source_obj.sql) != _normalize_sql(target_obj.sql):
            definition_mismatches.append(
                {
                    "type": source_obj.obj_type,
                    "name": source_obj.name,
                    "source_sql": source_obj.sql,
                    "target_sql": target_obj.sql,
                }
            )

    version_issues = {
        key: {"source": source_versions[key], "target": target_versions[key]}
        for key in source_versions
        if source_versions[key] != target_versions[key]
    }

    return {
        "missing_in_target": missing_in_target,
        "missing_in_source": missing_in_source,
        "definition_mismatches": definition_mismatches,
        "version_issues": version_issues,
        "is_equal": not (
            missing_in_target
            or missing_in_source
            or definition_mismatches
            or version_issues
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare SQLite tables, views, triggers, indexes, and version metadata."
    )
    parser.add_argument("source_db", help="Path to source SQLite DB")
    parser.add_argument("target_db", help="Path to target SQLite DB")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    args = parser.parse_args()

    result = compare_databases(args.source_db, args.target_db)
    if args.pretty:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))

    return 0 if result["is_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
