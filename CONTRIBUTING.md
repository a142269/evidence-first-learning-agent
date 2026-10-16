# Contributing

感谢你改进 Triple-U。提交前请保持变更范围清晰，并确保没有加入密钥、真实账号、供应商账单或运行时生成文件。

## 本地检查

```bash
ruff check --select=E9,F63,F7,F82 backend/app scripts tests
pytest tests/ --no-cov --benchmark-disable -q

cd frontend
npm ci
npm run build
```

## Pull Request

请在描述中写明：

1. 解决的问题和实现方式；
2. 已运行的验证命令；
3. 数据库迁移、兼容性或费用方面的影响；
4. UI 变更的截图。

如果变更会调用在线模型或 Embedding 服务，请使用独立预算编号和明确的硬上限。
