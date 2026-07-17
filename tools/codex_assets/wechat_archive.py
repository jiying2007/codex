from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable, Sequence
from urllib.parse import urlencode, urlparse


DEFAULT_TOPICS = (
    "LLM",
    "大模型",
    "Agent",
    "智能体",
    "Skill",
    "Skills",
    "Workflow",
    "工作流",
    "Profile",
    "MCP",
    "Hook",
    "Harness",
    "上下文工程",
    "Agent 记忆",
    "Token 优化",
    "多 Agent",
    "AI Coding",
    "Agent 评测",
    "Agent 安全",
    "工具调用",
    "RAG",
)

TOPIC_PATTERNS: dict[str, str] = {
    "llm": r"\bllm\b|大模型|混元|通义|qwen",
    "agent": r"\bagent(?:ic|s)?\b|智能体|多智能体|multi-agent",
    "skill": r"\bskills?\b|技能",
    "workflow": r"\bworkflow\b|工作流|流程编排",
    "profile": r"\bprofile\b|配置画像",
    "mcp": r"\bmcp\b|model context protocol",
    "hook": r"\bhooks?\b|钩子",
    "harness": r"\bharness\b",
    "context": r"上下文|context engineering|context rot|token",
    "memory": r"记忆|memory",
    "rag": r"\brag\b|检索增强|知识库",
    "tool-calling": r"工具调用|function calling|tool calling|tool use",
    "evaluation": r"评测|评估|质量反馈|测试智能体",
    "security": r"安全|越权|注入|投毒|权限",
    "ai-coding": r"ai\s*cod(?:ing|e)|代码生成|研发效能|vibe coding",
}

FORBIDDEN_PERSISTED_KEYS = {
    "content",
    "body",
    "html",
    "raw_html",
    "cookie",
    "cookies",
    "authorization",
    "session",
}

ACCESS_GATE_TERMS = (
    "antispider",
    "captcha",
    "wappoc_appmsgcaptcha",
    "请输入验证码",
    "人机验证",
    "环境异常",
    "访问过于频繁",
    "登录后继续",
)


class WechatArchiveError(RuntimeError):
    pass


