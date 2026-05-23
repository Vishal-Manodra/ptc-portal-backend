# add_filing_columns.py
# One-time migration: adds GST filing return status columns to the clients table.
# Safe to run multiple times — skips columns that already exist.
#
# Run with:  python add_filing_columns.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import engine
from sqlalchemy import text, inspect

NEW_COLUMNS = [
    ("gstr1_iff_status", "VARCHAR(20)"),
    ("gstr3b_status", "VARCHAR(20)"),
    ("gstr4_status", "VARCHAR(20)"),
    ("cmp08_status", "VARCHAR(20)"),
    ("gstr4_annual_status", "VARCHAR(20)"),
    ("gstr9_annual_status", "VARCHAR(20)"),
    ("gstr9c_status", "VARCHAR(20)"),
    ("gstr1a_status", "VARCHAR(20)"),
    ("gstr1_iff_status_prev", "VARCHAR(20)"),
    ("gstr3b_status_prev", "VARCHAR(20)"),
    ("gstr4_status_prev", "VARCHAR(20)"),
    ("cmp08_status_prev", "VARCHAR(20)"),
    ("gstr4_annual_status_prev", "VARCHAR(20)"),
    ("gstr9_annual_status_prev", "VARCHAR(20)"),
    ("gstr9c_status_prev", "VARCHAR(20)"),
    ("gstr1a_status_prev", "VARCHAR(20)"),
    ("last_filing_check", "TIMESTAMP"),
]

def run_migration():
    inspector = inspect(engine)
    existing_columns = [col["name"] for col in inspector.get_columns("clients")]

    with engine.connect() as conn:
        for col_name, col_type in NEW_COLUMNS:
            if col_name in existing_columns:
                print(f"[SKIP] Column '{col_name}' already exists.")
                continue
            stmt = text(f'ALTER TABLE clients ADD COLUMN {col_name} {col_type}')
            conn.execute(stmt)
            print(f"[OK] Added column '{col_name}' ({col_type})")
        conn.commit()

    print("\n[SUCCESS] Migration complete — all filing columns are present.")


if __name__ == "__main__":
    run_migration()
