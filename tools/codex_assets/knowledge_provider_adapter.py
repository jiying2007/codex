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

OPERATIONS = {"status", "context", "archive", "resolve", "grant", "register", "bind", "assign", "reconcile", "capture-source",
              "evidence-pack", "action-check", "proposal-route", "activity-capture"}
AUXILIARY = {"evidence-pack": "knowledge-evidence-pack.sh", "action-check": "knowledge-action-check.sh",
             "proposal-route": "knowledge-proposal-route.sh", "activity-capture": "knowledge-activity.sh"}


class ProviderAdapterError(RuntimeError):
    pass


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
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
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
