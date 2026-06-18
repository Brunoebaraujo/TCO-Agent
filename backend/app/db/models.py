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


class ChatSession(Base):
    """
    Uma sessão de conversa entre o vendedor e o agente TCO.
    Guarda o histórico bruto de mensagens (JSON) para permitir retomar
    a conversa exatamente de onde parou, e referencia o tco_result
    estruturado mais recente gerado nesta sessão (se houver).
    """
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Título legível para a listagem do History — derivado da primeira
    # mensagem do usuário ou do customer_name do tco_result, quando existir.
    title: Mapped[str] = mapped_column(String(200), default="Nova conversa")

    # Histórico completo de mensagens, serializado como JSON:
    # [{"role": "user"|"assistant", "content": "...", "tco_result": {...} | null}, ...]
    messages_json: Mapped[str] = mapped_column(Text, default="[]")

    # Espelha o último tco_result gerado nesta sessão, para exibir
    # resumo na listagem do History sem precisar reabrir a conversa inteira.
    last_tco_result_json: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class GoodpackSKU(Base):
    __tablename__ = "goodpack_skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Specs físicas — opcionais para permitir cadastrar a SKU pelo nome
    # primeiro (ex: a partir de uma lista) e completar os números depois,
    # sem bloquear o cadastro inicial.
    volume_liters: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    max_payload_kg: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    tare_weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))

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


class AccessoryType(Base):
    __tablename__ = "accessory_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    accessory_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PackagingAccessory(Base):
    __tablename__ = "packaging_accessories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    packaging_type: Mapped[str] = mapped_column(String(20), nullable=False)
    goodpack_sku_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goodpack_skus.id"))
    competitor_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competitor_units.id"))

    # NULL = vale para qualquer produto/tipo (default genérico da embalagem).
    # Preenchido = vale especificamente para essa combinação embalagem+tipo de produto
    # (ex: MB6 + Orange/FCOJ usa Poly Liner; MB6 + Orange/NFC usa Aseptic Bag).
    product_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_types.id"))

    accessory_type_id: Mapped[int] = mapped_column(ForeignKey("accessory_types.id"), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)

    default_unit_price: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    region: Mapped[str] = mapped_column(String(20), default="GLOBAL")

    collected_at: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    source_type: Mapped[Optional[str]] = mapped_column(String(50))
    source_detail: Mapped[Optional[str]] = mapped_column(Text)
    collected_by: Mapped[Optional[str]] = mapped_column(String(100))
    confidence_level: Mapped[str] = mapped_column(String(30), default="validation_required")

    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    accessory_type: Mapped["AccessoryType"] = relationship()
    product_type: Mapped[Optional["ProductType"]] = relationship()


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


class TransportType(Base):
    """
    Catálogo de tipos de transporte (20ft Dry, 40ft Reefer, etc.) com seus
    limites de peso bruto — constantes do meio de transporte, não da
    embalagem nem da oportunidade específica.
    """
    __tablename__ = "transport_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transport_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Limite padrão de peso bruto do equipamento (ex: container 40ft reefer)
    standard_gross_weight_limit_kg: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    # Limite prático/regulatório de peso bruto, normalmente menor que o
    # padrão por restrição de rodagem/porto (ex: limite rodoviário local)
    gross_weight_limit_kg: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductCategory(Base):
    """Nível 1 da hierarquia de produtos. Ex: Citrus, Dairy, Petrochemicals."""
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class Product(Base):
    """Nível 2 da hierarquia. Ex: Orange, Lemon — pertence a uma categoria."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("product_categories.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    category: Mapped["ProductCategory"] = relationship()

    __table_args__ = (UniqueConstraint("category_id", "product_name", name="uq_product_per_category"),)


class ProductType(Base):
    """
    Nível 3 (mais específico) da hierarquia. Ex: NFC, FCOJ, Concentrate —
    o tipo de processamento de um produto. É este nível que determina quais
    acessórios uma embalagem usa (ver PackagingAccessory.product_type_id).
    """
    __tablename__ = "product_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    type_name: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    product: Mapped["Product"] = relationship()

    __table_args__ = (UniqueConstraint("product_id", "type_name", name="uq_type_per_product"),)


class TCOAnalysis(Base):
    __tablename__ = "tco_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    salesforce_opportunity_id: Mapped[Optional[str]] = mapped_column(String(100))

    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_types.id"))
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


class CustomerCompetitorPrice(Base):
    """
    Preço real de uma embalagem concorrente confirmado por um cliente
    específico, extraído automaticamente do TCO_RESULT ao final de cada
    análise.

    Diferente de CompetitorPricing (que são benchmarks de mercado editáveis
    no KB por região), esta tabela registra o que cada cliente *de fato*
    pagou ou declarou pagar — a fonte primária para análise de inteligência
    competitiva por cliente ("quem paga mais caro pelo Octabin?").
    """
    __tablename__ = "customer_competitor_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Referência à sessão de chat que originou este registro — permite
    # rastrear de qual análise o preço veio e reabrir o contexto completo.
    chat_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL")
    )

    # Nome do cliente exatamente como apareceu no TCO_RESULT — não FK
    # para uma tabela de clientes (não temos essa tabela ainda), apenas
    # texto livre para facilitar agrupamento e busca.
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # FK para a embalagem concorrente, resolvida pelo nome no momento da
    # extração — NULL se o nome não bater com nenhuma unidade cadastrada.
    competitor_unit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("competitor_units.id", ondelete="SET NULL")
    )
    # Guardamos também o nome bruto (como veio do agente) para não perder
    # o dado quando a embalagem não estiver cadastrada ainda.
    competitor_name_raw: Mapped[str] = mapped_column(String(200), nullable=False)

    # SKU Goodpack que foi comparada nessa análise — contexto útil para
    # saber em qual cenário competitivo o preço foi registrado.
    goodpack_sku: Mapped[Optional[str]] = mapped_column(String(20))

    # Produto e tipo, para filtrar por mercado (ex: só Citrus).
    product_name: Mapped[Optional[str]] = mapped_column(String(200))

    # Preço da embalagem concorrente conforme declarado pelo vendedor
    # (competitor_per_unit da categoria Packaging, que inclui unit cost +
    # acessórios do concorrente, por unidade de embalagem).
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Volume e lease days do TCO — contexto adicional que pode influenciar
    # o preço negociado (ex: desconto por volume).
    simulated_metric_tonnes: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    lease_days: Mapped[Optional[int]] = mapped_column(Integer)

    recorded_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    competitor_unit: Mapped[Optional["CompetitorUnit"]] = relationship()

    __table_args__ = (
        Index("idx_ccp_competitor_unit", "competitor_unit_id", "recorded_at"),
        Index("idx_ccp_customer", "customer_name", "recorded_at"),
    )
