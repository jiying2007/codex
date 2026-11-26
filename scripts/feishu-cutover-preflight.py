#!/usr/bin/env python3
"""Read-only local observations for Feishu Bot cutover; never a cutover gate."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess


UNIT = "feishu-codex-bot.service"
ENV_KEYS = (
    "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_TARGET_CHAT_ID",
    "FEISHU_BOT_CONFIG", "FEISHU_STATE_DB", "FEISHU_LOCK_FILE",
    "FEISHU_CODEX_WORKDIR", "FEISHU_ALLOWED_OPEN_IDS", "FEISHU_CODEX_BIN",
    "FEISHU_AGENT_BILLING_SOURCE", "FEISHU_AGENT_CODEX_HOME",
    "FEISHU_AGENT_OPENAI_API_KEY", "FEISHU_AGENT_OPENAI_BASE_URL",
    "FEISHU_AGENT_BUDGET_BACKEND", "FEISHU_AGENT_BUDGET_KEY_ALIAS",
    "FEISHU_AGENT_BUDGET_MAX_USD", "FEISHU_AGENT_MODEL",
    "FEISHU_AGENT_GITHUB_READ_TOKEN", "FEISHU_AGENT_GITHUB_WRITE_TOKEN",
)


def command(argv, cwd=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    try:
        result = subprocess.run(
            argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def absolute_path(value, cwd):
    if value is None or not str(value).strip():
        return None
    try:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = Path(cwd) / path
        # Normalize ".." without resolving symlinks; lstat must see the
        # actual path components so a private-file symlink cannot be hidden.
        return Path(os.path.abspath(str(path)))
    except (OSError, ValueError, RuntimeError):
        return None


def has_symlink_component(path):
    if path is None:
        return False
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current = current / component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        except OSError:
            return True
        if stat.S_ISLNK(metadata.st_mode):
            return True
    return False


def parent_chain_issue(path):
    for parent in reversed(path.parents):
        try:
            metadata = parent.lstat()
        except OSError:
            return "unavailable"
        if not stat.S_ISDIR(metadata.st_mode):
            return "unsafe_type"
        if metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX:
            return "unsafe_permissions"
    return ""


def info(path, directory=False):
    if path is None:
        return "unresolved"
    if has_symlink_component(path):
        return "unsafe_symlink_component"
    parent_issue = parent_chain_issue(path)
    if parent_issue:
        return "unsafe_parent_" + parent_issue
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"
    expected = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if not expected:
        return "unsafe_type"
    if (metadata.st_uid != os.getuid() or metadata.st_mode & 0o077
            or (not directory and metadata.st_nlink != 1)):
        return "unsafe_owner_or_permissions"
    return "private_directory" if directory else "private_file"


def read_private(path):
    if path is None or has_symlink_component(path):
        raise ValueError("private path unresolved or contains a symlink")
    if parent_chain_issue(path):
        raise ValueError("private path has an unsafe parent directory")
    # O_NONBLOCK prevents an unexpected FIFO from hanging the probe. Never
    # follow a symlink, open for writing, or emit source text on errors.
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1 or metadata.st_mode & 0o077
                or metadata.st_size > 524288):
            raise ValueError("private file invalid")
        raw = stream.read(524289)
        if len(raw) > 524288:
            raise ValueError("private file too large")
    return raw.decode("utf-8")


def read_env(path):
    result = {}
    for raw_line in read_private(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("invalid env syntax")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key in ENV_KEYS:
            result[key] = value
    return result


def read_proc(pid, name):
    with (Path("/proc") / str(pid) / name).open("rb") as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("process metadata too large")
    return raw.decode("utf-8", errors="replace").split("\0")


def argument(argv, name):
    hits = [argv[index + 1] for index, value in enumerate(argv[:-1]) if value == name]
    hits += [value[len(name) + 1:] for value in argv if value.startswith(name + "=")]
    if len(hits) > 1:
        raise ValueError("ambiguous argument")
    return hits[0] if hits else None


def find_consumer(main_pid):
    pending = [main_pid] if main_pid > 0 else []
    seen, matches = set(), []
    while pending and len(seen) < 128:
        pid = pending.pop()
        if pid in seen or pid <= 0:
            continue
        seen.add(pid)
        try:
            argv = read_proc(pid, "cmdline")
            if ("-m" in argv and "tools.codex_assets" in argv
                    and "feishu-codex-bot" in argv and "start" in argv):
                matches.append((pid, argv))
            children = (Path("/proc") / str(pid) / "task" / str(pid) / "children").read_text()
            pending.extend(int(value) for value in children.split())
        except (OSError, ValueError):
            continue
    if pending or len(matches) != 1:
        return None
    return matches[0]


def service_observation():
    properties = (
        "LoadState", "ActiveState", "SubState", "MainPID", "WorkingDirectory",
        "UnitFileState", "UMask", "NoNewPrivileges", "PrivateTmp",
    )
    raw = command(
        ["systemctl", "--user", "show", UNIT]
        + ["--property=" + value for value in properties]
    )
    return dict(line.split("=", 1) for line in (raw or "").splitlines() if "=" in line)


def probe(root, explicit_env=None, expected_sha=None, show_paths=False):
    if expected_sha is not None and not re.fullmatch(r"[a-f0-9]{40}", expected_sha):
        raise ValueError("expected SHA must be a full lowercase 40-character commit")
    root = absolute_path(root, Path.cwd())
    if root is None:
        raise ValueError("checkout root unresolved")
    svc = service_observation()
    security = {
        "umask_0077": svc.get("UMask") == "0077",
        "no_new_privileges": svc.get("NoNewPrivileges") == "yes",
        "private_tmp": svc.get("PrivateTmp") == "yes",
    }
    working_directory_matches = svc.get("WorkingDirectory") == str(root)
    result = {
        "scope": "read_only_observation_not_cutover",
        "service_changed": False, "model_called": False,
        "database_opened": False, "cutover_proven": False,
        "service": {key: svc.get(key) for key in (
            "LoadState", "ActiveState", "SubState", "UnitFileState",
            "UMask", "NoNewPrivileges", "PrivateTmp",
        )},
    }
    result["service"]["security"] = security
    result["service"]["working_directory_matches_checkout"] = working_directory_matches
    blockers = []
    if not security["umask_0077"]:
        blockers.append("systemd_umask_not_0077")
    if not security["no_new_privileges"]:
        blockers.append("systemd_no_new_privileges_not_enabled")
    if not security["private_tmp"]:
        blockers.append("systemd_private_tmp_not_enabled")
    if not working_directory_matches:
        blockers.append("systemd_working_directory_differs_from_checkout")
    if has_symlink_component(root):
        blockers.append("checkout_path_contains_symlink")
    try:
        pid = int(svc.get("MainPID", "0"))
    except ValueError:
        pid = 0
    active = svc.get("ActiveState") == "active"
    consumer = find_consumer(pid) if active else None
    runtime_env = {}
    cwd = root
    service_root = None
    detected_env = None
    runtime_verified = False
    if consumer:
        try:
            proc_pid, argv = consumer
            cwd = Path("/proc").joinpath(str(proc_pid), "cwd").resolve(strict=True)
            service_root = absolute_path(argument(argv, "--root"), cwd)
            raw_env_path = argument(argv, "--env-file")
            detected_env = absolute_path(raw_env_path, cwd) if raw_env_path else (
                service_root / "mcp/secrets/feishu.env" if service_root else None
            )
            runtime_env = {
                key: value for key, value in (
                    item.split("=", 1) for item in read_proc(proc_pid, "environ") if "=" in item
                ) if key in ENV_KEYS and value
            }
            runtime_verified = service_root is not None and detected_env is not None
        except (OSError, ValueError, RuntimeError):
            runtime_verified = False
    env_path = absolute_path(
        explicit_env or detected_env or (root / "mcp/secrets/feishu.env"), cwd
    )
    if explicit_env is not None and detected_env is not None and env_path != detected_env:
        blockers.append("explicit_env_differs_from_running_consumer")
        runtime_verified = False
    if service_root is not None and service_root != root:
        blockers.append("running_consumer_root_differs_from_requested_checkout")
    if not runtime_verified:
        blockers.append("effective_running_consumer_configuration_not_proven")

    git = ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false"]
    sha = command(git + ["rev-parse", "--verify", "HEAD"], root)
    status = command(
        git + ["status", "--porcelain=v1", "--untracked-files=all"], root
    )
    sha = (sha or "").strip()
    valid_sha = sha if re.fullmatch(r"[a-f0-9]{40}", sha) else None
    result["checkout"] = {
        "sha": valid_sha, "expected_sha": expected_sha,
        "matches_expected_sha": None if expected_sha is None or valid_sha is None else valid_sha == expected_sha,
        "dirty": None if status is None else bool(status.strip()),
        "running_code_sha_proven": False,
    }
    if expected_sha is not None and valid_sha != expected_sha:
        blockers.append("checkout_does_not_match_expected_sha")
    if status is None or status.strip():
        blockers.append("checkout_cleanliness_not_proven")

    result["tools_present"] = {
        key: shutil.which(key) is not None for key in ("git", "rtk", "codex", "bwrap", "python3")
    }
    result["config"] = {
        "env_file": info(env_path),
        "running_consumer_args_observed": runtime_verified,
        "env_file_source": (
            "explicit" if explicit_env is not None
            else ("running_argv" if detected_env else "checkout_default_unverified")
        ),
    }
    values = {}
    try:
        values = read_env(env_path)
        result["config"]["env_parsed"] = True
    except (OSError, ValueError, TypeError, UnicodeError):
        result["config"]["env_parsed"] = False
        blockers.append("private_env_unreadable_or_invalid")
    if runtime_verified:
        values.update(runtime_env)
    policy_path = absolute_path(values.get("FEISHU_BOT_CONFIG"), cwd)
    policy = {}
    try:
        policy = json.loads(read_private(policy_path))
        if not isinstance(policy, dict):
            raise ValueError("policy is not an object")
        result["config"]["policy_parsed"] = True
    except (OSError, ValueError, TypeError, UnicodeError):
        policy = {}
        result["config"]["policy_parsed"] = False
        blockers.append("explicit_private_policy_unreadable_or_absent")
    result["config"].update(
        policy_file=info(policy_path),
        legacy_env_fields=[
            key for key in ("FEISHU_CODEX_WORKDIR", "FEISHU_ALLOWED_OPEN_IDS") if key in values
        ],
        legacy_policy_fields=[
            key for key in ("manual_workitems_enabled", "engineering_cards_enabled") if key in policy
        ],
        engineering_enabled=(
            policy.get("engineering_enabled") is True if result["config"]["policy_parsed"] else None
        ),
        agent_intake_enabled=(
            policy.get("agent_intake_enabled") is True if result["config"]["policy_parsed"] else None
        ),
        repositories=(
            len(policy["repositories"]) if isinstance(policy.get("repositories"), dict) else None
        ),
        environment_fields_present={
            key: (bool(values.get(key)) if result["config"]["env_parsed"] else None)
            for key in ENV_KEYS
            if key not in ("FEISHU_STATE_DB", "FEISHU_LOCK_FILE", "FEISHU_BOT_CONFIG")
        },
        required_feishu_fields_present=(
            all(bool(values.get(key, "").strip()) for key in
                ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_TARGET_CHAT_ID"))
            if result["config"]["env_parsed"] else None
        ),
        dedicated_model_fields_present=(
            all(bool(values.get(key, "").strip()) for key in (
                "FEISHU_AGENT_OPENAI_API_KEY", "FEISHU_AGENT_OPENAI_BASE_URL",
                "FEISHU_AGENT_BUDGET_KEY_ALIAS", "FEISHU_AGENT_BUDGET_MAX_USD",
                "FEISHU_AGENT_CODEX_HOME", "FEISHU_AGENT_MODEL",
                "FEISHU_AGENT_BUDGET_BACKEND",
            )) if result["config"]["env_parsed"] else None
        ),
        billing_source=(
            values.get("FEISHU_AGENT_BILLING_SOURCE", "unapproved").strip().lower()
            if values.get("FEISHU_AGENT_BILLING_SOURCE", "unapproved").strip().lower()
            in ("unapproved", "codex_shared", "work_shared", "external_api_key", "external_gateway", "self_hosted")
            else "invalid"
        ),
        budget_backend=(
            "litellm" if values.get("FEISHU_AGENT_BUDGET_BACKEND", "").strip() == "litellm"
            else ("unconfigured" if not values.get("FEISHU_AGENT_BUDGET_BACKEND", "").strip() else "unsupported")
        ),
        agent_modes_all_empty=(
            all(
                isinstance(item, dict) and item.get("agent_allowed_modes", []) == []
                for item in policy["repositories"].values()
            )
            if result["config"]["policy_parsed"] and isinstance(policy.get("repositories"), dict)
            else None
        ),
    )
    db = absolute_path(
        values.get("FEISHU_STATE_DB") or policy.get("state_db")
        or (root / "mcp/secrets/feishu-codex-state.sqlite3"), cwd
    )
    lock = absolute_path(
        values.get("FEISHU_LOCK_FILE") or policy.get("lock_file")
        or "/tmp/feishu-codex-bot.lock", cwd
    )
    spool = db.parent / "feishu-pending-jobs" if db else None
    legacy = db.with_name("feishu-engineering-agent.sqlite3") if db else None
    result["state"] = {
        "bot_db": info(db), "legacy_db": info(legacy), "spool": info(spool, True),
        "lock": info(lock),
        "paths_explicit_in_policy": False,
        "policy_state_explicit_and_matches": False,
        "policy_lock_explicit_and_matches": False,
        "state_parent_metadata": info(db.parent, True) if db else "unresolved",
        "path_basis": (
            "observed_process_and_current_config_files"
            if runtime_verified and result["config"]["env_parsed"] and result["config"]["policy_parsed"]
            else "partial_or_inferred_not_effective_runtime_proof"
        ),
        "task_status": "not_observed_no_sqlite_access",
    }
    policy_db = absolute_path(policy.get("state_db"), cwd)
    policy_lock = absolute_path(policy.get("lock_file"), cwd)
    result["state"]["policy_state_explicit_and_matches"] = bool(
        isinstance(policy.get("state_db"), str) and Path(policy["state_db"]).is_absolute()
        and policy_db == db and not has_symlink_component(db)
    )
    result["state"]["policy_lock_explicit_and_matches"] = bool(
        isinstance(policy.get("lock_file"), str) and Path(policy["lock_file"]).is_absolute()
        and policy_lock == lock and not has_symlink_component(lock)
    )
    result["state"]["paths_explicit_in_policy"] = (
        result["state"]["policy_state_explicit_and_matches"]
        and result["state"]["policy_lock_explicit_and_matches"]
    )
    for name, path in (("bot", db), ("legacy", legacy)):
        for suffix in ("-wal", "-shm"):
            result["state"][name + suffix] = info(
                path.with_name(path.name + suffix) if path else None
            )
    if spool is not None and info(spool, True) == "private_directory":
        try:
            count = 0
            unsafe = 0
            for entry in spool.iterdir():
                count += 1
                unsafe += info(entry) != "private_file"
                if count > 10000:
                    raise ValueError("spool count bound")
            result["state"].update(spool_count_observed=count, spool_unsafe_entries=unsafe)
        except (OSError, ValueError):
            result["state"]["spool_count_observed"] = None

    after = service_observation()
    result["service"]["same_pid_and_state_during_observation"] = bool(
        svc and after and all(
            svc.get(key) == after.get(key) for key in ("MainPID", "ActiveState", "SubState")
        )
    )
    if not svc:
        blockers.append("user_systemd_unavailable")
    if not result["service"]["same_pid_and_state_during_observation"]:
        blockers.append("service_state_changed_or_unavailable")
    result["blockers_observed"] = blockers
    result["still_required"] = [
        "freeze_all_writers", "check_pending_tasks_and_remote_effects",
        "paired_private_backup_and_restore", "offline_legacy_unify_if_required",
        "configuration_conversion", "single_service_cutover",
        "read_only_gateway_preflight_with_model_intake_disabled",
        "request_level_hard_budget_and_final_settlement",
        "real_feishu_multi_repo_and_business_acceptance",
    ]
    if show_paths:
        result["local_paths_do_not_share"] = {
            key: str(value) if value is not None else None
            for key, value in (
                ("root", root), ("env", env_path), ("policy", policy_path),
                ("state_db", db), ("legacy_db", legacy), ("spool", spool), ("lock", lock),
            )
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "codex")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument(
        "--expected-sha", default=None,
        help="exact expected 40-character main SHA; omit to report without comparing",
    )
    parser.add_argument(
        "--show-paths", action="store_true",
        help="local terminal only; paths may reveal private host layout",
    )
    args = parser.parse_args(argv)
    try:
        result = probe(args.root, args.env_file, args.expected_sha, args.show_paths)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        # Keep exception messages private: paths, env contents and credentials
        # must never appear in an observation sent back to a chat.
        print(json.dumps({
            "scope": "read_only_observation_not_cutover",
            "error_type": type(exc).__name__, "cutover_proven": False,
        }))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
