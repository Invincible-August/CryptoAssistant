"""
交易所配置模型。
存储各交易所的API密钥、网络模式等连接信息。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ExchangeConfig(Base):
    """
    交易所配置表模型。

    每行代表一个交易所账户的连接配置，包括API密钥、密钥、
    可选口令以及测试网/正式网的切换标志。
    """

    __tablename__ = "exchange_configs"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )

    # ---- 交易所标识 ----
    exchange_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="交易所名称（如 binance / okx）"
    )

    # ---- API凭证（敏感数据，存储时应加密） ----
    api_key: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="API Key"
    )
    api_secret: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="API Secret"
    )
    passphrase: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="口令（部分交易所如OKX需要）"
    )

    # ---- 运行模式 ----
    is_testnet: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否使用测试网"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="该配置是否启用"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True, comment="最后更新时间"
    )

    def __repr__(self) -> str:
        return (
            f"<ExchangeConfig(id={self.id}, exchange='{self.exchange_name}', "
            f"testnet={self.is_testnet}, enabled={self.enabled})>"
        )
