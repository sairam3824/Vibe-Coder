import httpx

from apps.api.config import Settings
from packages.agent.services.openrouter import OpenRouterClient


class StubHttpClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls = 0

    def post(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls += 1
        return self.response


def test_openrouter_client_parses_chat_response() -> None:
    response = httpx.Response(
        200,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        json={
            "choices": [{"message": {"content": '{"goal_summary":"Do thing"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
    )
    client = OpenRouterClient(
        settings=Settings(OPENROUTER_API_KEY="test-key"),
        http_client=StubHttpClient(response),
    )

    result = client.chat(
        model="test-model",
        system_prompt="system",
        user_prompt="user",
        json_mode=True,
    )

    assert result.content == '{"goal_summary":"Do thing"}'
    assert result.usage and result.usage.total_tokens == 30


def test_openrouter_extract_json_handles_fenced_blocks() -> None:
    payload = OpenRouterClient.extract_json('```json\n{"value": 1}\n```')
    assert payload["value"] == 1

