"""简历优化 Prompt 的离线测试。

运行方式：
    uv run python tests/test_resume_prompt.py
也兼容 pytest：
    uv run pytest tests/test_resume_prompt.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.prompts.base import PromptScenario
from app.prompts.registry import prompt_registry
from app.prompts.renderer import (
    PromptRenderError,
    extract_variables,
    render_prompt,
)

PROMPT_ID = "resume_optimize"
VERSION = "v1"

SAMPLE_RESUME = """张三 | 前端开发 | 3 年经验
教育背景：某大学 计算机科学与技术 本科 2018-2022
技能：JavaScript、TypeScript、React、Vue、Webpack
工作经历：
2022-07 至今 某电商公司 前端开发
负责相关工作，参与项目开发，使用 React 完成页面。
项目经历：
促销活动页：独立开发活动页，使用 React + TypeScript，支持多端适配。
"""


def _prompt():
    return prompt_registry.get(prompt_id=PROMPT_ID, version=VERSION)


def test_prompt_registered():
    keys = [f"{p.prompt_id}@{p.version}" for p in prompt_registry.list()]

    assert f"{PROMPT_ID}@{VERSION}" in keys
    assert _prompt().scenario == PromptScenario.GENERAL_CHAT
    assert _prompt().version == VERSION


def test_required_variables():
    assert _prompt().required_variables == ["resume_text", "target_position"]


def test_template_placeholders_match_required_variables():
    prompt = _prompt()
    placeholders: set[str] = set()

    for message in prompt.messages:
        placeholders |= extract_variables(message.template)

    assert placeholders == set(prompt.required_variables), (
        f"模板占位符 {placeholders} 与必填变量 "
        f"{set(prompt.required_variables)} 不一致"
    )


def test_render_with_valid_variables():
    messages = render_prompt(
        prompt=_prompt(),
        variables={
            "resume_text": SAMPLE_RESUME,
            "target_position": "资深前端工程师",
        },
    )

    assert len(messages) == 2
    assert messages[0].role.value == "system"
    assert messages[1].role.value == "user"

    user_content = messages[1].content
    assert "资深前端工程师" in user_content
    assert "促销活动页" in user_content

    system_content = messages[0].content
    assert "问题分析" in system_content
    assert "优化建议" in system_content
    assert "改写版本" in system_content

    for message in messages:
        assert "{resume_text}" not in message.content
        assert "{target_position}" not in message.content


def test_render_missing_variable_raises():
    try:
        render_prompt(
            prompt=_prompt(),
            variables={"resume_text": SAMPLE_RESUME},
        )
    except PromptRenderError as exc:
        assert "target_position" in str(exc)
    else:
        raise AssertionError("缺少 target_position 时应当抛出 PromptRenderError")


def test_anti_fabrication_constraints_present():
    system_content = _prompt().messages[0].template

    assert "不得编造" in system_content
    assert "严禁新增" in system_content
    assert "需你补充" in system_content


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    passed = 0

    for test in tests:
        test()
        passed += 1
        print(f"PASS  {test.__name__}")

    print(f"\n{passed} passed")


if __name__ == "__main__":
    main()
