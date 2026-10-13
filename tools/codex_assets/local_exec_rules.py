"""Explicit machine permission inputs for the managed source-to-live build."""

import ast
import hashlib
import json
import pathlib


def load_rules(path, expected_sha256, profile, base):
    path = pathlib.Path(path).expanduser().resolve()
    raw = path.read_bytes()
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("local rule input hash mismatch")
    value = json.loads(raw)
    if (set(value) != {"schema_version", "profile", "target", "base_sha256", "extra_rules"}
            or value["schema_version"] != 1 or value["profile"] != profile
            or value["target"] != "rules/default.rules"
            or value["base_sha256"] != hashlib.sha256(base).hexdigest()):
        raise ValueError("local rule input does not match the managed base/profile")
    rules = value["extra_rules"]
    if not isinstance(rules, list) or len(rules) > 100 or len(set(rules)) != len(rules):
        raise ValueError("local rules must be a bounded unique list")
    for line in rules:
        if not isinstance(line, str) or "\n" in line or "\r" in line or len(line) > 4096:
            raise ValueError("local rule must be one bounded line")
        parsed = ast.parse(line)
        if len(parsed.body) != 1 or not isinstance(parsed.body[0], ast.Expr):
            raise ValueError("local rule must be a prefix_rule declaration")
        call = parsed.body[0].value
        if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name)
                or call.func.id != "prefix_rule" or call.args
                or {key.arg for key in call.keywords} != {"pattern", "decision"}):
            raise ValueError("local rule must use only pattern and decision")
        fields = {key.arg: ast.literal_eval(key.value) for key in call.keywords}
        if (fields["decision"] not in {"allow", "prompt", "forbidden"}
                or not isinstance(fields["pattern"], list) or not fields["pattern"]
                or any(not isinstance(part, str) or not part for part in fields["pattern"])):
            raise ValueError("local prefix rule fields are invalid")
    text = base.decode("utf-8").rstrip("\n") + "\n"
    if rules:
        text += "\n".join(rules) + "\n"
    return text, {"path": str(path), "sha256": expected_sha256}


def verified_inputs(inputs, source, profile):
    if not isinstance(inputs, dict) or set(inputs) - {"exec_rules"}:
        raise ValueError("unsupported machine build input")
    if "exec_rules" in inputs:
        item = inputs["exec_rules"]
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("invalid local rule input identity")
        load_rules(item["path"], item["sha256"], profile, (source / "rules/default.rules").read_bytes())
    return inputs
