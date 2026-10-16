"""验证脚本：模块导入 + Spark 配置 + RAG + Agent 注册表"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def check_imports():
    modules = [
        "backend.app.core.config",
        "backend.app.core.llm_client",
        "backend.app.agents.base",
        "backend.app.agents.orchestrator",
        "backend.app.agents",
        "backend.app.services.safety.content_filter",
        "backend.app.services.realtime_state_service",
        "backend.app.services.rag_service",
        "backend.app.services.agent_tools.registry",
    ]
    print("[1/4] 模块导入检查")
    all_ok = True
    for mod_name in modules:
        try:
            __import__(mod_name)
            print(f"  ✅  {mod_name}")
        except Exception as e:
            print(f"  ❌  {mod_name}: {e}")
            all_ok = False
    return all_ok

def check_spark():
    from backend.app.core.config import get_config
    llm = get_config().llm
    print("\n[2/4] 讯飞 Spark 配置检查")
    print(f"  provider: {llm.provider}")
    has = bool(llm.spark_app_id and llm.spark_api_key)
    print(f"  status: {'✅ 可发起 Spark 调用' if has else '⚠️ 缺少配置'}")

def check_rag():
    from backend.app.services.rag_service import get_rag_service
    stats = get_rag_service().stats()
    print(f"\n[3/4] RAG 索引检查")
    print(f"  backend: {stats['backend']}")
    print(f"  total_chunks: {stats['total_chunks']}")
    print(f"  by_course: {stats['by_course']}")

def check_agents():
    from backend.app.agents import AGENT_REGISTRY
    from backend.app.services.agent_tools.registry import get_tool_registry
    print(f"\n[4/4] Agent 注册表检查")
    print(f"  已注册: {list(AGENT_REGISTRY.keys())}")
    print(f"  工具: {len(get_tool_registry().list_a_tools())} 个")

if __name__ == "__main__":
    print("=" * 50)
    print("A3 验证脚本")
    print("=" * 50)
    check_imports()
    check_spark()
    check_rag()
    check_agents()
    print("\n✅ 验证完成")
