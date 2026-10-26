# Exploratory Requirements Brief

用于需求宽泛、用户只给方向、PRD 过长或验收口径不清的开场阶段。目标是先发散，再拷问边界，最后压缩成可验证工程条目。

## 流程

1. 不写代码、不改文件，先给出 2-4 个可行方向。
2. 对每个方向说明收益、成本、风险和适用前提。
3. 追问目标、非目标、用户、术语、边界、验收和验证方式。
4. 将长描述压缩为 3-7 条验收标准。
5. 若仍缺关键信息，输出阻塞问题；若已足够清晰，转入 `adk-task-breakdown`。

## 输出

```md
- Candidate Directions:
- Boundary Questions:
- Shared Terms:
- Acceptance Criteria:
- Blocking Questions:
- Next Skill:
```

## 边界

- 不复制外部 skill 文案或安装外部运行态。
- 不把共享语言写入长期文件，除非用户明确要求或已有项目级术语治理入口。
- 发散阶段不能替代后续实现前的验证计划。