class AccessGateError(WechatArchiveError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_title(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)


def topic_hits(text: str) -> list[str]:
    return [
        name
        for name, pattern in TOPIC_PATTERNS.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise WechatArchiveError(f"{field} must be YYYY-MM-DD: {value}") from exc


def ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = raw.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def parse_accounts(values: Sequence[str]) -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        parts = ordered_unique(raw.split("|"))
        if not parts:
            continue
        canonical = parts[0]
        key = canonical.casefold()
        if key in seen:
            raise WechatArchiveError(f"duplicate canonical account: {canonical}")
        seen.add(key)
        accounts.append({"canonical": canonical, "aliases": parts})
    if not accounts:
        raise WechatArchiveError("at least one --account is required")
    return accounts


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WechatArchiveError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WechatArchiveError(f"invalid JSON: {path}: {exc}") from exc


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WechatArchiveError(f"invalid JSONL at {path}:{number}: {exc}") from exc
        if not isinstance(value, dict):
            raise WechatArchiveError(f"JSONL record must be an object: {path}:{number}")
        records.append(value)
    return records


def plan_path(args: argparse.Namespace) -> pathlib.Path:
    if args.plan_file:
        return pathlib.Path(args.plan_file).expanduser().resolve()
    return pathlib.Path(args.output_dir).expanduser().resolve() / "plan.json"


def evidence_path(args: argparse.Namespace) -> pathlib.Path:
    if args.evidence_file:
        return pathlib.Path(args.evidence_file).expanduser().resolve()
    return pathlib.Path(args.output_dir).expanduser().resolve() / "evidence.jsonl"


def make_plan(args: argparse.Namespace) -> dict[str, Any]:
    accounts = parse_accounts(args.account)
    start = parse_date(args.date_from, "--date-from")
    end = parse_date(args.date_to, "--date-to")
    if start > end:
        raise WechatArchiveError("--date-from must not be after --date-to")
    topics = ordered_unique(args.topic or DEFAULT_TOPICS)
    if not topics:
        raise WechatArchiveError("at least one topic is required")
    queries = [
        {"account": account["canonical"], "topic": topic, "query": f"{account['canonical']} {topic}"}
        for account in accounts
        for topic in topics
    ]
    if len(queries) > args.max_queries:
        raise WechatArchiveError(
            f"query plan has {len(queries)} queries, above --max-queries={args.max_queries}"
        )
    if not 1 <= args.max_results_per_query <= 10:
        raise WechatArchiveError("--max-results-per-query must be in 1..10")
    if not 1 <= args.max_candidates <= 100:
        raise WechatArchiveError("--max-candidates must be in 1..100")
    if args.delay < 1:
        raise WechatArchiveError("--delay must be at least 1 second")
    return {
        "schema_version": 1,
        "kind": "wechat-account-research-plan",
        "created_at": now_utc(),
        "accounts": accounts,
        "window": {"from": start.isoformat(), "to": end.isoformat(), "inclusive": True},
        "topics": topics,
        "queries": queries,
        "seed_urls": ordered_unique(args.seed_url),
        "limits": {
            "max_queries": args.max_queries,
            "max_results_per_query": args.max_results_per_query,
            "max_candidates": args.max_candidates,
            "delay_seconds": args.delay,
            "retry_budget_after_access_gate": 0,
        },
        "body_policy": "persist-never",
        "access_policy": "public-read-only-stop-on-gate",
    }


def account_for_source(plan: dict[str, Any], source: str) -> str:
    actual = source.strip().casefold()
    if not actual:
        return ""
    for account in plan["accounts"]:
        if actual in {str(item).strip().casefold() for item in account["aliases"]}:
            return str(account["canonical"])
    return ""


def account_aliases(plan: dict[str, Any], canonical: str) -> set[str]:
    for account in plan["accounts"]:
        if account["canonical"] == canonical:
            return {str(item).strip() for item in account["aliases"]}
    return {canonical}


def candidate_key(account: str, title: str) -> str:
    value = f"{account.casefold()}\0{normalize_title(title)}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def iter_index_values(value: Any) -> Iterable[dict[str, Any]]:
    values: Any
    if isinstance(value, dict):
        values = value.values()
    elif isinstance(value, list):
        values = value
    else:
        raise WechatArchiveError("discovery index must be a JSON object or array")
    for item in values:
        if isinstance(item, dict):
            yield item


def load_index_candidates(plan: dict[str, Any], path: pathlib.Path) -> tuple[list[dict[str, Any]], int]:
    raw = load_json(path)
    chosen: dict[str, dict[str, Any]] = {}
    raw_count = 0
    for item in iter_index_values(raw):
        raw_count += 1
        title = str(item.get("title", "")).strip()
        source = str(item.get("source", "")).strip()
        account = account_for_source(plan, source)
        if not title or not account:
            continue
        summary = str(item.get("summary", "")).strip()
        hits = topic_hits(f"{title} {summary}")
        if not hits:
            continue
        key = candidate_key(account, title)
        candidate = {
            "candidate_key": key,
            "requested_account": account,
            "candidate_title": title,
            "discovery_source": source,
            "discovery_query": str(item.get("keyword", "")),
            "discovery_topic_hits": hits,
            "_redirect_url": str(item.get("url", "")),
            "_summary_length": len(summary),
            "_fresh": False,
        }
        current = chosen.get(key)
        if current is None or candidate["_summary_length"] > current["_summary_length"]:
            chosen[key] = candidate
    return sorted(chosen.values(), key=lambda item: item["candidate_key"]), raw_count


def decode_agent_value(raw: str) -> Any:
    value: Any = raw.strip()
    for _ in range(3):
        if not isinstance(value, str):
            break
        text = value.strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            break
    return value


class BrowserClient:
    def __init__(self, binary: str = ""):
        resolved = binary or shutil.which("agent-browser")
        if not resolved:
            raise WechatArchiveError("agent-browser not found; pass --agent-browser-bin")
        self.binary = str(pathlib.Path(resolved).expanduser().absolute())

    def run(self, args: Sequence[str], timeout: int = 30, allow_failure: bool = False) -> str:
        try:
            result = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            if allow_failure:
                return ""
            raise WechatArchiveError(f"agent-browser timeout: {args[:2]}") from exc
        if result.returncode and not allow_failure:
            detail = (result.stderr or result.stdout).strip()[:300]
            raise WechatArchiveError(f"agent-browser failed ({result.returncode}): {detail}")
        return result.stdout.strip()

    def open(self, url: str) -> None:
        self.run(["open", url], timeout=30)
        self.run(["wait", "--load", "networkidle"], timeout=20, allow_failure=True)

    def evaluate(self, script: str, timeout: int = 20) -> Any:
        return decode_agent_value(self.run(["eval", script], timeout=timeout))

    def close(self) -> None:
        self.run(["close", "--all"], timeout=15, allow_failure=True)


PROBE_JS = r"""
(function() {
  return JSON.stringify({
    href: document.location.href || '',
    text: document.body ? document.body.innerText.substring(0, 800) : ''
  });
})()
"""


def access_gate_reason(probe: dict[str, Any]) -> str:
    text = f"{probe.get('href', '')}\n{probe.get('text', '')}".casefold()
    for term in ACCESS_GATE_TERMS:
        if term.casefold() in text:
            return term
    return ""


def assert_not_gated(client: BrowserClient) -> dict[str, Any]:
    value = client.evaluate(PROBE_JS)
    probe = value if isinstance(value, dict) else {}
    reason = access_gate_reason(probe)
    if reason:
        raise AccessGateError(f"access gate detected: {reason}")
    return probe


SEARCH_RESULTS_JS = r"""
(function() {
  var rows = [];
  var items = document.querySelectorAll('.news-list li, .txt-box');
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    var a = item.querySelector('h3 a, h4 a, .tit a');
    if (!a || !a.href) continue;
    var source = item.querySelector('a.account, .account');
    var summary = item.querySelector('.txt-info, p.txt-info');
    rows.push({
      title: (a.textContent || '').trim().substring(0, 200),
      source: source ? (source.textContent || '').trim() : '',
      summary: summary ? (summary.textContent || '').trim().substring(0, 500) : '',
      url: a.href
    });
  }
  return JSON.stringify(rows);
})()
"""


def search_sogou(client: BrowserClient, query: str, limit: int) -> list[dict[str, str]]:
    url = "https://weixin.sogou.com/weixin?" + urlencode(
        {"type": 2, "query": query, "page": 1, "ie": "utf8"}
    )
    client.open(url)
    assert_not_gated(client)
    value = client.evaluate(SEARCH_RESULTS_JS)
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        href = str(item.get("url", "")).strip()
        key = normalize_title(title)
        if not title or not href or key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "title": title,
                "source": str(item.get("source", "")).strip(),
                "summary": str(item.get("summary", "")).strip(),
                "url": href,
            }
        )
        if len(result) >= limit:
            break
    return result


