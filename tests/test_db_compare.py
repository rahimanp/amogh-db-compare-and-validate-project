import sqlite3
import tempfile
import unittest
from pathlib import Path

from db_compare import compare_databases


class DbCompareTests(unittest.TestCase):
    def _create_db(self, setup_sql: str, user_version: int = 0, application_id: int = 0) -> Path:
        """Create a temporary SQLite DB for tests using trusted, inline schema SQL."""

        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()
        db_path = Path(temp_file.name)

        if not isinstance(user_version, int) or not isinstance(application_id, int):
            raise TypeError("user_version and application_id must be integers")

        with sqlite3.connect(db_path) as conn:
            conn.executescript(setup_sql)
            conn.execute(f"PRAGMA user_version = {user_version}")
            conn.execute(f"PRAGMA application_id = {application_id}")

        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        return db_path

    def test_identical_databases_are_equal(self):
        schema = """
        CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE VIEW active_users AS SELECT id, name FROM users;
        CREATE TRIGGER users_name_check BEFORE INSERT ON users BEGIN
          SELECT CASE WHEN NEW.name = '' THEN RAISE(ABORT, 'name required') END;
        END;
        CREATE INDEX idx_users_name ON users(name);
        """
        source = self._create_db(schema, user_version=2, application_id=7)
        target = self._create_db(schema, user_version=2, application_id=7)

        result = compare_databases(str(source), str(target))

        self.assertTrue(result["is_equal"])
        self.assertEqual(result["missing_in_target"], [])
        self.assertEqual(result["missing_in_source"], [])
        self.assertEqual(result["definition_mismatches"], [])
        self.assertEqual(result["version_issues"], {})

    def test_detects_missing_objects_definition_and_version_issues(self):
        source = self._create_db(
            """
            CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE VIEW user_names AS SELECT name FROM users;
            CREATE INDEX idx_users_name ON users(name);
            """,
            user_version=3,
            application_id=9,
        )
        target = self._create_db(
            """
            CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT);
            CREATE TRIGGER users_name_trim BEFORE INSERT ON users BEGIN
              SELECT NEW.name;
            END;
            """,
            user_version=1,
            application_id=9,
        )

        result = compare_databases(str(source), str(target))

        self.assertFalse(result["is_equal"])
        self.assertIn({"type": "view", "name": "user_names"}, result["missing_in_target"])
        self.assertIn({"type": "index", "name": "idx_users_name"}, result["missing_in_target"])
        self.assertIn({"type": "trigger", "name": "users_name_trim"}, result["missing_in_source"])
        self.assertEqual(result["version_issues"]["user_version"], {"source": 3, "target": 1})

        mismatch_names = {(item["type"], item["name"]) for item in result["definition_mismatches"]}
        self.assertIn(("table", "users"), mismatch_names)


if __name__ == "__main__":
    unittest.main()
