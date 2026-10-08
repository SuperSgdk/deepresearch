"""Read-only infrastructure and knowledge check. Does not print credentials."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

from dotenv import dotenv_values
import psycopg
from pymilvus import MilvusClient


def main():
    values = dotenv_values(ROOT / ".env")
    checks = {}
    try:
        with psycopg.connect(values["POSTGRES_DSN"], connect_timeout=5) as connection:
            checks["postgres"] = connection.execute("SELECT 1").fetchone()[0] == 1
    except Exception as error:
        checks["postgres"] = type(error).__name__
    try:
        client = MilvusClient(uri=f"http://{values['MILVUS_HOST']}:{values['MILVUS_PORT']}", timeout=5)
        name = values.get("KNOWLEDGE_COLLECTION", "mult_agent_knowledge")
        checks["milvus"] = True
        checks["knowledge_collection_exists"] = client.has_collection(name)
        if checks["knowledge_collection_exists"]:
            checks["knowledge_rows"] = int(client.get_collection_stats(name)["row_count"])
        else:
            checks["knowledge_rows"] = 0
        client.close()
    except Exception as error:
        checks["milvus"] = type(error).__name__
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks.get("postgres") is True and checks.get("milvus") is True and checks.get("knowledge_rows", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
