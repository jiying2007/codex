# adk-interface-contract-design — 补充参考资料

此参考文件只提供可选背景、示例和检查提示；当前能力流程、权限、回退与放行结论以 `../SKILL.md`、Manifest 及运行时门禁为准。示例命令不得被解释为写权限授权。

## Commands
```bash
# 接口定义扫描
rg -n "interface|api|contract|schema" <module_path>
rg -n "typedef.*\(" include/<module>/*.h

# 错误码一致性检查
rg -n "= -[0-9]+" include/<module>/errors.h | sort -t= -k2 -n

# 版本信息检查
rg -n "VERSION|version|COMPAT" include/<module>/

# 废弃接口扫描
rg -n "TODO.*compat|deprecated|DEPRECATED" <module_path>

# 契约测试
gcc -I include/ -Wall -Werror -o contract_test tests/contract.c && ./contract_test

# 结构体对齐检查（嵌入式关键）
pahole --class_name=iface_msg_t <module>.o

# 字节序验证
python3 -c "import struct; print(struct.pack('<I', 0xCAFEBABE).hex())"
```
