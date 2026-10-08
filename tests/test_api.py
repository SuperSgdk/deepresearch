import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi.testclient import TestClient
from app_main import create_app
from backend.service import get_workflow_service


class StubWorkflow:
    async def stream_events(self, **kwargs):
        yield {"type": "phase", "node": "write", "message": "writing"}
        yield {"type": "final", "final": "stub report"}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.dependency_overrides[get_workflow_service] = lambda: StubWorkflow()
        self.client = TestClient(self.app)

    def test_health_and_configuration_status_do_not_initialize_models(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        with patch("socket.create_connection", side_effect=OSError("offline")):
            response = self.client.get("/api/local-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"dashscope_configured", "bocha_configured", "postgres_reachable", "milvus_reachable"})

    def test_stream_sends_phase_and_final_events(self):
        response = self.client.post("/api/v1/research/stream", json={"query": "test question"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn('"type": "phase"', response.text)
        self.assertIn('"final": "stub report"', response.text)

    def test_empty_query_is_rejected(self):
        response = self.client.post("/api/v1/research/stream", json={"query": ""})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
