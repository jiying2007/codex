"""Read-only Feishu Project and TAPD WorkItem adapters.

Transport/credentials are injected by an explicitly authorized host service;
no client is created or called on import. This module has no mutation methods.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, Mapping
from urllib.parse import urlencode, urlsplit

from .models import IntakeRejected, WorkItemKey, _check_id

# request(method, fixed_url, headers, optional_json_body) -> parsed JSON object
Transport = Callable[[str, str, Dict[str, str], Any], Mapping[str, Any]]


@dataclasses.dataclass(frozen=True)
class WorkItemSnapshot:
    key: WorkItemKey
    title: str
    state: str
    version: str
    description: str
    source: str = "provider_read_only"

    def __post_init__(self):
        if (not self.title or len(self.title) > 512 or
                len(self.description) > 4000 or
                not self.version or len(self.version) > 128):
            raise IntakeRejected("invalid or missing WorkItem source fields")
        # External text is untrusted evidence, not an instruction or approval.


def _snapshot(key: WorkItemKey, record: Mapping[str, Any],
              title_field: str, version_fields: tuple) -> WorkItemSnapshot:
    if not isinstance(record, dict):
        raise IntakeRejected("invalid provider record")
    if str(record.get("id", "")) != key.item_id:
        raise IntakeRejected("provider item identity mismatch")
    if str(record.get("workspace_id", record.get("project_key", ""))) != key.workspace:
        raise IntakeRejected("provider workspace identity mismatch")
    version = next((str(record[x]) for x in version_fields if record.get(x)), "")
    if not version:
        raise IntakeRejected("provider item version unavailable")
    return WorkItemSnapshot(
        key=key,
        title=str(record.get(title_field, ""))[:512],
        state=str(record.get("status", record.get("sub_stage", "unknown")))[:128],
        version=version[:128],
        description=str(record.get("description") or "")[:4000],
    )


class TapdReader:
    """TAPD GET /stories or /bugs by exact numeric workspace+item ID."""

    BASE_URL = "https://api.tapd.cn"

    def __init__(self, tenant: str, bearer_token: str, request: Transport):
        self.tenant = _check_id(tenant, "tenant")
        if not isinstance(bearer_token, str) or len(bearer_token) < 8:
            raise IntakeRejected("missing private TAPD credential")
        if not callable(request):
            raise IntakeRejected("injected read-only transport is required")
        self._token = bearer_token
        self._request = request

    def read(self, key: WorkItemKey) -> WorkItemSnapshot:
        if key.provider != "tapd" or key.tenant != self.tenant:
            raise IntakeRejected("TAPD tenant/provider mismatch")
        if not key.workspace.isdecimal() or not key.item_id.isdecimal():
            raise IntakeRejected("TAPD requires numeric source IDs")
        endpoint, field = (
            ("stories", "Story") if key.kind == "requirement" else ("bugs", "Bug")
        )
        query = urlencode({"workspace_id": key.workspace, "id": key.item_id,
                           "limit": 1})
        payload = self._request(
            "GET", self.BASE_URL + "/" + endpoint + "?" + query,
            {"Authorization": "Bearer " + self._token}, None,
        )
        if not isinstance(payload, dict) or payload.get("status") != 1:
            raise IntakeRejected("TAPD read failed or permission denied")
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != 1:
            raise IntakeRejected("TAPD item missing or ambiguous")
        wrapped = data[0]
        record = wrapped.get(field) if isinstance(wrapped, dict) else None
        if not isinstance(record, dict):
            raise IntakeRejected("TAPD response type mismatch")
        snapshot = _snapshot(
            key, record, "name" if key.kind == "requirement" else "title",
            ("modified", "updated_at", "version"),
        )
        return snapshot


class FeishuProjectReader:
    """Meegle plugin-scoped POST query; no service credentials in source."""

    def __init__(
        self, tenant: str, base_url: str, plugin_token: str,
        user_key: str, request: Transport,
        requirement_type: str = "story", defect_type: str = "issue",
    ):
        self.tenant = _check_id(tenant, "tenant")
        parsed = urlsplit(base_url)
        # Host must come from the administrator's explicit tenant configuration.
        # Do not use user-provided work item links as API origins.
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.port
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or parsed.hostname not in ("project.feishu.cn", "project.larksuite.com")):
            raise IntakeRejected("invalid explicitly allowlisted Meegle API host")
        self.base = "https://" + parsed.hostname
        if (not isinstance(plugin_token, str) or len(plugin_token) < 8
                or not isinstance(user_key, str) or not user_key):
            raise IntakeRejected("Meegle plugin/user credentials unavailable")
        _check_id(requirement_type, "requirement_type")
        _check_id(defect_type, "defect_type")
        if not callable(request):
            raise IntakeRejected("injected read-only transport is required")
        self.types = {"requirement": requirement_type, "defect": defect_type}
        self._headers = {
            "X-PLUGIN-TOKEN": plugin_token,
            "X-USER-KEY": user_key,
            "Content-Type": "application/json",
        }
        self._request = request

    def read(self, key: WorkItemKey) -> WorkItemSnapshot:
        if key.provider != "feishu_project" or key.tenant != self.tenant:
            raise IntakeRejected("Meegle tenant/provider mismatch")
        if not key.item_id.isdecimal():
            raise IntakeRejected("Meegle query needs numeric WorkItem ID")
        kind_key = self.types[key.kind]
        url = (
            self.base + "/open_api/" + key.workspace
            + "/work_item/" + kind_key + "/query"
        )
        payload = self._request(
            "POST", url, dict(self._headers),
            {"work_item_ids": [int(key.item_id)]},
        )
        if not isinstance(payload, dict) or payload.get("err_code") != 0:
            raise IntakeRejected("Meegle read failed or permission denied")
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != 1:
            raise IntakeRejected("Meegle item missing or ambiguous")
        record = data[0]
        if not isinstance(record, dict) or record.get("work_item_type_key") != kind_key:
            raise IntakeRejected("Meegle source item kind mismatch")
        return _snapshot(
            key, record, "name", ("updated_at", "modified", "update_time"),
        )
