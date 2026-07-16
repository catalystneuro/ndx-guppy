from pathlib import Path


def test_readme(tmp_path, monkeypatch):
    """Test the first python code block in the README by simply executing it.

    The README block is self-contained -- it writes and then reads back a hardcoded
    "guppy_session.nwb". Run it inside ``tmp_path`` so that artifact stays out of the repo.
    """
    readme_path = Path(__file__).parents[4] / "README.md"
    lines = readme_path.read_text().splitlines(keepends=True)
    start_line = None
    for i, line in enumerate(lines):
        if line == "```python\n":
            start_line = i
        elif line == "```\n" and start_line is not None:
            end_line = i
            break
    code_block = "".join(lines[start_line + 1 : end_line])

    monkeypatch.chdir(tmp_path)
    readme_outputs = {}
    exec(code_block, readme_outputs)
    assert "nwbfile" in readme_outputs