def discover_online(
    plan: dict[str, Any], client: BrowserClient
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    chosen: dict[str, dict[str, Any]] = {}
    stats = {"queries_attempted": 0, "raw_hits": 0}
    limit = int(plan["limits"]["max_results_per_query"])
    delay = float(plan["limits"]["delay_seconds"])
    for query in plan["queries"]:
        rows = search_sogou(client, str(query["query"]), limit)
        stats["queries_attempted"] += 1
        stats["raw_hits"] += len(rows)
        aliases = account_aliases(plan, str(query["account"]))
        alias_keys = {item.casefold() for item in aliases}
        for row in rows:
            source = row["source"].strip()
            if source and source.casefold() not in alias_keys:
                continue
            hits = topic_hits(f"{row['title']} {row['summary']}")
            if not hits:
                continue
            key = candidate_key(str(query["account"]), row["title"])
            chosen.setdefault(
                key,
                {
                    "candidate_key": key,
                    "requested_account": str(query["account"]),
                    "candidate_title": row["title"],
                    "discovery_source": source,
                    "discovery_query": str(query["query"]),
                    "discovery_topic_hits": hits,
                    "_redirect_url": row["url"],
                    "_summary_length": len(row["summary"]),
                    "_fresh": True,
                },
            )
        time.sleep(delay)
    return sorted(chosen.values(), key=lambda item: item["candidate_key"]), stats


def select_title(expected: str, rows: Sequence[dict[str, str]]) -> tuple[dict[str, str] | None, float]:
    normalized = normalize_title(expected)
    best: dict[str, str] | None = None
    score = 0.0
    for row in rows:
        actual = normalize_title(row.get("title", ""))
        if not actual:
            continue
        candidate_score = SequenceMatcher(None, normalized, actual).ratio()
        if normalized in actual or actual in normalized:
            candidate_score = max(candidate_score, 0.95)
        if candidate_score > score:
            best = row
            score = candidate_score
    return best, score


def resolve_redirect(client: BrowserClient, url: str) -> str:
    client.open(url)
    probe = assert_not_gated(client)
    href = str(probe.get("href", ""))
    return href if "mp.weixin.qq.com" in href else ""


ARTICLE_JS = r"""
(function() {
  function text(selector) {
    var el = document.querySelector(selector);
    return el ? (el.textContent || '').trim() : '';
  }
  var pub = text('#publish_time');
  if (!pub) {
    var scripts = document.querySelectorAll('script');
    for (var i = 0; i < scripts.length; i++) {
      var match = scripts[i].textContent.match(/var\s+(?:create_time|ct)\s*=\s*["']?(\d+)["']?/);
      if (match) {
        pub = new Date(parseInt(match[1], 10) * 1000).toISOString().split('T')[0];
        break;
      }
    }
  }
  var body = document.querySelector('#js_content, .rich_media_content');
  return JSON.stringify({
    title: text('#activity-name') || document.title || '',
    account: text('#js_name') || text('a.rich_media_meta_nickname'),
    pub_date: pub,
    content: body ? body.innerText : ''
  });
})()
"""


def normalized_pub_date(value: str) -> str:
    match = re.search(r"(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})", value)
    if not match:
        return ""
    return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def stable_wechat_locator(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc == "mp.weixin.qq.com" and re.fullmatch(r"/s/[A-Za-z0-9_-]+", parsed.path) and not parsed.query:
        return url
    return ""


def title_query_locator(title: str) -> str:
    return "https://weixin.sogou.com/weixin?" + urlencode({"type": 2, "query": title})


def fetch_article(client: BrowserClient, url: str) -> dict[str, str]:
    client.open(url)
    assert_not_gated(client)
    value = client.evaluate(ARTICLE_JS, timeout=25)
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item or "") for key, item in value.items()}


