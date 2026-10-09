import anthropic
import httpx2
from pydantic import SecretStr
import pytest
from sarjy_gateway.claude import ClaudeChatModel
from sarjy_gateway.llm import FallbackChatModel, MissingChatModel, OpenAiCompatibleChatModel
from sarjy_gateway.services import build_anthropic_client, build_chat_model
from sarjy_gateway.settings import Settings


def chat_model_for(settings: Settings) -> object:
    return build_chat_model(settings, httpx2.AsyncClient(), build_anthropic_client(settings))


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        (Settings(llm_api_key=SecretStr("groq-key"), anthropic_api_key=None), OpenAiCompatibleChatModel),
        (Settings(llm_api_key=None, anthropic_api_key=SecretStr("claude-key")), ClaudeChatModel),
        (Settings(llm_api_key=None, anthropic_api_key=None), MissingChatModel),
        (
            Settings(llm_api_key=SecretStr("groq-key"), anthropic_api_key=SecretStr("claude-key"), llm_primary="claude"),
            FallbackChatModel,
        ),
    ],
    ids=["groq only", "claude only, even when groq is primary", "no key at all", "both keys"],
)
def test_the_chat_model_follows_the_keys_that_are_set(settings: Settings, expected: type) -> None:
    assert isinstance(chat_model_for(settings), expected)


def test_without_a_claude_key_there_is_no_claude_client() -> None:
    assert build_anthropic_client(Settings(anthropic_api_key=None)) is None
    assert isinstance(build_anthropic_client(Settings(anthropic_api_key=SecretStr("k"))), anthropic.AsyncAnthropic)
