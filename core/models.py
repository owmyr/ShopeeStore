"""SQLModel table definitions."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    """A Shopee product listing, deduped by (item_id, shop_id)."""

    __tablename__ = "product"

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(index=True)
    shop_id: int
    title: str
    url: str
    image_url: str = ""
    shop_name: str = ""
    first_seen_at: datetime
    last_seen_at: datetime


class PriceSnapshot(SQLModel, table=True):
    """Point-in-time capture of a product's commercial fields."""

    __tablename__ = "price_snapshot"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    captured_at: datetime
    price_cents: int
    sold_count: int = 0
    rating: float | None = None
    run_id: str = Field(index=True)  # agent_ledger run that captured this


class AgentLedger(SQLModel, table=True):
    """One row per agent run (observability / supervision surface)."""

    __tablename__ = "agent_ledger"

    run_id: str = Field(primary_key=True)
    agent: str = Field(index=True)
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "running"  # running | success | error
    inputs_hash: str = ""
    outputs_path: str = ""
    error: str = ""
    duration_sec: float | None = None
