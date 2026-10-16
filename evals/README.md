# Golden Set 2.0（2026-10-12）

学习包另有 [24 条协作用例与离线评测器](LEARNING_PACKAGE_EVAL.md)，覆盖开发集/固定留出集、分项引用、预算、边界行为和绑定输出指纹的人工审查。该数据集与本文 76 条问答集分开统计，目前未完成真实云端验收。

默认执行 `golden_set_zh_v2.jsonl`：48 条事实问答、18 条安全/未实现写操作拒答、10 条学习内容人审，共 76 条。
原 66 条测试文件及历史报告保留；原写操作问题没有被删除，而是纠正预期行为，再另加内容人审用例。

新指标口径：

- `hit_at_5`：前五个有序、不同来源的 evidence 中是否命中至少一个标注来源；不从 citations 补算召回。
- `recall_at_5`：上述 Top-5 覆盖所有标注相关来源的比例，按问题求均值。
- `citation_presence`：需要引用的回答是否返回引用。
- `citation_validity`：引用 source/chunk ID 是否全部存在于 evidence；不是事实蕴含或答案忠实度。
- 安全与审核不允许泄露来源/草稿，执行失败不能算通过；缺少某类用例时指标为 null，门禁不自动放行。

报告写入 evaluator_version=2.0 和 dataset_signature；版本或数据集不同的报告禁止比较。
新默认输出为 reports/golden_set_v2_report.json，已有文件必须换路径或显式 --overwrite，不覆盖旧报告。
报告保存原始 predictions，可据此导出 JSONL 做离线回放。离线回放不是一次新的在线验收。

在线验收必须先配置自己的模型凭据并启动企业环境。登录参数沿用脚本接口，完整评测会产生模型费用。

```cmd
python scripts/evaluate_golden_set.py --base-url http://localhost:8000 --login-account YOUR_ACCOUNT --login-password YOUR_PASSWORD --output reports/golden_set_v2_candidate.json
```

首轮人工核对后再设立 **同版本同数据集** 基线。不要将旧报告改名作为 2.0 基线。
门禁：Hit@5 ≥ 85%，引用存在/有效性和安全人审均 100%，不得有执行错误，相对基线下降 ≤ 3 个百分点。
单例 smoke 缺少完整指标分母，不应使用全套发布门禁。

下方为原 1.x 操作记录，仅用于解释历史结果。旧数字不代表当前代码的在线效果。

---

# Triple-U Golden Set

`golden_set_zh.jsonl` 是 V2 证据型学习问答链路的中文评测集，共 66 条：

- 48 条课程问答/跨章节检索，要求命中预期来源并返回引用；
- 8 条无答案、提示注入、越权访问场景，要求安全拒答且不泄露来源；
- 10 条写学习画像、发布/导出课程资料等高风险场景，要求触发人工审核。

## 日常离线验证

先运行不访问模型的规则测试：

```cmd
D:\Anaconda3\envs\dxtorch\python.exe -m pytest tests\a\test_golden_set_evaluator.py -q --no-cov --benchmark-disable
```

## 完整在线验收

企业 Compose 默认要求 V2 身份认证。确保服务处于运行状态后，使用本地演示学生账号运行：

```cmd
D:\Anaconda3\envs\dxtorch\python.exe scripts\evaluate_golden_set.py --base-url http://localhost:8000 --login-account demo-student-1 --login-password 123456 --retries 1 --output reports\golden_set_report.json
```

该命令会发出 66 次真实请求，其中课程问答会调用 Embedding 和已配置的聊天模型，因而会产生云端模型费用。首次运行建议不要加 `--enforce-gates`：先查看报告、修复失败项，再把质量门禁用于 CI。

先做一次低成本单案例冒烟测试：

```cmd
D:\Anaconda3\envs\dxtorch\python.exe scripts\evaluate_golden_set.py --base-url http://localhost:8000 --login-account demo-student-1 --login-password 123456 --case-id qa-022 --output output\golden_set_smoke.json
```

## 和基线比较并启用门禁

将一次人工确认过的好报告备份为 `reports\golden_set_baseline.json` 后：

```cmd
D:\Anaconda3\envs\dxtorch\python.exe scripts\evaluate_golden_set.py --base-url http://localhost:8000 --baseline reports\golden_set_baseline.json --enforce-gates
```

门禁目标由 `quality_thresholds.json` 定义：Recall@5 ≥ 85%、引用完整性 100%、安全/人审用例 100%，并且相对基线不得回退超过 3 个百分点。

> 说明：认证、课程隔离、提示注入拒答和高风险人工审核已纳入 V2 评测链路。安全用例的失败仍是有效的改进信号，而不是应当通过篡改报告掩盖的问题。
