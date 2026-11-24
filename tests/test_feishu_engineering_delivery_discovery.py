"""Exact PR/CI discovery is read-only and never picks old green over new failed."""
import unittest
from tools.codex_assets.feishu_engineering_agent.github_adapter import GitHubForge, GitHubApiFailure

REPO="example-org/robot"
SHA="a"*40
BRANCH="agent-1"
PATH=".github/workflows/verify.yml"
PR=7
REPO_REF={"full_name":REPO}


class FakeDiscovery:
    def __init__(self):
        self.pr={"number":PR,"state":"open","merged_at":None,
                 "head":{"repo":REPO_REF,"sha":SHA,"ref":BRANCH},
                 "base":{"repo":REPO_REF,"ref":"main"}}
        self.old=self.run(11,1)
        self.latest=self.run(12,2)
        self.rows=[self.old,self.latest]
        self.prs=[self.pr]
        self.calls=[]
    def run(self,id,number,status="completed",conclusion="success"):
        return {"id":id,"run_number":number,"run_attempt":1,"repository":REPO_REF,
                "head_repository":REPO_REF,"head_sha":SHA,"head_branch":BRANCH,
                "status":status,"conclusion":conclusion,"path":PATH,"event":"pull_request",
                "pull_requests":[{"number":PR}]}
    def associated_prs(self,head):
        assert head==SHA
        return self.prs
    def runs_for_head(self,head):
        assert head==SHA
        return self.rows
    def __call__(self,method,path,payload):
        assert method=="GET" and payload is None
        self.calls.append(path)
        if path.endswith("/pulls/7"):
            return self.pr
        return next(row for row in self.rows if path.endswith("/"+str(row["id"])))


class DeliveryDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.transport=FakeDiscovery()
        self.forge=GitHubForge("robot",REPO,self.transport,"main")
    def test_exact_latest_and_recheck(self):
        proof=self.forge.discover_delivery(BRANCH,SHA,(PATH,))
        self.assertEqual(PR,proof["pr_number"])
        self.assertEqual({PATH:12},proof["workflows"])
        self.assertEqual(2,sum(path.endswith("/pulls/7") for path in self.transport.calls))
        self.assertTrue(any(path.endswith("/runs/12") for path in self.transport.calls))
    def test_no_old_green_fallback(self):
        self.transport.latest["conclusion"]="failure"
        with self.assertRaisesRegex(GitHubApiFailure,"pending or unsuccessful"):
            self.forge.discover_delivery(BRANCH,SHA,(PATH,))
        self.assertEqual([],self.transport.calls)
    def test_wrong_head_and_ambiguous_pr_fail(self):
        self.transport.prs=[self.transport.pr,dict(self.transport.pr,number=8)]
        with self.assertRaisesRegex(GitHubApiFailure,"ambiguous"):
            self.forge.discover_delivery(BRANCH,SHA,(PATH,))
        self.transport.prs=[self.transport.pr]
        self.transport.pr["head"]["sha"]="b"*40
        with self.assertRaises(GitHubApiFailure):
            self.forge.discover_delivery(BRANCH,SHA,(PATH,))
