import re
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class IntentClassificationOutput(BaseModel):
    intent: Literal[
        "query_order",
        "refund",
        "logistics",
        "product_question",
        "human_service",
        "other",
    ] = Field(..., description="用户意图")
    confidence: float = Field(..., ge=0, le=1, description="置信度")

    need_order_id: bool = Field(default=False, description="是否需要用户提供订单 ID")

    reply_strategy: Literal[
        "answer_directly",
        "ask_order_id",
        "call_tool",
        "transfer_human",
        "reject",
    ] = Field(..., description="回复策略")

    reason: str = Field(..., description="判断原因")


class RAGStructuredAnswerOutput(BaseModel):
    answer: str = Field(..., description="AI 最终回答")

    is_answered: bool = Field(
        ...,
        description="是否根据知识库回答了问题",
    )

    citations: list[str] = Field(
        default_factory=list,
        description="引用文档 ID 列表",
    )

    mission_info: str | None = Field(
        default=None,
        description="如果无法回答，缺少什么信息",
    )

    confidence: float = Field(
        default=0,
        ge=0,
        le=1,
        description="回答置信度",
    )


class AgentPlanStep(BaseModel):
    step_id: int = Field(..., ge=1, description="步骤序号 ID")

    name: str = Field(..., description="步骤名称")

    action_type: Literal["think", "tool_call", "respond"] = Field(
        ..., description="步骤动作类型"
    )

    tool_name: str | None = Field(
        default=None,
        description="需要调用的工具名称",
    )

    arguments: dict = Field(
        default_factory=dict,
        description="工具参数",
    )

    reason: str = Field(..., description="为什么需要这一步")


class AgentPlanOutput(BaseModel):
    goal: str = Field(..., description="用户目标")

    need_tools: bool = Field(
        default=False,
        description="是否需要调用工具",
    )

    steps: list[AgentPlanStep] = Field(
        ...,
        min_length=1,
        description="执行步骤",
    )

    final_response_style: Literal[
        "short",
        "detailed",
        "customer_service",
    ] = Field(
        default="short",
        description="最终回复风格",
    )


class ResumeOptimizationOutput(BaseModel):
    problems: list[str] = Field(default_factory=list, description="简历存在的问题")

    suggestions: list[str] = Field(default_factory=list, description="简历优化建议")

    rewritten_text: str = Field(..., description="改写后的简历内容")


# 新增订单信息抽取结构化输出
class OrderInfoExtractOutput(BaseModel):
    order_id: str | None = Field(default=None, description="订单号")
    phone_last4: str | None = Field(default=None, description="手机号后四位")
    has_required_info: bool = Field(..., description="是否具备查询订单所需信息")
    missing_fields: list[str] = Field(default_factory=list, description="缺少字段")

    @field_validator("order_id", "phone_last4", mode="before")
    @classmethod
    def normalize_empty_value(cls, value):
        """模型爱把空值写成字符串，这里统一收敛成 None。"""
        if value is None:
            return None

        if isinstance(value, str):
            text = value.strip()
            if text.lower() in {"", "null", "none", "n/a", "无", "未知", "未提供"}:
                return None
            return text

        return str(value)

    @field_validator("phone_last4")
    @classmethod
    def validate_phone_last4(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\d{4}", value):
            raise ValueError("phone_last4 必须是 4 位数字")
        return value

    @model_validator(mode="after")
    def reconcile_required_info(self):
        """has_required_info / missing_fields 以实际字段为准，不采信模型自报。"""
        missing = [
            name for name in ("order_id", "phone_last4")
            if getattr(self, name) is None
        ]
        self.missing_fields = missing
        self.has_required_info = not missing
        return self
