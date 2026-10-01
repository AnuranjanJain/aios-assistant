import hashlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.migrations import MIGRATIONS, apply_migrations


@pytest.mark.parametrize("trailing_newline", [False, True])
def test_existing_column_migration_checksums_remain_valid(trailing_newline):
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as session:
        apply_migrations(session, engine)
        for spec in MIGRATIONS:
            if spec.statements:
                continue
            payload = spec.version + "\n" + "\n".join(
                f"{item.table}.{item.column}:{item.statement}" for item in spec.additions
            )
            historical = hashlib.sha256(
                (payload + ("\n" if trailing_newline else "")).encode()
            ).hexdigest()
            session.execute(
                text("UPDATE aios_schema_migration SET checksum=:checksum WHERE version=:version"),
                {"checksum": historical, "version": spec.version},
            )
        session.commit()
        assert apply_migrations(session, engine) == []


def test_unknown_checksum_still_blocks_startup():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as session:
        apply_migrations(session, engine)
        session.execute(text("UPDATE aios_schema_migration SET checksum='invalid'"))
        session.commit()
        with pytest.raises(RuntimeError, match="checksum mismatch"):
            apply_migrations(session, engine)
