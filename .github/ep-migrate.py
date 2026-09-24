from pathlib import Path
import ast, copy, hashlib, json, shutil, subprocess, sys
from datetime import datetime, timezone

ROOT = Path.cwd()
UP = ROOT / '.adk-source'
COMMIT = '7367ef84787de75bb751940b32c9e80009660e47'
assert subprocess.check_output(['git', '-C', str(UP), 'rev-parse', 'HEAD'], text=True).strip() == COMMIT
sys.path.insert(0, str(ROOT))
from tools.codex_assets.execution_policy import engine as old

def blob(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def write(path, text):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')

def update(path, function):
    write(path, function((ROOT / path).read_text(encoding='utf-8')))

def write_json(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')

# Freeze old-engine outputs before importing the new namespace.
nodes = []
for node in ast.parse((UP / 'tests/test_execution_policy.py').read_text()).body:
    if isinstance(node, ast.ClassDef):
        break
    if isinstance(node, ast.FunctionDef):
        nodes.append(node)
namespace = {'datetime': datetime, 'timezone': timezone, 'goal_intake_attestation_sha256': old.goal_intake_attestation_sha256}
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'reviewed-fixture-helpers', 'exec'), namespace)
active, event, usage = (namespace[key] for key in ('active_events', 'event', 'usage'))
as_of = '2026-08-24T01:12:00+00:00'
cases = []
def add(name, events, gate='steady', now=as_of):
    case = {'name': name, 'events': events, 'gate_event': gate, 'as_of': now}
    try:
        state = old.reduce_events(events)
        decision = old.evaluate(state, namespace['policy'](), gate_event=gate, as_of=datetime.fromisoformat(now))
        case.update(state_sha256=digest(state), decision_sha256=digest(decision), expected_action=decision['recommended_action'], expected_gate_allowed=decision['gate_allowed'])
    except old.ExecutionPolicyError as exc:
        case['expected_error'] = str(exc)
    cases.append(case)
for total, last, name in [(500,100,'continue'),(800,100,'checkpoint'),(1000,100,'compact-token'),(1100,100,'stop'),(500,600,'compact-context')]:
    add(name, active(total, last))
add('retry-exhausted', active()[:-1] + [event(4,'retry.recorded',{'reason_id':'attempt-1'}),event(5,'retry.recorded',{'reason_id':'attempt-2'}),usage(6,500)])
add('stale', active(), now='2026-08-24T02:30:00+00:00')
add('aborted', active()+[event(5,'goal.aborted',{})], 'final')
complete = active()[:-1] + [event(4,'evidence.added',{'evidence_id':'tests','sha256':'b'*64}), event(5,'evidence.added',{'evidence_id':'review','sha256':'c'*64}), event(6,'checkpoint.verified',{'revision':1,'evidence_ids':['tests','review']}), event(7,'goal.updated',{'open_items_count':0}), event(8,'artifact.verified',{'artifact_type':'repo','evidence_id':'tests'}), event(9,'artifact.verified',{'artifact_type':'build','evidence_id':'tests'}), event(10,'goal.completed',{}), usage(11,1200)]
add('completed-final', complete, 'final')
add('commit-missing-review', complete, 'commit')
add('missing-checkpoint', complete[:5]+complete[6:], 'final')
replanned = copy.deepcopy(complete)
replanned.insert(-2, event(12,'progress.advanced',{'revision':2},minute=9))
add('stale-checkpoint', replanned, 'final')
apply_events = active()[:-1] + [event(4,'evidence.added',{'evidence_id':'proof','sha256':'b'*64})] + [event(i,'artifact.verified',{'artifact_type':kind,'evidence_id':'proof'}) for i,kind in enumerate(['repo','build','plan','dry-run'],5)] + [usage(9,500)]
add('active-apply', apply_events, 'apply')
add('active-final-blocked', apply_events, 'final')
add('unmanaged-review', namespace['completed_events_without_artifacts']('review','readonly'), 'final')
add('duplicate-idempotent', active()+[copy.deepcopy(active()[-1])])
bad = copy.deepcopy(active()[-1]); bad['payload']['total_tokens'] += 1
add('duplicate-conflict', active()+[bad])
bad = namespace['goal_started'](); bad['payload']['objective'] = 'fixture-only'
add('raw-content-rejected', [bad])
bad = copy.deepcopy(active()[-1]); bad['thread_id'] = 'other-thread'
add('mixed-thread-rejected', active()[:-1]+[bad])
fixture = {'kind':'execution-policy-migration-replay/v1','evidence_class':'synthetic-regression-not-live','baseline_consumer_commit':'6318ad8ddd4d5f268c8ca68980119e998f250e43','baseline_provider_version':'7.0.4','baseline_engine_blob':blob((ROOT/'tools/codex_assets/execution_policy/engine.py').read_bytes()),'baseline_contracts_blob':blob((ROOT/'tools/codex_assets/execution_policy/contracts.py').read_bytes()),'policy':namespace['policy'](),'cases':cases}
write('tests/fixtures/execution-policy-migration-replay.json', json.dumps(fixture, ensure_ascii=False, indent=2))
assert blob((ROOT/'tests/fixtures/execution-policy-migration-replay.json').read_bytes()) == '43e92cf960bd0f8c6729750c803f59e18d24d381'

expected_sources = {'__init__.py':'10d3b1e71e2a91bdf30b7cf15215adcbec2b800e','contracts.py':'626af591141b2dda6302edbe4363637435066628','decision.py':'b786e05d2e4615cb23d36e9d4ea2ba9582686ac9','reducer.py':'e9bfb216239ddc1bc7ce45be4f21b408105d4d3c'}
for filename, expected in expected_sources.items():
    source = UP/'src/agent_dev_kit/execution_policy'/filename
    assert blob(source.read_bytes()) == expected
    shutil.copyfile(source, ROOT/'tools/codex_assets/execution_policy'/filename)
(ROOT/'tools/codex_assets/execution_policy/engine.py').unlink()
base = {'repository':'jiying2007/agent-dev-kit','version':'7.0.31','commit':COMMIT,'source_blobs':expected_sources}
config = json.loads((ROOT/'manifests/execution_policy.json').read_text())
config['schema_version'] = 4
config['engine']['module'] = 'tools.codex_assets.execution_policy'
config['engine']['behavior_baseline'] = base
write_json('manifests/execution_policy.json', config)
lock = json.loads((ROOT/'manifests/provider-locks/agent-dev-kit.json').read_text())
assert blob((UP/'manifest.json').read_bytes()) == 'b50c24c47ac467ae6cfd1fa49e722844d77500cf'
lock.update(version='7.0.31', release_tag='v7.0.31', provider_commit=COMMIT, provider_tree='46fd5d2b99aa7fef7fb35c2c6624fd8790139506', manifest_blob='b50c24c47ac467ae6cfd1fa49e722844d77500cf', release_artifact={'name':'agent-dev-kit-7.0.31.tar.gz','sha256':'6326e9009d97660147a43b96802eae2bb5b7cf9c4555c451e4054f6fa278b5d9'})
write_json('manifests/provider-locks/agent-dev-kit.json', lock)
agents = json.loads((ROOT/'manifests/agents.json').read_text())
count = 0
for item in agents['agents']:
    if item.get('source_repo') != base['repository']:
        continue
    source = UP/item['source_path']
    assert blob(source.read_bytes()) == item['source_blob']
    item.update(version='7.0.31', source_ref=COMMIT, imported_at='2026-09-24', vendor_rel=item['vendor_rel'].replace('/7.0.4/','/7.0.31/'))
    target = ROOT/'src/codex-home'/item['vendor_rel']; target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target); count += 1
assert count == 9
write_json('manifests/agents.json',agents)
for version in ('5.1.0','5.1.1','7.0.4'):
    shutil.rmtree(ROOT/'src/codex-home/vendor/agents/agent-dev-kit'/version)
binding = json.loads((ROOT/'manifests/integrations/digital-worker-runtime-binding.json').read_text())
binding['source_binding'].update(release_version='7.0.31',provider_commit=COMMIT)
write_json('manifests/integrations/digital-worker-runtime-binding.json',binding)

def adapter(text):
    start=text.index('from .execution_policy.engine import ('); end=text.index('\n\n\nUTC',start)
    text=text[:start]+'''from .execution_policy.contracts import (
    ExecutionPolicyError,
    goal_intake_attestation_sha256,
    validate_policy,
)
from .execution_policy.decision import evaluate
from .execution_policy.reducer import reduce_events'''+text[end:]
    start=text.index('ENGINE_BASELINE = {'); end=text.index('\n\n\nclass ',start)
    text=text[:start]+'ENGINE_BASELINE = '+json.dumps(base,indent=4)+text[end:]
    text=text.replace('if value.get("schema_version") != 3:','if value.get("schema_version") != 4:').replace('"tools.codex_assets.execution_policy.engine"','"tools.codex_assets.execution_policy"')
    text=text.replace('for filename, key in (("engine.py", "engine_blob"), ("contracts.py", "support_blob")):', '''retired_engine = root / "tools/codex_assets/execution_policy/engine.py"
    if retired_engine.exists() or retired_engine.is_symlink():
        raise ExecutionPolicyAdapterError("retired Execution Policy module must be removed")
    for filename, expected_blob in ENGINE_BASELINE["source_blobs"].items():''')
    return text.replace('if actual_blob != ENGINE_BASELINE[key]:','if actual_blob != expected_blob:')
