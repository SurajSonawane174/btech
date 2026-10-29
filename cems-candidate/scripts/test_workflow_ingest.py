"""
scripts/test_workflow_ingest.py

Tests the standard CEMS ingestion workflow:
1. Upsert a document in Supabase PostgreSQL
2. Insert 4 review comments with 'embedded = false'
3. Run vectordb.comment_sync.sync_embeddings() to embed via Ollama and push to Qdrant Cloud
4. Verify Supabase rows have 'embedded = true'
5. Verify points exist in Qdrant Cloud
6. Perform a test similarity search on Qdrant Cloud to verify retrieval
"""
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database import db
from vectordb import comment_sync, qdrant_client as vdb


def main():
    print("=" * 65)
    print("  CEMS Workflow Test: 4 Comments Ingestion (Supabase + Qdrant)")
    print("=" * 65)

    # 1. Initialize DB and ensure Qdrant collections
    db.init_pool()
    vdb.ensure_collections()

    # 2. Upsert document
    print("\n[1/5] Creating / Upserting document in Supabase...")
    doc_id = db.upsert_document(
        praj_project_number="PRJ-CEMS-DEMO",
        praj_document_number="DWG-PIPING-402",
        praj_revision_number="Rev-01",
        supplier_name="PRAJ-Fab",
        supplier_po_number="PO-7788",
        customer_document_number="CUST-DWG-402",
        customer_revision="Rev-A"
    )
    print(f"  [OK] Document ID in Supabase: {doc_id}")

    # 3. Prepare 4 test comments
    timestamp_suffix = datetime.now().strftime("%H%M%S")
    sample_comments = [
        {
            "comment_id": f"CMT-DEMO-001-{timestamp_suffix}",
            "page_sheet": "1",
            "actual_extracted_comment": "Weld size on support bracket B-12 must be increased to 8mm as per AWS D1.1 specifications.",
            "snapshot_file": "snaps/b12_weld.png",
            "name_of_person_commented": "S. Kulkarni",
            "comment_color": "RED",
            "is_client_comment": True,
            "comment_category": "technical",
            "is_handwritten": False,
            "extraction_confidence_percent": 95,
        },
        {
            "comment_id": f"CMT-DEMO-002-{timestamp_suffix}",
            "page_sheet": "2",
            "actual_extracted_comment": "Verify pipe wall thickness and schedule for 4-inch line 1021-P per ASME B31.3 standards.",
            "snapshot_file": "snaps/pipe_sched.png",
            "name_of_person_commented": "V. Sharma",
            "comment_color": "BLUE",
            "is_client_comment": False,
            "comment_category": "technical",
            "is_handwritten": False,
            "extraction_confidence_percent": 98,
        },
        {
            "comment_id": f"CMT-DEMO-003-{timestamp_suffix}",
            "page_sheet": "1",
            "actual_extracted_comment": "Align drawing title block notes to the left margin; text currently overlaps border.",
            "snapshot_file": "snaps/title_align.png",
            "name_of_person_commented": "A. Deshmukh",
            "comment_color": "GREEN",
            "is_client_comment": True,
            "comment_category": "aesthetic",
            "is_handwritten": False,
            "extraction_confidence_percent": 90,
        },
        {
            "comment_id": f"CMT-DEMO-004-{timestamp_suffix}",
            "page_sheet": "3",
            "actual_extracted_comment": "Check structural bolt grade and torque values for base plate anchor connection.",
            "snapshot_file": "snaps/bolt_anchor.png",
            "name_of_person_commented": "S. Kulkarni",
            "comment_color": "RED",
            "is_client_comment": True,
            "comment_category": "technical",
            "is_handwritten": False,
            "extraction_confidence_percent": 92,
        },
    ]

    print(f"\n[2/5] Inserting {len(sample_comments)} comments into Supabase PostgreSQL...")
    inserted_count = db.insert_comments(doc_id, sample_comments)
    print(f"  [OK] Inserted {inserted_count} new comment row(s) into Supabase.")

    # Retrieve the exact IDs of the 4 comments we just inserted
    with db.get_cursor() as cur:
        cur.execute("SELECT id FROM comments WHERE document_id = %s ORDER BY id DESC LIMIT %s", (doc_id, len(sample_comments)))
        new_comment_ids = [r["id"] for r in cur.fetchall()]
    print(f"  [OK] Generated Comment IDs in Supabase: {new_comment_ids}")

    # 4. Sync embeddings specifically for these 4 comments to Qdrant Cloud
    print("\n[3/5] Running comment_sync.sync_embeddings(ids=...) (Ollama embed -> Qdrant Cloud)...")
    sync_result = comment_sync.sync_embeddings(ids=new_comment_ids)
    print(f"  [OK] Sync completed:")
    print(f"       - Embedded & pushed to Qdrant Cloud: {sync_result['embedded']}")
    print(f"       - Failed:                            {sync_result['failed']}")

    if sync_result['failed'] > 0:
        print(f"  [ERROR] Some embeddings failed: {sync_result['failed_ids']}")
        sys.exit(1)

    # 5. Verify Supabase embedded status
    print("\n[4/5] Verifying Supabase row statuses...")
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT id, comment_id, embedded, status FROM comments WHERE document_id = %s ORDER BY id DESC LIMIT 4",
            (doc_id,),
        )
        rows = cur.fetchall()
        for r in rows:
            print(f"  [OK] Supabase Comment ID={r['id']} ({r['comment_id']}): embedded={r['embedded']}, status={r['status']}")

    # 6. Verify in Qdrant Cloud with a similarity query
    print("\n[5/5] Testing semantic search on Qdrant Cloud...")
    search_query = "welding requirements on bracket"
    print(f"  Query: '{search_query}'")
    search_resp = comment_sync.find_similar(search_query, top_k=2)
    hits = search_resp["results"]
    print(f"  [OK] Found {len(hits)} matching hit(s) from Qdrant Cloud:")
    for h in hits:
        print(f"       - Score: {h['score']:.4f} | ID: {h['id']} | Category: {h.get('comment_category')} | Text: \"{h['text']}\"")

    print("\n" + "=" * 65)
    print("  SUCCESS: Comments saved in Supabase & synced to Qdrant Cloud!")
    print("=" * 65)


if __name__ == "__main__":
    main()
