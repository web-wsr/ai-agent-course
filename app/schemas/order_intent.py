# 订单意图识别结果

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderIntent(str, Enum):
    """订单相关意图，四个取值互斥。"""

    QUERY_ORDER = "query_order"  # 查订单本身：状态、金额、是否发货
    REFUND = "refund"  # 退款、退货、换货、售后、赔偿
    LOGISTICS = "logistics"  # 明确问快递：到哪了、物流单号、配送进度
    OTHER = "other"  # 以上都不是或信息不足


class OrderIntentResult(BaseModel):
    """大模型意图识别输出的校验模型。"""

    model_config = ConfigDict(
        extra="ignore",  # 模型多吐字段不报错，少吐必填字段会报错
        str_strip_whitespace=True,
    )

    intent: OrderIntent = Field(..., description="用户意图")
    confidence: float = Field(..., ge=0, le=1, description="置信度，0-1")
    order_no: str | None = Field(
        default=None,
        description="从用户问题中提取到的订单号，没有则为 None",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="判断依据，一句话",
    )
    need_human: bool = Field(
        default=False,
        description="是否需要转人工",
    )

    @field_validator("order_no", mode="before")
    @classmethod
    def normalize_order_no(cls, value):
        """把模型常见的空值写法统一成 None，其余原样保留，不做编造性补全。"""
        if value is None:
            return None

        if isinstance(value, str):
            text = value.strip()
            if text.lower() in {"", "null", "none", "n/a", "无", "未知"}:
                return None
            return text

        return str(value)
