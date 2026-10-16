"""P0-1 配套实操示例 03 · MLP / MNIST（神经网络基础）

对应章节：06 神经网络与深度学习
对应 KP   ：neural_networks / backpropagation
Bloom 关注：Apply / Analyze
运行方式 ：python 03_mlp_mnist.py
依赖     ：PyTorch（requirements.txt 已列）
"""
from __future__ import annotations


def main() -> None:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms

    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])

    train_ds = datasets.MNIST("data/.tmp", train=True, download=True, transform=transform)
    test_ds = datasets.MNIST("data/.tmp", train=False, download=True, transform=transform)
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False)

    class MLP(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.fc1 = nn.Linear(28 * 28, 256)
            self.fc2 = nn.Linear(256, 10)
            self.drop = nn.Dropout(0.2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
            x = x.view(x.size(0), -1)
            x = F.relu(self.fc1(x))
            x = self.drop(x)
            return self.fc2(x)

    model = MLP().to(device)
    optim = torch.optim.Adam(model.parameters(), lr=1e-3)

    # 教学目的：限制 1 epoch 即可，演示 loss 下降
    model.train()
    losses = []
    for batch_idx, (x, y) in enumerate(train_loader):
        if batch_idx >= 50:  # 50 步即可看到下降趋势（教学示例不需训完）
            break
        x, y = x.to(device), y.to(device)
        optim.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits, y)
        loss.backward()
        optim.step()
        losses.append(loss.item())

    # 评估
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for x, y in test_loader:
            x, y = x.to(device), y.to(device)
            pred = model(x).argmax(dim=1)
            correct += (pred == y).sum().item()
            total += y.size(0)
    acc = correct / total
    print(f"[MLP-MNIST] last loss = {losses[-1]:.4f}  test acc = {acc:.3f}")

    # 断言：50 步即可学到一个比随机好的精度
    assert acc > 0.7, f"acc too low for 50 steps: {acc:.3f}"
    print("[OK] MLP-MNIST demo passed")


if __name__ == "__main__":
    main()
