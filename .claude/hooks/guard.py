#!/usr/bin/env python3
"""PreToolUse guard for the Claude transition of raspberry-pi-homelab.

Contract (verified 2026-09-18 against https://code.claude.com/docs/en/hooks):
  * the event JSON arrives on stdin and carries `tool_name`, `tool_input` and `cwd`,
  * exit code 2 blocks the tool call and stderr becomes the reason shown to Claude,
  * exit code 0 means "no decision"; the normal permission flow still applies,
  * every other exit code does NOT block, so this guard only ever uses 0 or 2.

Design rules H1-H8 of `.claude/ClaudeTransition.md` section 5.4:
  H1 Python 3 standard library only, no `.venv` dependency.
  H2 Fail closed: unparsable input, unknown tool-input shape or a parse error blocks.
  H3 Exit 2 plus a one-line stderr reason, no stdout JSON.
  H4 Project root from `CLAUDE_PROJECT_DIR`, else `git rev-parse --show-toplevel`, else block.
  H5 Policy data lives in `guard-config.json`, logic lives here.
  H6 Every decision is appended to `.claude/logs/guard.log` as one JSON line.
  H7 Mode `transition` enforces C1-C5; mode `operate` drops the C1/C2 path restrictions.
  H8 Tokenising uses `shlex`; `$( )`, backticks and process substitutions are extracted
     first by the balanced-delimiter scanner below and then inspected recursively.

The guard never approves anything (Q8): commands it cannot classify exit 0 and fall through
to the deny rules in `settings.json` and to the operator's approval prompt.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

EXIT_PASS = 0
EXIT_BLOCK = 2

FILE_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
FILE_READ_TOOLS = {"Read", "Grep", "Glob"}
EDIT_LIKE_NAME = re.compile(r"(write|edit|notebook|create|patch|append)", re.IGNORECASE)

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^[0-9]+(\.[0-9]+)?[smhd]?$")
FILE_MODE = re.compile(r"^[0-7]{3,4}$")
OWNER_SPEC = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*(:[A-Za-z_][A-Za-z0-9_.-]*)?$")

SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "setsid", "unbuffer", "time"}
FLAG_WRAPPERS = {"nice", "ionice", "stdbuf", "timeout"}
SHELL_KEYWORDS = {
    "if",
    "then",
    "else",
    "elif",
    "fi",
    "do",
    "done",
    "while",
    "until",
    "for",
    "case",
    "esac",
    "select",
    "function",
    "!",
    "{",
    "}",
    "(",
    ")",
}
REDIRECT_OPS = {">", ">>", ">|", "&>", "&>>", "<", "<<", "<<<", "<>"}
SUBSTITUTION_PLACEHOLDER = " __subst__ "


class Blocked(Exception):
    """Raised for every classified violation and for every fail-closed case."""


class Context:
    """Everything a check needs: policy data plus the resolved locations."""

    def __init__(self, config: dict, root: Path, cwd: Path) -> None:
        self.config = config
        self.root = root
        self.cwd = cwd
        self.transition = config.get("mode", "transition") == "transition"
        self.self_protect = bool(config.get("self_protect", False))
        self.write_dir = (root / str(config.get("write_dir", ".claude"))).resolve()

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def names(self, key: str) -> set[str]:
        return {str(x) for x in self.config.get(key, [])}


# --------------------------------------------------------------------------- paths


def resolve(ctx: Context, raw: str) -> Path:
    """Resolve `raw` against the session cwd and follow symlinks and `..`."""
    expanded = os.path.expanduser(raw)
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = ctx.cwd / candidate
    return Path(os.path.realpath(str(candidate)))


def is_inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def is_self_protected(ctx: Context, path: Path) -> bool:
    if not ctx.self_protect:
        return False
    for entry in ctx.get("self_protected_paths", []):
        target = (ctx.write_dir / str(entry)).resolve()
        if is_inside(path, target):
            return True
    return False


def is_write_allowed(ctx: Context, raw: str) -> bool:
    """True when writing to `raw` is permitted under the current mode."""
    if raw in ctx.names("null_targets"):
        return True
    path = resolve(ctx, raw)
    for prefix in ctx.get("allowed_temp_prefixes", []):
        if path.as_posix().startswith(str(prefix)):
            return True
    if is_self_protected(ctx, path):
        return False
    if not ctx.transition:
        return True
    return is_inside(path, ctx.write_dir)


def is_secret(ctx: Context, raw: str) -> bool:
    """True when `raw` names secret material (5.4.4). `.env.example` stays readable."""
    if not raw:
        return False
    expanded = os.path.expanduser(raw)
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = ctx.cwd / candidate
    parts = {part.lower() for part in candidate.parts}
    if parts & {name.lower() for name in ctx.get("secret_dir_names", [])}:
        return True
    name = candidate.name
    for exception in ctx.get("secret_suffix_exceptions", []):
        if name.endswith(str(exception)):
            return False
    for suffix in ctx.get("secret_suffixes", []):
        if name.endswith(str(suffix)):
            return True
    posix = candidate.as_posix()
    for prefix in ctx.get("secret_path_prefixes", []):
        expanded_prefix = Path(os.path.expanduser(str(prefix))).as_posix()
        if posix == expanded_prefix or posix.startswith(expanded_prefix + "/"):
            return True
    return False


# ------------------------------------------------------------------- shell scanning


def _match_delimiter(text: str, start: int, opener: str, closer: str) -> tuple[str, int]:
    """Return the body between balanced delimiters and the index after the closer."""
    depth = 1
    in_single = False
    in_double = False
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "\\" and not in_single and i + 1 < len(text):
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start:i], i + 1
        i += 1
    raise Blocked("unbalanced command substitution")


def _match_backtick(text: str, start: int) -> tuple[str, int]:
    i = start
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] == "`":
            return text[start:i], i + 1
        i += 1
    raise Blocked("unbalanced backtick substitution")


def extract_substitutions(text: str) -> tuple[str, list[str]]:
    """Split `$( )`, backticks and `<( )`/`>( )` out of `text` (H8).

    Single-quoted bodies are left in place because the shell does not execute them.
    """
    out: list[str] = []
    bodies: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and not in_single and i + 1 < len(text):
            out.append(text[i : i + 2])
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
            i += 1
            continue
        if not in_single:
            pair = text[i : i + 2]
            if pair == "$(" or (not in_double and pair in ("<(", ">(")):
                body, end = _match_delimiter(text, i + 2, "(", ")")
                bodies.append(body)
                out.append(SUBSTITUTION_PLACEHOLDER)
                i = end
                continue
            if ch == "`":
                body, end = _match_backtick(text, i + 1)
                bodies.append(body)
                out.append(SUBSTITUTION_PLACEHOLDER)
                i = end
                continue
        out.append(ch)
        i += 1
    if in_single or in_double:
        raise Blocked("unbalanced quotes in command")
    return "".join(out), bodies


def split_segments(text: str) -> list[str]:
    """Split on `;`, `&&`, `||`, `|`, `&` and newlines outside quotes."""
    segments: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and not in_single and i + 1 < len(text):
            current.append(text[i : i + 2])
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            i += 1
            continue
        if not in_single and not in_double:
            if text[i : i + 2] in ("&&", "||", "|&", ";;"):
                segments.append("".join(current))
                current = []
                i += 2
                continue
            if ch in ";|&\n":
                segments.append("".join(current))
                current = []
                i += 1
                continue
        current.append(ch)
        i += 1
    segments.append("".join(current))
    return [segment.strip() for segment in segments if segment.strip()]


def tokenise(segment: str) -> list[str]:
    """Tokenise one segment, keeping shell operators as separate tokens."""
    lexer = shlex.shlex(segment, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError as exc:
        raise Blocked(f"unparsable command segment: {exc}") from exc


# ------------------------------------------------------------------ bash inspection


def strip_wrappers(words: list[str]) -> list[str]:
    """Remove assignments, `env`, and the wrappers listed in 5.4.5 step 3."""
    changed = True
    while changed and words:
        changed = False
        head = os.path.basename(words[0])
        if ASSIGNMENT.match(words[0]):
            words = words[1:]
            changed = True
        elif head == "env":
            words = words[1:]
            while words and (ASSIGNMENT.match(words[0]) or words[0].startswith("-")):
                words = words[1:]
            changed = True
        elif head in SIMPLE_WRAPPERS:
            words = words[1:]
            changed = True
        elif head in FLAG_WRAPPERS:
            words = words[1:]
            while words and (words[0].startswith("-") or DURATION.match(words[0])):
                words = words[1:]
            changed = True
        elif words[0] in SHELL_KEYWORDS:
            words = words[1:]
            changed = True
    return words


def git_subcommand(words: list[str]) -> str | None:
    index = 1
    while index < len(words):
        word = words[index]
        if word.startswith("-"):
            if word in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
                index += 2
            else:
                index += 1
            continue
        return word
    return None


def first_operand(words: list[str]) -> str | None:
    for word in words[1:]:
        if not word.startswith("-"):
            return word
    return None


def check_pi_script(ctx: Context, token: str) -> None:
    normalised = token.replace("\\", "/")
    for fragment in ctx.get("pi_script_fragments", []):
        if str(fragment) in normalised:
            raise Blocked(f"C5: host reconciliation script is Pi-only: {token}")
    if os.path.basename(normalised) in ctx.names("pi_script_basenames"):
        raise Blocked(f"C5: Pi-only script must not be executed here: {token}")


def operands(ctx: Context, words: list[str], head: str) -> list[str]:
    """Return the positional operands of `words`, without flags and their values."""
    result: list[str] = []
    skip_next = False
    for word in words[1:]:
        if skip_next:
            skip_next = False
            continue
        if word.startswith("-"):
            if head in ("install", "chmod", "chown", "chgrp") and word in ("-m", "-o", "-g"):
                skip_next = True
            continue
        if "=" in word and head == "dd":
            key, value = word.split("=", 1)
            if key == "of":
                result.append(value)
            continue
        if head in ctx.names("mode_operand_heads") and (
            FILE_MODE.match(word) or (":" in word and OWNER_SPEC.match(word))
        ):
            continue
        result.append(word)
    return result


def write_targets(ctx: Context, words: list[str], head: str) -> list[str]:
    """Operands that the command would write to (5.4.5, C1 row).

    `cp`, `mv`, `ln` and `install` write only to their last operand; the preceding
    operands are sources and are checked for secrets, not for write permission.
    `sed -i` takes a script as its first operand unless `-e`/`-f` is given.
    """
    values = operands(ctx, words, head)
    if not values:
        return []
    if head == "dd":
        return values
    if head in ctx.names("target_last_operand_heads"):
        return values[-1:]
    if head == "sed":
        if any(word.startswith(("-e", "-f", "--expression", "--file")) for word in words[1:]):
            return values
        return values[1:]
    return values


def check_write_operands(ctx: Context, words: list[str], head: str) -> None:
    for target in write_targets(ctx, words, head):
        if target == "{}":
            raise Blocked(f"C1: `{head}` would write to the files matched by `find`")
        if is_self_protected(ctx, resolve(ctx, target)):
            raise Blocked(f"self-protection: only the operator edits {target}")
        if not is_write_allowed(ctx, target):
            raise Blocked(f"C1: `{head}` would write outside .claude/: {target}")


def check_secret_operands(ctx: Context, words: list[str], head: str) -> None:
    for word in words[1:]:
        if word.startswith("-"):
            continue
        if "=" in word and head == "dd":
            word = word.split("=", 1)[1]
        if is_secret(ctx, word):
            raise Blocked(f"C3: `{head}` would read secret material: {word}")


def check_redirections(ctx: Context, tokens: list[str]) -> list[str]:
    """Validate redirect targets and return the remaining command words."""
    words: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("<<", "<<<"):
            raise Blocked("C1: here-documents are not inspectable during the transition")
        if token in REDIRECT_OPS or re.fullmatch(r"[0-9]*(>>|>\||>&|&>>|&>|>|<)", token):
            if words and words[-1].isdigit():
                words.pop()
            target = tokens[index + 1] if index + 1 < len(tokens) else None
            if target is None:
                raise Blocked("C1: redirection without a target")
            index += 2
            if token.endswith("&") or target.startswith("&") or target.isdigit():
                continue
            if token.endswith("<"):
                if is_secret(ctx, target):
                    raise Blocked(f"C3: input redirection reads secret material: {target}")
                continue
            if not is_write_allowed(ctx, target):
                raise Blocked(f"C1: redirection would write outside .claude/: {target}")
            continue
        if token in ("(", ")", "|", "||", "&&", "&", ";"):
            index += 1
            continue
        words.append(token)
        index += 1
    return words


def analyse_segment(ctx: Context, tokens: list[str], depth: int) -> None:
    words = strip_wrappers(check_redirections(ctx, tokens))
    if not words:
        return
    head = words[0]
    base = os.path.basename(head)

    check_pi_script(ctx, head)

    if base in ctx.names("shell_heads"):
        if "-c" in words:
            analyse_bash(ctx, words[words.index("-c") + 1], depth + 1)
            return
        operand = first_operand(words)
        if operand is not None:
            check_pi_script(ctx, operand)
        raise Blocked("C1/C5: shell invocation without `-c` hides the executed code")

    if base in ctx.names("interpreter_heads"):
        inline = ctx.names("interpreter_inline_flags")
        if any(word in inline for word in words[1:]):
            raise Blocked(f"C1: inline interpreter code is not inspectable: {base}")

    if base in ctx.names("nested_exec_heads"):
        analyse_nested(ctx, base, words, depth)
        return

    if base == "git":
        subcommand = git_subcommand(words)
        if subcommand in ctx.names("denied_git_subcommands"):
            raise Blocked(f"C4: git {subcommand} is reserved for the operator")
        if subcommand in ctx.names("write_git_subcommands"):
            check_write_operands(ctx, words, base)
        return

    if base in ctx.names("operator_only_heads"):
        raise Blocked(f"C4: `{base}` changes repository state and is reserved for the operator")

    if base in ctx.names("remote_heads"):
        raise Blocked(f"C5: remote access tool is denied: {base}")

    if base in ctx.names("host_mutation_heads"):
        raise Blocked(f"C5: host mutation command is denied: {base}")

    if base in ctx.names("denied_heads"):
        raise Blocked(f"C2: command has side effects and is denied: {base}")

    if base == "make":
        check_make(ctx, words)
        return

    if base == "docker":
        check_docker(ctx, words)
        return

    if base in ("pip", "pip3"):
        subcommand = first_operand(words)
        if subcommand not in ctx.names("allowed_pip_subcommands"):
            raise Blocked(f"C2: pip {subcommand} modifies the environment")
        return

    if base == "ruff":
        check_ruff(ctx, words)
        return

    if base == "sed" and any(word.startswith("-i") for word in words[1:]):
        check_write_operands(ctx, words, base)
        check_secret_operands(ctx, words, base)
        return

    if base in ctx.names("write_heads"):
        check_write_operands(ctx, words, base)
        if base == "dd":
            check_secret_operands(ctx, words, base)

    if base in ctx.names("secret_read_heads"):
        check_secret_operands(ctx, words, base)

    if base in ctx.names("target_last_operand_heads"):
        for source in operands(ctx, words, base)[:-1]:
            if is_secret(ctx, source):
                raise Blocked(f"C3: `{base}` would copy secret material: {source}")


def analyse_nested(ctx: Context, base: str, words: list[str], depth: int) -> None:
    """Recurse into commands that another command executes (5.4.5 step 2)."""
    if base == "eval":
        analyse_bash(ctx, " ".join(words[1:]), depth + 1)
        return
    if base == "xargs":
        rest = words[1:]
        while rest and rest[0].startswith("-"):
            if rest[0] in ("-n", "-I", "-P", "-L", "-d", "-s", "-a", "-E"):
                rest = rest[2:]
            else:
                rest = rest[1:]
        if rest:
            analyse_bash(ctx, shlex.join(rest), depth + 1)
        return
    if base == "find":
        for flag in ("-exec", "-execdir"):
            if flag in words:
                rest = words[words.index(flag) + 1 :]
                inner: list[str] = []
                for word in rest:
                    if word in (";", "+"):
                        break
                    inner.append(word)
                if inner:
                    analyse_bash(ctx, shlex.join(inner), depth + 1)
        if "-delete" in words:
            raise Blocked("C1: `find -delete` removes files outside .claude/")
        return
    if base == "watch":
        rest = [word for word in words[1:] if not word.startswith("-")]
        if rest:
            analyse_bash(ctx, shlex.join(rest), depth + 1)
        return
    if base == "flock":
        rest = words[1:]
        while rest and rest[0].startswith("-"):
            rest = rest[1:]
        if len(rest) > 1:
            analyse_bash(ctx, shlex.join(rest[1:]), depth + 1)
        return


def check_make(ctx: Context, words: list[str]) -> None:
    allowed = ctx.names("allowed_make_targets")
    targets = [word for word in words[1:] if not word.startswith("-") and "=" not in word]
    if not targets:
        raise Blocked("C2: bare `make` runs the default target and modifies the tree")
    for target in targets:
        if target not in allowed:
            raise Blocked(
                f"C2: make target `{target}` has side effects (allowed: {sorted(allowed)})"
            )


def check_docker(ctx: Context, words: list[str]) -> None:
    subcommand = first_operand(words)
    if subcommand == "compose":
        rest = words[words.index("compose") + 1 :]
        index = 0
        while index < len(rest):
            if rest[index].startswith("-"):
                index += 2 if rest[index] in ("-f", "--file", "-p", "--project-name") else 1
                continue
            break
        inner = rest[index] if index < len(rest) else None
        if inner not in ctx.names("allowed_docker_compose_subcommands"):
            raise Blocked(f"C2: `docker compose {inner}` changes runtime state")
        return
    if subcommand not in ctx.names("allowed_docker_subcommands"):
        raise Blocked(f"C2: `docker {subcommand}` is not a read-only docker command")


def check_ruff(ctx: Context, words: list[str]) -> None:
    subcommand = first_operand(words)
    flags = set(words[1:])
    if subcommand == "check" and "--no-fix" in flags:
        return
    if subcommand == "format" and ({"--check", "--diff"} & flags):
        return
    raise Blocked("C2: ruff may only run as `check --no-fix` or `format --check`")


def analyse_bash(ctx: Context, command: str, depth: int = 0) -> None:
    if depth > int(ctx.get("max_nesting_depth", 5)):
        raise Blocked("C1: command nesting is too deep to inspect safely")
    if depth == 0:
        raw_scan(ctx, command)
    stripped, bodies = extract_substitutions(command)
    for body in bodies:
        analyse_bash(ctx, body, depth + 1)
    for segment in split_segments(stripped):
        analyse_segment(ctx, tokenise(segment), depth)


def raw_scan(ctx: Context, command: str) -> None:
    """Catch Pi identifiers that quoting tricks would hide from the parser (step 7)."""
    normalised = re.sub(r"[\\'\"]", "", command).lower()
    for identifier in ctx.get("pi_identifiers", []):
        if str(identifier).lower() in normalised:
            raise Blocked(f"C5: command references the Raspberry Pi ({identifier})")


# ------------------------------------------------------------------------- tools


def check_file_tool(ctx: Context, tool_input: dict) -> None:
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw:
        raise Blocked("fail-closed: file tool without a usable path")
    path = resolve(ctx, raw)
    if is_self_protected(ctx, path):
        raise Blocked(f"self-protection: only the operator edits {raw}")
    if ctx.transition and not is_inside(path, ctx.write_dir):
        raise Blocked(f"C1: writes are restricted to .claude/ during the transition: {raw}")


def check_read_tool(ctx: Context, tool_name: str, tool_input: dict) -> None:
    if tool_name == "Read":
        raw = tool_input.get("file_path")
        if not isinstance(raw, str) or not raw:
            raise Blocked("fail-closed: Read without a usable path")
    for key in ("file_path", "path", "pattern", "glob"):
        value = tool_input.get(key)
        if isinstance(value, str) and is_secret(ctx, value):
            raise Blocked(f"C3: secret material must not be read: {value}")


def check_webfetch(ctx: Context, tool_input: dict) -> None:
    url = tool_input.get("url")
    if not isinstance(url, str) or not url:
        raise Blocked("fail-closed: WebFetch without a usable url")
    lowered = url.lower()
    for identifier in ctx.get("pi_identifiers", []):
        if str(identifier).lower() in lowered:
            raise Blocked(f"C5: fetching from the Raspberry Pi is denied ({identifier})")


def dispatch(ctx: Context, tool_name: str, tool_input: dict) -> None:
    if tool_name in FILE_WRITE_TOOLS:
        check_file_tool(ctx, tool_input)
        return
    if tool_name in FILE_READ_TOOLS:
        check_read_tool(ctx, tool_name, tool_input)
        return
    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            raise Blocked("fail-closed: Bash without a usable command string")
        analyse_bash(ctx, command)
        return
    if tool_name == "WebFetch":
        check_webfetch(ctx, tool_input)
        return
    if EDIT_LIKE_NAME.search(tool_name) and (
        "file_path" in tool_input or "notebook_path" in tool_input
    ):
        check_file_tool(ctx, tool_input)


# ----------------------------------------------------------------------- plumbing


def config_path(argv: list[str]) -> Path:
    if "--config" in argv:
        index = argv.index("--config")
        if index + 1 < len(argv):
            return Path(argv[index + 1])
        raise Blocked("fail-closed: --config without a value")
    return Path(__file__).resolve().parent / "guard-config.json"


def project_root(event: dict, cwd: Path) -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(os.path.realpath(env_root))
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(os.path.realpath(result.stdout.strip()))
    raise Blocked("fail-closed: project root could not be determined")


def log_decision(root: Path | None, entry: dict) -> None:
    if root is None:
        return
    with contextlib.suppress(Exception):
        directory = root / ".claude" / "logs"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "guard.log").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


def summarise(tool_name: str, tool_input: dict) -> str:
    for key in ("command", "file_path", "notebook_path", "url", "path", "pattern"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return f"{key}={value[:500]}"
    return tool_name


def main(argv: list[str]) -> int:
    root: Path | None = None
    tool_name = "?"
    summary = "?"
    try:
        config = json.loads(config_path(argv).read_text(encoding="utf-8"))
        event = json.loads(sys.stdin.read())
        if not isinstance(event, dict):
            raise Blocked("fail-closed: event payload is not an object")
        tool_name = str(event.get("tool_name", ""))
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            raise Blocked("fail-closed: tool_input is not an object")
        summary = summarise(tool_name, tool_input)
        cwd = Path(os.path.realpath(str(event.get("cwd") or os.getcwd())))
        root = project_root(event, cwd)
        dispatch(Context(config, root, cwd), tool_name, tool_input)
    except Blocked as blocked:
        reason = str(blocked)
        log_decision(root, _entry(tool_name, summary, "block", reason))
        print(f"guard: {reason}", file=sys.stderr)
        return EXIT_BLOCK
    except Exception as exc:  # H2: anything unexpected blocks
        reason = f"fail-closed: {type(exc).__name__}: {exc}"
        log_decision(root, _entry(tool_name, summary, "block", reason))
        print(f"guard: {reason}", file=sys.stderr)
        return EXIT_BLOCK
    log_decision(root, _entry(tool_name, summary, "pass", ""))
    return EXIT_PASS


def _entry(tool_name: str, summary: str, decision: str, reason: str) -> dict:
    return {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": tool_name,
        "input": summary,
        "decision": decision,
        "reason": reason,
    }


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
