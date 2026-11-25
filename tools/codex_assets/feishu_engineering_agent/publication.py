"""Explicit exact-commit publication through the existing Bot controller.

The model and verification sandbox never receive this transport or credential.
A durable intent permits one attempt; later commands only reconcile via GET.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from .delivery import ContextDelivery
from .github_adapter import validate_delivery_config
from .models import IntakeRejected


_SHA = re.compile(r"[a-f0-9]{40}\Z")
_COMMAND = re.compile(r"/publish ([a-f0-9]{40})\Z")
_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*\Z")


def _branch(value):
    if (not isinstance(value, str) or len(value) > 200 or not _BRANCH.fullmatch(value)
            or ".." in value or any(part.endswith((".lock", ".")) for part in value.split("/"))):
        raise IntakeRejected("invalid publication branch")
    return value


def _credential(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{8,512}", value):
        raise IntakeRejected("未配置独立 GitHub 写凭据")
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubPublicationTransport:
    """Only exact repository reads and draft-PR creation; never merge/delete."""

    def __init__(self, repository, token):
        if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository) or ".." in repository:
            raise IntakeRejected("invalid publication repository")
        self.repository = repository
        self.root = "https://api.github.com/repos/" + repository
        self.token = _credential(token)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _request(self, method, suffix, *, payload=None, missing=False):
        # All callers below construct bounded paths; no chat-supplied URL.
        if method not in ("GET", "POST") or (method == "POST" and suffix != "/pulls"):
            raise IntakeRejected("publication transport operation denied")
        headers = {"Authorization": "Bearer " + self.token,
                   "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2026-03-10",
                   "User-Agent": "feishu-engineering-agent"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(self.root + suffix, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                if 'rel="next"' in (response.headers.get("Link", "") or ""):
                    raise IntakeRejected("publication observation exceeds one page")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise IntakeRejected("oversized publication response")
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if missing and method == "GET" and exc.code == 404:
                return None
            raise IntakeRejected("GitHub publication response unavailable; do not retry writes") from None
        except (urllib.error.URLError, ValueError, OSError):
            raise IntakeRejected("GitHub publication response unavailable; do not retry writes") from None

    def branch_head(self, branch):
        branch = _branch(branch)
        observed = self._request("GET", "/git/ref/heads/" + urllib.parse.quote(branch, safe=""), missing=True)
        if observed is None:
            return None
        obj = observed.get("object") if isinstance(observed, dict) else None
        if (not isinstance(obj, dict) or observed.get("ref") != "refs/heads/" + branch
                or obj.get("type") != "commit" or not isinstance(obj.get("sha"), str)
                or not _SHA.fullmatch(obj["sha"])):
            raise IntakeRejected("GitHub branch identity mismatch")
        return obj["sha"]

    def _pull(self, row, branch, base, sha, *, draft_required=False):
        if not isinstance(row, dict):
            raise IntakeRejected("GitHub PR identity mismatch")
        head, target = row.get("head"), row.get("base")
        if (not isinstance(head, dict) or not isinstance(target, dict)
                or not isinstance(head.get("repo"), dict) or not isinstance(target.get("repo"), dict)
                or head["repo"].get("full_name", "").lower() != self.repository.lower()
                or target["repo"].get("full_name", "").lower() != self.repository.lower()
                or head.get("ref") != branch or head.get("sha") != sha or target.get("ref") != base
                or row.get("state") != "open" or row.get("merged_at") is not None
                or type(row.get("number")) is not int or row["number"] < 1
                or type(row.get("draft")) is not bool or (draft_required and row["draft"] is not True)):
            raise IntakeRejected("GitHub PR identity mismatch")
        return {"number": row["number"], "draft": row["draft"]}

    def find_pull(self, branch, base, sha):
        _branch(branch)
        _branch(base)
        if not _SHA.fullmatch(sha):
            raise IntakeRejected("invalid exact publication commit")
        query = urllib.parse.urlencode({"state": "all", "head": self.repository.split("/")[0] + ":" + branch,
                                        "base": base, "per_page": "100"})
        rows = self._request("GET", "/pulls?" + query)
        if not isinstance(rows, list) or len(rows) > 1:
            raise IntakeRejected("GitHub PR observation is ambiguous")
        return self._pull(rows[0], branch, base, sha) if rows else None

    def create_pull(self, branch, base, sha, task_id):
        _branch(branch)
        _branch(base)
        if not _SHA.fullmatch(sha) or type(task_id) is not int or task_id < 1:
            raise IntakeRejected("invalid exact publication identity")
        # No work-item text, source document, actor, private path or credential.
        payload = {"title": "Engineering task " + str(task_id) + ": " + sha[:12],
                   "head": branch, "base": base, "draft": True,
                   "maintainer_can_modify": False,
                   "body": "Controller-published local commit: `" + sha
                           + "`.\n\nRequired CI and project acceptance remain pending."}
        return self._pull(self._request("POST", "/pulls", payload=payload),
                          branch, base, sha, draft_required=True)


class NativePublicationGit:
    """Copy exact objects into a private bare repo before authenticated push."""

    def __init__(self, config):
        self.config = config

    def verify_local(self, repo, row):
        from ..feishu_codex_bot import ResumeTarget, WorktreeManager
        manager = WorktreeManager(self.config)
        cwd = pathlib.Path(row["cwd"])
        target = ResumeTarget(row["thread_id"], cwd, row["root_task_id"], row["branch"], row["commit_sha"])
        manager.require_resume_base(target, repo)
        origin = manager._git(repo.path, ["config", "--local", "--no-includes", "--get-all", "remote.origin.url"])
        accepted = {"https://github.com/" + repo.github_repository,
                    "https://github.com/" + repo.github_repository + ".git",
                    "git@github.com:" + repo.github_repository,
                    "git@github.com:" + repo.github_repository + ".git"}
        if origin not in accepted:
            raise IntakeRejected("本地源仓库与发布白名单不一致")
        common = pathlib.Path(manager._git(cwd, ["rev-parse", "--path-format=absolute", "--git-common-dir"]))
        if (common.resolve() != common or (common / "objects").is_symlink()
                or (common / "objects" / "info" / "alternates").exists()
                or (common / "objects" / "info" / "alternates").is_symlink()
                or (common / "shallow").exists()
                or manager._git(cwd, ["for-each-ref", "--format=%(refname)", "refs/replace/"])):
            raise IntakeRejected("发布拒绝替换对象、浅克隆或外部对象存储")
        return cwd

    @staticmethod
    def environment(token="", repository=""):
        from ..feishu_codex_bot import controller_git_environment
        env = controller_git_environment(os.environ)
        env.update({"GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1"})
        controls = {"credential.helper": "", "credential.interactive": "false",
                    "http.proxy": "", "http.followRedirects": "false", "http.sslVerify": "true",
                    "push.followTags": "false", "push.recurseSubmodules": "no",
                    "push.gpgSign": "false", "core.askPass": "", "gc.auto": "0"}
        if token:
            _credential(token)
            if not _REPOSITORY.fullmatch(repository) or ".." in repository:
                raise IntakeRejected("invalid publication repository")
            controls["protocol.https.allow"] = "always"
            authorization = base64.b64encode(("x-access-token:" + token).encode("ascii")).decode("ascii")
            controls["http.https://github.com/" + repository + ".git.extraHeader"] = "Authorization: Basic " + authorization
        start = int(env["GIT_CONFIG_COUNT"])
        for index, (key, value) in enumerate(controls.items(), start):
            env["GIT_CONFIG_KEY_" + str(index)] = key
            env["GIT_CONFIG_VALUE_" + str(index)] = value
        env["GIT_CONFIG_COUNT"] = str(start + len(controls))
        return env

    @staticmethod
    def _run(cwd, args, env, *, stdin=None, stdout=None, input=None):
        try:
            completed = subprocess.run(
                ["rtk", "proxy", "git", "-C", str(cwd), *args], cwd=str(cwd), env=env,
                stdin=stdin, stdout=stdout if stdout is not None else subprocess.PIPE,
                stderr=subprocess.PIPE, input=input, timeout=120, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise IntakeRejected("Git publication outcome unavailable; do not retry writes") from None
        if completed.returncode != 0:
            raise IntakeRejected("Git publication did not confirm success; do not retry writes")
        return completed.stdout or b""

    def push_create(self, repo, row, token):
        cwd = self.verify_local(repo, row)
        sha, branch = row["commit_sha"], _branch(row["branch"])
        if not _SHA.fullmatch(sha) or branch == repo.github_base_branch:
            raise IntakeRejected("发布必须使用隔离分支的精确 SHA")
        with tempfile.TemporaryDirectory(prefix="feishu-publication-") as temporary:
            private = pathlib.Path(temporary)
            bare = private / "objects.git"
            safe = self.environment()
            self._run(private, ["init", "--bare", str(bare)], safe)
            pack = private / "objects.pack"
            with pack.open("xb") as handle:
                self._run(cwd, ["pack-objects", "--stdout", "--revs"], safe,
                          stdout=handle, input=(sha + "\n").encode("ascii"))
            if pack.stat().st_size > 512 * 1024 * 1024:
                raise IntakeRejected("publication object snapshot exceeds safety bound")
            with pack.open("rb") as handle:
                self._run(bare, ["index-pack", "--stdin"], safe, stdin=handle)
            if self._run(bare, ["rev-parse", "--verify", sha + "^{commit}"], safe).decode("ascii").strip() != sha:
                raise IntakeRejected("publication object snapshot mismatch")
            # Empty expected OID is an atomic create-if-absent condition, not
            # permission to overwrite an existing ref (including ancestors).
            self._run(bare, ["push", "--porcelain", "--no-follow-tags",
                             "--recurse-submodules=no", "--force-with-lease=refs/heads/" + branch + ":",
                             "--", "https://github.com/" + repo.github_repository + ".git",
                             sha + ":refs/heads/" + branch], self.environment(token, repo.github_repository))


class ContextPublication:
    def __init__(self, config, executor, *, transport_factory=None, pusher=None):
        self.config, self.executor, self.store = config, executor, executor.store
        self.transport_factory = transport_factory
        self.pusher = pusher or NativePublicationGit(config)

    @staticmethod
    def _policy(repo):
        payload = {"repository": repo.github_repository, "base": repo.github_base_branch,
                   "path": str(repo.path), "worktrees": str(repo.worktree_root),
                   "branch_prefix": repo.branch_prefix, "enabled": repo.github_publish_enabled}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _mark_unknown(self, task_id):
        with self.store._connect() as db:
            db.execute("UPDATE engineering_context_publications SET status='unknown',updated_at=? "
                       "WHERE task_id=? AND status!='published'", (int(time.time()), task_id))

    def _observe(self, transport, row, repo):
        if transport.branch_head(row["branch"]) != row["commit_sha"]:
            raise IntakeRejected("远端分支尚未确认或已漂移")
        pull = transport.find_pull(row["branch"], repo.github_base_branch, row["commit_sha"])
        if pull is None:
            raise IntakeRejected("尚未观察到精确 PR")
        with self.store._connect() as db:
            old = db.execute("SELECT pr_number FROM engineering_context_publications WHERE task_id=?",
                             (row["task_id"],)).fetchone()
            if old is None or (old["pr_number"] is not None and old["pr_number"] != pull["number"]):
                raise IntakeRejected("发布回执与观察到的 PR 不一致")
            db.execute("UPDATE engineering_context_publications SET status='published',pr_number=?,updated_at=? WHERE task_id=?",
                       (pull["number"], int(time.time()), row["task_id"]))
        return ("已核对精确提交 " + row["commit_sha"] + " 的 GitHub PR：\nhttps://github.com/"
                + repo.github_repository + "/pull/" + str(pull["number"])
                + "\n该会话已封存；必需 CI、项目验收及合并仍待独立完成。")

    def publish(self, event, result):
        command = _COMMAND.fullmatch(event.text.strip())
        if (event.source != "feishu_message" or command is None or result.intent != "publish"
                or result.scope_text != command.group(1) or event.chat != self.config.target_chat_id):
            raise IntakeRejected("发布必须由当前可信话题中的 /publish <40位提交SHA> 明确授权")
        row, repo = ContextDelivery(self.config, self.executor)._local(event, result)
        if (getattr(repo, "github_publish_enabled", False) is not True
                or not self.config.sender_allowed(event.actor, repo)):
            raise IntakeRejected("当前仓库尚未启用受控 GitHub 发布")
        validate_delivery_config(repo.github_repository, repo.github_base_branch, repo.github_required_workflows)
        token = _credential(getattr(self.config, "agent_github_write_token", ""))
        if (repo.worktree_root is None or repo.edit_strategy != "worktree" or not repo.commit_enabled
                or row["commit_sha"] != command.group(1) or not _SHA.fullmatch(row["commit_sha"])
                or type(row["root_task_id"]) is not int or row["root_task_id"] < 1
                or row["branch"] != repo.branch_prefix + "-" + str(row["root_task_id"])
                or row["branch"] in (repo.github_base_branch, "main", "master", "develop")
                or row["cwd"] != str(repo.worktree_root / ("task-" + str(row["root_task_id"])))):
            raise IntakeRejected("发布 SHA、隔离分支或工作区与完成回执不一致")
        _branch(row["branch"])
        policy = self._policy(repo)
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            receipt = db.execute("SELECT e.content_sha256,e.context_id,v.repository FROM engineering_context_events e "
                                 "JOIN engineering_context_event_targets v ON v.event_key=e.event_key WHERE e.event_key=?",
                                 (event.event_key,)).fetchone()
            latest = ContextDelivery._latest_edit(db, result.context_id, result.repo)
            if (receipt is None or receipt["content_sha256"] != event.content_digest
                    or receipt["context_id"] != result.context_id or receipt["repository"] != result.repo
                    or latest is None or latest["task_id"] != row["task_id"] or latest["status"] != "completed"
                    or latest["commit_sha"] != row["commit_sha"] or latest["branch"] != row["branch"]):
                raise IntakeRejected("发布命令或研发版本已变化")
            old = db.execute("SELECT * FROM engineering_context_publications WHERE root_task_id=?",
                             (row["root_task_id"],)).fetchone()
            if old is not None:
                if (old["task_id"] != row["task_id"] or old["head_sha"] != row["commit_sha"]
                        or old["policy_sha256"] != policy or old["context_id"] != row["context_id"]):
                    raise IntakeRejected("该会话已有不同的发布意图；禁止覆盖或重推")
                created = False
            else:
                self.pusher.verify_local(repo, row)
                now = int(time.time())
                db.execute("INSERT INTO engineering_context_publications "
                           "(task_id,root_task_id,context_id,repo_alias,repository,base_branch,branch,head_sha,"
                           "command_event_key,command_sha256,policy_sha256,status,created_at,updated_at) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?,'intent',?,?)",
                           (row["task_id"], row["root_task_id"], row["context_id"], repo.alias,
                            repo.github_repository, repo.github_base_branch, row["branch"], row["commit_sha"],
                            event.event_key, event.content_digest, policy, now, now))
                created = True
        transport = (self.transport_factory(repo, token) if self.transport_factory
                     else GitHubPublicationTransport(repo.github_repository, token))
        try:
            if created:
                remote = transport.branch_head(row["branch"])
                if remote is not None and remote != row["commit_sha"]:
                    raise IntakeRejected("远端分支已有其他提交，拒绝覆盖")
                if remote is None:
                    self.pusher.push_create(repo, row, token)
                if transport.branch_head(row["branch"]) != row["commit_sha"]:
                    raise IntakeRejected("发布后远端分支未确认或已漂移")
                if transport.find_pull(row["branch"], repo.github_base_branch, row["commit_sha"]) is None:
                    transport.create_pull(row["branch"], repo.github_base_branch, row["commit_sha"], row["task_id"])
            return self._observe(transport, row, repo)
        except Exception:
            self._mark_unknown(row["task_id"])
            return ("GitHub 交付尚未核实，已保留发布意图并封存该会话。"
                    "再次发送相同 /publish <SHA> 只进行远端查询对账，不会重复推送或创建 PR。")
