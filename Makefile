# ================================================================
# A3 Makefile — 质量门禁快捷命令
# 用法: make lint / make test / make bench / make check
# ================================================================
.PHONY: help install lint lint-fix typecheck test test-cov bench check clean

# 默认目标
help:
	@echo "A3 质量门禁命令:"
	@echo "  make install   - 安装所有依赖"
	@echo "  make lint      - ruff 检查（不修复）"
	@echo "  make lint-fix  - ruff 检查 + 自动修复"
	@echo "  make typecheck - mypy 类型检查"
	@echo "  make test      - 运行所有测试"
	@echo "  make test-cov  - 运行测试 + 覆盖率报告"
	@echo "  make bench     - 运行性能基准测试"
	@echo "  make check     - 完整质量门禁 (lint + typecheck + test)"
	@echo "  make clean     - 清理缓存与临时文件"

install:
	pip install -r requirements.txt --break-system-packages
	pre-commit install

lint:
	ruff check backend/

lint-fix:
	ruff check backend/ --fix
	ruff format backend/

typecheck:
	mypy backend/app/agents/base.py backend/app/agents/orchestrator.py backend/app/core/llm_client.py --config-file=pyproject.toml

typecheck-all:
	mypy backend/ --config-file=pyproject.toml

test:
	pytest tests/a/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=backend/app --cov-report=term-missing --cov-report=html

bench:
	pytest tests/a/benchmarks/ -v --benchmark-only

bench-save:
	pytest tests/a/benchmarks/ -v --benchmark-save=baseline

bench-compare:
	pytest tests/a/benchmarks/ -v --benchmark-compare=baseline

# 完整质量门禁（Phase 0 验收标准）
check: lint typecheck test
	@echo "=== 质量门禁全部通过 ==="

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".benchmarks" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage
