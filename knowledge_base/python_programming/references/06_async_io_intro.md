---
title: "asyncio 异步编程入门"
authors: [Python Documentation Team, Yury Selivanov]
year: 2024
url: https://docs.python.org/3/library/asyncio.html
kp_refs: [PY_022, PY_023]
summary_zh: Python 3.4+ asyncio 异步编程指南,理解 async/await 与并发 I/O。
---

# asyncio 异步编程入门

> **面向读者**:已学完 §15 迭代器/生成器,想了解 Python 异步编程的同学

## 摘要

`asyncio` 是 Python 3.4 引入的标准库,3.5 加入 `async`/`await` 语法,3.7 完善 API。核心是"单线程 + 事件循环"实现高并发 I/O,适合 Web 爬虫、API 网关、聊天服务器等 I/O 密集场景。

## 为什么需要 asyncio

传统并发方式的问题:
- **多线程**:GIL 限制 CPU 密集型,线程切换有开销
- **多进程**:内存开销大,通信复杂
- **asyncio**:单线程,协程切换极快,适合大量 I/O 等待

## 核心概念

### 1. coroutine 协程

```python
import asyncio

async def fetch(url):
    print(f"fetching {url}")
    await asyncio.sleep(1)  # 模拟 I/O 等待
    print(f"done {url}")
    return url

# 串行:3 秒
async def main_serial():
    await fetch("a")
    await fetch("b")
    await fetch("c")

# 并发:1 秒
async def main_concurrent():
    await asyncio.gather(fetch("a"), fetch("b"), fetch("c"))

asyncio.run(main_concurrent())
```

### 2. await / async

- `async def`:定义协程函数
- `await`:等待可等待对象(coroutine / Future / Task)
- 只能在 `async def` 内部 `await`

### 3. Task 任务

```python
async def main():
    task1 = asyncio.create_task(fetch("a"))
    task2 = asyncio.create_task(fetch("b"))
    result = await task1
```

### 4. gather 与 wait

```python
# gather:等待所有任务
results = await asyncio.gather(task1, task2)

# gather + return_exceptions
results = await asyncio.gather(task1, task2, return_exceptions=True)

# wait:更细粒度
done, pending = await asyncio.wait([t1, t2], timeout=2)
```

## 实战:并发抓取

```python
import aiohttp
import asyncio

async def fetch_url(session, url):
    async with session.get(url) as resp:
        return await resp.text()

async def main():
    urls = ["https://a.com", "https://b.com", "https://c.com"]
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
    for url, html in zip(urls, results):
        print(f"{url}: {len(html)} bytes")

asyncio.run(main())
```

## 同步 → 异步改造

```python
import asyncio
import time

# 同步
def sync_main():
    time.sleep(1)
    time.sleep(1)
    time.sleep(1)

# 异步等价
async def async_main():
    await asyncio.sleep(1)
    await asyncio.sleep(1)
    await asyncio.sleep(1)

# 性能:同步 3 秒,异步 1 秒
```

**注意**:`time.sleep(1)` 阻塞整个线程,必须用 `await asyncio.sleep(1)`。

## 常见误区

- **误区 1**:用 `requests` 在协程中——`requests` 同步会阻塞事件循环,要用 `aiohttp` / `httpx`
- **误区 2**:`asyncio.run()` 调用多次——每次 run 创建新事件循环,可能冲突
- **误区 3**:CPU 密集型用 asyncio——asyncio 不解决 GIL,该用 `multiprocessing`
- **误区 4**:`asyncio.create_task()` 在 `__init__` 中——必须从协程内调用

## 与多线程的对比

| 维度 | asyncio | threading |
|------|---------|-----------|
| 切换开销 | 极低(协程) | 中等(线程) |
| 并行 CPU | 否(GIL) | 否(GIL) |
| 并发 I/O | ✅ 极佳 | ✅ 可用 |
| 代码复杂度 | 需理解事件循环 | 简单 |
| 适用 | 高并发 I/O | I/O 为主,简单并行 |
| 生态 | aiohttp / FastAPI / asyncpg | 全库通用 |

## 推荐学习路径

1. **理解生成器 → 协程**:yield → yield from → await
2. **基本用法**:async/await + gather
3. **异步 I/O**:aiohttp / asyncpg
4. **异步框架**:FastAPI / Starlette
5. **底层原理**:事件循环源码

## 链接

- 官方文档:https://docs.python.org/3/library/asyncio.html
- Real Python 教程:https://realpython.com/async-io-python/
- PEP 492(async/await):https://peps.python.org/pep-0492/
- FastAPI:https://fastapi.tiangolo.com/
