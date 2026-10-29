"""
scripts/test_db_connection.py

Test script to verify connection to PostgreSQL (Supabase or local),
check if required tables exist, and insert a test document row.

Usage:
    python scripts/test_db_connection.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database import db


def mask_url(url: str) -> str:
    """Mask password in connection URL for safe logging."""
    if not url:
        return "(empty)"
    import re
    return re.sub(r":([^:@]+)@", r":****@", url)


def main():
    print("=" * 60)
    print("  CEMS Database Connection & Insert Test")
    print("=" * 60)

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print(f"Target: DATABASE_URL = {mask_url(db_url)}")
    else:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        dbname = os.getenv("POSTGRES_DB", "cems")
        user = os.getenv("POSTGRES_USER", "cems")
        print(f"Target: Host={host}, Port={port}, DB={dbname}, User={user}")

    print("\n[1/4] Initializing connection pool...")
    try:
        db.init_pool()
        print("  [OK] Connection pool initialized successfully.")
    except Exception as e:
        print(f"  [ERROR] Failed to initialize pool: {e}")
        sys.exit(1)

    print("\n[2/4] Testing PostgreSQL handshake & version...")
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT version();")
            version_str = cur.fetchone()["version"]
            print(f"  [OK] Connected! Server:\n    {version_str[:80]}...")
    except Exception as e:
        print(f"  [ERROR] Query failed: {e}")
        sys.exit(1)

    print("\n[3/4] Checking required tables (documents, users, comments)...")
    expected_tables = ["documents", "users", "comments"]
    missing_tables = []
    with db.get_cursor() as cur:
        for t in expected_tables:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)",
                (t,),
            )
            exists = cur.fetchone()["exists"]
            if exists:
                print(f"  [OK] Table 'public.{t}' exists.")
            else:
                print(f"  [MISSING] Table 'public.{t}' does not exist.")
                missing_tables.append(t)

    if missing_tables:
        print(f"\n[WARNING] The following tables are missing: {', '.join(missing_tables)}")
        print("          Please run database/schema.sql in your Supabase SQL Editor first.")
        sys.exit(1)

    print("\n[4/4] Inserting a test row into 'documents'...")
    test_project = "PRJ-TEST-001"
    test_doc = "DOC-TEST-CHECK"
    test_rev = "R0"
    test_supplier = "TestSupplier"
    test_po = "PO-9999"

    try:
        doc_id = db.upsert_document(
            praj_project_number=test_project,
            praj_document_number=test_doc,
            praj_revision_number=test_rev,
            supplier_name=test_supplier,
            supplier_po_number=test_po,
            customer_document_number="CUST-DOC-01",
            customer_revision="CA",
        )
        print(f"  [OK] Successfully upserted test document with ID: {doc_id}")

        # Fetch and verify the row
        row = db.get_document(doc_id)
        print(f"  [OK] Verified row retrieval from database:")
        print(f"       - ID: {row['id']}")
        print(f"       - Project: {row['praj_project_number']}")
        print(f"       - Document: {row['praj_document_number']}")
        print(f"       - Revision: {row['praj_revision_number']}")
        print(f"       - Created At: {row.get('created_at')}")

        print("\n" + "=" * 60)
        print("  SUCCESS! Your Supabase database connection is 100% working.")
        print("=" * 60)
    except Exception as e:
        print(f"  [ERROR] Failed to insert test document: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
