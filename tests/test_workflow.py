import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from mult_agents import graph
from mult_agents.config import AppConfig
from mult_agents.nodes import write_node
from mult_agents.state import create_initial_state
from backend.service.workflow_service import WorkflowService


class WorkflowTests(unittest.TestCase):
    def test_parallel_retrieval_joins_once_and_stops_at_budget(self):
        visits = []

        def intent(state, agent, agent_name):
            return {"intent": "multiagent"}

        def web(state, agent, agent_name):
            return {"web_search": "web evidence"}

        def local(state, agent, agent_name):
            return {"local_rag": "local evidence"}

        def audit(state, agent, agent_name):
            self.assertTrue(state["web_search"] and state["local_rag"])
            visits.append("audit")
            return {}

        def reflect(state, agent, agent_name):
            visits.append("reflect")
            return {"iteration": state["iteration"] + 1}

        def analyze(state, agent, agent_name):
            return {"needs_more_research": True}

        def write(state, agent, agent_name):
            return {"final": "report"}

        replacements = dict(intent_node=intent, plan_node=lambda state, agent, agent_name: {},
                            web_search_node=web, local_rag_node=local,
                            deep_dive_node=audit, analyze_node=analyze,
                            reflect_node=reflect, write_node=write)
        agents = SimpleNamespace(**{key: None for key in (
            "intent_router", "direct_responder", "planner", "reflector",
            "scout_web", "scout_local", "evidence_judge", "analyst", "writer")})
        with patch.multiple(graph, **replacements):
            app = graph.build_app(agents, InMemorySaver())
            result = app.invoke(create_initial_state("research", 1, "u", "t"),
                                {"configurable": {"thread_id": "join-test"}})
        self.assertEqual(result["final"], "report")
        self.assertEqual(visits.count("audit"), 2)
        self.assertEqual(visits.count("reflect"), 1)

    def test_checkpoint_identity_separates_users_tenants_and_chats(self):
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-placeholder"}, clear=True):
            config = AppConfig.from_file()
        base = WorkflowService._checkpoint_config(config)
        for override in ({"user_id": "another-user"}, {"tenant_id": "another-tenant"},
                         {"thread_id": "another-chat"}):
            self.assertNotEqual(base, WorkflowService._checkpoint_config(config.with_overrides(**override)))
        self.assertEqual(base, WorkflowService._checkpoint_config(config))

    def test_missing_model_key_fails_before_agent_initialization(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DASHSCOPE_API_KEY"):
                AppConfig.from_file()

    def test_writer_references_follow_current_output_and_drop_unknown_ids(self):
        state = create_initial_state("question", 1, "u", "t")
        state.update(draft="old draft [WEB1_1-2]", source_index=[
            {"source_id": "WEB1_1-1", "label": "Current source", "locator": "https://example.com/current", "source_type": "web"},
            {"source_id": "WEB1_1-2", "label": "Unused source", "locator": "https://example.com/unused", "source_type": "web"},
        ])
        agent = SimpleNamespace(invoke=lambda _: {"messages": [AIMessage(content="Current fact [WEB1_1-1]. Unknown [WEB9_9-9].")]})
        result = write_node(state, agent, "writer")["final"]
        self.assertIn("https://example.com/current", result)
        self.assertNotIn("https://example.com/unused", result)
        self.assertNotIn("WEB9_9-9", result)


if __name__ == "__main__":
    unittest.main()
