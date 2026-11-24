"""GET-only GitHub evidence for exact commits, PRs and required CI.

Source work items remain in Feishu Project or TAPD. Publishing and product
acceptance are outside this observer; it has no remote write operation.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Callable, Mapping, Optional, Sequence

from .models import IntakeRejected

_OWNER_REPO = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_SHA = re.compile(r"\A[a-f0-9]{40}\Z")
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
        if method != "GET" or payload is not None:
            raise GitHubApiFailure("Git evidence transport is read-only")
        if (not isinstance(path, str) or not path.startswith(self.root + "/")
                or not re.fullmatch(r"/(?:pulls/[1-9][0-9]*|actions/runs/[1-9][0-9]*)",
                                    path[len(self.root):])):
            raise GitHubApiFailure("untrusted Git evidence path")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "feishu-engineering-agent",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(
            "https://api.github.com" + path, method="GET",
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

    def _read_discovery(self, path: str, expected_type):
        # Paths are built only by the two exact-SHA helpers below, not supplied
        # by chat or the model. No redirect or write capability.
        headers = {"Accept":"application/vnd.github+json",
                   "X-GitHub-Api-Version":"2026-03-10",
                   "User-Agent":"feishu-engineering-agent"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request("https://api.github.com"+self.root+path,
                                     method="GET",headers=headers)
        try:
            with self.opener.open(req,timeout=10) as response:
                if 'rel="next"' in (response.headers.get("Link","") or ""):
                    raise GitHubApiFailure("discovery result exceeds one bounded page")
                raw = response.read(2*1024*1024+1)
                if len(raw)>2*1024*1024:
                    raise GitHubApiFailure("oversized GitHub discovery response")
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value,expected_type):
                    raise GitHubApiFailure("invalid discovery response")
                return value
        except (urllib.error.URLError, ValueError, OSError) as exc:
            raise GitHubApiFailure("GitHub discovery unavailable or denied") from exc

    def associated_prs(self, head_sha: str):
        if not isinstance(head_sha,str) or not _SHA.fullmatch(head_sha):
            raise GitHubApiFailure("invalid exact commit")
        result = self._read_discovery("/commits/"+head_sha+"/pulls?per_page=100",list)
        if len(result)>=100:
            raise GitHubApiFailure("ambiguous or incomplete PR discovery")
        return result

    def runs_for_head(self, head_sha: str):
        if not isinstance(head_sha,str) or not _SHA.fullmatch(head_sha):
            raise GitHubApiFailure("invalid exact commit")
        result = self._read_discovery("/actions/runs?head_sha="+head_sha+"&per_page=100",dict)
        rows = result.get("workflow_runs")
        if (not isinstance(rows,list) or type(result.get("total_count")) is not int
                or result["total_count"]!=len(rows) or len(rows)>=100):
            raise GitHubApiFailure("ambiguous or incomplete CI discovery")
        return rows


class GitHubForge:
    """A qualified Git evidence adapter for one configured repository."""

    def __init__(
        self, repo_alias: str, repo_full_name: str,
        request: Callable[[str, str, Optional[dict]], Mapping],
        base_branch: str = "main",
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

    def discover_delivery(self, branch: str, head_sha: str, required_workflows: Sequence[str]) -> dict:
        required = validate_delivery_config(self.repo_full_name,self.base_branch,required_workflows)
        self._head_branch("refs/heads/"+branch)
        if not _SHA.fullmatch(head_sha):
            raise GitHubApiFailure("invalid local commit SHA")
        expected = self.repo_full_name.lower()
        def repo_matches(value):
            return (isinstance(value,Mapping) and isinstance(value.get("full_name"),str)
                    and value["full_name"].lower()==expected)
        if not callable(getattr(self.request,"associated_prs",None)) or not callable(getattr(self.request,"runs_for_head",None)):
            raise GitHubApiFailure("trusted discovery transport required")
        candidates = []
        for pr in self.request.associated_prs(head_sha):
            if not isinstance(pr,Mapping):
                raise GitHubApiFailure("invalid associated PR")
            head,base = pr.get("head"),pr.get("base")
            if (isinstance(head,Mapping) and isinstance(base,Mapping)
                    and repo_matches(head.get("repo")) and repo_matches(base.get("repo"))
                    and head.get("sha")==head_sha and head.get("ref")==branch
                    and base.get("ref")==self.base_branch
                    and (pr.get("state")=="open" or (pr.get("state")=="closed" and pr.get("merged_at")))):
                if type(pr.get("number")) is not int:
                    raise GitHubApiFailure("invalid PR number")
                candidates.append(pr["number"])
        if len(set(candidates))!=1:
            raise GitHubApiFailure("exact PR missing or ambiguous; no proof")
        pr_number=candidates[0]
        by_path={}
        for ci in self.request.runs_for_head(head_sha):
            if not isinstance(ci,Mapping):
                raise GitHubApiFailure("invalid CI discovery item")
            path,event=ci.get("path"),ci.get("event")
            associated=ci.get("pull_requests")
            if (path not in required or not repo_matches(ci.get("repository"))
                    or not repo_matches(ci.get("head_repository"))
                    or ci.get("head_sha")!=head_sha or ci.get("head_branch")!=branch
                    or event not in ("pull_request","push")
                    or (event=="pull_request" and (not isinstance(associated,list)
                        or not any(isinstance(p,Mapping) and p.get("number")==pr_number for p in associated)))):
                continue
            if any(type(ci.get(field)) is not int or ci[field]<=0 for field in ("run_number","run_attempt","id")):
                raise GitHubApiFailure("CI ordering receipt invalid")
            rank=(ci["run_number"],ci["run_attempt"])
            old=by_path.get(path)
            if old is not None and rank==(old["run_number"],old["run_attempt"]) and old["id"]!=ci["id"]:
                raise GitHubApiFailure("ambiguous latest CI run")
            if old is None or rank>(old["run_number"],old["run_attempt"]):
                by_path[path]=ci
        if set(by_path)!=set(required):
            raise GitHubApiFailure("required CI discovery incomplete")
        if any(ci.get("status")!="completed" or ci.get("conclusion")!="success" for ci in by_path.values()):
            raise GitHubApiFailure("latest required CI is pending or unsuccessful")
        ids=[by_path[path]["id"] for path in required]
        # Re-read the chosen PR and every run through the existing strict verifier.
        return self.observe_delivery(pr_number,ids,branch,head_sha,required)

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