def base_record(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_key": candidate["candidate_key"],
        "requested_account": candidate.get("requested_account", ""),
        "candidate_title": candidate.get("candidate_title", ""),
        "discovery_source": candidate.get("discovery_source", ""),
        "discovery_query": candidate.get("discovery_query", ""),
        "discovery_topic_hits": candidate.get("discovery_topic_hits", []),
        "retrieved_at": now_utc(),
        "body_persisted": False,
        "temporary_url_persisted": False,
    }


def verify_candidate(
    plan: dict[str, Any],
    client: BrowserClient,
    candidate: dict[str, Any],
    min_similarity: float,
) -> dict[str, Any]:
    base = base_record(candidate)
    source_url = str(candidate.get("_seed_url", ""))
    similarity = 1.0 if source_url else 0.0
    if not source_url:
        redirect = str(candidate.get("_redirect_url", ""))
        if not candidate.get("_fresh") or not redirect:
            rows = search_sogou(client, str(candidate["candidate_title"]), 10)
            selected, similarity = select_title(str(candidate["candidate_title"]), rows)
            if selected is None or similarity < min_similarity:
                return {**base, "status": "search-unresolved", "title_similarity": round(similarity, 4)}
            redirect = selected["url"]
        source_url = resolve_redirect(client, redirect)
        if not source_url:
            return {**base, "status": "redirect-unresolved", "title_similarity": round(similarity, 4)}

    payload = fetch_article(client, source_url)
    content = payload.pop("content", "")
    if len(content) < 100:
        return {
            **base,
            "status": "fetch-inaccessible",
            "title_similarity": round(similarity, 4),
            "temporary_url_sha256": hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        }

    title = payload.get("title", "").strip()
    actual_account = payload.get("account", "").strip()
    pub_date = normalized_pub_date(payload.get("pub_date", ""))
    matched_account = account_for_source(plan, actual_account)
    requested = str(candidate.get("requested_account", ""))
    status = "direct-read"
    if not matched_account or (requested and matched_account != requested):
        status = "account-mismatch"
    elif not pub_date:
        status = "date-unknown"
    else:
        current = parse_date(pub_date, "article date")
        start = parse_date(str(plan["window"]["from"]), "plan window from")
        end = parse_date(str(plan["window"]["to"]), "plan window to")
        if not start <= current <= end:
            status = "out-of-window"

    locator = stable_wechat_locator(str(candidate.get("_seed_url", ""))) or title_query_locator(title or str(candidate["candidate_title"]))
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    return {
        **base,
        "status": status,
        "title": title,
        "account": actual_account,
        "canonical_account": matched_account,
        "pub_date": pub_date,
        "title_similarity": round(similarity, 4),
        "char_count": len(content),
        "paragraph_count": len(paragraphs),
        "code_block_count": len(re.findall(r"```", content)) // 2,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "topic_hits": topic_hits(f"{title}\n{content}"),
        "source_locator": locator,
        "locator_kind": "stable-wechat-short-url" if stable_wechat_locator(locator) else "sogou-title-query",
        "temporary_url_sha256": hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
    }


