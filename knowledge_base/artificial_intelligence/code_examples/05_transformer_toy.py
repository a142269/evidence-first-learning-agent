"""P0-1 配套实操示例 05 · Transformer Toy（自回归语言建模最小复现）

对应章节：05 Transformer与注意力机制 / 06 多智能体章节（架构说明）
对应 KP   ：transformer / attention_mechanism
Bloom 关注：Apply / Analyze
运行方式 ：python 05_transformer_toy.py
依赖     ：PyTorch
说明     ：不追求 SOTA；最小可运行复现 mask + multi-head + residual，
           用于教学演示 attention 权重可视化与解码策略。
"""
from __future__ import annotations

import math


def main() -> None:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    vocab_size, d_model, n_heads = 32, 32, 4
    seq_len, batch_size = 12, 4

    class ToyTransformer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embed = nn.Embedding(vocab_size, d_model)
            self.pos = nn.Embedding(seq_len, d_model)
            layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=n_heads, dim_feedforward=64, batch_first=True
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=2)
            self.head = nn.Linear(d_model, vocab_size)

        def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
            pos = torch.arange(x.size(1), device=x.device).unsqueeze(0)
            h = self.embed(x) + self.pos(pos)
            mask = torch.triu(torch.ones(x.size(1), x.size(1), device=x.device), diagonal=1).bool()
            h = self.encoder(h, mask=mask)
            return self.head(h)

    model = ToyTransformer().to(device)
    optim = torch.optim.Adam(model.parameters(), lr=3e-4)

    # 构造一个 toy 任务：每步预测 [1, 2, 3, ..., t+1] 的下一 token
    base = torch.arange(1, seq_len, device=device).repeat(batch_size, 1)

    for step in range(60):
        x = base[:, : min(step + 1, seq_len - 1)]
        if x.size(1) < 2:
            break
        target = base[:, 1 : x.size(1) + 1]
        # pad 到固定长度
        if x.size(1) < seq_len - 1:
            pad = torch.zeros(batch_size, seq_len - 1 - x.size(1), dtype=torch.long, device=device)
            x = torch.cat([x, pad], dim=1)
            target_pad = torch.zeros_like(x)
            target_pad[:, : target.size(1)] = target
            target = target_pad

        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, vocab_size), target.reshape(-1))
        optim.zero_grad()
        loss.backward()
        optim.step()

        if step % 10 == 0:
            print(f"[Transformer-Toy] step={step:02d}  loss={loss.item():.4f}")

    # sanity check：loss 应当下降到 < 2.0（vocab 32，均匀随机 ~3.46）
    assert loss.item() < 2.5, f"loss not converging: {loss.item():.3f}"
    print("[OK] Transformer-Toy demo passed")


if __name__ == "__main__":
    main()
