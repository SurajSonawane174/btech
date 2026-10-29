"""
scripts/test_qdrant_cloud.py

Tests connection to Qdrant Cloud cluster, checks collections,
and ensures 'comments' and 'standards_chunks' collections exist.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vectordb import qdrant_client as vdb


def main():
    print("=" * 60)
    print("  Qdrant Cloud Connection Test")
    print("=" * 60)

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not url:
        print("[ERROR] QDRANT_URL is not set in .env")
        sys.exit(1)

    print(f"Target URL: {url}")
    print(f"API Key:    {api_key[:10]}...{api_key[-5:] if api_key else ''}")

    print("\n[1/3] Connecting to Qdrant Cloud...")
    try:
        client = vdb.get_client()
        collections_resp = client.get_collections()
        existing = [c.name for c in collections_resp.collections]
        print(f"  [OK] Successfully connected to Qdrant Cloud!")
        print(f"       Existing collections: {existing if existing else '(none yet)'}")
    except Exception as e:
        print(f"  [ERROR] Connection failed: {e}")
        sys.exit(1)

    print("\n[2/3] Ensuring required collections exist ('comments', 'standards_chunks')...")
    try:
        vdb.ensure_collections()
        collections_resp = client.get_collections()
        updated = [c.name for c in collections_resp.collections]
        print(f"  [OK] Collections verified: {updated}")
    except Exception as e:
        print(f"  [ERROR] Failed to ensure collections: {e}")
        sys.exit(1)

    print("\n[3/3] Fetching collection details...")
    for col_name in (vdb.COMMENTS_COLLECTION, vdb.STANDARDS_COLLECTION):
        try:
            info = client.get_collection(col_name)
            points_count = info.points_count
            print(f"  [OK] Collection '{col_name}': {points_count} points, vector size={info.config.params.vectors.size}, distance={info.config.params.vectors.distance}")
        except Exception as e:
            print(f"  [WARNING] Could not get info for '{col_name}': {e}")

    print("\n" + "=" * 60)
    print("  SUCCESS! Your Qdrant Cloud connection is 100% working.")
    print("=" * 60)


if __name__ == "__main__":
    main()