def seed_candidates(plan: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for url in plan.get("seed_urls", []):
        key = hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:20]
        result.append(
            {
                "candidate_key": f"seed-{key}",
                "requested_account": "",
                "candidate_title": "seed-url",
                "discovery_source": "user-seed",
                "discovery_query": "seed-url",
                "discovery_topic_hits": [],
                "_seed_url": str(url),
                "_fresh": True,
            }
        )
    return result


def collect(args: argparse.Namespace) -> int:
    plan = load_json(plan_path(args))
    if not isinstance(plan, dict) or plan.get("kind") != "wechat-account-research-plan":
        raise WechatArchiveError("--plan-file is not a WeChat account research plan")
    output = pathlib.Path(args.output_dir).expanduser().resolve()
    evidence = evidence_path(args)
    if evidence.exists() and not args.resume:
        raise WechatArchiveError(f"evidence already exists: {evidence}; use --resume")

    browser = BrowserClient(args.agent_browser_bin)
    run_summary: dict[str, Any] = {
        "schema_version": 1,
        "kind": "wechat-account-research-run",
        "started_at": now_utc(),
        "status": "running",
        "access_gate": "",
        "processed": 0,
        "accepted": 0,
        "discovery": {},
        "retry_budget_after_access_gate": 0,
        "body_persisted": False,
    }
    candidates = seed_candidates(plan)
    try:
        if args.discovery_index:
            indexed, raw_count = load_index_candidates(
                plan, pathlib.Path(args.discovery_index).expanduser().resolve()
            )
            candidates.extend(indexed)
            run_summary["discovery"] = {
                "mode": "hermes-index-read-only",
                "raw_hits": raw_count,
                "filtered_candidates": len(indexed),
            }
        else:
            online, stats = discover_online(plan, browser)
            candidates.extend(online)
            run_summary["discovery"] = {"mode": "bounded-agent-browser", **stats, "filtered_candidates": len(online)}

        deduped: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            deduped.setdefault(str(candidate["candidate_key"]), candidate)
        candidates = list(deduped.values())[: int(plan["limits"]["max_candidates"])]
        already = {str(record.get("candidate_key", "")) for record in load_jsonl(evidence)}

        for candidate in candidates:
            if candidate["candidate_key"] in already:
                continue
            try:
                record = verify_candidate(plan, browser, candidate, args.min_title_similarity)
            except AccessGateError as exc:
                record = {**base_record(candidate), "status": "access-gated", "reason": str(exc)}
                append_jsonl(evidence, record)
                run_summary["processed"] += 1
                run_summary["access_gate"] = str(exc)
                run_summary["status"] = "partial-access-gated"
                break
            except WechatArchiveError as exc:
                record = {**base_record(candidate), "status": "fetch-inaccessible", "reason": str(exc)}
            append_jsonl(evidence, record)
            run_summary["processed"] += 1
            if record["status"] == "direct-read":
                run_summary["accepted"] += 1
            time.sleep(float(plan["limits"]["delay_seconds"]))
        else:
            run_summary["status"] = "complete"
    except AccessGateError as exc:
        run_summary["access_gate"] = str(exc)
        run_summary["status"] = "partial-access-gated"
    finally:
        browser.close()
        run_summary["finished_at"] = now_utc()
        run_summary["evidence_file"] = evidence.as_posix()
        write_json(output / "run-summary.json", run_summary)

    print(json.dumps(run_summary, ensure_ascii=False, sort_keys=True))
    return 3 if run_summary["status"] == "partial-access-gated" else 0


