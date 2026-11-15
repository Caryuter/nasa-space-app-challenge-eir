import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError
from fastapi import HTTPException
from app.main import ChatRequest, chat, apollo_config


class FakeResponse:
    def __enter__(self):
        return io.BytesIO(json.dumps({"message": {"content": "Hola desde el modelo"}}).encode())
    def __exit__(self, *args):
        pass


class ApolloTests(unittest.TestCase):
    def test_original_contract_and_explicit_fallback(self):
        with patch.dict(os.environ, {"APOLLO_PROVIDER": "ollama"}):
            result = chat(ChatRequest(message="hola", provider="deterministic"))
        self.assertEqual(result["mode"], "deterministic")
        self.assertEqual(set(result), {"assistant", "mode", "reply"})

    def test_ollama_request_and_response(self):
        with patch.dict(os.environ, {"APOLLO_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen3:0.6b"}), patch("app.main.urllib.request.urlopen", return_value=FakeResponse()) as send:
            result = chat(ChatRequest(message="hola"))
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["content"], "hola")
        self.assertEqual(result["mode"], "ollama")
        self.assertEqual(result["reply"], "Hola desde el modelo")

    def test_unavailable_is_not_disguised_as_llm_response(self):
        with patch.dict(os.environ, {"APOLLO_PROVIDER": "ollama"}), patch("app.main.urllib.request.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(HTTPException) as error:
                chat(ChatRequest(message="hola"))
        self.assertEqual(error.exception.status_code, 503)

    def test_configuration(self):
        with patch.dict(os.environ, {"APOLLO_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen3:1.7b"}):
            self.assertEqual(apollo_config(), {"provider": "ollama", "model": "qwen3:1.7b"})


if __name__ == "__main__":
    unittest.main()
