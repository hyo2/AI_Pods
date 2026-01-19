import pytest

class FakeResponse:
    def __init__(self, text: str):
        self._text = text

class FakeModel:
    def __init__(self, out_text: str):
        self.out_text = out_text
    def generate_content(self, prompt, generation_config=None):
        return FakeResponse(self.out_text)

def fake_extract_text_fn(resp):
    return getattr(resp, "_text", "") or ""

@pytest.fixture
def fake_model_factory():
    def _factory(out_text: str):
        return FakeModel(out_text)
    return _factory

@pytest.fixture
def extract_text_fn():
    return fake_extract_text_fn
