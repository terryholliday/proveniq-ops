-- PROVENIQ Ops Database Schema
-- Engine: PostgreSQL (Supabase)
-- Policy: Schema-first, no dynamic typing

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- VENDORS
-- External suppliers with priority ranking
-- ============================================
CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    api_endpoint VARCHAR(512),
    priority_level INTEGER NOT NULL DEFAULT 1,  -- 1 = primary, higher = fallback
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT vendors_priority_positive CHECK (priority_level > 0)
);

CREATE INDEX idx_vendors_priority ON vendors(priority_level) WHERE is_active = true;

-- ============================================
-- PRODUCTS
-- Master product catalog with par levels
-- ============================================
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    barcode VARCHAR(100) UNIQUE,
    par_level INTEGER NOT NULL DEFAULT 0,
    risk_category VARCHAR(50) NOT NULL DEFAULT 'standard',  -- standard, perishable, hazardous, controlled
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT products_par_non_negative CHECK (par_level >= 0),
    CONSTRAINT products_risk_valid CHECK (risk_category IN ('standard', 'perishable', 'hazardous', 'controlled'))
);

CREATE INDEX idx_products_barcode ON products(barcode) WHERE barcode IS NOT NULL;
CREATE INDEX idx_products_risk ON products(risk_category);

-- ============================================
-- VENDOR_PRODUCTS
-- SKU mapping and pricing per vendor
-- ============================================
CREATE TABLE vendor_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    vendor_sku VARCHAR(100) NOT NULL,
    current_price DECIMAL(12, 4) NOT NULL,
    stock_available INTEGER,  -- NULL = unknown
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT vendor_products_price_positive CHECK (current_price > 0),
    CONSTRAINT vendor_products_stock_non_negative CHECK (stock_available IS NULL OR stock_available >= 0),
    UNIQUE(vendor_id, product_id),
    UNIQUE(vendor_id, vendor_sku)
);

CREATE INDEX idx_vendor_products_vendor ON vendor_products(vendor_id);
CREATE INDEX idx_vendor_products_product ON vendor_products(product_id);

-- ============================================
-- INVENTORY_SNAPSHOTS
-- Timestamped scan records with provenance
-- ============================================
CREATE TABLE inventory_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    confidence_score DECIMAL(5, 4),  -- 0.0000 to 1.0000
    scanned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scanned_by VARCHAR(100) NOT NULL DEFAULT 'bishop',  -- 'bishop' or user identifier
    scan_method VARCHAR(50) NOT NULL DEFAULT 'manual',  -- manual, barcode, silhouette, volumetric
    location_tag VARCHAR(255),
    
    CONSTRAINT snapshots_quantity_non_negative CHECK (quantity >= 0),
    CONSTRAINT snapshots_confidence_range CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
    CONSTRAINT snapshots_method_valid CHECK (scan_method IN ('manual', 'barcode', 'silhouette', 'volumetric'))
);

CREATE INDEX idx_snapshots_product ON inventory_snapshots(product_id);
CREATE INDEX idx_snapshots_scanned_at ON inventory_snapshots(scanned_at DESC);
CREATE INDEX idx_snapshots_scanned_by ON inventory_snapshots(scanned_by);

-- ============================================
-- ORDERS (Extended for Vendor Bridge)
-- ============================================
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    status VARCHAR(50) NOT NULL DEFAULT 'queued',  -- queued, submitted, confirmed, delivered, cancelled, blocked
    total_amount DECIMAL(12, 4),
    blocked_reason VARCHAR(255),  -- populated if status = blocked
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT orders_status_valid CHECK (status IN ('queued', 'submitted', 'confirmed', 'delivered', 'cancelled', 'blocked'))
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    vendor_product_id UUID REFERENCES vendor_products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(12, 4) NOT NULL,
    
    CONSTRAINT order_items_quantity_positive CHECK (quantity > 0)
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_vendor ON orders(vendor_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);

-- ============================================
-- BISHOP_STATE_LOG
-- FSM state transition audit trail
-- ============================================
CREATE TABLE bishop_state_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    previous_state VARCHAR(50),
    current_state VARCHAR(50) NOT NULL,
    trigger_event VARCHAR(100) NOT NULL,
    context_data JSONB,
    output_message TEXT,
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT bishop_state_valid CHECK (current_state IN ('IDLE', 'SCANNING', 'ANALYZING_RISK', 'CHECKING_FUNDS', 'ORDER_QUEUED'))
);

CREATE INDEX idx_bishop_log_state ON bishop_state_log(current_state);
CREATE INDEX idx_bishop_log_time ON bishop_state_log(logged_at DESC);
