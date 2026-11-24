# 订单意图识别 Prompt（输出 JSON）

from app.prompts.base import (
    PromptMessageTemplate,
    PromptRole,
    PromptScenario,
    PromptTemplate,
)

ORDER_INTENT_PROMPT_V1 = PromptTemplate(
    prompt_id="order_intent",
    name="订单意图识别（JSON 输出）",
    scenario=PromptScenario.GENERAL_CHAT,
    version="v1",
    description="把用户问题归类为 query_order / refund / logistics / other，只输出 JSON。",
    required_variables=[
        "user_question",
    ],
    messages=[
        PromptMessageTemplate(
            role=PromptRole.SYSTEM,
            template=(
                "你是一个电商平台的订单意图识别器。\n"
                "你的唯一任务：把用户问题归类到下面四个意图之一，并输出 JSON。\n"
                "\n"
                "可选意图（必须四选一）：\n"
                "1. query_order：查询订单本身的状态、金额、下单信息、是否已发货。\n"
                "2. refund：退款、退货、换货、售后、赔偿、发票等资金或权益诉求。\n"
                "3. logistics：明确询问快递物流，例如包裹到哪了、物流单号、"
                "配送进度、签收异常。\n"
                "4. other：以上都不属于，或者信息不足无法判断。\n"
                "\n"
                "判定优先级：\n"
                "1. 出现“退款、退货、换货、售后、赔偿”等词，优先判 refund，"
                "即使同时提到订单号。\n"
                "2. 只问“到哪了、物流、快递、配送”，判 logistics；"
                "问“订单状态、有没有发货、付了多少钱”，判 query_order。\n"
                "3. 一句话里既有退款诉求又有物流抱怨时，按用户真正的诉求判断；"
                "判断不了就用 other，不要硬套。\n"
                "\n"
                "输出格式要求：\n"
                "1. 只输出一个 JSON 对象，不要输出任何解释文字，"
                "不要用 markdown 代码块包裹，不要加注释。\n"
                "2. JSON 字段固定为以下五个，字段名和类型必须完全一致：\n"
                "{{\n"
                '  "intent": "query_order | refund | logistics | other",\n'
                '  "confidence": 0.0,\n'
                '  "order_no": "订单号或 null",\n'
                '  "reason": "一句话说明判断依据",\n'
                '  "need_human": false\n'
                "}}\n"
                "3. confidence 是 0 到 1 之间的小数；信息不足、只能猜时，"
                "必须给低于 0.5 的分。\n"
                "4. order_no 只能从用户问题里原样提取，没有就填 null，"
                "严禁编造订单号。\n"
                "5. reason 不超过 50 个字，不要复述用户原话。\n"
                "6. need_human 表示是否需要人工介入：涉及投诉、赔付、"
                "情绪激烈时为 true。\n"
            ),
        ),
        PromptMessageTemplate(
            role=PromptRole.USER,
            template=(
                "用户问题：\n"
                "{user_question}\n"
                "\n"
                "请输出意图识别 JSON。"
            ),
        ),
    ],
)
