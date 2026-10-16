#!/usr/bin/env python3
"""
生成MP3语音文件
使用edge-tts库生成高质量中文语音
"""

import os
import asyncio
import re

# 语音脚本配置
SCRIPTS = [
    ("chapter_05_intro.md", "ch05_transformer_llm_intro.mp3", "第五章 Transformer导学"),
    ("chapter_06_intro.md", "ch06_multi_agent_intro.mp3", "第六章 多智能体系统导学"),
    ("chapter_08_intro.md", "ch08_multimodal_intro.mp3", "第八章 多模态大模型导学"),
    ("chapter_09_intro.md", "ch09_rag_intro.mp3", "第九章 RAG技术导学"),
    ("chapter_10_intro.md", "ch10_ai_agent_intro.mp3", "第十章 AI Agent导学"),
    ("chapter_12_intro.md", "ch12_project_practice_intro.mp3", "第十二章 项目实战导学"),
    ("experiment_01_intro.md", "exp01_attention_mechanism.mp3", "实验一 注意力机制"),
    ("experiment_02_intro.md", "exp02_transformer_architecture.mp3", "实验二 Transformer架构"),
    ("experiment_03_intro.md", "exp03_prompt_engineering.mp3", "实验三 提示工程"),
    ("experiment_04_intro.md", "exp04_rag_system.mp3", "实验四 RAG系统构建"),
]

SCRIPTS_DIR = "docs/voice_scripts"
OUTPUT_DIR = "data/artifacts/mp3"


def clean_text_for_tts(text: str) -> str:
    """清理文本，移除TTS标记"""
    # 移除Markdown标记
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'\*\*|__', '', text)
    text = re.sub(r'\*|_', '', text)
    text = re.sub(r'`[^`]*`', lambda m: m.group().strip('`'), text)

    # 移除TTS指令
    text = re.sub(r'【停顿】', '，', text)
    text = re.sub(r'【重音】', '', text)

    # 移除元数据行
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('>') and ('用途' in line or '朗读说明' in line or '生成时间' in line):
            continue
        if line.startswith('---'):
            continue
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


async def generate_mp3(script_file: str, output_file: str, title: str):
    """生成单个MP3文件"""
    script_path = os.path.join(SCRIPTS_DIR, script_file)
    output_path = os.path.join(OUTPUT_DIR, output_file)

    if not os.path.exists(script_path):
        print(f"  [失败] {script_file}: 文件不存在")
        return False

    try:
        # 读取并清理文本
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        text = clean_text_for_tts(content)

        # 限制文本长度（避免TTS过长）
        if len(text) > 5000:
            text = text[:5000] + "..."

        # 使用edge-tts生成语音
        import edge_tts

        communicate = edge_tts.Communicate(text, voice="zh-CN-XiaoxiaoNeural")
        await communicate.save(output_path)

        file_size = os.path.getsize(output_path)
        print(f"  [成功] {output_file} ({file_size/1024:.1f} KB) - {title}")
        return True

    except ImportError:
        print(f"  [失败] 请先安装 edge-tts: pip install edge-tts")
        return False
    except Exception as e:
        print(f"  [失败] {output_file}: {str(e)}")
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("生成章节导学语音 (MP3)")
    print("=" * 60)

    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 检查edge-tts
    try:
        import edge_tts
        print(f"\n[edge-tts 已安装]")
    except ImportError:
        print("\n[错误] 未安装 edge-tts，请先运行: pip install edge-tts")
        return

    print(f"\n脚本目录: {SCRIPTS_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"\n生成 {len(SCRIPTS)} 个语音文件:\n")

    success_count = 0
    for script_file, output_file, title in SCRIPTS:
        if await generate_mp3(script_file, output_file, title):
            success_count += 1
        await asyncio.sleep(0.5)  # 避免请求过快

    print(f"\n{'=' * 60}")
    print(f"[完成] {success_count}/{len(SCRIPTS)} 个文件生成成功")
    print(f"输出位置: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)

    # 列出生成的文件
    if success_count > 0:
        print("\n生成的文件列表:")
        for f in sorted(os.listdir(OUTPUT_DIR)):
            if f.endswith('.mp3'):
                size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
                print(f"  - {f} ({size/1024:.1f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
