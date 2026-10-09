import asyncio
import logging
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ValidationError


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sarjy_gateway.llm import ToolCall, ToolSpec


logger = logging.getLogger(__name__)

# A voice turn can't wait long in silence; a tool slower than this counts as failed.
TOOL_TIMEOUT_SECONDS = 5.0


# One thing the model can do: search tours, check the weather, remember a fact. `run`
# gets the arguments as the model's JSON text; a tool parses them with its own Pydantic
# model, whose JSON schema is also what `spec` shows the model.
class Tool(Protocol):
    @property
    def spec(self) -> ToolSpec: ...

    async def run(self, arguments: str) -> str: ...


# A tool that can't do its job raises this; the message goes back to the model, so it
# should say what went wrong in words the model can pass on.
class ToolError(Exception):
    pass


class ToolFailure(BaseModel):
    error: str


# Runs the model's tool calls. A bad call never fails the turn: an unknown tool, invalid
# arguments, a ToolError or a timeout becomes an error result the model reads and answers
# from, for example by saying it can't check the weather right now.
class Toolbox:
    def __init__(self, tools: Sequence[Tool], clock: Callable[[], float], timeout_seconds: float) -> None:
        self._tools = {tool.spec.name: tool for tool in tools}
        self._clock = clock
        self._timeout_seconds = timeout_seconds

    @property
    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    # The shared tools plus one visit's own, such as its user's memory tools (D-67).
    def including(self, tools: Sequence[Tool]) -> Toolbox:
        return Toolbox([*self._tools.values(), *tools], self._clock, self._timeout_seconds)

    # The model may ask for several tools in one round; they run side by side, and the
    # results come back in the order of the calls.
    async def run_all(self, calls: Sequence[ToolCall], turn_id: str) -> list[str]:
        return list(await asyncio.gather(*(self._run_timed(call, turn_id) for call in calls)))

    async def _run_timed(self, call: ToolCall, turn_id: str) -> str:
        started = self._clock()
        result = await self._run(call)
        logger.info(
            "tool %(tool)s ran",
            {"turn_id": turn_id, "tool": call.name, "ms": round((self._clock() - started) * 1000, 1)},
        )
        return result

    async def _run(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            return failure(f"There is no tool called {call.name}.")
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await tool.run(call.arguments)
        except ValidationError as error:
            return failure(f"Invalid arguments: {describe(error)}")
        except ToolError as error:
            return failure(str(error))
        except TimeoutError:
            return failure(f"{call.name} took longer than {self._timeout_seconds:g} seconds.")


def failure(message: str) -> str:
    return ToolFailure(error=message).model_dump_json()


def failed(result: str) -> bool:
    try:
        ToolFailure.model_validate_json(result)
    except ValidationError:
        return False
    return True


# "date: Field required; city: Input should be a valid string", short enough for the model
# to read and correct its next call.
def describe(error: ValidationError) -> str:
    problems: list[str] = []
    for problem in error.errors(include_url=False):
        where = ".".join(str(part) for part in problem["loc"]) or "arguments"
        problems.append(f"{where}: {problem['msg']}")
    return "; ".join(problems)
