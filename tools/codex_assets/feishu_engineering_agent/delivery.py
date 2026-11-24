"""Read-only Git/CI evidence for actual tasks in the unified Bot state."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import time

from .models import IntakeRejected


class ContextDelivery:
    """Read-only proof for the latest actual edit in a live topic.

    No publication, model, source-status change, or simulated QA. Persist only
    exact GitHub evidence after rechecking the local task receipt.
    """
    def __init__(self, config, executor, forge_factory=None):
        self.config, self.executor = config, executor
        self.store = executor.store
        self.forge_factory = forge_factory

    @staticmethod
    def _latest_edit(db, context_id, repository):
        # Reads/reviews do not replace an edit's deliverable. Select before
        # checking status so a newer failed or unknown edit blocks old proof.
        return db.execute(
            "SELECT x.task_id,t.status,x.commit_sha,x.branch FROM engineering_context_tasks x "
            "JOIN tasks t ON t.id=x.task_id WHERE x.context_id=? AND t.repository=? "
            "AND t.mode='edit' ORDER BY x.task_id DESC LIMIT 1",
            (context_id, repository),
        ).fetchone()

    def _local(self, event, result):
        with self.store._connect() as db:
            latest = self._latest_edit(db, result.context_id, result.repo)
        if latest is None or latest["status"]!="completed":
            raise IntakeRejected("当前话题没有已完成的本地编辑版本")
        row=self.executor.binding(latest["task_id"])
        if (row is None or (row["tenant"],row["chat"],row["actor"],row["topic"],row["repo"])!=
                (event.tenant,event.chat,event.actor,result.topic,result.repo)):
            raise IntakeRejected("交付话题身份不匹配")
        repo=self.config.repositories.get(result.repo)
        if repo is None or not self.config.sender_allowed(event.actor,repo):
            raise IntakeRejected("当前仓库不再授权")
        with self.store._connect() as db:
            local=db.execute("SELECT branch_name,commit_hash,worktree_path FROM task_results WHERE task_id=?",
                             (row["task_id"],)).fetchone()
        if (local is None or not row["branch"] or not row["commit_sha"]
                or local["branch_name"]!=row["branch"] or local["commit_hash"]!=row["commit_sha"]
                or local["worktree_path"]!=row["cwd"]):
            raise IntakeRejected("本地 Git 交付回执不完整或不一致")
        return row,repo

    def verify(self,event,result):
        from .github_adapter import GitHubForge, GitHubTransport
        row,repo=self._local(event,result)
        if not repo.github_repository or not repo.github_required_workflows:
            return "已存在本地提交 "+row["commit_sha"]+"；尚未配置该仓库的 GitHub 必需 CI，不能宣称交付通过。"
        forge=(self.forge_factory(repo) if self.forge_factory else GitHubForge(
            repo.alias,repo.github_repository,
            GitHubTransport(repo.github_repository,self.config.agent_github_read_token),
            repo.github_base_branch))
        observed=forge.discover_delivery(row["branch"],row["commit_sha"],repo.github_required_workflows)
        if (observed.get("repo_alias")!=repo.alias or observed.get("repo_full_name")!=repo.github_repository
                or observed.get("head_sha")!=row["commit_sha"] or observed.get("branch")!=row["branch"]
                or observed.get("base_branch")!=repo.github_base_branch
                or set(observed.get("workflows",{}))!=set(repo.github_required_workflows)
                or type(observed.get("pr_number")) is not int):
            raise IntakeRejected("独立交付观察与实际 Git 版本不一致")
        proof=json.dumps(observed,sort_keys=True,separators=(",",":"))
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            latest=self._latest_edit(db, row["context_id"], row["repository"])
            if (latest is None or latest["task_id"]!=row["task_id"] or latest["status"]!="completed"
                    or latest["commit_sha"]!=row["commit_sha"] or latest["branch"]!=row["branch"]):
                raise IntakeRejected("核验期间研发版本发生变化")
            old=db.execute("SELECT head_sha,repository,pr_number FROM engineering_context_delivery WHERE task_id=?",
                           (row["task_id"],)).fetchone()
            if old is not None and (old["head_sha"]!=row["commit_sha"]
                    or old["repository"]!=repo.github_repository or old["pr_number"]!=observed["pr_number"]):
                raise IntakeRejected("交付回执冲突")
            db.execute(
                "INSERT INTO engineering_context_delivery(task_id,head_sha,repository,pr_number,proof_json,verified_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET proof_json=excluded.proof_json,verified_at=excluded.verified_at",
                (row["task_id"],row["commit_sha"],repo.github_repository,observed["pr_number"],proof,int(time.time())))
        return ("已独立核验精确本地提交 "+row["commit_sha"]+" 的 PR 与全部必需 CI。"
                "\nPR：https://github.com/"+repo.github_repository+"/pull/"+str(observed["pr_number"])
                +"\n必需 CI："+str(len(observed["workflows"]))+" 项；等待项目实际测试/QA。原工单未关闭。")

    @staticmethod
    def _joint_snapshot(db,context_id):
        # Retain every participating repository. A read-only participant's
        # latest task remains visible so _local rejects its missing edit.
        return [dict(row) for row in db.execute(
            "SELECT t.repository,x.task_id,t.mode,t.status,x.commit_sha,x.branch "
            "FROM engineering_context_tasks x JOIN tasks t ON t.id=x.task_id "
            "WHERE x.context_id=? AND x.task_id IN (SELECT "
            "COALESCE(MAX(CASE WHEN q.mode='edit' THEN y.task_id END),MAX(y.task_id)) "
            "FROM engineering_context_tasks y JOIN tasks q ON q.id=y.task_id "
            "WHERE y.context_id=? GROUP BY q.repository) ORDER BY t.repository",
            (context_id,context_id))]

    def verify_joint(self,event,result):
        """Refresh participating repositories; CI evidence is not joint product QA."""
        with self.store._connect() as db:
            snapshot=self._joint_snapshot(db,result.context_id)
        if len(snapshot)<2:
            raise IntakeRejected("联合交付至少需要两个实际研发仓库")
        selections=[]
        for item in snapshot:
            selected=dataclasses.replace(result,repo=item["repository"])
            row,repo=self._local(event,selected)
            if (row["task_id"]!=item["task_id"] or row["commit_sha"]!=item["commit_sha"]
                    or not repo.github_repository or not repo.github_required_workflows):
                raise IntakeRejected("联合交付仓库版本或 CI 配置不完整")
            selections.append(selected)
        for selected in selections:
            self.verify(event,selected)
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._joint_snapshot(db,result.context_id)!=snapshot:
                raise IntakeRejected("联合核验期间研发版本发生变化")
            evidence=[]
            for item in snapshot:
                proof=db.execute("SELECT * FROM engineering_context_delivery WHERE task_id=?",
                                 (item["task_id"],)).fetchone()
                repo=self.config.repositories.get(item["repository"])
                if (proof is None or repo is None or not self.config.sender_allowed(event.actor,repo)
                        or proof["head_sha"]!=item["commit_sha"] or proof["repository"]!=repo.github_repository):
                    raise IntakeRejected("联合交付缺少精确仓库证明")
                observed=json.loads(proof["proof_json"])
                if set(observed["workflows"])!=set(repo.github_required_workflows):
                    raise IntakeRejected("联合交付必需 CI 已变化")
                evidence.append({"alias":item["repository"],"task_id":item["task_id"],
                                 "head_sha":item["commit_sha"],"branch":item["branch"],
                                 "repository":proof["repository"],"pr_number":proof["pr_number"],
                                 "workflows":observed["workflows"]})
            heads=json.dumps(snapshot,sort_keys=True,separators=(",",":"))
            digest=hashlib.sha256(heads.encode("utf-8")).hexdigest()
            db.execute("INSERT INTO engineering_context_joint_delivery(context_id,head_set_sha256,proof_json,verified_at) "
                       "VALUES (?,?,?,?) ON CONFLICT(context_id,head_set_sha256) DO UPDATE SET "
                       "proof_json=excluded.proof_json,verified_at=excluded.verified_at",
                       (result.context_id,digest,json.dumps(evidence,sort_keys=True,separators=(",",":")),int(time.time())))
        lines=["联合交付 CI 核验通过（不是跨仓集成测试或产品验收）","版本集合："+digest]
        for proof in evidence:
            lines.append(proof["alias"]+" "+proof["head_sha"]+" PR #"+str(proof["pr_number"]))
        lines.append("待针对上述精确版本集合完成实际跨仓联调及独立 QA；原工单未关闭。")
        return "\n".join(lines)

    def feedback(self,event,result):
        row,repo=self._local(event,result)
        with self.store._connect() as db:
            sources=list(db.execute("SELECT url FROM engineering_context_sources WHERE context_id=? ORDER BY url",
                                    (row["context_id"],)))
            proof=db.execute("SELECT * FROM engineering_context_delivery WHERE task_id=?",(row["task_id"],)).fetchone()
        lines=["研发交付反馈（原工单由业务负责人验收）","仓库："+repo.alias,
               "本地提交："+row["commit_sha"],"分支："+row["branch"]]
        lines.extend("来源："+s["url"] for s in sources)
        if proof is None or proof["head_sha"]!=row["commit_sha"] or proof["repository"]!=repo.github_repository:
            lines.append("PR/CI：尚未独立核验，请在本话题发送“检查 CI”。")
        else:
            observed=json.loads(proof["proof_json"])
            root="https://github.com/"+proof["repository"]
            lines.append("PR："+root+"/pull/"+str(proof["pr_number"]))
            lines.extend("CI："+root+"/actions/runs/"+str(i) for i in observed["workflows"].values())
            lines.append("以上为记录的精确版本核验证据；如代码/CI 变化须重新核验。")
        lines.extend(["独立产品/测试验收：待实际负责人确认。",
                      "未执行原工作项回写、自动关闭、发布或设备烧录。"])
        return "\n".join(lines)
