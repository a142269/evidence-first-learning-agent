"""P0-1 配套实操示例 01 · 线性回归 / scikit-learn

对应章节：04 机器学习基础 / 05 监督学习算法
对应 KP   ：linear_regression / ml_basics
Bloom 关注：Apply
运行方式 ：python 01_linear_regression.py
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def make_toy_dataset(n: int = 200, noise: float = 0.5, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """构造可解释回归数据：y = 3x + 2 + ε"""
    rng = np.random.default_rng(seed)
    X = rng.uniform(-3, 3, size=(n, 1))
    y = 3 * X[:, 0] + 2 + rng.normal(0, noise, size=n)
    return X, y


def main() -> None:
    X, y = make_toy_dataset()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"[LinearRegression] coeff={model.coef_[0]:.3f} (expected ~3)  intercept={model.intercept_:.3f} (expected ~2)")
    print(f"[LinearRegression] MSE={mse:.3f}  R^2={r2:.3f}")

    # 验收断言：系数与截距都接近真值，R^2 接近 1
    assert abs(model.coef_[0] - 3.0) < 0.1, "coefficient drift"
    assert abs(model.intercept_ - 2.0) < 0.2, "intercept drift"
    assert r2 > 0.9, f"r2 too low: {r2:.3f}"
    print("[OK] LinearRegression demo passed")


if __name__ == "__main__":
    main()
