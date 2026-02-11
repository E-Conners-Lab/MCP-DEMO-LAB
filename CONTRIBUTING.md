# Contributing to network-mcp

Thanks for your interest in contributing!

## Getting Started

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Make your changes
5. Run tests: `pytest`
6. Submit a PR

## Adding a New MCP Tool

1. Pick the right module in `mcp_tools/` (or create a new one)
2. Write an async function with a clear docstring — the docstring becomes the tool description in the AI
3. Register it in the `TOOLS` list at the bottom of the module
4. Import it in `mcp_tools/__init__.py`
5. Add a test

Example:

```python
# mcp_tools/my_module.py

async def my_tool(device_name: str) -> str:
    """
    One-line description of what this tool does.

    Args:
        device_name: Target device name from inventory

    Returns:
        JSON string with results
    """
    # Implementation here
    return json.dumps({"result": "ok"})

TOOLS = [
    {"fn": my_tool, "name": "my_tool", "category": "my_category"},
]
```

## Code Style

- Use `ruff` for linting (`ruff check .`)
- Type hints encouraged but not required
- Docstrings are important — they're what the AI sees

## Reporting Issues

Open an issue with:
- What you expected
- What happened
- Device type and OS version (if relevant)
- MCP client you're using (Claude Desktop, etc.)