def catalog_record(record: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version",
        "candidate_key",
        "canonical_account",
        "account",
        "pub_date",
        "title",
        "status",
        "topic_hits",
        "char_count",
        "paragraph_count",
        "code_block_count",
        "content_sha256",
        "source_locator",
        "locator_kind",
        "retrieved_at",
        "body_persisted",
        "temporary_url_persisted",
    )
    return {**{field: record.get(field) for field in fields}, "review_status": "review-required"}


def report(args: argparse.Namespace) -> int:
    plan = load_json(plan_path(args))
    records = load_jsonl(evidence_path(args))
    output = pathlib.Path(args.output_dir).expanduser().resolve()
    eligible = [record for record in records if record.get("status") in {"direct-read", "official-mirror-verified"}]
    catalog = [catalog_record(record) for record in eligible]
    catalog_path = output / "catalog.jsonl"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in catalog),
        encoding="utf-8",
    )
    status_counts = Counter(str(record.get("status", "unknown")) for record in records)
    account_counts = Counter(str(record.get("canonical_account", "")) for record in eligible)
    coverage = {
        "schema_version": 1,
        "kind": "wechat-account-research-coverage",
        "generated_at": now_utc(),
        "window": plan["window"],
        "accounts": plan["accounts"],
        "query_count": len(plan["queries"]),
        "attempted_candidates": len(records),
        "eligible_candidates": len(eligible),
        "status_counts": dict(sorted(status_counts.items())),
        "eligible_by_account": dict(sorted(account_counts.items())),
        "limitations": [
            "Sogou returns ranked result pages, not a complete account export.",
            "Recent articles can have indexing latency.",
            "Generated catalog records remain review-required.",
            "No article body or temporary signed redirect URL is persisted.",
        ],
    }
    write_json(output / "coverage.json", coverage)

    lines = [
        "# WeChat Account Research Evidence Pack",
        "",
        f"- Window: `{plan['window']['from']}` to `{plan['window']['to']}` inclusive",
        f"- Accounts: {', '.join(item['canonical'] for item in plan['accounts'])}",
        f"- Queries: {len(plan['queries'])}",
        f"- Attempted candidates: {len(records)}",
        f"- Eligible metadata records: {len(eligible)}",
        "- Body persisted: `false`",
        "- Editorial status: `review-required`",
        "",
        "## Status counts",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| `{status}` | {count} |" for status, count in sorted(status_counts.items()))
    lines.extend(["", "## Candidates", "", "| Date | Account | Title | Status | Locator |", "|---|---|---|---|---|"])
    for item in catalog:
        locator = str(item.get("source_locator") or "")
        link = f"[open]({locator})" if locator else "-"
        title = str(item.get("title") or "").replace("|", "\\|")
        lines.append(
            f"| {item.get('pub_date') or '-'} | {item.get('canonical_account') or item.get('account') or '-'} | {title} | `{item.get('status')}` | {link} |"
        )
    lines.extend(
        [
            "",
            "## Coverage and copyright boundary",
            "",
            "This pack is a bounded public-search evidence set, not an exhaustive account export. Search snippets and locator mirrors do not prove account ownership. Article bodies were used in memory only for verification, hashing, and topic signals and were not archived.",
            "",
        ]
    )
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(coverage, ensure_ascii=False, sort_keys=True))
    return 0


