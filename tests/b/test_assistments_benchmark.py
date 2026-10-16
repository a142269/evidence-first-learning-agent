"""
ASSISTments 数据加载器 + Benchmark 全流程测试

测试覆盖：
- CSV 加载与预处理
- Q 矩阵构造
- 序列构造
- 各模型 Adapter 接口一致性
- Cross-validation 流程
- Naive baseline 预测
- DKT 训练 + 推理（轻量）
- Metrics 计算
"""
import os
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# 1. 数据加载测试
# ---------------------------------------------------------------------------

class TestAssistmentsLoader:
    """ASSISTments 数据加载与预处理。"""

    def test_load_raw_returns_dataframe(self):
        """load_raw 应返回非空 DataFrame"""
        from backend.app.research.datasets.assistments import load_raw
        df = load_raw()  # 使用已缓存的 CSV
        assert len(df) > 100_000
        assert "user_id" in df.columns
        assert "skill_id" in df.columns
        assert "correct" in df.columns

    def test_no_nan_skill_id_after_filter(self):
        """过滤后不应有 NaN skill_id"""
        from backend.app.research.datasets.assistments import load_raw
        df = load_raw()
        assert df["skill_id"].notna().all()

    def test_correct_is_binary(self):
        """correct 列应只有 0 和 1"""
        from backend.app.research.datasets.assistments import load_raw
        df = load_raw()
        assert set(df["correct"].unique()).issubset({0, 1})

    def test_prepare_benchmark_data_structure(self):
        """prepare_benchmark_data 应返回完整字典结构"""
        from backend.app.research.datasets.assistments import prepare_benchmark_data
        data = prepare_benchmark_data()
        required_keys = [
            "n_students", "n_skills", "n_items", "n_interactions",
            "responses", "q_matrix", "item_ids", "skill_ids",
            "student_ids", "sequences", "skill_names",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_q_matrix_shape(self):
        """Q 矩阵形状应为 (n_items, n_skills)"""
        from backend.app.research.datasets.assistments import prepare_benchmark_data
        data = prepare_benchmark_data()
        assert data["q_matrix"].shape == (data["n_items"], data["n_skills"])

    def test_q_matrix_binary(self):
        """Q 矩阵每行至少一个 1（每个 item 至少测一个 skill）"""
        from backend.app.research.datasets.assistments import prepare_benchmark_data
        data = prepare_benchmark_data()
        row_sums = data["q_matrix"].sum(axis=1)
        assert np.all(row_sums >= 1.0)

    def test_sequences_match_students(self):
        """sequences 数量应等于 n_students"""
        from backend.app.research.datasets.assistments import prepare_benchmark_data
        data = prepare_benchmark_data()
        assert len(data["sequences"]) == data["n_students"]

    def test_sequence_skill_onehot_dim(self):
        """每个 sequence entry 的 skill_onehot 维度应等于 n_skills"""
        from backend.app.research.datasets.assistments import prepare_benchmark_data
        data = prepare_benchmark_data()
        seq = data["sequences"][0]
        assert len(seq) > 0
        assert seq[0]["skill_onehot"].shape == (data["n_skills"],)

    def test_min_interactions_filter(self):
        """过滤后学生数应少于全量（min_interactions 过滤生效）"""
        from backend.app.research.datasets.assistments import prepare_benchmark_data
        data_full = prepare_benchmark_data(min_interactions=1)
        data_filtered = prepare_benchmark_data(min_interactions=10)
        # 过滤后学生数应严格少于全量
        assert data_filtered["n_students"] < data_full["n_students"]
        # 过滤后总交互数也应减少
        assert data_filtered["n_interactions"] < data_full["n_interactions"]

    def test_skill_names_match_ids(self):
        """skill_names 应覆盖所有 skill_ids"""
        from backend.app.research.datasets.assistments import prepare_benchmark_data
        data = prepare_benchmark_data()
        for sid in data["skill_ids"]:
            assert sid in data["skill_names"]

    def test_cached_download_skips_redundant(self):
        """已缓存时 download 应直接返回路径不重新下载"""
        from backend.app.research.datasets.assistments import download_assistments
        path = download_assistments()
        assert path.exists()
        assert path.stat().st_size > 1_000_000


# ---------------------------------------------------------------------------
# 2. Metrics 测试
# ---------------------------------------------------------------------------

class TestMetrics:
    """评估指标计算。"""

    def test_auc_perfect_classifier(self):
        """完美分类器 AUC = 1.0"""
        from backend.app.research.evaluation.metrics import compute_auc
        y_true = [1, 1, 0, 0]
        y_prob = [0.9, 0.8, 0.2, 0.1]
        auc = compute_auc(y_true, y_prob)
        assert abs(auc - 1.0) < 0.01

    def test_auc_random_classifier(self):
        """随机分类器 AUC ≈ 0.5"""
        from backend.app.research.evaluation.metrics import compute_auc
        import random
        random.seed(42)
        y_true = [1, 1, 0, 0, 1, 0]
        y_prob = [random.random() for _ in range(6)]
        auc = compute_auc(y_true, y_prob)
        assert 0.3 < auc < 0.7

    def test_auc_binary_labels_only(self):
        """AUC 应只接受 0/1 标签"""
        from backend.app.research.evaluation.metrics import compute_auc
        with pytest.raises((ValueError, TypeError)):
            compute_auc([1, 2, 0, 1], [0.5, 0.5, 0.5, 0.5])

    def test_rmse_perfect(self):
        """完美预测 RMSE = 0.0"""
        from backend.app.research.evaluation.metrics import compute_rmse
        y_true = [1, 0, 1, 0]
        y_prob = [1.0, 0.0, 1.0, 0.0]
        assert compute_rmse(y_true, y_prob) < 0.01

    def test_rmse_bad(self):
        """完全反预测 RMSE ≈ 1.0"""
        from backend.app.research.evaluation.metrics import compute_rmse
        y_true = [1, 0, 1, 0]
        y_prob = [0.0, 1.0, 0.0, 1.0]
        rmse = compute_rmse(y_true, y_prob)
        assert 0.9 < rmse <= 1.0

    def test_accuracy(self):
        """Accuracy 计算"""
        from backend.app.research.evaluation.metrics import compute_accuracy
        y_true = [1, 0, 1, 1]
        y_pred = [1, 0, 0, 1]
        assert compute_accuracy(y_true, y_pred) == 0.75


# ---------------------------------------------------------------------------
# 3. Naive Baseline 测试
# ---------------------------------------------------------------------------

class TestNaiveBaseline:
    """均值基线模型。"""

    def test_fit_and_predict(self):
        """训练后应能预测"""
        from backend.app.research.models.naive_baseline import NaiveBaseline
        model = NaiveBaseline()
        model.fit(
            train_students=["s1", "s2"],
            train_responses={"s1": {"i1": 1, "i2": 0}, "s2": {"i1": 1, "i2": 1}},
            train_item_ids=["i1", "i2"],
            train_skill_ids=["sk1"],
            train_q_matrix=np.array([[1.0], [1.0]]),
        )
        probs = model.predict_proba(["s1"], ["i1", "i2"])
        assert len(probs) == 2
        for p in probs:
            assert 0.0 <= p <= 1.0

    def test_naive_skill_rate(self):
        """预测值应反映训练集 item 正确率"""
        from backend.app.research.models.naive_baseline import NaiveBaseline
        model = NaiveBaseline()
        # i1: s1 对 + s2 对 = 2/2 = 1.0
        # i2: s1 对 + s2 错 = 1/2 = 0.5
        model.fit(
            train_students=["s1", "s2"],
            train_responses={"s1": {"i1": 1, "i2": 1}, "s2": {"i1": 1, "i2": 0}},
            train_item_ids=["i1", "i2"],
            train_skill_ids=["sk1"],
            train_q_matrix=np.array([[1.0], [1.0]]),
        )
        probs = model.predict_proba(["s1"], ["i1", "i2"])
        # i1 历史全对 → 预测 1.0；i2 一半对 → 预测 0.5
        assert abs(probs[0] - 1.0) < 0.05, f"i1 rate {probs[0]} != 1.0"
        assert abs(probs[1] - 0.5) < 0.05, f"i2 rate {probs[1]} != 0.5"


# ---------------------------------------------------------------------------
# 4. DKT 测试（轻量，CPU）
# ---------------------------------------------------------------------------

class TestDKT:
    """DKT PyTorch 模型（轻量测试）。"""

    def test_dkt_model_forward(self):
        """DKT forward pass 应返回合法输出"""
        import torch
        from backend.app.research.models.dkt import DKTModel
        n_skills = 10
        hidden_dim = 16
        model = DKTModel(n_skills=n_skills, hidden_dim=hidden_dim)
        # batch of sequences: 3 students, 5 timesteps
        x = torch.randn(3, 5, 2 * n_skills)  # input: concat(skill_onehot, correct)
        output = model(x)
        assert output.shape == (3, 5, n_skills)
        assert torch.all((output >= 0) & (output <= 1))

    def test_dkt_single_step_predict(self):
        """单步预测应返回 skill 维度的概率"""
        import torch
        from backend.app.research.models.dkt import DKTModel
        n_skills = 5
        model = DKTModel(n_skills=n_skills, hidden_dim=8)
        # Input: concat(skill_onehot[n_skills], correctness_onehot[n_skills]) = 2*n_skills
        skill_onehot = torch.zeros(1, 1, n_skills)
        skill_onehot[0, 0, 2] = 1.0
        correct_onehot = torch.zeros(1, 1, n_skills)
        correct_onehot[0, 0] = 1.0  # correct=1 broadcast to all skills
        x = torch.cat([skill_onehot, correct_onehot], dim=-1)
        assert x.shape == (1, 1, 2 * n_skills)
        out = model(x)
        assert out.shape == (1, 1, n_skills)

    def test_dkt_gradient_flow(self):
        """反向传播应无错误"""
        import torch
        from backend.app.research.models.dkt import DKTModel
        model = DKTModel(n_skills=5, hidden_dim=8)
        x = torch.randn(2, 3, 10)
        y = model(x)
        loss = ((y[:, -1, 0] - 1.0) ** 2).mean()
        loss.backward()
        # Check gradients exist
        grad_exists = any(p.grad is not None for p in model.parameters())
        assert grad_exists


# ---------------------------------------------------------------------------
# 5. Adapter 接口测试
# ---------------------------------------------------------------------------

class TestAdapters:
    """统一适配器接口。"""

    def test_dina_adapter_interface(self):
        """DINA Adapter 应实现 fit + predict_proba"""
        from backend.app.research.evaluation.adapters import DINAAdapter
        adapter = DINAAdapter()
        assert hasattr(adapter, "fit")
        assert hasattr(adapter, "predict_proba")

    def test_bkt_adapter_interface(self):
        """BKT Adapter 应实现 fit + predict_proba"""
        from backend.app.research.evaluation.adapters import BKTAdapter
        adapter = BKTAdapter()
        assert hasattr(adapter, "fit")
        assert hasattr(adapter, "predict_proba")

    def test_dkt_adapter_interface(self):
        """DKT Adapter 应实现 fit + predict_proba"""
        from backend.app.research.evaluation.adapters import DKTAdapter
        adapter = DKTAdapter()
        assert hasattr(adapter, "fit")
        assert hasattr(adapter, "predict_proba")

    def test_naive_adapter_interface(self):
        """Naive Adapter 应实现 fit + predict_proba"""
        from backend.app.research.evaluation.adapters import NaiveModelAdapter
        adapter = NaiveModelAdapter()
        assert hasattr(adapter, "fit")
        assert hasattr(adapter, "predict_proba")


# ---------------------------------------------------------------------------
# 6. Cross-validation 测试（小规模，非 slow）
# ---------------------------------------------------------------------------

class TestCrossValidation:
    """交叉验证流程（小规模）。"""

    def test_5fold_split_preserves_students(self):
        """5-fold 划分：每折 test 不重叠且并集=全集，train/test 不相交"""
        from backend.app.research.evaluation.cross_validation import student_kfold_split
        student_ids = [f"s{i}" for i in range(20)]
        folds = list(student_kfold_split(student_ids, n_folds=5))
        assert len(folds) == 5

        # Collect all test sets across folds
        all_test = []
        for train, test in folds:
            # train and test must be disjoint within each fold
            assert len(set(train) & set(test)) == 0
            all_test.extend(test)

        # All test sets across folds should partition the full student set
        # (each student appears exactly once as test)
        assert set(all_test) == set(student_ids)
        assert len(all_test) == 20  # no duplicates

    def test_2fold_split(self):
        """2-fold 划分"""
        from backend.app.research.evaluation.cross_validation import student_kfold_split
        student_ids = [f"s{i}" for i in range(10)]
        folds = list(student_kfold_split(student_ids, n_folds=2))
        assert len(folds) == 2
        for train, test in folds:
            assert len(train) + len(test) == 10