update('tools/codex_assets/execution_policy_adapter.py',adapter)

def validator(text):
    text=text.replace('import re\n','import re\nimport sys\n').replace('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path(__file__).resolve().parents[1]\nsys.path.insert(0, str(ROOT))')
    text=text.replace('ENGINE = ROOT / "tools/codex_assets/execution_policy/engine.py"\nCONTRACTS = ROOT / "tools/codex_assets/execution_policy/contracts.py"\n','')
    start=text.index('ADK_RELEASE = {'); end=text.index('\nADK_FIELDS =',start)
    release={key:lock[key] for key in ('version','release_tag','provider_commit','provider_tree','manifest_blob')}
    release['release_artifact_sha256']=lock['release_artifact']['sha256']
    text=text[:start]+'ADK_RELEASE = '+json.dumps(release,indent=4)+text[end:]
    text=text.replace('7.0.4','7.0.31')
    start=text.index('def validate_runtime_source(');end=text.index('\n\ndef validate_receipt_v2',start)
    text=text[:start]+'''def validate_runtime_source(runtime: dict[str, object]) -> None:
    from tools.codex_assets.execution_policy_adapter import load_runtime_config

    checked = load_runtime_config(ROOT)
    require(runtime == {key: value for key, value in checked.items() if not key.startswith("_")},
            "runtime config validation must use the same canonical source")
'''+text[end:]
    text=text.replace('BINDING, ADK, RUNTIME, ENGINE, CONTRACTS, HUB','BINDING, ADK, RUNTIME, HUB')
    text=text.replace('    print(f"runtime_engine_blob={ADK_RELEASE[\'engine_blob\']}")\n    print(f"runtime_support_blob={ADK_RELEASE[\'support_blob\']}")','    print("runtime_modules=contracts,decision,reducer,package")')
    return text
