"""P0-1 配套实操示例 06 · 字符级 RNN/LSTM 文本生成最小复现

对应章节：18 RNN 与 LSTM
对应 KP   ：rnn / lstm
Bloom 关注：Apply / Analyze
运行方式 ：python 06_rnn_text.py
依赖     ：PyTorch
说明     ：用一个短小的内置中文 + 英文语料，演示 Embedding → LSTM → Linear
           的字符级语言建模，并在训练结束后从 seed 字符生成新文本。
           不追求 SOTA；目标 < 30 秒跑通、loss 可见下降、生成结果非全
           随机字符。整段脚本可作为课堂现场 demo。
"""
from __future__ import annotations

import random
from collections import Counter
from typing import List, Tuple


# ---------------------------------------------------------------------------
# 1. 语料：内置一段混合短文，覆盖中英文常见字符
# ---------------------------------------------------------------------------
CORPUS = (
    "床前明月光，疑是地上霜。\n"
    "举头望明月，低头思故乡。\n"
    "Deep learning is fun. RNN can remember short sequences.\n"
    "LSTM forgets less than vanilla RNN on long context.\n"
    "A3 学习系统让 AI 教学更高效。\n"
    "Knowledge is power, and learning is the key.\n"
    "学而不思则罔，思而不学则殆。\n"
    "Practice makes perfect, code makes sense.\n"
)


def build_vocab(text: str) -> Tuple[dict, dict]:
    """构造字符级 vocab；返回 {char: idx}, {idx: char}。"""
    chars = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    itos = {i: ch for ch, i in stoi.items()}
    return stoi, itos


def make_dataset(text: str, stoi: dict, seq_len: int = 20) -> Tuple["list", "list"]:
    """把语料切成定长输入 / 目标序列对（next-token 预测）。"""
    ids = [stoi[ch] for ch in text if ch in stoi]
    xs, ys = [], []
    for i in range(0, len(ids) - seq_len):
        xs.append(ids[i : i + seq_len])
        ys.append(ids[i + 1 : i + seq_len + 1])
    return xs, ys


# ---------------------------------------------------------------------------
# 2. 模型：Embedding → LSTM(128, 2 层) → Linear → softmax（logits）
# ---------------------------------------------------------------------------
def build_model(vocab_size: int, seq_len: int):
    """延迟导入 torch；只有真的跑 main() 时才依赖 PyTorch。"""
    import torch
    import torch.nn as nn

    class CharLSTM(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embed = nn.Embedding(vocab_size, 64)
            self.lstm = nn.LSTM(64, 128, num_layers=2, batch_first=True, dropout=0.1)
            self.head = nn.Linear(128, vocab_size)

        def forward(self, x, hidden=None):  # type: ignore[override]
            h = self.embed(x)
            out, hidden = self.lstm(h, hidden)
            logits = self.head(out)
            return logits, hidden

    return CharLSTM()


# ---------------------------------------------------------------------------
# 3. 训练 + 推理
# ---------------------------------------------------------------------------
def train_and_generate(seed_text: str = "床前", epochs: int = 200) -> str:
    import torch
    import torch.nn.functional as F

    torch.manual_seed(42)
    random.seed(42)

    stoi, itos = build_vocab(CORPUS)
    vocab_size = len(stoi)
    seq_len = 16

    xs, ys = make_dataset(CORPUS, stoi, seq_len=seq_len)
    assert len(xs) >= 8, "语料太短，无法构造有效训练样本"
    X = torch.tensor(xs, dtype=torch.long)
    Y = torch.tensor(ys, dtype=torch.long)

    model = build_model(vocab_size, seq_len)
    optim = torch.optim.Adam(model.parameters(), lr=5e-3)

    initial_loss = None
    for epoch in range(1, epochs + 1):
        # 小 batch = 全量（语料很小，batch 化收益不大）
        logits, _ = model(X)
        loss = F.cross_entropy(logits.reshape(-1, vocab_size), Y.reshape(-1))
        optim.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optim.step()
        if epoch == 1:
            initial_loss = loss.item()
        if epoch % 50 == 0 or epoch == 1:
            print(f"[RNN-text] epoch={epoch:03d}  loss={loss.item():.4f}")

    final_loss = loss.item()
    print(f"[RNN-text] initial_loss={initial_loss:.4f}  final_loss={final_loss:.4f}")

    # 简单 sanity check：loss 必须有可见下降（vocab 较小时下降门槛更宽松）
    assert final_loss < initial_loss * 0.95, (
        f"loss 未明显下降: {initial_loss:.3f} -> {final_loss:.3f}"
    )

    # 4. 推理：从 seed 生成 80 个字符
    model.eval()
    generated: List[str] = list(seed_text)
    with torch.no_grad():
        ids = [stoi.get(ch, 0) for ch in seed_text]
        # warm-up：把 seed 整个喂一遍
        input_seq = torch.tensor([ids[-seq_len:]], dtype=torch.long)
        _, hidden = model(input_seq)
        for _ in range(80):
            logits, hidden = model(input_seq, hidden)
            probs = F.softmax(logits[0, -1], dim=-1)
            # 轻微温度 + 采样，避免完全 deterministic
            probs = probs ** 0.8
            probs = probs / probs.sum()
            next_id = int(torch.multinomial(probs, 1).item())
            generated.append(itos[next_id])
            input_seq = torch.cat([input_seq[:, 1:], torch.tensor([[next_id]])], dim=1)

    text = "".join(generated)
    print(f"[RNN-text] generated: {text!r}")
    # sanity check：生成内容应当至少有 1 个训练集中出现过的字符
    common = set(CORPUS) & set(text[len(seed_text):])
    assert common, "生成结果与训练语料完全没有交集，请检查推理流程"
    return text


# ---------------------------------------------------------------------------
# 5. 入口
# ---------------------------------------------------------------------------
def main() -> None:
    # doctest 风格的轻量自检：保证 Counter 仍能数清楚生成结果里的字符
    cnt = Counter(CORPUS)
    assert cnt.most_common(1)[0][1] >= 2, "语料中无重复字符，模型无法学到统计规律"

    train_and_generate(seed_text="Deep ", epochs=200)
    train_and_generate(seed_text="学而", epochs=150)

    print("[OK] RNN text demo passed")


if __name__ == "__main__":
    main()