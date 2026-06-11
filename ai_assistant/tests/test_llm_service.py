from services.llm_service import LLMService


class _FakeResponse:
    def read(self):
        return b'{"models":[{"name":"gemma2:2b"},{"name":"llama3.2:latest"}]}'


class _FakeUrlopen:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return _FakeResponse()

    def __exit__(self, *args):
        return False

    @property
    def status(self):
        return 200


def test_resolve_ollama_model_exact_match(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeUrlopen())
    service = LLMService.__new__(LLMService)
    resolved = service._resolve_ollama_model("http://localhost:11434/v1", "gemma2:2b")
    assert resolved == "gemma2:2b"


def test_resolve_ollama_model_family_fallback(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeUrlopen())
    service = LLMService.__new__(LLMService)
    resolved = service._resolve_ollama_model("http://localhost:11434/v1", "gemma2:9b")
    assert resolved == "gemma2:2b"