update('scripts/validate-runtime-binding.py',validator)
update('scripts/validate-adk-agent-binding.py',lambda text:text.replace('7.0.4','7.0.31').replace('1d6c28e89eb98a4af5ac978707730783f0c84437',COMMIT).replace('    adk_agents = {','    require(sorted(path.name for path in (SOURCE / "vendor/agents/agent-dev-kit").iterdir()) == [PROVIDER_VERSION], "retired ADK vendor tree returned")\n\n    adk_agents = {'))
update('tests/test_governance.py',lambda text:text.replace('"tools/codex_assets/execution_policy/engine.py",','"tools/codex_assets/execution_policy/__init__.py",\n        "tools/codex_assets/execution_policy/decision.py",\n        "tools/codex_assets/execution_policy/reducer.py",').replace('"7.0.4", report["execution_policy"]','"7.0.31", report["execution_policy"]').replace('execution_policy/engine.py','execution_policy/decision.py').replace('drift: engine.py','drift: decision.py'))
update('tests/test_doctor_execution_policy.py',lambda text:text.replace('("engine.py", "contracts.py")','("__init__.py", "contracts.py", "decision.py", "reducer.py")'))
update('tests/test_adk_skill_distribution.py',lambda text:text.replace('"7.0.4", report["provider_lock_version"]','"7.0.31", report["provider_lock_version"]').replace('self.assertEqual(0, report["skills_matching_provider_lock_commit"])','self.assertEqual(42, report["skills_matching_provider_lock_commit"])'))
text=(ROOT/'tests/test_execution_policy_source_set.py').read_text()
start=text.index('from tools.codex_assets.execution_policy.engine');end=text.index('\n\nROOT',start)
text=text[:start]+'''from tools.codex_assets.execution_policy.contracts import (
    POLICY_SCHEMA_V2,
    goal_intake_attestation_sha256,
    validate_policy,
)
from tools.codex_assets.execution_policy.reducer import reduce_events'''+text[end:]
start=text.index('ENGINE_BLOB =');end=text.index('\n\ndef git_blob_sha',start)
text=text[:start]+'SOURCE_BLOBS = '+json.dumps(expected_sources,indent=4)+text[end:]
start=text.index('    def test_vendored_execution_policy_matches_adk_704');end=text.index('\n    def test_policy_manifest_is_v2_only',start)
text=text[:start]+'''    def test_vendored_execution_policy_matches_adk_7031(self) -> None:
        directory = ROOT / "tools/codex_assets/execution_policy"
        self.assertEqual(set(SOURCE_BLOBS), {p.name for p in directory.glob("*.py")})
        for filename, expected in SOURCE_BLOBS.items():
            self.assertEqual(expected, git_blob_sha(directory / filename))
        provider = json.loads((ROOT / "manifests/provider-locks/agent-dev-kit.json").read_text())
        self.assertEqual("7.0.31", provider["version"])
        self.assertEqual("7367ef84787de75bb751940b32c9e80009660e47", provider["provider_commit"])
'''+text[end:]
write('tests/test_execution_policy_source_set.py',text.replace('self.assertEqual(3, manifest["schema_version"])','self.assertEqual(4, manifest["schema_version"])'))
update('README.md',lambda text:text.replace('- Canonical engine：`tools/codex_assets/execution_policy/engine.py`，行为基线绑定 ADK 7.0.4 exact source identity。','- Canonical policy：`tools/codex_assets/execution_policy/` 的 contracts / decision / reducer，绑定 ADK 7.0.31 exact source identity。'))
update('docs/execution-policy.md',lambda text:text.replace('ADK 7.0.4','ADK 7.0.31').replace('- exact engine：`tools/codex_assets/execution_policy/engine.py`','- exact decision：`tools/codex_assets/execution_policy/decision.py`\n- exact reducer：`tools/codex_assets/execution_policy/reducer.py`\n- exact public namespace：`tools/codex_assets/execution_policy/__init__.py`').replace('两份固定 engine/contract 源文件','四份固定 package/contracts/decision/reducer 源文件')+'''
## 7.0.31 来源迁移

manifest schema 由 3 升至 4：`engine.module` 指向 canonical package，
`behavior_baseline.source_blobs` 精确记录四份上游源文件；旧 engine.py 物理退役，
不提供 alias/facade，也不静默接受旧自定义配置。自定义 config 需按当前 manifest
结构迁移并重新验证，不能只改变版本数字。

本次四份上游文件逐字节复制，9 个 Agent 在该来源中正文与旧版相同但来源归属已
重新核验。既有 host-owned ManifestError/privacy adapter 保持不变，不冒充上游源码。
Policy v2、event/state v1、decision v2、intake v1 及日志位置不变；已有日志不重写。
基线生成的 19 个合成回放样本验证状态/决策指纹与失败语义，不能代替真实任务资格。
来源完整不等于成员已升级、权限已批准或运行时/产品已通过资格认证。
''')
update('docs/adk-source-upgrade.md',lambda text:text+'''
### Agent / Execution Policy 同源迁移（2026-09-24）

在完成上述 Skill 导入后，9 个既有 Agent 及执行策略更新至同一固定 ADK 7.0.31
来源。Agent 正文经核验没有变化；不是新增角色或提高能力数量。执行策略复制完整
canonical package/contracts/decision/reducer，移除旧 engine.py；调用方改用真实
owner 模块，Provider lock 与可选 L2 的当前 source binding 同步，历史 receipt 不改写。

安装目标与 Agent profile 保持原样，默认配置不新增多 Agent；主机的会话、权限与
知识提供方不变。配置 schema 4 的显式迁移及合成历史日志回放见 `execution-policy.md`。
上文各批次“仍固定7.0.4”只描述当时交付范围，不是当前运行资源的版本。
''')
expected = {'manifests/agents.json':'a452dcec4ec55d40502114405c51953603e18b43','manifests/execution_policy.json':'79f95f10791d2a0566a8e18e96587d555f73138f','manifests/provider-locks/agent-dev-kit.json':'46c5abe4f30cd07ffca3b7a0fd661b990dae1211','tools/codex_assets/execution_policy_adapter.py':'a88567237af3975e82349ef2a8f3fcc25689f209','scripts/validate-runtime-binding.py':'6e91f95890ecbea6e297424c2deb8ba9c80f2e88','scripts/validate-adk-agent-binding.py':'ab3c9cb9fc20ce6a3f5a0022e3340b312d180340','tests/test_governance.py':'8dbd08c1eae45a4ebbf424a664a2f52a50f2b52c','tests/test_execution_policy_source_set.py':'f3a7a0f92750e975179070307d1ebdcf8cf8623e'}
for path, expected_blob in expected.items():
    actual = blob((ROOT/path).read_bytes())
    assert actual == expected_blob, (path, actual, expected_blob)
print(json.dumps({'status':'prepared','source_commit':COMMIT,'agents':count,'replay_cases':len(cases),'validated_consumer_blobs':len(expected)},sort_keys=True))
