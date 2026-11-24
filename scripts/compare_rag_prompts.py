"""对比 RAG_QA_PROMPT_V1 与 RAG_QA_PROMPT_V2。

默认只做离线对比（渲染 + 结构差异 + 约束覆盖），不花钱：
    uv run python scripts/compare_rag_prompts.py

加 --live 会真实调用大模型，并对引用覆盖率打分：
    uv run python scripts/compare_rag_prompts.py --live
    uv run python scripts/compare_rag_prompts.py --live --model glm-5.3-flash
"""

import argparse
import asyncio
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.prompts.registry import prompt_registry
from app.prompts.renderer import render_prompt

PROMPT_ID = "rag_qa"
VERSIONS = ("v1", "v2")

SAMPLE_QUESTION = "公司年假有几天？可以跨年使用吗？"

SAMPLE_CONTEXT = """[1] 员工入职满一年后，每年享有 5 天带薪年假。
[2] 年假需在当年 12 月 31 日前使用完毕，不支持跨年结转。
[3] 报销审批周期为 3 个工作日。"""

# 期望 v2 覆盖的约束点：标签 -> 关键词
CONSTRAINT_KEYWORDS = {
    "引用格式要求": "引用格式",
    "每个结论带编号": "每个结论",
    "只能使用已有编号": "不得自行新增",
    "无引用不允许输出": "不允许输出",
    "无依据兜底话术": "暂未找到相关信息",
    "末尾引用来源行": "引用来源",
}

CITATION_PATTERN = re.compile(r"\[\d+\]")
SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？；\n]")
# 兜底话术不算“结论”，统计引用覆盖率时排除
FALLBACK_TEXT = "知识库中暂未找到相关信息"


def render(version: str):
    prompt = prompt_registry.get(prompt_id=PROMPT_ID, version=version)
    variables = {
        "user_question": SAMPLE_QUESTION,
        "retrieved_context": SAMPLE_CONTEXT,
    }
    return prompt, render_prompt(prompt=prompt, variables=variables)


def coverage_table() -> dict[str, dict[str, bool]]:
    result: dict[str, dict[str, bool]] = {}

    for version in VERSIONS:
        _, messages = render(version)
        system_text = messages[0].content
        result[version] = {
            label: keyword in system_text
            for label, keyword in CONSTRAINT_KEYWORDS.items()
        }

    return result


def print_offline_diff():
    prompt_v1, messages_v1 = render("v1")
    prompt_v2, messages_v2 = render("v2")

    print("=" * 72)
    print("RAG Prompt 离线对比：v1 vs v2")
    print("=" * 72)
    print(f"{'':22}{'v1':>18}{'v2':>18}")
    print(
        f"{'description':22}{len(prompt_v1.description):>18}"
        f"{len(prompt_v2.description):>18}"
    )
    print(
        f"{'system 字数':22}{len(messages_v1[0].content):>18}"
        f"{len(messages_v2[0].content):>18}"
    )
    print(
        f"{'user 字数':22}{len(messages_v1[1].content):>18}"
        f"{len(messages_v2[1].content):>18}"
    )

    print("\n--- 约束覆盖情况 ---")
    table = coverage_table()
    print(f"{'约束点':24}{'v1':>6}{'v2':>6}")
    for label in CONSTRAINT_KEYWORDS:
        row = "".join(
            f"{'✅' if table[version][label] else '❌':>6}" for version in VERSIONS
        )
        print(f"{label:24}{row}")

    print("\n--- SYSTEM Prompt 差异（+ 为 v2 新增）---")
    diff = difflib.unified_diff(
        messages_v1[0].content.splitlines(),
        messages_v2[0].content.splitlines(),
        fromfile="v1",
        tofile="v2",
        lineterm="",
    )
    for line in diff:
        print(line)


def citation_stats(answer: str) -> dict[str, int]:
    lines = [
        line.strip()
        for line in answer.splitlines()
        if line.strip() and not line.strip().startswith("引用来源")
    ]

    sentences = []
    for line in lines:
        sentences.extend(
            part.strip()
            for part in SENTENCE_SPLIT_PATTERN.split(line)
            if part.strip() and FALLBACK_TEXT not in part
        )

    cited = [s for s in sentences if CITATION_PATTERN.search(s)]
    body_text = "\n".join(lines)

    return {
        "sentences": len(sentences),
        "cited": len(cited),
        "uncited": len(sentences) - len(cited),
        "markers": len(CITATION_PATTERN.findall(body_text)),
        "fallback": FALLBACK_TEXT in body_text,
    }


async def run_live(model: str):
    # 延迟导入：离线对比不需要初始化 LLM 依赖
    from app.llm.factory import LLMProviderFactory
    from app.llm.schemas import LLMRequest

    provider = LLMProviderFactory.create()

    print("\n" + "=" * 72)
    print(f"真实调用对比（model={model}）")
    print("=" * 72)

    for version in VERSIONS:
        _, messages = render(version)
        response = await provider.chat(
            LLMRequest(model=model, messages=messages, temperature=0, stream=False)
        )
        stats = citation_stats(response.content)

        print(f"\n########## {version} ##########")
        print(response.content)
        print("-" * 72)
        print(
            f"句子数={stats['sentences']} 带引用={stats['cited']} "
            f"无引用={stats['uncited']} 引用标记数={stats['markers']} "
            f"引用覆盖率={stats['cited'] / stats['sentences']:.0%}"
            if stats["sentences"]
            else "无有效结论句"
        )
        print(f"是否走兜底话术={stats['fallback']}")
        print(f"token 用量={response.usage.model_dump()}")

    print(
        "\n提示：v2 的期望是无引用结论为 0；"
        "若 v2 仍出现无引用句子，说明约束还可以再加强。"
    )


def main():
    parser = argparse.ArgumentParser(description="对比 RAG Prompt v1 与 v2")
    parser.add_argument(
        "--live",
        action="store_true",
        help="真实调用大模型做引用覆盖率对比（会产生费用）",
    )
    parser.add_argument(
        "--model",
        default="glm-5.3-flash",
        help="--live 时使用的模型，默认 glm-5.3-flash",
    )
    args = parser.parse_args()

    print_offline_diff()

    if args.live:
        asyncio.run(run_live(args.model))


if __name__ == "__main__":
    main()
