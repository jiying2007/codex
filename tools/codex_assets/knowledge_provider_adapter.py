"""CLI transport to the sole Provider contract with exact executable identity."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

OPERATIONS = {"status", "context", "archive", "resolve", "grant", "register", "register-repository", "bind", "assign", "reconcile", "capture-source", "migrate-project", "maintain-content",
              "evidence-pack", "action-check", "proposal-route", "activity-capture", "activity-report"}
AUXILIARY = {"evidence-pack": "knowledge-evidence-pack.sh", "action-check": "knowledge-action-check.sh",
             "proposal-route": "knowledge-proposal-route.sh", "activity-capture": "knowledge-activity.sh",
             "activity-report": "knowledge-activity.sh"}
PROVIDER_TIMEOUT_SECONDS = 180


class ProviderAdapterError(RuntimeError):
    pass


def validate_evidence_pack(value):
    """Accept the existing readonly wire schema without promoting candidates."""
    lanes = ("must", "should", "context", "provisional", "conflict", "missing")
    if (value.get("schema_version") != "knowledge-hub.evidence-pack.v1"
            or value.get("read_only") is not True
            or not isinstance(value.get("authority_contract"), dict)
            or value["authority_contract"].get("active_only") is not True
            or not isinstance(value.get("counts"), dict)):
        raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
    for lane in lanes:
        rows = value.get(lane)
        if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                or type(value["counts"].get(lane)) is not int
                or value["counts"][lane] != len(rows)):
            raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        if lane in {"must", "should", "context", "provisional"}:
            for row in rows:
                authority = "provisional" if lane == "provisional" else "active"
                if (not isinstance(row.get("id"), str) or not row["id"]
                        or not isinstance(row.get("summary_zh"), str)
                        or row.get("authority") != authority
                        or (lane != "provisional" and row.get("status") != "active")
                        or (lane == "provisional" and row.get("status") not in {"reviewing", "draft", "active"})):
                    raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")


def sha256(path):
    if path.is_symlink() or not path.is_file():
        raise ProviderAdapterError("SOURCE_DRIFT")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source(native_root, hub_root):
    try:
        lock = json.loads((native_root / "manifests/provider-locks/knowledge-hub.json").read_text())
        manifest = hub_root / "registry/provider-runtime-files.json"
        if (lock.get("repository") != "jiying2007/knowledge-hub" or lock.get("protocol_version") != 4
                or re.fullmatch(r"[a-f0-9]{40}", str(lock.get("provider_commit", ""))) is None
                or sha256(manifest) != lock.get("source_manifest_sha256")):
            raise ProviderAdapterError("SOURCE_DRIFT")
        value = json.loads(manifest.read_text())
        if (type(value.get("schema_version")) is not int or value["schema_version"] != 1
                or value.get("inventory_roots") != ["tools"] or not isinstance(value.get("files"), dict) or not value["files"]):
            raise ProviderAdapterError("SOURCE_DRIFT")
        for path in hub_root.iterdir():
            if path.suffix in {".py", ".pyc", ".pyo"} and (path.is_file() or path.is_symlink()):
                raise ProviderAdapterError("SOURCE_DRIFT")
            if path.name != "tools" and path.is_dir() and any(
                    (path / name).exists() or (path / name).is_symlink()
                    for name in ("__init__.py", "__init__.pyc", "__init__.pyo")):
                raise ProviderAdapterError("SOURCE_DRIFT")
        actual = set()
        for path in (hub_root / "tools").rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                raise ProviderAdapterError("SOURCE_DRIFT")
            if path.is_file() and path.suffix in {".pyc", ".pyo"}:
                raise ProviderAdapterError("SOURCE_DRIFT")
            if path.is_file() and (path.suffix in {".py", ".sh"} or path.stat().st_mode & 0o111):
                actual.add(str(path.relative_to(hub_root)))
        if actual != {key for key in value["files"] if key.startswith("tools/")}:
            raise ProviderAdapterError("SOURCE_DRIFT")
        for relative, expected in value["files"].items():
            pure = pathlib.PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                raise ProviderAdapterError("SOURCE_DRIFT")
            path = hub_root / relative
            if any(path.is_symlink() for path in [hub_root.joinpath(*pure.parts[:i]) for i in range(1, len(pure.parts) + 1)]):
                raise ProviderAdapterError("SOURCE_DRIFT")
            if sha256(path) != expected:
                raise ProviderAdapterError("SOURCE_DRIFT")
        return {"source_manifest_sha256": lock["source_manifest_sha256"], "provider_commit": lock["provider_commit"]}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ProviderAdapterError("PROVIDER_UNAVAILABLE") from exc


def main(argv=None):
    supplied = list(sys.argv[1:] if argv is None else argv)
    root_help = supplied in (["--help"], ["-h"])
    if root_help:
        supplied = ["status", "--help"]
    operation = supplied[0] if supplied else "status"
    rest = supplied[1:]
    help_requested = any(arg in {"-h", "--help"} for arg in rest)
    if operation not in OPERATIONS:
        print(json.dumps({"status": "BLOCKED", "persisted": False, "reason_codes": ["UNSUPPORTED_OPERATION"]}))
        return 2
    if any(arg == "--root" or arg.startswith("--root=") or arg in {"--a", "--ap", "--app", "--appl"} for arg in rest):
        print(json.dumps({"status": "BLOCKED", "persisted": False, "reason_codes": ["SCHEMA_INVALID"]}))
        return 2
    if operation == "activity-report" and not help_requested:
        values = {"--period", "--scope", "--detail", "--as-of", "--knowledge-as-of",
                  "--start", "--end", "--subject-id", "--project-id"}
        switches = {"--json", "--summary-json", "--stdout-only"}
        index = 0
        while index < len(rest):
            flag = rest[index]
            if flag in switches:
                index += 1
            elif flag in values and index + 1 < len(rest) and not rest[index + 1].startswith("--"):
                index += 2
            else:
                print(json.dumps({"status": "BLOCKED", "persisted": False,
                                  "write_performed": False, "reason_codes": ["SCHEMA_INVALID"]}))
                return 2
        rest.append("--stdout-only")
    native_root = pathlib.Path(__file__).resolve().parents[2]
    hub_root = pathlib.Path(os.environ.get("KNOWLEDGE_HUB_ROOT", str(pathlib.Path.home() / "knowledge-hub"))).expanduser().resolve()
    invoked, receipt = False, {}
    try:
        if (hub_root / "local/provider-maintenance.json").exists():
            raise ProviderAdapterError("PROVIDER_MAINTENANCE")
        identity = verify_source(native_root, hub_root)
        if operation in AUXILIARY:
            args = ["bash", str(hub_root / "tools" / AUXILIARY[operation])]
            if operation == "activity-capture":
                args.append("capture")
            elif operation == "activity-report":
                args.append("report")
        else:
            args = ["bash", str(hub_root / "tools/knowledge-provider.sh"), operation]
        with tempfile.TemporaryDirectory(prefix="provider-import-") as directory:
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            for key in list(env):
                if key in {"BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS", "CDPATH"} or key.startswith("BASH_FUNC_"):
                    env.pop(key, None)
            env["PYTHONPYCACHEPREFIX"] = directory
            if help_requested:
                rest = ["--help"]
            elif operation in AUXILIARY and not any(flag in rest for flag in ("--json", "--summary-json")):
                rest.append("--json")
            invoked = True
            result = subprocess.run(args + rest, env=env, cwd=env.get("KNOWLEDGE_PROVIDER_CALLER_CWD", os.getcwd()),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=PROVIDER_TIMEOUT_SECONDS)
        try:
            receipt = json.loads(result.stdout)
        except ValueError:
            receipt = {}
        if verify_source(native_root, hub_root) != identity:
            raise ProviderAdapterError("SOURCE_DRIFT")
        if help_requested:
            if operation in AUXILIARY and result.returncode == 0 and result.stdout.startswith("usage:") and len(result.stdout) <= 32768:
                receipt = {"schema_version": "knowledge-provider.help/v4", "status": "HELP",
                           "operation": operation, "read_only": True, "persisted": False,
                           "write_performed": False, "usage": result.stdout}
            if (result.returncode != 0 or not isinstance(receipt, dict)
                    or receipt.get("schema_version") != "knowledge-provider.help/v4"
                    or receipt.get("status") != "HELP" or receipt.get("operation") != operation
                    or receipt.get("read_only") is not True or receipt.get("persisted") is not False
                    or receipt.get("write_performed") is not False):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
            if root_help:
                receipt["operation"] = None
                receipt["operations"] = sorted(OPERATIONS)
            print(json.dumps(receipt, ensure_ascii=False))
            return 0
        if not isinstance(receipt, dict) or not receipt:
            raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        if operation == "context":
            if (receipt.get("schema_version") != "knowledge-provider.context/v4" or receipt.get("read_only") is not True
                    or not isinstance(receipt.get("context"), list) or not isinstance(receipt.get("retrieval_scope"), list)):
                if result.returncode != 0 and receipt.get("schema_version") == "knowledge-provider.operation-receipt/v4" and receipt.get("status") in {"BLOCKED", "CONFLICT", "UNKNOWN"}:
                    print(result.stdout.strip())
                    return result.returncode
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        elif operation == "evidence-pack":
            validate_evidence_pack(receipt)
        elif operation == "activity-report":
            if (receipt.get("schema_version") != 2 or not isinstance(receipt.get("status"), str)
                    or (result.returncode == 0 and
                        (receipt.get("mode") != "report-only" or receipt.get("written") is not False
                         or not isinstance(receipt.get("source_coverage"), dict)
                         or not isinstance(receipt.get("facts"), dict)
                         or receipt["facts"].get("schema_version") != 2
                         or receipt["facts"].get("kind") != "knowledge-hub.activity-facts-v2"
                         or receipt["facts"].get("period") != receipt.get("period")
                         or not isinstance(receipt["facts"].get("work_items"), list)
                         or not isinstance(receipt.get("privacy"), dict)
                         or any(receipt["privacy"].get(key) is not False for key in
                                ("raw_sessions_stored", "raw_logs_stored", "credentials_stored",
                                 "identity_inferred_from_git", "memory_write", "external_write"))))):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        elif operation == "resolve":
            if (receipt.get("schema_version") != "knowledge-provider.resolve/v1" or receipt.get("read_only") is not True
                    or not isinstance(receipt.get("state"), str)):
                if result.returncode != 0 and receipt.get("schema_version") == "knowledge-provider.operation-receipt/v4" and receipt.get("status") in {"BLOCKED", "CONFLICT", "UNKNOWN"}:
                    print(result.stdout.strip())
                    return result.returncode
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        elif operation in {"archive", "assign", "reconcile"}:
            if (receipt.get("schema_version") != "knowledge-provider.operation-receipt/v4"
                    or not {"status", "persisted", "write_performed", "operation_id", "content_sha256", "subject_ref"} <= receipt.keys()):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
            if receipt["status"] in {"ARCHIVED", "ALREADY_ARCHIVED", "ASSIGNED", "ALREADY_ASSIGNED", "VERIFIED"}:
                if (receipt["persisted"] is not True or not isinstance(receipt["subject_ref"], dict)
                        or any(re.fullmatch(r"[a-f0-9]{64}", str(receipt[key])) is None for key in ("operation_id", "content_sha256"))):
                    raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        elif operation == "maintain-content":
            if receipt.get("schema_version") == "knowledge-provider.operation-receipt/v4" and result.returncode != 0 and receipt.get("status") in {"BLOCKED", "CONFLICT", "UNKNOWN"}:
                print(result.stdout.strip())
                return result.returncode
            if (receipt.get("schema_version") != "knowledge-provider.content-maintenance/v1"
                    or receipt.get("status") not in {"PLANNED", "MAINTAINED"}
                    or re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("expected_hash", ""))) is None
                    or any(type(receipt.get(key)) is not int or receipt[key] < 0 for key in ("item_count", "write_count", "delete_count"))
                    or receipt.get("active_promoted") is not False or receipt.get("owner_review_performed") is not False):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
            wrote = receipt["status"] == "MAINTAINED"
            if (receipt.get("persisted") is not wrote or receipt.get("write_performed") is not wrote
                    or receipt.get("read_only") is not (not wrote)):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
            if wrote and (receipt.get("transaction_id") != "content-maintenance-" + receipt["expected_hash"][:24]
                          or receipt.get("manifest_ref") != "artifacts/manifests/content-maintenance-" + receipt["expected_hash"] + ".json"):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        elif operation == "migrate-project":
            if receipt.get("schema_version") == "knowledge-provider.operation-receipt/v4" and result.returncode != 0 and receipt.get("status") in {"BLOCKED", "CONFLICT", "UNKNOWN"}:
                print(result.stdout.strip())
                return result.returncode
            if (receipt.get("schema_version") != "knowledge-provider.project-migration/v1"
                    or receipt.get("status") not in {"PLANNED", "MIGRATED", "ALREADY_MIGRATED"}
                    or not isinstance(receipt.get("subject_ref"), dict)
                    or receipt["subject_ref"].get("type") != "project"
                    or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", str(receipt["subject_ref"].get("id", ""))) is None
                    or re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("expected_hash", ""))) is None
                    or receipt.get("active_promoted") is not False or receipt.get("owner_review_performed") is not False
                    or any(type(receipt.get(key)) is not int or receipt[key] < 0 for key in
                           ("source_file_count", "source_item_count", "write_count", "delete_count", "provider_proofs"))):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
            persisted = receipt["status"] != "PLANNED"
            wrote = receipt["status"] == "MIGRATED"
            if receipt.get("persisted") is not persisted or receipt.get("write_performed") is not wrote or receipt.get("read_only") is not (not wrote):
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
            if persisted and receipt.get("manifest_ref") != "artifacts/manifests/project-migration-" + receipt["expected_hash"] + ".json":
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
            if wrote and receipt.get("transaction_id") != "project-migration-" + receipt["expected_hash"][:24]:
                raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        elif not isinstance(receipt.get("status"), str) or not receipt["status"]:
            raise ProviderAdapterError("PROVIDER_RESPONSE_INVALID")
        print(result.stdout.strip())
        return result.returncode
    except (ProviderAdapterError, OSError, subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, ProviderAdapterError) else "PROVIDER_TIMEOUT" if isinstance(exc, subprocess.TimeoutExpired) else "PROVIDER_UNAVAILABLE"
        uncertain = invoked and "--apply" in rest
        value = {"status": "UNKNOWN" if uncertain else "BLOCKED", "persisted": None if uncertain else False,
                 "write_performed": None if uncertain else False, "reason_codes": [reason]}
        if isinstance(receipt, dict) and re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("operation_id", ""))):
            value["operation_id"] = receipt["operation_id"]
        print(json.dumps(value))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
