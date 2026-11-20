# Memory Candidate

id:
stable_identity_key:
protected_entry_class:
scope:
type:
risk:
confidence:
status:
created_at:
last_verified:
next_review_by:
source:
evidence:
old_memory:
new_facts:
event: ADD | UPDATE | DELETE | NONE
content:
reusable_when:
promotion_score:
promotion_action: review | conflict_review | blocked | auto_promote_candidate | promoted | discard
lifecycle_state: research | engineering | archive
requested_promotion: none | engineering | archive
safety_filter:
write_route:
requires_user_confirmation:
supersedes:
conflicts_with:
duplicate_key_status:
contradiction_status: none | duplicate | stale | conflicts_with | supersedes | missing_evidence | conflict_review
raw_evidence:
owner_review:
rollback_path:
owner:
notes:

## Admission Check

- 下次同类任务会用到:
- 不是完整聊天记录或一次性草稿:
- 不包含密钥、凭据、隐私原文:
- 风险分级已说明:
- 事件类型为 ADD / UPDATE / DELETE / NONE:
- stable_identity_key 已记录；纠正、决策、进度和执行日志必须带 protected_entry_class:
- 旧记忆、新事实和原始证据入口已记录:
- active 候选至少有一个 evidence 或 raw_evidence 路径:
- 请求晋升到 engineering / archive 的候选已记录 raw_evidence、owner_review 和 rollback_path:
- duplicate_key_status 已标记；同 key 冲突不得自动晋升:
- contradiction_status 已标记；冲突项进入 conflict_review:
- 评分依据、作用域和跨会话重复证据已记录:
- `[REDACTED]`、疑似密钥、token、cookie、连接串或原始敏感日志已阻断:
- `conflict_review` 和高风险候选未自动晋升:
- 高风险候选已等待人工确认:
- 过期或复验条件已记录:
