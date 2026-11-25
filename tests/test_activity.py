"""Tests for how the activity terminal shows Claude's commands and their output."""
import jarvis


def plain(text):
    return jarvis.ANSI.sub("", text)


def test_shell_command_looks_like_a_terminal():
    shown = plain(jarvis.format_tool_call("Bash", {"command": "df -h ~",
                                                   "description": "Check free disk space"}))
    assert shown == "# Check free disk space\n$ df -h ~\n"


def test_other_tools_show_what_they_touch():
    assert plain(jarvis.format_tool_call("Read", {"file_path": "/tmp/a.txt"})) == "▸ Read /tmp/a.txt\n"


def test_long_output_is_cut():
    shown = plain(jarvis.format_tool_output("\n".join(map(str, range(50))), max_lines=10))
    assert shown.splitlines()[:2] == ["  0", "  1"]
    assert shown.splitlines()[-1] == "  … (40 more lines)"


def test_file_contents_are_only_summarized():
    assert plain(jarvis.format_tool_output("a\nb\nc", full=False)) == "  ↳ 3 lines\n"


def test_errors_are_always_shown():
    assert "permission denied" in jarvis.format_tool_output("permission denied", is_error=True,
                                                            full=False)