def contains_forbidden_url(value: Any) -> bool:
    if isinstance(value, str):
        lower = value.casefold()
        return "signature=" in lower or ("mp.weixin.qq.com" in lower and "timestamp=" in lower)
    if isinstance(value, list):
        return any(contains_forbidden_url(item) for item in value)
    if isinstance(value, dict):
        return any(contains_forbidden_url(item) for item in value.values())
    return False


def check(args: argparse.Namespace) -> int:
    errors: list[str] = []
    plan = load_json(plan_path(args))
    records = load_jsonl(evidence_path(args))
    if plan.get("body_policy") != "persist-never":
        errors.append("plan body_policy must be persist-never")
    if len(plan.get("queries", [])) > int(plan.get("limits", {}).get("max_queries", 0)):
        errors.append("plan query count exceeds declared cap")
    for index, record in enumerate(records, 1):
        keys = {str(key).casefold() for key in record}
        forbidden = sorted(keys & FORBIDDEN_PERSISTED_KEYS)
        if forbidden:
            errors.append(f"evidence:{index} forbidden keys: {','.join(forbidden)}")
        if record.get("body_persisted") is not False:
            errors.append(f"evidence:{index} body_persisted must be false")
        if record.get("temporary_url_persisted") is not False:
            errors.append(f"evidence:{index} temporary_url_persisted must be false")
        if contains_forbidden_url(record):
            errors.append(f"evidence:{index} contains a temporary signed URL")
        if record.get("status") == "direct-read":
            digest = str(record.get("content_sha256", ""))
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                errors.append(f"evidence:{index} direct-read digest is invalid")
            try:
                current = parse_date(str(record.get("pub_date", "")), "evidence pub_date")
                start = parse_date(str(plan["window"]["from"]), "plan window from")
                end = parse_date(str(plan["window"]["to"]), "plan window to")
                if not start <= current <= end:
                    errors.append(f"evidence:{index} direct-read date is outside plan window")
            except WechatArchiveError as exc:
                errors.append(f"evidence:{index} {exc}")
            if not record.get("canonical_account"):
                errors.append(f"evidence:{index} direct-read canonical account is missing")

    catalog_file = pathlib.Path(args.output_dir).expanduser().resolve() / "catalog.jsonl"
    if catalog_file.is_file():
        catalog = load_jsonl(catalog_file)
        expected = sum(record.get("status") in {"direct-read", "official-mirror-verified"} for record in records)
        if len(catalog) != expected:
            errors.append(f"catalog count {len(catalog)} does not match eligible evidence {expected}")
        if any(contains_forbidden_url(record) for record in catalog):
            errors.append("catalog contains a temporary signed URL")

    payload = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "evidence_records": len(records),
        "direct_read": sum(record.get("status") == "direct-read" for record in records),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"[{payload['status'].upper()}] evidence={len(records)} direct_read={payload['direct_read']} errors={len(errors)}")
    for error in errors:
        print(f"[ERROR] {error}")
    return 1 if errors else 0


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("action", choices=["plan", "collect", "report", "check"])
    parser.add_argument("--account", action="append", default=[])
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--seed-url", action="append", default=[])
    parser.add_argument("--date-from", default="")
    parser.add_argument("--date-to", default="")
    parser.add_argument("--output-dir", default="build/wechat-account-research")
    parser.add_argument("--plan-file", default="")
    parser.add_argument("--evidence-file", default="")
    parser.add_argument("--discovery-index", default="")
    parser.add_argument("--agent-browser-bin", default="")
    parser.add_argument("--max-queries", type=int, default=50)
    parser.add_argument("--max-results-per-query", type=int, default=10)
    parser.add_argument("--max-candidates", type=int, default=50)
    parser.add_argument("--min-title-similarity", type=float, default=0.72)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")


def run(args: argparse.Namespace) -> int:
    if args.action == "plan":
        plan = make_plan(args)
        if args.dry_run:
            print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        target = plan_path(args)
        write_json(target, plan)
        print(f"[DONE] plan={target} queries={len(plan['queries'])}")
        return 0
    if args.action == "collect":
        return collect(args)
    if args.action == "report":
        return report(args)
    if args.action == "check":
        return check(args)
    raise WechatArchiveError(f"unsupported action: {args.action}")
