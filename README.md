# amogh-db-compare-and-validate-project

Compares two SQLite database schemas to find object and version differences.

## What it checks
- Tables
- Views
- Triggers
- Indexes
- Version metadata (`PRAGMA user_version`, `PRAGMA schema_version`, `PRAGMA application_id`)

## Usage
```bash
python db_compare.py /path/to/source.db /path/to/target.db --pretty
```

- Exit code `0`: databases match for all compared objects and versions
- Exit code `1`: one or more differences found

The output is JSON with:
- `missing_in_target`
- `missing_in_source`
- `definition_mismatches`
- `version_issues`
- `is_equal`

## Run tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```
