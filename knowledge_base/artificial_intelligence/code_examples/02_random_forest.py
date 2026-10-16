"""P0-1 配套实操示例 02 · 随机森林分类 / 决策树集成

对应章节：05.2 决策树与集成学习 / 15 决策树
对应 KP   ：decision_trees
Bloom 关注：Apply / Analyze
运行方式 ：python 02_random_forest.py
"""
from __future__ import annotations

from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


def main() -> None:
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.3, random_state=42, stratify=iris.target
    )

    clf = RandomForestClassifier(n_estimators=120, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    print(f"[RandomForest] test accuracy = {acc:.3f}")

    # 特征重要性 Top-3（教学要点：RF 可解释性）
    importances = sorted(
        zip(iris.feature_names, clf.feature_importances_), key=lambda x: -x[1]
    )[:3]
    print("[RandomForest] top-3 feature importances:")
    for fname, imp in importances:
        print(f"  {fname:<20s} {imp:.3f}")

    assert acc > 0.9, f"accuracy too low: {acc:.3f}"
    print("[OK] RandomForest demo passed")


if __name__ == "__main__":
    main()
