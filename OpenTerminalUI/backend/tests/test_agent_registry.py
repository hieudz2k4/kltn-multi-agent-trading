import pytest
from backend.agent.tools.registry import ToolSpec, ToolRegistry


@pytest.mark.asyncio
async def test_register_and_execute():
    reg = ToolRegistry()

    async def handler(args):
        return {"echo": args["x"]}

    reg.register(ToolSpec(
        name="echo", description="echo x",
        parameters={"type": "object", "properties": {"x": {"type": "string"}},
                    "required": ["x"]},
        handler=handler, read_only=True,
    ))
    result = await reg.execute("echo", {"x": "hi"})
    assert result == {"echo": "hi"}


def test_tool_defs_wire():
    reg = ToolRegistry()
    reg.register(ToolSpec("t", "d", {"type": "object"}, handler=None, read_only=True))
    defs = reg.tool_defs()
    assert defs[0].name == "t"


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        await reg.execute("nope", {})


def test_duplicate_registration_raises():
    reg = ToolRegistry()
    spec = ToolSpec("t", "d", {"type": "object"}, handler=None, read_only=True)
    reg.register(spec)
    with pytest.raises(ValueError):
        reg.register(spec)
