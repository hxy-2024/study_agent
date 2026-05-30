from sqlalchemy import Column
from sqlalchemy.dialects import postgresql, sqlite


def assert_json_column_compiles_for_supported_dialects(column: Column) -> None:
    postgresql_type = column.type.compile(dialect=postgresql.dialect()).upper()
    sqlite_type = column.type.compile(dialect=sqlite.dialect()).upper()

    assert postgresql_type == "JSONB"
    assert sqlite_type == "JSON"
