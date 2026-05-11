from __future__ import annotations

import argparse
import pathlib
import re
from datetime import datetime
from typing import Sequence


TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".csv"}
SIGNAL = re.compile(
    r"(决策|规则|约束|根因|正确做法|验证|风险|后续|目标|阻塞|待办|todo|next|decision|constraint|lesson|blocker|snapshot|context)",
    re.I,
)
SENSITIVE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|api[_-]?key|token|password|BEGIN .*PRIVATE KEY)", re.I)
SKIP_PARTS = {".git", "sessions", "log", "logs", "cache", "tmp", ".tmp", "mcp/secrets"}


def readable(path: pathlib.Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_SUFFIXES


def list_files(root: pathlib.Path) -> list[pathlib.Path]:
    if not root.exists():
        return []
    files: list[pathlib.Path] = []
    for path in root.rglob("*"):
        parts = set(path.relative_to(root).parts)
        if parts & SKIP_PARTS:
            continue
        if readable(path):
            files.append(path)
    return sorted(files)


def safe_read(path: pathlib.Path, limit: int = 120_000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return data[:limit]


def redact(value: str) -> str:
    return SENSITIVE.sub("[REDACTED]", value)


def rel(path: pathlib.Path, root: pathlib.Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def extract_signals(path: pathlib.Path, max_items: int = 12) -> list[str]:
    text = safe_read(path)
    items: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) > 220:
            continue
        if line.startswith("#") or SIGNAL.search(line):
            items.append(redact(line))
        if len(items) >= max_items:
            break
    return items


def classify_action(line: str) -> str:
    lower = line.lower()
    if "不得" in line or "禁止" in line or "必须" in line or "rule" in lower:
        return "promote-to-agents"
    if any(word in lower for word in ["blocker", "snapshot", "context", "open work"]) or any(word in line for word in ["目标", "阻塞", "待办"]):
        return "write-to-codex-agent-mem"
    if "决策" in line or "decision" in lower or "根因" in line or "验证" in line:
        return "archive-only"
    if "todo" in lower or "后续" in line or "next" in lower:
        return "drop-or-review"
    return "archive-only"


def codex_agent_mem_sources(repo: pathlib.Path, memories: pathlib.Path) -> list[pathlib.Path]:
    roots = [
        pathlib.Path.home() / ".codex_agent_mem",
        memories / ".codex-agent-mem",
        repo / "docs/archive/codex-agent-mem",
    ]
    files: list[pathlib.Path] = []
    for root in roots:
        files.extend(list_files(root))
    return sorted(dict.fromkeys(files))


def section(title: str, lines: list[str]) -> list[str]:
    return [f"## {title}", "", *lines, ""]


def bullet_files(paths: list[pathlib.Path], root: pathlib.Path, max_items: int = 80) -> list[str]:
    if not paths:
        return ["- 无"]
    rows = [f"- `{rel(path, root)}`" for path in paths[:max_items]]
    if len(paths) > max_items:
        rows.append(f"- ... 另有 {len(paths) - max_items} 个文件")
    return rows


def build_report(repo: pathlib.Path, memories: pathlib.Path, days: int) -> str:
    now = datetime.now().astimezone()
    agents = [path for path in [repo / "AGENTS.md", repo / "src/codex-home/AGENTS.md"] if path.is_file()]
    memory_files = list_files(memories)
    codex_agent_mem_files = codex_agent_mem_sources(repo, memories)
    archive_files = list_files(repo / "docs/archive")
    decision_files = [
        path
        for path in list_files(repo / "docs")
        if re.search(r"(decision|adr|决策|设计|summary|总结|debug|排障)", path.as_posix(), re.I)
    ]
    signal_sources = agents + memory_files + codex_agent_mem_files + decision_files[:80]

    lines: list[str] = [
        f"# Memory Curation {now.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "本报告用于周期性整理 Codex memories、项目 AGENTS、会话总结和决策记录。",
        "默认只产出审计材料，不直接修改 `~/.codex/memories` 或 `AGENTS.md`。",
        "",
        f"- Repo: `{repo}`",
        f"- Memories: `{memories}`",
        f"- Window: `{days}` days hint",
        "",
    ]

    lines += section("输入概览", [
        f"- Memory files: `{len(memory_files)}`",
        f"- codex-agent-mem files: `{len(codex_agent_mem_files)}`",
        f"- AGENTS files: `{len(agents)}`",
        f"- Archive files: `{len(archive_files)}`",
        f"- Decision-like docs: `{len(decision_files)}`",
    ])
    lines += section("Memory 文件", bullet_files(memory_files, memories))
    lines += section("codex-agent-mem 候选输入", bullet_files(codex_agent_mem_files, pathlib.Path.home()))
    lines += section("AGENTS 文件", bullet_files(agents, repo))
    lines += section("候选知识来源", bullet_files(decision_files, repo))

    signal_lines: list[str] = []
    action_rows: list[str] = ["| Action | Source | Signal |", "| --- | --- | --- |"]
    for path in signal_sources:
        signals = extract_signals(path)
        if not signals:
            continue
        signal_lines.append(f"### `{rel(path, repo)}`")
        signal_lines.append("")
        signal_lines.extend(f"- {item}" for item in signals)
        signal_lines.append("")
        for item in signals[:6]:
            action_rows.append(f"| `{classify_action(item)}` | `{rel(path, repo)}` | {item} |")
    lines += section("可复用信号摘录", signal_lines or ["- 暂无"])

    lines += section("候选整理动作", [
        "- `promote-to-agents`：跨会话行为规则、硬约束、反复验证的工作方式",
        "- `write-to-codex-agent-mem`：短小结构化的目标、阻塞、open work、snapshot、项目事实",
        "- `archive-only`：长文章、日报、调研证据、排障叙事、历史背景",
        "- `drop-or-review`：一次性过程噪音、过期 TODO、机器私有状态、需要人工判断的信息",
    ])
    lines += section("阶段模型", [
        "- Phase 1 报告归档：默认阶段，只生成 `docs/archive/` 归档和本审计报告",
        "- Phase 2 手动写入：人工确认后才写入 `~/.codex/memories` 或 codex-agent-mem note/snapshot",
        "- Phase 3 任务闭环：会话开始读取 context，会话结束执行 `knowledge-archive + memory-curator`",
    ])
    lines += section("动作建议矩阵", action_rows if len(action_rows) > 2 else ["- 暂无"])
    lines += section("人工审核清单", [
        "- 是否存在敏感信息需要删除",
        "- 是否有过期规则需要废弃",
        "- 是否有高频经验应提升为 AGENTS 规则",
        "- 是否有短小结构化状态应手动写入 codex-agent-mem note/snapshot",
        "- 是否有长材料应只保留在 `docs/archive/`",
        "- 不要自动双写到 `~/.codex/memories` 与 codex-agent-mem",
    ])
    return "\n".join(lines)


def write_candidate(memories: pathlib.Path, report: str) -> pathlib.Path:
    out = memories / ".codex/curation-inbox" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-memory-candidate.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    content = [
        "# Memory Candidate",
        "",
        "本文件由 memory-curator 生成，必须人工审核后才可提升为正式 memory。",
        "",
        "## Review Required",
        "",
        "- 删除敏感信息",
        "- 删除一次性过程记录",
        "- 只保留稳定、短小、可复用的偏好/约束/项目事实",
        "",
        "## Source Report Excerpt",
        "",
        report[:20_000],
        "",
    ]
    out.write_text("\n".join(content), encoding="utf-8")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Curate Codex memory sources into an auditable report.")
    parser.add_argument("--repo", default=str(pathlib.Path.home() / "codex"))
    parser.add_argument("--memories", default=str(pathlib.Path.home() / ".codex/memories"))
    parser.add_argument("--output", default="")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-memory-candidate", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo).expanduser().resolve()
    memories = pathlib.Path(args.memories).expanduser().resolve()
    report = build_report(repo, memories, args.days)
    default_output = repo / "docs/archive/memory-curation" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-memory-curation.md"
    output = pathlib.Path(args.output).expanduser().resolve() if args.output else default_output

    if args.dry_run:
        print(report)
        print(f"[DRY ] output={output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"[DONE] report={output}")

    if args.write_memory_candidate:
        candidate = write_candidate(memories, report)
        print(f"[DONE] memory_candidate={candidate}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
