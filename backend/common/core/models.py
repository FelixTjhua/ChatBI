from pydantic import field_serializer, field_validator
from sqlmodel import BigInteger, SQLModel, Field
from typing import Optional

from common.utils.snowflake import snowflake

class SnowflakeBase(SQLModel):
    id: Optional[int] = Field(
        default_factory=snowflake.generate_id,
        primary_key=True,
        sa_type=BigInteger(),
        index=True,
        nullable=False
    )

    @field_serializer('id')
    def serialize_large_int(self, v: int, _info) -> int | str:
        """将超过 JS Number.MAX_SAFE_INTEGER 的大整数序列化为字符串，防止前端精度丢失"""
        if isinstance(v, int) and v > (2**53 - 1):
            return str(v)
        return v
