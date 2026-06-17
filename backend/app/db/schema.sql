-- =============================================================
-- TCO ENGINE — Schema do banco de dados
-- Baseado na análise do arquivo TCO_PFA_Jun_2026_MB4.xlsx
-- =============================================================
-- Convenções:
--   • Todos os campos de data usam TIMESTAMPTZ (UTC)
--   • confidence_level: 'verified' | 'high_confidence' | 'validation_required'
--   • Campos de custo em moeda base (USD); currency armazenada separadamente
--   • Tabelas de benchmark têm rastreabilidade obrigatória (source + collected_at)
-- =============================================================


-- -------------------------------------------------------------
-- 1. PRODUTOS GOODPACK (specs fixas — fonte: TDS oficiais)
-- -------------------------------------------------------------
-- Dados que NÃO mudam: dimensões, capacidade, stack heights.
-- Origem: PDFs TDS (MB4, MB5, MB6, etc.)
-- Sempre confidence_level = 'verified'

CREATE TABLE goodpack_skus (
    id                      SERIAL PRIMARY KEY,
    sku_code                VARCHAR(20)     NOT NULL UNIQUE,  -- 'MB4', 'MB5', 'MB6', 'RP3'...
    description             TEXT,

    -- Dimensões físicas (mm)
    volume_liters           NUMERIC(8,2)    NOT NULL,         -- volume interno
    max_payload_kg          NUMERIC(8,2)    NOT NULL,         -- payload máximo
    tare_weight_kg          NUMERIC(8,2)    NOT NULL,         -- peso vazio

    -- Capacidade de stacking
    stack_full_warehouse    INTEGER,                          -- laden, em armazém
    stack_empty_warehouse   INTEGER,                          -- empty/collapsed
    stack_full_transit      INTEGER,                          -- laden, em trânsito

    -- Qty por tipo de container marítimo
    qty_20ft_dry            INTEGER,
    qty_40ft_dry            INTEGER,
    qty_20ft_reefer         INTEGER,
    qty_40ft_reefer         INTEGER,
    qty_40ft_hc_dry         INTEGER,

    -- Características especiais
    is_collapsible          BOOLEAN DEFAULT FALSE,
    is_nestable             BOOLEAN DEFAULT FALSE,
    special_features        TEXT,                             -- 'bottom discharge', 'removable sidewall'

    -- Rastreabilidade
    tds_document_ref        VARCHAR(100),                     -- 'GP TDS MB4 Mar24/2022'
    active                  BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE goodpack_skus IS
    'Especificações técnicas dos produtos Goodpack. Dados fixos vindos dos TDS oficiais.';


-- -------------------------------------------------------------
-- 2. UNIDADES CONCORRENTES (specs + benchmark de preço)
-- -------------------------------------------------------------
-- Dados físicos são relativamente estáveis.
-- Preços e premissas de handling mudam — rastreados com data/fonte.

CREATE TABLE competitor_units (
    id                      SERIAL PRIMARY KEY,
    unit_name               VARCHAR(100)    NOT NULL UNIQUE,  -- 'Octabin', 'Conical Drum'...
    unit_type               VARCHAR(50),                      -- 'ibc', 'drum', 'bin', 'pallet', 'cage'
    manufacturer            VARCHAR(100),

    -- Specs físicas
    volume_liters           NUMERIC(8,2),
    max_payload_kg          NUMERIC(8,2),
    tare_weight_kg          NUMERIC(8,2),

    -- Stack heights (quando disponível — muitas vezes desconhecido)
    stack_full_warehouse    INTEGER,
    stack_empty_warehouse   INTEGER,

    -- Qty por tipo de container marítimo
    qty_20ft_dry            INTEGER,
    qty_40ft_dry            INTEGER,
    qty_20ft_reefer         INTEGER,
    qty_40ft_reefer         INTEGER,
    qty_40ft_hc_dry         INTEGER,

    -- Rastreabilidade das specs
    specs_source            VARCHAR(200),                     -- 'Datasheet fabricante', 'Visita cliente Mar/25'
    specs_collected_at      DATE,
    specs_confidence        VARCHAR(30) DEFAULT 'high_confidence'
                                CHECK (specs_confidence IN ('verified','high_confidence','validation_required')),
    active                  BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE competitor_units IS
    'Cadastro de embalagens concorrentes: Octabin, drums, Blue Ocean, etc.
     Specs físicas são relativamente estáveis. Preços ficam em competitor_pricing.';


-- -------------------------------------------------------------
-- 3. PREÇOS DE EMBALAGENS CONCORRENTES (histórico com data)
-- -------------------------------------------------------------
-- ESTE é o dado que mais muda e mais precisa de rastreabilidade.
-- Cada atualização de preço vira um novo registro — histórico preservado.

CREATE TABLE competitor_pricing (
    id                      SERIAL PRIMARY KEY,
    competitor_unit_id      INTEGER         NOT NULL REFERENCES competitor_units(id),

    -- Preço da unidade principal
    unit_price              NUMERIC(10,2)   NOT NULL,
    currency                VARCHAR(3)      NOT NULL DEFAULT 'USD',

    -- Acessórios incluídos neste benchmark (preços por unidade)
    price_pallet            NUMERIC(8,2)    DEFAULT 0,
    price_poly_liner        NUMERIC(8,2)    DEFAULT 0,
    price_aseptic_bag       NUMERIC(8,2)    DEFAULT 0,
    price_base_pad          NUMERIC(8,2)    DEFAULT 0,
    price_lid               NUMERIC(8,2)    DEFAULT 0,
    price_strapping         NUMERIC(8,2)    DEFAULT 0,
    price_dunnage           NUMERIC(8,2)    DEFAULT 0,
    price_top_sheet         NUMERIC(8,2)    DEFAULT 0,
    price_fibc              NUMERIC(8,2)    DEFAULT 0,
    price_other             NUMERIC(8,2)    DEFAULT 0,
    price_other_description TEXT,

    -- Rastreabilidade OBRIGATÓRIA
    collected_at            DATE            NOT NULL,         -- quando o dado foi coletado
    valid_until             DATE,                             -- alerta automático após esta data
    source_type             VARCHAR(50)     NOT NULL,         -- 'cliente', 'visita', 'pesquisa_mercado', 'interno'
    source_detail           TEXT,                             -- 'Informado por Pesquera Fiordo Austral em Jun/25'
    collected_by            VARCHAR(100),                     -- nome do vendedor/analista
    region                  VARCHAR(50),                      -- 'LATAM', 'Europe', 'Global' — preços variam por região

    confidence_level        VARCHAR(30)     NOT NULL DEFAULT 'high_confidence'
                                CHECK (confidence_level IN ('verified','high_confidence','validation_required')),
    notes                   TEXT,
    is_current              BOOLEAN DEFAULT TRUE,             -- FALSE quando substituído por versão mais nova
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE competitor_pricing IS
    'Histórico de preços de embalagens concorrentes. Cada atualização = novo registro.
     O agente usa o registro mais recente (is_current=TRUE) e alerta se collected_at
     exceder o limite de validade configurado (ex: 6 meses).';

CREATE INDEX idx_competitor_pricing_current
    ON competitor_pricing (competitor_unit_id, is_current, collected_at DESC);


-- -------------------------------------------------------------
-- 4A. REGIÕES (lookup table)
-- -------------------------------------------------------------
-- Hierarquia: global → região → país (para expansão futura).
-- Por ora apenas região é obrigatória; país é opcional.

CREATE TABLE regions (
    id                      SERIAL PRIMARY KEY,
    region_code             VARCHAR(20)     NOT NULL UNIQUE,  -- 'LATAM', 'EUROPE', 'ASIA', 'GLOBAL'
    region_name             VARCHAR(100)    NOT NULL,
    parent_region_code      VARCHAR(20)     REFERENCES regions(region_code),  -- para hierarquia futura
    notes                   TEXT,
    active                  BOOLEAN DEFAULT TRUE
);

INSERT INTO regions (region_code, region_name) VALUES
    ('GLOBAL', 'Global — fallback quando região específica não existe'),
    ('LATAM',  'Latin America'),
    ('EUROPE', 'Europe'),
    ('ASIA',   'Asia Pacific'),
    ('NAMERICA','North America'),
    ('MEA',    'Middle East & Africa');

COMMENT ON TABLE regions IS
    'Lookup de regiões. O agente usa hierarquia: busca região específica primeiro,
     cai para GLOBAL se não encontrar. Expansão futura: adicionar país como filho de região.';


-- -------------------------------------------------------------
-- 4B. CATÁLOGO DE PARÂMETROS DE HANDLING
-- -------------------------------------------------------------
-- Define QUAIS parâmetros existem, sua unidade e a qual contexto se aplicam.
-- Separar o catálogo dos valores permite adicionar novos parâmetros sem alterar schema.

CREATE TABLE handling_parameter_types (
    id                      SERIAL PRIMARY KEY,
    param_key               VARCHAR(80)     NOT NULL UNIQUE,
    param_label             TEXT            NOT NULL,         -- label legível para UI e relatórios
    unit                    VARCHAR(20)     NOT NULL,         -- 'USD/h', 'USD/stack/month', 'persons', 'min', 'units/h'
    value_type              VARCHAR(20)     NOT NULL CHECK (value_type IN ('cost','time','manpower','rate')),
    role                    VARCHAR(20)     CHECK (role IN ('packer','enduser','both')),
    applies_to              VARCHAR(20)     NOT NULL CHECK (applies_to IN ('goodpack','competitor','both')),
    description             TEXT,
    active                  BOOLEAN DEFAULT TRUE
);

-- Parâmetros extraídos diretamente do Excel (Input sheet)
INSERT INTO handling_parameter_types
    (param_key, param_label, unit, value_type, role, applies_to) VALUES
-- Custos (variam por região — rastreados individualmente)
('labor_cost_per_hour',              'Labor cost per hour',                  'USD/h',              'cost',     'both',    'both'),
('storage_cost_per_month_per_stack', 'Storage cost per month / stack',       'USD/stack/month',    'cost',     'both',    'both'),
-- Tempos e manpower — Packer
('storage_time_months_packer',       'Storage time in months (packer)',      'months',             'time',     'packer',  'both'),
('assembly_manpower',                'Assembly manpower',                    'persons',            'manpower', 'packer',  'both'),
('fill_assemble_units_per_hour',     'Fill & assemble qty of units per hour','units/h',            'rate',     'packer',  'both'),
('stacking_manpower_full_packer',    'Stacking manpower (full, packer)',     'persons',            'manpower', 'packer',  'both'),
('stacking_time_full_min_packer',    'Stacking time full units (packer)',    'min',                'time',     'packer',  'both'),
('stacking_manpower_empty_packer',   'Stacking manpower (empty, packer)',    'persons',            'manpower', 'packer',  'both'),
('stacking_time_empty_min_packer',   'Stacking time empty units (packer)',   'min',                'time',     'packer',  'both'),
('loading_manpower',                 'Loading manpower',                     'persons',            'manpower', 'packer',  'both'),
('loading_time_min',                 'Loading time per truck',               'min',                'time',     'packer',  'both'),
-- Tempos e manpower — Enduser
('storage_time_months_enduser',      'Storage time in months (enduser)',     'months',             'time',     'enduser', 'both'),
('disassembly_manpower',             'Disassembly manpower',                 'persons',            'manpower', 'enduser', 'both'),
('empty_disassemble_units_per_hour', 'Empty & disassemble qty per hour',     'units/h',            'rate',     'enduser', 'both'),
('remove_trash_min',                 'Remove trash time',                    'min',                'time',     'enduser', 'both'),
('stacking_manpower_full_enduser',   'Stacking manpower (full, enduser)',    'persons',            'manpower', 'enduser', 'both'),
('stacking_time_full_min_enduser',   'Stacking time full units (enduser)',   'min',                'time',     'enduser', 'both'),
('stacking_manpower_empty_enduser',  'Stacking manpower (empty, enduser)',   'persons',            'manpower', 'enduser', 'both'),
('stacking_time_empty_min_enduser',  'Stacking time empty units (enduser)',  'min',                'time',     'enduser', 'both'),
('unloading_manpower',               'Unloading manpower',                   'persons',            'manpower', 'enduser', 'both'),
('unloading_time_min',               'Unloading time per truck',             'min',                'time',     'enduser', 'both');

COMMENT ON TABLE handling_parameter_types IS
    'Catálogo de todos os parâmetros de handling possíveis. Adicionar novo parâmetro
     = inserir uma linha aqui; nenhuma alteração de schema necessária.';


-- -------------------------------------------------------------
-- 4C. VALORES DE HANDLING POR REGIÃO (chave-valor rastreável)
-- -------------------------------------------------------------
-- Cada linha = um parâmetro + região + applies_to + valor + rastreabilidade.
-- Isso permite atualizar labor_cost da Europa sem tocar no storage_cost da Europa,
-- e manter histórico completo de cada parâmetro independentemente.

CREATE TABLE handling_benchmarks (
    id                          SERIAL PRIMARY KEY,

    -- O quê
    param_key                   VARCHAR(80)     NOT NULL REFERENCES handling_parameter_types(param_key),

    -- Para quem e onde
    applies_to                  VARCHAR(20)     NOT NULL CHECK (applies_to IN ('goodpack','competitor')),
    competitor_unit_id          INTEGER         REFERENCES competitor_units(id),  -- NULL = todos os concorrentes
    region_code                 VARCHAR(20)     NOT NULL REFERENCES regions(region_code),
    product_category            VARCHAR(50),    -- 'FAO','KFJ','DAY' — NULL = todas as categorias

    -- O valor
    value                       NUMERIC(10,4)   NOT NULL,
    currency                    VARCHAR(3)      DEFAULT 'USD',  -- relevante para params de custo

    -- Rastreabilidade INDIVIDUAL por parâmetro
    collected_at                DATE            NOT NULL,
    valid_until                 DATE,
    source_type                 VARCHAR(50)     NOT NULL
                                    CHECK (source_type IN ('cliente','visita','pesquisa_mercado','interno','estimativa')),
    source_detail               TEXT,           -- 'Coletado em visita à Nestle Holanda, Mar/2025'
    collected_by                VARCHAR(100),

    confidence_level            VARCHAR(30)     NOT NULL DEFAULT 'high_confidence'
                                    CHECK (confidence_level IN ('verified','high_confidence','validation_required')),
    notes                       TEXT,
    is_current                  BOOLEAN         DEFAULT TRUE,
    created_at                  TIMESTAMPTZ     DEFAULT NOW(),

    -- Garantia: só um valor current por combinação param+applies_to+region+categoria+concorrente
    CONSTRAINT uq_handling_current UNIQUE NULLS NOT DISTINCT
        (param_key, applies_to, competitor_unit_id, region_code, product_category, is_current)
        DEFERRABLE INITIALLY DEFERRED
);

COMMENT ON TABLE handling_benchmarks IS
    'Valores de handling por parâmetro, por região e por applies_to (goodpack/competitor).
     Modelo chave-valor: cada parâmetro é atualizado e rastreado independentemente.
     Hierarquia de fallback do agente: região específica → GLOBAL.
     Exemplo de busca: labor_cost_per_hour + LATAM + goodpack → se não existir → GLOBAL.';

CREATE INDEX idx_handling_lookup
    ON handling_benchmarks (param_key, applies_to, region_code, is_current, collected_at DESC);

CREATE INDEX idx_handling_competitor
    ON handling_benchmarks (competitor_unit_id, param_key, region_code, is_current)
    WHERE competitor_unit_id IS NOT NULL;


-- -------------------------------------------------------------
-- DADOS INICIAIS — handling_benchmarks (valores do Excel atual)
-- -------------------------------------------------------------
-- Estes são os valores "Goodpack's Estimation" do arquivo TCO_PFA_Jun_2026_MB4.xlsx.
-- Região GLOBAL, confidence = high_confidence (base histórica interna).
-- À medida que dados regionais forem coletados, inserir com região específica.

INSERT INTO handling_benchmarks
    (param_key, applies_to, region_code, value, currency,
     collected_at, source_type, source_detail, collected_by, confidence_level) VALUES

-- GOODPACK — valores do Excel (coluna "Goodpack's Estimation")
('labor_cost_per_hour',              'goodpack', 'GLOBAL', 20,   'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('storage_cost_per_month_per_stack', 'goodpack', 'GLOBAL', 10,   'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('storage_time_months_packer',       'goodpack', 'GLOBAL', 1,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('assembly_manpower',                'goodpack', 'GLOBAL', 1,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('fill_assemble_units_per_hour',     'goodpack', 'GLOBAL', 10,   'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('stacking_manpower_full_packer',    'goodpack', 'GLOBAL', 1,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('stacking_time_full_min_packer',    'goodpack', 'GLOBAL', 20,   'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('loading_manpower',                 'goodpack', 'GLOBAL', 1,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('loading_time_min',                 'goodpack', 'GLOBAL', 30,   'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('storage_time_months_enduser',      'goodpack', 'GLOBAL', 2,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('disassembly_manpower',             'goodpack', 'GLOBAL', 1,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('empty_disassemble_units_per_hour', 'goodpack', 'GLOBAL', 4,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('remove_trash_min',                 'goodpack', 'GLOBAL', 2,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('stacking_time_full_min_enduser',   'goodpack', 'GLOBAL', 20,   'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('unloading_manpower',               'goodpack', 'GLOBAL', 1,    'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),
('unloading_time_min',               'goodpack', 'GLOBAL', 30,   'USD', '2026-06-01', 'interno', 'Valor padrão extraído de TCO_PFA_Jun_2026_MB4.xlsx', 'sistema', 'high_confidence'),

-- COMPETITOR (Octabin) — valores do Excel (coluna "Competitive Unit")
('labor_cost_per_hour',              'competitor', 'GLOBAL', 11,  'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('storage_cost_per_month_per_stack', 'competitor', 'GLOBAL', 10,  'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('assembly_manpower',                'competitor', 'GLOBAL', 2,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('fill_assemble_units_per_hour',     'competitor', 'GLOBAL', 4,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('stacking_manpower_full_packer',    'competitor', 'GLOBAL', 1,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('stacking_time_full_min_packer',    'competitor', 'GLOBAL', 40,  'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('loading_manpower',                 'competitor', 'GLOBAL', 1,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('loading_time_min',                 'competitor', 'GLOBAL', 40,  'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('disassembly_manpower',             'competitor', 'GLOBAL', 2,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('empty_disassemble_units_per_hour', 'competitor', 'GLOBAL', 4,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('remove_trash_min',                 'competitor', 'GLOBAL', 4,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('unloading_manpower',               'competitor', 'GLOBAL', 1,   'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required'),
('unloading_time_min',               'competitor', 'GLOBAL', 40,  'USD', '2026-06-01', 'interno', 'Valor do Octabin extraído de TCO_PFA_Jun_2026_MB4.xlsx — VALIDAR', 'sistema', 'validation_required');


-- -------------------------------------------------------------
-- 5. TIPOS DE CONTAINER DE TRANSPORTE
-- -------------------------------------------------------------
-- Dados fixos de capacidade de peso por tipo de container.

CREATE TABLE transport_container_types (
    id                      SERIAL PRIMARY KEY,
    container_type          VARCHAR(50)     NOT NULL UNIQUE,  -- '20ft Dry Good', '40ft Reefer'...
    gross_weight_limit_kg   NUMERIC(8,2)    NOT NULL,
    net_weight_limit_kg     NUMERIC(8,2),
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE transport_container_types IS 'Limites de peso por tipo de container ISO.';


-- -------------------------------------------------------------
-- 6. CATÁLOGO DE PRODUTOS / CATEGORIAS
-- -------------------------------------------------------------
-- Lista de produtos transportados e suas categorias internas Goodpack.

CREATE TABLE product_catalog (
    id                      SERIAL PRIMARY KEY,
    product_name            VARCHAR(100)    NOT NULL UNIQUE,  -- 'Omega 3', 'FCOJ', 'Palm Oils'
    category_code           VARCHAR(10),                      -- 'FAO', 'KFJ', 'CIT', 'DAY'
    category_name           VARCHAR(100),                     -- 'Fat and Oils', 'Key Fruit Juice'
    notes                   TEXT,
    active                  BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE product_catalog IS
    'Catálogo de produtos transportados e suas categorias. Orienta sugestão de SKU Goodpack.';

-- Produtos iniciais — expandir conforme oportunidades reais surgirem.
-- FCOJ e NFC incluídos por serem usados no exemplo de especialização de
-- acessórios por produto (ver packaging_accessories mais abaixo).
INSERT INTO product_catalog (product_name, category_code, category_name) VALUES
    ('FCOJ', 'CIT', 'Citrus Juice Concentrate'),
    ('NFC', 'CIT', 'Not From Concentrate Juice'),
    ('Omega 3', 'FAO', 'Fat and Oils'),
    ('Palm Oil', 'FAO', 'Fat and Oils'),
    ('Purê de tomate', 'DAY', 'Dairy and Fruit/Vegetable Derivatives');


-- -------------------------------------------------------------
-- 7A. CATÁLOGO DE ACESSÓRIOS (o que existe)
-- -------------------------------------------------------------
-- Lista mestre de tipos de acessório, independente de qual embalagem usa.
-- Ex: Poly Liner, Aseptic Bag, Base Pad, Pallet, Strapping, Dunnage, Lid.

CREATE TABLE accessory_types (
    id                      SERIAL PRIMARY KEY,
    accessory_name          VARCHAR(100)    NOT NULL UNIQUE,   -- 'Aseptic Bag', 'Poly Liner', 'Base Pad'...
    description             TEXT,
    active                  BOOLEAN DEFAULT TRUE
);

INSERT INTO accessory_types (accessory_name) VALUES
    ('Pallet'), ('Poly Liner'), ('Base Pad'), ('Aseptic Bag'),
    ('Strapping Cost'), ('Lid'), ('Dunnage'), ('Top Sheet'), ('FIBC');

COMMENT ON TABLE accessory_types IS
    'Catálogo mestre de tipos de acessório de embalagem. Cada embalagem usa um
     subconjunto destes, definido em packaging_accessories.';


-- -------------------------------------------------------------
-- 7B. VÍNCULO EMBALAGEM ↔ ACESSÓRIO (o que cada embalagem usa)
-- -------------------------------------------------------------
-- Define QUAIS acessórios cada embalagem (Goodpack ou concorrente) usa por padrão.
-- O preço de cada acessório é rastreado separadamente (com fonte/data), pois muda
-- por oportunidade e precisa de confidence_level próprio.
-- packaging_type/packaging_id aponta para goodpack_skus OU competitor_units.

CREATE TABLE packaging_accessories (
    id                      SERIAL PRIMARY KEY,

    -- A qual embalagem este vínculo se refere
    packaging_type          VARCHAR(20)     NOT NULL CHECK (packaging_type IN ('goodpack','competitor')),
    goodpack_sku_id         INTEGER         REFERENCES goodpack_skus(id),
    competitor_unit_id      INTEGER         REFERENCES competitor_units(id),

    -- NULL = vale para qualquer produto (default genérico da embalagem).
    -- Preenchido = vale especificamente para essa combinação embalagem+produto.
    -- Ex: MB6 + FCOJ usa Poly Liner; MB6 + NFC usa Aseptic Bag — duas linhas
    -- diferentes aqui, mesma embalagem, produtos diferentes.
    product_id               INTEGER        REFERENCES product_catalog(id),

    -- Qual acessório
    accessory_type_id       INTEGER         NOT NULL REFERENCES accessory_types(id),
    is_default               BOOLEAN        DEFAULT TRUE,      -- faz parte do padrão dessa embalagem?

    -- Preço default — separado do uso real em cada TCO (que fica em tco_assumption_details)
    default_unit_price      NUMERIC(8,2),
    currency                VARCHAR(3)      DEFAULT 'USD',
    region                  VARCHAR(20)     DEFAULT 'GLOBAL' REFERENCES regions(region_code),

    -- Rastreabilidade do preço default
    collected_at             DATE,
    valid_until               DATE,
    source_type               VARCHAR(50),
    source_detail             TEXT,
    collected_by              VARCHAR(100),
    confidence_level          VARCHAR(30)    DEFAULT 'validation_required'
                                  CHECK (confidence_level IN ('verified','high_confidence','validation_required')),

    is_current                BOOLEAN        DEFAULT TRUE,
    created_at                 TIMESTAMPTZ    DEFAULT NOW(),

    CONSTRAINT chk_packaging_ref CHECK (
        (packaging_type = 'goodpack' AND goodpack_sku_id IS NOT NULL AND competitor_unit_id IS NULL)
        OR
        (packaging_type = 'competitor' AND competitor_unit_id IS NOT NULL AND goodpack_sku_id IS NULL)
    )
);

COMMENT ON TABLE packaging_accessories IS
    'Define quais acessórios cada embalagem (Goodpack ou concorrente) usa por padrão,
     opcionalmente específico por produto (product_id), e o preço default de cada um,
     com rastreabilidade própria. Lógica de busca do agente: primeiro tenta
     embalagem+produto específico; se não encontrar, cai para embalagem+product_id NULL
     (default genérico). O agente NUNCA assume "sem acessórios" silenciosamente.';

CREATE INDEX idx_packaging_accessories_goodpack
    ON packaging_accessories (goodpack_sku_id, product_id, is_current) WHERE goodpack_sku_id IS NOT NULL;
CREATE INDEX idx_packaging_accessories_competitor
    ON packaging_accessories (competitor_unit_id, product_id, is_current) WHERE competitor_unit_id IS NOT NULL;


-- -------------------------------------------------------------
-- DADOS INICIAIS — packaging_accessories
-- -------------------------------------------------------------
-- Estrutura (QUAIS acessórios) confirmada pelo usuário em 17/06/2026.
-- Preços DEFAULT ainda não confirmados — confidence_level = validation_required
-- até que valores reais sejam informados. O agente deve perguntar o preço
-- de cada acessório listado aqui sempre que gerar um TCO com esta embalagem.

-- MB6: Aseptic Bag, Base Pad, Strapping Cost
INSERT INTO packaging_accessories (packaging_type, goodpack_sku_id, accessory_type_id, region, confidence_level, source_type, source_detail, collected_at)
SELECT 'goodpack', sku.id, acc.id, 'GLOBAL', 'validation_required', 'interno',
       'Estrutura confirmada pelo usuário (17/06/2026) — preço pendente de definição', '2026-06-17'
FROM goodpack_skus sku, accessory_types acc
WHERE sku.sku_code = 'MB6' AND acc.accessory_name IN ('Aseptic Bag', 'Base Pad', 'Strapping Cost');

-- MB4 e MB5: mesmo padrão do MB6 (confirmado pelo usuário)
INSERT INTO packaging_accessories (packaging_type, goodpack_sku_id, accessory_type_id, region, confidence_level, source_type, source_detail, collected_at)
SELECT 'goodpack', sku.id, acc.id, 'GLOBAL', 'validation_required', 'interno',
       'Estrutura confirmada pelo usuário (17/06/2026) — mesmo padrão do MB6, preço pendente', '2026-06-17'
FROM goodpack_skus sku, accessory_types acc
WHERE sku.sku_code IN ('MB4', 'MB5') AND acc.accessory_name IN ('Aseptic Bag', 'Base Pad', 'Strapping Cost');

-- Drum de aço 200L: Poly Liner, Aseptic Bag, Strapping Cost
INSERT INTO packaging_accessories (packaging_type, competitor_unit_id, accessory_type_id, region, confidence_level, source_type, source_detail, collected_at)
SELECT 'competitor', cu.id, acc.id, 'GLOBAL', 'validation_required', 'interno',
       'Estrutura confirmada pelo usuário (17/06/2026) — preço pendente de definição', '2026-06-17'
FROM competitor_units cu, accessory_types acc
WHERE cu.unit_name = 'Drum 200L' AND acc.accessory_name IN ('Poly Liner', 'Aseptic Bag', 'Strapping Cost');

-- Octabin: Pallet, Poly Liner, Aseptic Bag, Strapping Cost, Dunnage
INSERT INTO packaging_accessories (packaging_type, competitor_unit_id, accessory_type_id, region, confidence_level, source_type, source_detail, collected_at)
SELECT 'competitor', cu.id, acc.id, 'GLOBAL', 'validation_required', 'interno',
       'Estrutura confirmada pelo usuário (17/06/2026) — preço pendente de definição', '2026-06-17'
FROM competitor_units cu, accessory_types acc
WHERE cu.unit_name = 'Octabin' AND acc.accessory_name IN ('Pallet', 'Poly Liner', 'Aseptic Bag', 'Strapping Cost', 'Dunnage');

-- -------------------------------------------------------------
-- EXEMPLO DE ESPECIALIZAÇÃO POR PRODUTO
-- -------------------------------------------------------------
-- Mencionado pelo usuário (17/06/2026): o mesmo MB6 usa acessórios diferentes
-- dependendo do produto envasado. Estas linhas SOBRESCREVEM o default genérico
-- acima quando o produto da oportunidade for FCOJ ou NFC especificamente.
-- Requer que 'FCOJ' e 'NFC' existam em product_catalog antes deste INSERT rodar.

-- MB6 + FCOJ: usa Poly Liner (em vez do Aseptic Bag do default genérico)
INSERT INTO packaging_accessories (packaging_type, goodpack_sku_id, product_id, accessory_type_id, region, confidence_level, source_type, source_detail, collected_at)
SELECT 'goodpack', sku.id, prod.id, acc.id, 'GLOBAL', 'validation_required', 'interno',
       'Especialização por produto confirmada pelo usuário (17/06/2026) — FCOJ usa Poly Liner', '2026-06-17'
FROM goodpack_skus sku, product_catalog prod, accessory_types acc
WHERE sku.sku_code = 'MB6' AND prod.product_name = 'FCOJ' AND acc.accessory_name = 'Poly Liner';

-- MB6 + NFC: usa Aseptic Bag (igual ao default genérico, mas explícito para este produto)
INSERT INTO packaging_accessories (packaging_type, goodpack_sku_id, product_id, accessory_type_id, region, confidence_level, source_type, source_detail, collected_at)
SELECT 'goodpack', sku.id, prod.id, acc.id, 'GLOBAL', 'validation_required', 'interno',
       'Especialização por produto confirmada pelo usuário (17/06/2026) — NFC usa Aseptic Bag', '2026-06-17'
FROM goodpack_skus sku, product_catalog prod, accessory_types acc
WHERE sku.sku_code = 'MB6' AND prod.product_name = 'NFC' AND acc.accessory_name = 'Aseptic Bag';

COMMENT ON TABLE packaging_accessories IS
    'Nota de implantação: os INSERTs acima assumem que goodpack_skus já contém MB4/MB5/MB6
     e competitor_units já contém "Drum 200L" e "Octabin" antes deste script rodar.
     Se os nomes exatos forem diferentes, ajustar o WHERE antes de popular o banco.';


-- -------------------------------------------------------------
-- 8. TCOs GERADOS (histórico de análises)
-- -------------------------------------------------------------
-- Cada TCO gerado pelo agente é salvo para auditoria e aprendizado.

CREATE TABLE tco_analyses (
    id                      SERIAL PRIMARY KEY,
    salesforce_opportunity_id  VARCHAR(100),                  -- ID da oportunidade no Salesforce

    -- Contexto da oportunidade
    customer_name           VARCHAR(200)    NOT NULL,
    product_id              INTEGER         REFERENCES product_catalog(id),
    product_name_raw        VARCHAR(100),                     -- fallback se produto não estiver no catálogo
    goodpack_sku_id         INTEGER         REFERENCES goodpack_skus(id),
    competitor_unit_id      INTEGER         REFERENCES competitor_units(id),

    -- Parâmetros da simulação
    simulated_metric_tonnes NUMERIC(10,2)   NOT NULL,
    lease_days_assumed      INTEGER,
    transport_container_type VARCHAR(50),
    currency                VARCHAR(3)      DEFAULT 'USD',

    -- Resultados resumidos (espelho do Summary do Excel)
    goodpack_total_cost_per_mt   NUMERIC(10,4),
    competitor_total_cost_per_mt NUMERIC(10,4),
    saving_per_mt                NUMERIC(10,4),
    total_saving                 NUMERIC(12,2),

    -- Desdobramento por categoria
    saving_packaging        NUMERIC(12,2),
    saving_handling_packer  NUMERIC(12,2),
    saving_transport        NUMERIC(12,2),
    saving_handling_enduser NUMERIC(12,2),
    saving_empty_mgmt       NUMERIC(12,2),

    -- Qualidade das premissas usadas
    assumptions_verified_count         INTEGER DEFAULT 0,
    assumptions_high_confidence_count  INTEGER DEFAULT 0,
    assumptions_validation_req_count   INTEGER DEFAULT 0,

    -- Metadados
    generated_by            VARCHAR(100),                     -- email/nome do vendedor
    generation_method       VARCHAR(20) DEFAULT 'agent'
                                CHECK (generation_method IN ('agent','manual','import')),
    notes                   TEXT,
    exported_at             TIMESTAMPTZ,                      -- quando foi exportado como PPT/PDF
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE tco_analyses IS
    'Histórico de todos os TCOs gerados. Permite auditoria, melhoria do agente e
     análise de win/loss quando integrado ao Salesforce.';


-- -------------------------------------------------------------
-- 9. DETALHES DE PREMISSAS POR TCO (rastreabilidade completa)
-- -------------------------------------------------------------
-- Registro granular de cada premissa usada em cada TCO.
-- É o que permite mostrar ao cliente: "este dado veio de X em Y com nível Z".

CREATE TABLE tco_assumption_details (
    id                      SERIAL PRIMARY KEY,
    tco_analysis_id         INTEGER         NOT NULL REFERENCES tco_analyses(id) ON DELETE CASCADE,

    assumption_key          VARCHAR(100)    NOT NULL,         -- 'competitor_unit_price', 'labor_cost_enduser'
    assumption_label        TEXT,                             -- label legível para o usuário
    value_used              NUMERIC(12,4),
    unit                    VARCHAR(20),                      -- 'USD', 'USD/h', 'min', 'persons'

    -- De onde veio o valor
    data_source             VARCHAR(50),                      -- 'knowledge_base', 'seller_input', 'salesforce'
    source_detail           TEXT,                             -- descrição completa da fonte
    source_date             DATE,                             -- data do dado original
    override_by_seller      BOOLEAN DEFAULT FALSE,            -- vendedor sobrescreveu o default?
    original_value          NUMERIC(12,4),                    -- valor que seria usado sem override

    confidence_level        VARCHAR(30)     NOT NULL
                                CHECK (confidence_level IN ('verified','high_confidence','validation_required')),
    alert_message           TEXT,                             -- ex: 'Dado com 14 meses — confirmar com cliente'
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE tco_assumption_details IS
    'Detalhe linha a linha de cada premissa usada num TCO. Base para o relatório de
     classificação (Verified / High-Confidence / Validation Required) que acompanha o summary.';

CREATE INDEX idx_tco_assumptions_analysis
    ON tco_assumption_details (tco_analysis_id, confidence_level);


-- -------------------------------------------------------------
-- 10. CONFIGURAÇÕES DO SISTEMA
-- -------------------------------------------------------------
-- Parâmetros globais editáveis sem necessidade de deploy.

CREATE TABLE system_config (
    id                      SERIAL PRIMARY KEY,
    config_key              VARCHAR(100)    NOT NULL UNIQUE,
    config_value            TEXT            NOT NULL,
    description             TEXT,
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_by              VARCHAR(100)
);

-- Valores iniciais
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('pricing_validity_days_verified',        '365', 'Preços "verified" expiram após N dias'),
    ('pricing_validity_days_high_confidence', '180', 'Preços "high_confidence" expiram após N dias'),
    ('pricing_validity_days_validation_req',  '90',  'Preços "validation_required" expiram após N dias'),
    ('default_currency',                      'USD', 'Moeda padrão do sistema'),
    ('default_lease_days',                    '240', 'Lease days padrão quando não informado'),
    ('default_labor_cost_usd_per_hour',       '20',  'Labor cost padrão quando não informado pelo cliente'),
    ('default_storage_cost_per_month_stack',  '10',  'Storage cost padrão por stack/mês');

COMMENT ON TABLE system_config IS
    'Parâmetros globais do sistema. Editáveis pelo administrador sem redeploy.';
