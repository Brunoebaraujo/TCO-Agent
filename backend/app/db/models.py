"""
Modelos SQLAlchemy — espelham o schema modelado em tco_engine_schema.sql
"""
from sqlalchemy import (
    String, Integer, Numeric, Boolean, Date, Text,
    ForeignKey, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime, date
from typing import Optional
from app.db.database import Base


class GoodpackSKU(Base):
    __tablename__ = "goodpack_skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    volume_liters: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    max_payload_kg: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    tare_weight_kg: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)

    stack_full_warehouse: Mapped[Optional[int]] = mapped_column(Integer)
    stack_empty_warehouse: Mapped[Optional[int]] = mapped_column(Integer)
    stack_full_transit: Mapped[Optional[int]] = mapped_column(Integer)

    qty_20ft_dry: Mapped[Optional[int]] = mapped_column(Integer)
    qty_40ft_dry: Mapped[Optional[int]] = mapped_column(Integer)
    qty_20ft_reefer: Mapped[Optional[int]] = mapped_column(Integer)
    qty_40ft_reefer: Mapped[Optional[int]] = mapped_column(Integer)
    qty_40ft_hc_dry: Mapped[Optional[int]] = mapped_column(Integer)

    is_collapsible: Mapped[bool] = mapped_column(Boolean, default=False)
    is_nestable: Mapped[bool] = mapped_column(Boolean, default=False)
    special_features: Mapped[Optional[str]] = mapped_column(Text)
    tds_document_ref: Mapped[Optional[str]] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class CompetitorUnit(Base):
    __tablename__ = "competitor_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    unit_type: Mapped[Optional[str]] = mapped_column(String(50))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))

    volume_liters: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    max_payload_kg: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    tare_weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))

    stack_full_warehouse: Mapped[Optional[int]] = mapped_column(Integer)
    stack_empty_warehouse: Mapped[Optional[int]] = mapped_column(Integer)

    qty_20ft_dry: Mapped[Optional[int]] = mapped_column(Integer)
    qty_40ft_dry: Mapped[Optional[int]] = mapped_column(Integer)
    qty_20ft_reefer: Mapped[Optional[int]] = mapped_column(Integer)
    qty_40ft_reefer: Mapped[Optional[int]] = mapped_column(Integer)
    qty_40ft_hc_dry: Mapped[Optional[int]] = mapped_column(Integer)

    specs_source: Mapped[Optional[str]] = mapped_column(String(200))
    specs_collected_at: Mapped[Optional[date]] = mapped_column(Date)
    specs_confidence: Mapped[str] = mapped_column(String(30), default="high_confidence")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    pricing: Mapped[list["CompetitorPricing"]] = relationship(back_populates="unit")


class CompetitorPricing(Base):
    __tablename__ = "competitor_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_unit_id: Mapped[int] = mapped_column(ForeignKey("competitor_units.id"), nullable=False)

    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    price_pallet: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    price_poly_liner: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    price_aseptic_bag: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    price_base_pad: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    price_lid: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    price_strapping: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    price_dunnage: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    price_top_sheet: Mapped[float] = mapped_column(Numeric(8, 2), default=0)

    collected_at: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_detail: Mapped[Optional[str]] = mapped_column(Text)
    collected_by: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(50))

    confidence_level: Mapped[str] = mapped_column(String(30), default="high_confidence")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    unit: Mapped["CompetitorUnit"] = relationship(back_populates="pricing")

    __table_args__ = (
        Index("idx_competitor_pricing_current", "competitor_unit_id", "is_current", "collected_at"),
    )


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    region_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_region_code: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("regions.region_code"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HandlingParameterType(Base):
    __tablename__ = "handling_parameter_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    param_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    param_label: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(20))
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HandlingBenchmark(Base):
    __tablename__ = "handling_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    param_key: Mapped[str] = mapped_column(String(80), ForeignKey("handling_parameter_types.param_key"), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False)
    competitor_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competitor_units.id"))
    region_code: Mapped[str] = mapped_column(String(20), ForeignKey("regions.region_code"), nullable=False)
    product_category: Mapped[Optional[str]] = mapped_column(String(50))

    value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    collected_at: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_detail: Mapped[Optional[str]] = mapped_column(Text)
    collected_by: Mapped[Optional[str]] = mapped_column(String(100))

    confidence_level: Mapped[str] = mapped_column(String(30), default="high_confidence")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        Index("idx_handling_lookup", "param_key", "applies_to", "region_code", "is_current"),
    )


class ProductCatalog(Base):
    __tablename__ = "product_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category_code: Mapped[Optional[str]] = mapped_column(String(10))
    category_name: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class TCOAnalysis(Base):
    __tablename__ = "tco_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    salesforce_opportunity_id: Mapped[Optional[str]] = mapped_column(String(100))

    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_catalog.id"))
    product_name_raw: Mapped[Optional[str]] = mapped_column(String(100))
    goodpack_sku_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goodpack_skus.id"))
    competitor_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competitor_units.id"))

    simulated_metric_tonnes: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    lease_days_assumed: Mapped[Optional[int]] = mapped_column(Integer)
    transport_container_type: Mapped[Optional[str]] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    goodpack_total_cost_per_mt: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    competitor_total_cost_per_mt: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    saving_per_mt: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    total_saving: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))

    saving_packaging: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    saving_handling_packer: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    saving_transport: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    saving_handling_enduser: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    saving_empty_mgmt: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))

    assumptions_verified_count: Mapped[int] = mapped_column(Integer, default=0)
    assumptions_high_confidence_count: Mapped[int] = mapped_column(Integer, default=0)
    assumptions_validation_req_count: Mapped[int] = mapped_column(Integer, default=0)

    generated_by: Mapped[Optional[str]] = mapped_column(String(100))
    generation_method: Mapped[str] = mapped_column(String(20), default="agent")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    exported_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    assumptions: Mapped[list["TCOAssumptionDetail"]] = relationship(back_populates="analysis")


class TCOAssumptionDetail(Base):
    __tablename__ = "tco_assumption_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tco_analysis_id: Mapped[int] = mapped_column(ForeignKey("tco_analyses.id", ondelete="CASCADE"), nullable=False)

    assumption_key: Mapped[str] = mapped_column(String(100), nullable=False)
    assumption_label: Mapped[Optional[str]] = mapped_column(Text)
    value_used: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    unit: Mapped[Optional[str]] = mapped_column(String(20))

    data_source: Mapped[Optional[str]] = mapped_column(String(50))
    source_detail: Mapped[Optional[str]] = mapped_column(Text)
    source_date: Mapped[Optional[date]] = mapped_column(Date)
    override_by_seller: Mapped[bool] = mapped_column(Boolean, default=False)
    original_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    confidence_level: Mapped[str] = mapped_column(String(30), nullable=False)
    alert_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    analysis: Mapped["TCOAnalysis"] = relationship(back_populates="assumptions")

    __table_args__ = (
        Index("idx_tco_assumptions_analysis", "tco_analysis_id", "confidence_level"),
    )
