# LLM Client + PromptCache 字段契约

> 模块: [backend/app/services/prompt_cache.py](../../backend/app/services/prompt_cache.py)
> 6/24 起新增能力 (T2.10)
> 受众: B 后端（attribution / variant / KT 等模块如要接入缓存，照此文档对接）

---

## 1. 何时该接入 PromptCache

**应该接入**：
- 同一 prompt 在不同会话里会被重复打（资源生成模板 / Bloom 自动标注 / attribution 8 分类）
- 演示链路里反复触达的 prompt（demo_journey / verify_demo_assets）
- 重试代价高的 LLM 调用（Spark websocket 重连慢）

**不应接入**：
- 实时对话流（每条 message 都不同，cache 永远 miss，徒增延迟）
- 个性化输出（prompt 含 user_id 等高基数字段，命中率近 0）

---

## 2. 三种用法

### 2.1 直接用 PromptCache 做手动缓存

```python
from backend.app.services.prompt_cache import PromptCache

cache = PromptCache()  # 默认 data/cache/prompt_cache.db, TTL 7 天

key = PromptCache.make_key(
    messages=[{"role": "user", "content": "解释 CNN"}],
    temperature=0.7,
    max_tokens=512,
    model="spark",  # 区分不同模型的同 prompt
)

if (cached := cache.get(key)) is not None:
    return cached
response = llm.chat(messages, temperature=0.7, max_tokens=512)
cache.set(key, response, tag="explain_kp")  # tag 用于事后统计/分类清理
```

### 2.2 用 CachedLLMClient 装饰已有 LLMClient（推荐）

```python
from backend.app.core.llm_client import LLMClient
from backend.app.services.prompt_cache import CachedLLMClient

raw = LLMClient()
cached = CachedLLMClient(inner=raw, model_name="spark")

# 调用方式与原 LLMClient.chat 完全一致
out = cached.chat(messages, temperature=0.2, max_tokens=512)
```

**好处**：业务无需关心 cache key 生成，包装层全部托管。

### 2.3 chat_json — JSON 输出 + 语义重试

针对 attribution / variant 这种要求结构化 JSON 输出的场景：

```python
result = cached.chat_json(
    messages=[
        {"role": "system", "content": "你是错题归因专家，只输出 JSON"},
        {"role": "user", "content": prompt},
    ],
    temperature=0.2,
    max_retries=2,  # 总共最多 3 次 (1 首次 + 2 重试)
)
# result 是已解析的 dict，无需再 json.loads
```

**语义重试机制**：
1. 首次返回非法 JSON → 在 messages 末追加 `{"role": "user", "content": "上一条无法解析为 JSON。请仅返回严格合法 JSON ..."}` 重试
2. 重试期间也走 cache（不同 messages 不同 key）
3. 重试 ≥ `max_retries` 仍失败 → 抛 `ValueError`

**容忍的非严格 JSON**：
- 裸 JSON: `{"a": 1}`
- `\`\`\`json ... \`\`\`` 围栏
- 含前后文字: `好的，结果如下:\n\n{"a": 1}\n以上`

---

## 3. 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `PROMPT_CACHE_ENABLED` | `1` | 设 `0` 时 `CachedLLMClient` 全部直通下游（保留语义重试） |
| `A3_OFFLINE_DEMO` | unset | （建议）离线演示时同步打开，与 cache 协同减少 LLM 调用 |

---

## 4. CLI 工具

```bash
# 看命中率
python -m scripts.prompt_cache_stats

# JSON 输出（CI 或脚本里用）
python -m scripts.prompt_cache_stats --json

# 清空缓存（危险，不可恢复）
python -m scripts.prompt_cache_stats --clear
```

输出示例：

```
============================================================
 PromptCache Stats
============================================================
  DB             : data\cache\prompt_cache.db
  Total entries  : 142
  Total hits     : 367
  Hit rate       : 72.1%  (calls = 509)
  Oldest entry   : 6.2d ago
  Newest entry   : 3.1m ago
============================================================
```

---

## 5. 测试约定

**单元测试**：使用 `PromptCache(db_path=":memory:")`，避免磁盘 IO 让测试变慢/不稳。

```python
import pytest
from backend.app.services.prompt_cache import PromptCache

@pytest.fixture
def memory_cache() -> PromptCache:
    return PromptCache(db_path=":memory:")
```

**已有测试覆盖**：[tests/a/test_prompt_cache.py](../../tests/a/test_prompt_cache.py) 18 用例（key 稳定性 / 命中 / TTL / 语义重试 / 并发安全 / lenient JSON 解析 / clear & stats）

---

## 6. 集成 Roadmap（建议）

| 阶段 | 接入模块 | 优势 |
|------|---------|------|
| W1 (6/24-30) | A: 演示主链路 demo_journey / verify_demo_assets | 离线 demo 速度 ×3 |
| W1 (6/24-30) | B: attribution_engine `_llm_classify` | 同一题反复归因走 cache |
| W2 (7/01-07) | A: variant_generator | 同 KP/Bloom 的变式题模板复用 |
| W2 (7/01-07) | B: bloom_relabel 自动标注脚本 | 重跑 200 题不再耗 200 次 LLM |
| W3 (7/08-14) | A: CoVDemoService / DebateModerator | 现场配额超走 cache |

---

## 7. 注意事项与红线

- **Cache key 含 temperature**：高温度（temp>0.5）的输出本身就该有多样性，强烈不建议接入 cache
- **不要 cache 含 PII 的 prompt**：当前实现存原文，含个人信息的 prompt 不应进 cache
- **TTL 不要小于 1h**：SQLite 频繁删除会变慢；要短 TTL 请走内存 dict
- **跨进程共享**：默认 DB 路径在 `data/cache/`，多进程同时写需各自加 `threading.Lock`（已内置）
- **clear 不可恢复**：CLI `--clear` 没有二次确认，CI 里务必带 `--db /tmp/test.db` 隔离
