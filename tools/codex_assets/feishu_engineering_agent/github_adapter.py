"""Optional GitHub PR/CI adapter: fixed origin, allowlisted repositories.

Not a GitHub Issues project manager. WorkItems still belong to Feishu Project
or TAPD; this adapter only observes Git proofs or creates an independently
approved draft PR for an already-pushed exact branch.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Mapping, Optional, Sequence

from .models import IntakeRejected

_OWNER_REPO = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_SHA = re.compile(r"\A[a-f0-9]{40}\Z")
_PR_REF = re.compile(r"\Agithub://pr/([1-9][0-9]{0,12})\Z")
_CI_REF = re.compile(r"\Agithub://ci/([1-9][0-9]{0,12})\Z")
_WORKFLOW_PATH = re.compile(r"\A\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml\Z")


def validate_delivery_config(repository, base_branch, workflows):
    if (not isinstance(repository, str) or not _OWNER_REPO.fullmatch(repository)
            or ".." in repository or not isinstance(base_branch, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}", base_branch)
            or ".." in base_branch or "//" in base_branch or base_branch.endswith("/")):
        raise IntakeRejected("invalid configured GitHub delivery repository or base")
    if (not isinstance(workflows, (list, tuple)) or not 1 <= len(workflows) <= 8
            or any(not isinstance(path, str) or not _WORKFLOW_PATH.fullmatch(path)
                   or ".." in path for path in workflows)
            or len(set(workflows)) != len(workflows)):
        raise IntakeRejected("configure one to eight unique required GitHub workflow paths")
    return tuple(sorted(workflows))


class GitHubApiFailure(IntakeRejected):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # never forward private authorization to another origin


class GitHubTransport:
    """Only sends traffic to api.github.com with bounded JSON and no redirects."""

    def __init__(self, repository: str, token: str = ""):
        if not _OWNER_REPO.fullmatch(repository):
            raise GitHubApiFailure("invalid allowlisted repository")
        if token and (not isinstance(token, str) or len(token) < 8):
            raise GitHubApiFailure("invalid private GitHub credential")
        self.root = "/repos/" + repository
        self.token = token
        self.opener = urllib.request.build_opener(_NoRedirect())

    def __call__(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        if method not in ("GET", "POST"):
            raise GitHubApiFailure("unsupported Git API method")
        if (not isinstance(path, str) or not path.startswith(self.root + "/")
                or ".." in path or "@" in path or "?" in path or "#" in path):
            raise GitHubApiFailure("untrusted Git API path")
        if method == "POST" and not self.token:
            raise GitHubApiFailure("GitHub remote write token absent")
        body = None
        if payload is not None:
            if method != "POST" or not isinstance(payload, dict):
                raise GitHubApiFailure("invalid GitHub request body")
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            if len(body) > 32768:
                raise GitHubApiFailure("Git request exceeds bound")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "feishu-engineering-agent",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            "https://api.github.com" + path, data=body, method=method,
            headers=headers,
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                raw = response.read(512 * 1024 + 1)
                if len(raw) > 512 * 1024:
                    raise GitHubApiFailure("oversized GitHub response")
                parsed = json.loads(raw.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise GitHubApiFailure("unexpected GitHub JSON")
                return parsed
        except (urllib.error.URLError, ValueError, OSError) as exc:
            # Never log bearer tokens or raw response bodies.
            raise GitHubApiFailure("GitHub API unavailable or denied") from exc


class GitHubForge:
    """A qualified Git evidence adapter for one configured repository."""

    def __init__(
        self, repo_alias: str, repo_full_name: str,
        request: Callable[[str, str, Optional[dict]], Mapping],
        base_branch: str = "main", remote_write_enabled: bool = False,
    ):
        if not _OWNER_REPO.fullmatch(repo_full_name):
            raise GitHubApiFailure("invalid configured repository")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}", base_branch):
            raise GitHubApiFailure("invalid configured base branch")
        if not callable(request):
            raise GitHubApiFailure("trusted Git API transport required")
        self.repo_alias = repo_alias
        self.repo_full_name = repo_full_name
        self.base_branch = base_branch
        self.remote_write_enabled = remote_write_enabled
        self.request = request
        self.root = "/repos/" + repo_full_name

    @staticmethod
    def _head_branch(target_ref: str) -> str:
        if not isinstance(target_ref, str) or not target_ref.startswith("refs/heads/"):
            raise GitHubApiFailure("an exact branch ref is required")
        branch = target_ref[len("refs/heads/"):]
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", branch)
                or ".." in branch or "//" in branch
                or branch.endswith(".lock") or branch.endswith("/")):
            raise GitHubApiFailure("invalid remote branch ref")
        return branch

    def publish(self, payload: Mapping) -> dict:
        """No Git push or merge. Draft PR for already-pushed exact remote ref."""
        if not self.remote_write_enabled:
            raise GitHubApiFailure("GitHub publishing disabled by default")
        if (not isinstance(payload, Mapping)
                or payload.get("repo_full_name") != self.repo_full_name
                or not _SHA.fullmatch(str(payload.get("head_sha", "")))):
            raise GitHubApiFailure("publication repository or SHA mismatch")
        branch = self._head_branch(payload.get("target_ref", ""))
        ref_path = self.root + "/git/ref/heads/" + urllib.parse.quote(branch, safe="/")
        observed_ref = self.request("GET", ref_path, None)
        obj = observed_ref.get("object") if isinstance(observed_ref, Mapping) else None
        if not isinstance(obj, Mapping) or obj.get("sha") != payload["head_sha"]:
            raise GitHubApiFailure("remote branch head differs from reviewed SHA")
        new_pr = self.request("POST", self.root + "/pulls", {
            "title": "Engineering AgentRun " + payload["run_id"][:12],
            "body": "Source WorkItem remains managed by original product/QA owner.\n"
                    "Exact reviewed commit: " + payload["head_sha"] + "\n"
                    "AgentRun: " + payload["run_id"],
            "base": self.base_branch, "head": branch, "draft": True,
        })
        if not isinstance(new_pr, Mapping) or not isinstance(new_pr.get("number"), int):
            raise GitHubApiFailure("unverified GitHub PR creation response")
        head = new_pr.get("head")
        if not isinstance(head, Mapping) or head.get("sha") != payload["head_sha"]:
            raise GitHubApiFailure("created PR head does not match reviewed source")
        return {
            "pr_id": str(new_pr["number"]),
            "head_sha": payload["head_sha"],
            "repo_full_name": self.repo_full_name,
        }

    def observe_delivery(
        self, pr_number: int, ci_run_ids: Sequence[int], branch: str,
        head_sha: str, required_workflows: Sequence[str],
    ) -> dict:
        """Strict read-only proof for one local commit, branch and required CI set.

        The caller supplies IDs, never conclusions, workflow names, or a
        repository override. Both PR reads must identify the same exact head.
        """
        required = validate_delivery_config(
            self.repo_full_name, self.base_branch, required_workflows,
        )
        self._head_branch("refs/heads/" + branch)
        if not _SHA.fullmatch(head_sha):
            raise GitHubApiFailure("invalid local commit SHA")
        if (type(pr_number) is not int or not 0 < pr_number < 10**13
                or not isinstance(ci_run_ids, (list, tuple))
                or len(ci_run_ids) != len(required)
                or any(type(value) is not int or not 0 < value < 10**13 for value in ci_run_ids)
                or len(set(ci_run_ids)) != len(ci_run_ids)):
            raise GitHubApiFailure("one unique CI run ID per required workflow is needed")
        expected_repo = self.repo_full_name.lower()

        def repo_matches(value):
            return (isinstance(value, Mapping)
                    and isinstance(value.get("full_name"), str)
                    and value["full_name"].lower() == expected_repo)

        def read_pr():
            pr = self.request("GET", self.root + "/pulls/" + str(pr_number), None)
            head = pr.get("head") if isinstance(pr, Mapping) else None
            base = pr.get("base") if isinstance(pr, Mapping) else None
            if (not isinstance(head, Mapping) or not isinstance(base, Mapping)
                    or pr.get("number") != pr_number
                    or not repo_matches(head.get("repo")) or not repo_matches(base.get("repo"))
                    or head.get("sha") != head_sha or head.get("ref") != branch
                    or base.get("ref") != self.base_branch
                    or not (pr.get("state") == "open"
                            or (pr.get("state") == "closed" and pr.get("merged_at")))):
                raise GitHubApiFailure("PR repository, branch, base, state or exact head mismatch")
            return "merged" if pr.get("merged_at") else "open"

        read_pr()
        by_path = {}
        for run_id in ci_run_ids:
            ci = self.request("GET", self.root + "/actions/runs/" + str(run_id), None)
            if not isinstance(ci, Mapping):
                raise GitHubApiFailure("invalid CI run receipt")
            path = ci.get("path")
            event = ci.get("event")
            associated = ci.get("pull_requests")
            if (ci.get("id") != run_id or not repo_matches(ci.get("repository"))
                    or not repo_matches(ci.get("head_repository"))
                    or ci.get("head_sha") != head_sha or ci.get("head_branch") != branch
                    or ci.get("status") != "completed" or ci.get("conclusion") != "success"
                    or path not in required or path in by_path
                    or event not in ("pull_request", "push")
                    or (event == "pull_request" and (
                        not isinstance(associated, list) or not any(
                            isinstance(pr, Mapping) and pr.get("number") == pr_number
                            for pr in associated)))):
                raise GitHubApiFailure("CI run does not prove a required workflow on this exact PR head")
            by_path[path] = run_id
        if set(by_path) != set(required):
            raise GitHubApiFailure("required GitHub workflow set incomplete")
        state = read_pr()
        return {
            "repo_alias": self.repo_alias, "repo_full_name": self.repo_full_name,
            "base_branch": self.base_branch, "branch": branch, "head_sha": head_sha,
            "pr_number": pr_number, "pr_state": state,
            "workflows": by_path,
        }

    def observe_pr(self, reference: str) -> dict:
        match = _PR_REF.fullmatch(reference)
        if not match:
            raise GitHubApiFailure("expected github://pr/<number>")
        observed = self.request(
            "GET", self.root + "/pulls/" + match.group(1), None,
        )
        head = observed.get("head") if isinstance(observed, Mapping) else None
        if (not isinstance(head, Mapping) or not _SHA.fullmatch(str(head.get("sha", "")))
                or observed.get("state") not in ("open", "closed")):
            raise GitHubApiFailure("PR record unverifiable")
        return {
            "reference": reference, "repo_alias": self.repo_alias,
            "head_sha": head["sha"],
            "state": "merged" if observed.get("merged_at") else observed["state"],
        }

    def observe_ci(self, reference: str) -> dict:
        match = _CI_REF.fullmatch(reference)
        if not match:
            raise GitHubApiFailure("expected github://ci/<run ID>")
        observed = self.request(
            "GET", self.root + "/actions/runs/" + match.group(1), None,
        )
        if (not isinstance(observed, Mapping)
                or not _SHA.fullmatch(str(observed.get("head_sha", "")))
                or observed.get("status") != "completed"):
            raise GitHubApiFailure("workflow run not completed or missing SHA")
        return {
            "reference": reference, "repo_alias": self.repo_alias,
            "head_sha": observed["head_sha"], "conclusion": observed.get("conclusion"),
        }
