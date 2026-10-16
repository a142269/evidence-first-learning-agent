"""P0-1 配套实操示例 04 · CNN / CIFAR-10（小图分类）

对应章节：06.1 卷积神经网络 CNN
对应 KP   ：cnn
Bloom 关注：Apply
运行方式 ：python 04_cnn_cifar10.py
依赖     ：PyTorch
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
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
    ])

    train_ds = datasets.CIFAR10("data/.tmp", train=True, download=True, transform=transform)
    test_ds = datasets.CIFAR10("data/.tmp", train=False, download=True, transform=transform)
    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False, num_workers=0)

    class SmallCNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv1 = nn.Conv2d(3, 16, 3, padding=1)
            self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
            self.fc = nn.Linear(32 * 8 * 8, 10)
            self.pool = nn.MaxPool2d(2, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
            x = self.pool(F.relu(self.conv1(x)))
            x = self.pool(F.relu(self.conv2(x)))
            x = x.view(x.size(0), -1)
            return self.fc(x)

    model = SmallCNN().to(device)
    optim = torch.optim.Adam(model.parameters(), lr=1e-3)

    model.train()
    losses = []
    for batch_idx, (x, y) in enumerate(train_loader):
        if batch_idx >= 30:  # 教学示例：30 步跑出趋势
            break
        x, y = x.to(device), y.to(device)
        optim.zero_grad()
        loss = F.cross_entropy(model(x), y)
        loss.backward()
        optim.step()
        losses.append(loss.item())

    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for x, y in test_loader:
            x, y = x.to(device), y.to(device)
            correct += (model(x).argmax(1) == y).sum().item()
            total += y.size(0)

    acc = correct / total
    print(f"[CNN-CIFAR10] last loss = {losses[-1]:.4f}  test acc = {acc:.3f}")

    # 30 步 + toy CNN 即可击败随机（10 类）
    assert acc > 0.2, f"acc too low: {acc:.3f}"
    print("[OK] CNN-CIFAR10 demo passed")


if __name__ == "__main__":
    main()
