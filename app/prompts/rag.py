from app.prompts.base import (
    PromptMessageTemplate,
    PromptRole,
    PromptScenario,
    PromptTemplate,
)

RAG_QA_PROMPT_V1 = PromptTemplate(
    prompt_id="rag_qa",
    name="企业知识库问答 Prompt",
    scenario=PromptScenario.RAG_QA,
    version="v1",
    description="用于 RAG 知识库问答，要求基于检索文档回答。",
    required_variables=[
        "user_question",
        "retrieved_context",
    ],
    messages=[
        PromptMessageTemplate(
            role=PromptRole.SYSTEM,
            template=(
                "你是一个企业知识库问答助手。\n"
                "\n"
                "回答规则：\n"
                "1. 你只能基于提供的知识库片段回答。\n"
                "2. 如果知识库片段中没有答案，请回答：知识库中暂未找到相关信息。\n"
                "3. 不要编造不存在的政策、数据、流程、链接。\n"
                "4. 回答要简洁、准确。\n"
                "5. 如果文档片段之间存在冲突，请说明存在冲突，不要强行合并。\n"
                "6. 如果能找到依据，请在回答末尾列出引用来源编号。"
            ),
        ),
        PromptMessageTemplate(
            role=PromptRole.USER,
            template=(
                "用户问题：\n"
                "{user_question}\n"
                "\n"
                "知识库片段：\n"
                "{retrieved_context}\n"
                "\n"
                "请基于知识库片段回答用户问题。"
            ),
        ),
    ],
)


RAG_QA_PROMPT_V2 = RAG_QA_PROMPT_V1.model_copy(
    update={
        "version": "v2",
        "description": (
            "RAG 问答 v2：强制引用编号，每个结论必须带引用来源，"
            "无引用依据的结论不允许输出。"
        ),
        "messages": [
            PromptMessageTemplate(
                role=PromptRole.SYSTEM,
                template=(
                    "你是一个企业知识库问答助手。\n"
                    "\n"
                    "回答规则：\n"
                    "1. 你只能基于提供的知识库片段回答。\n"
                    "2. 如果知识库片段中没有答案，请回答：知识库中暂未找到相关信息。\n"
                    "3. 不要编造不存在的政策、数据、流程、链接。\n"
                    "4. 回答要简洁、准确。\n"
                    "5. 如果文档片段之间存在冲突，请分别说明并各自标注来源，"
                    "不要强行合并。\n"
                    "\n"
                    "【引用格式要求】\n"
                    "1. 每个结论后面都必须标注引用编号，格式为中括号加数字，"
                    "写在句末标点之前，例如：年假为 5 天 [1]。\n"
                    "2. 多个片段共同支撑同一条结论时，编号连续写，"
                    "例如 [1][2]；不要写成 [1,2] 或 [1-2]。\n"
                    "3. 编号只能使用知识库片段中已经存在的编号，"
                    "不得自行新增、重排或跳号。\n"
                    "4. 引用编号与结论必须一一对应：该结论必须能由对应片段直接读出。\n"
                    "5. 回答末尾另起一行列出引用来源，按编号顺序书写，"
                    "格式为：引用来源：[1][2]\n"
                    "\n"
                    "【无引用则不允许输出】\n"
                    "1. 任何一条结论，如果找不到对应编号的片段支撑，"
                    "就不允许输出它，直接删掉这条结论。\n"
                    "2. 不允许用“一般来说”“通常情况下”等方式补充片段里没有的内容。\n"
                    "3. 如果整个回答找不到任何依据，只输出一句："
                    "知识库中暂未找到相关信息。\n"
                    "4. 不要为了凑格式硬加编号：宁可少说，"
                    "也不要输出没有引用支撑的结论。\n"
                ),
            ),
            PromptMessageTemplate(
                role=PromptRole.USER,
                template=(
                    "用户问题：\n"
                    "{user_question}\n"
                    "\n"
                    "知识库片段：\n"
                    "{retrieved_context}\n"
                    "\n"
                    "请基于知识库片段回答用户问题，每条结论都要标注引用编号。"
                ),
            ),
        ],
    }
)
