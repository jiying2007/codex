# session-wrap 许可证遗漏恢复

问题：41499025e9f8b2d3f2357dc507bf2bf9463b6af3升级4.0.0到4.0.1时删除旧目录LICENSE，但没有复制到新目录。历史4.0.0 LICENSE blob为92e9a1f563eff8d239932bf8bfe1e9328299cec3，SHA256为44ba154a1fc0ead85f111db232a1839b15ceea0cea0941a725a87846dbf80c97。

仅恢复同一技能的原始MIT许可证字节，保留原版权声明，不从路径、Git身份或邻近技能推断授权。SKILL.md、版本、manifest来源及用户配置保持不变。这是补回遗漏的随附文件；不是技能行为迭代，因此不创建新版本目录或新增授权。

验收：新文件与历史Git blob字节完全一致；check-skills无LICENSE告警，build/doctor通过；差异仅LICENSE、本文和生成lock。已授权提交、条件合并和完整source-to-live，用户dirty不纳入提交。最终验证记录source外，避免复验后源快照漂移。
