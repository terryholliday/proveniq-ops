# PROVENIQ OPS Backend

FastAPI backend for the PROVENIQ OPS Landlord Vector system.

## Overview

This backend implements the "Landlord Vector" - a zero-CAC user acquisition strategy where landlords mandate the app for tenants, creating a viral growth engine.

## Features

### Landlord Endpoints (`/landlord`)
- **Property Management**: Create/manage properties and units
- **CSV Tenant Upload**: Bulk onboard tenants via CSV
- **Inspection Diff Engine**: AI-powered move-in vs move-out comparison
- **Default Checklists**: Configure inspection checklists per property

### Tenant Endpoints (`/tenant`)
- **Inspections**: Create and submit move-in/move-out reports
- **Maintenance Requests**: Submit work orders with asset context
- **Deposit Shield**: View protection score and evidence locker
- **Unit Assets**: Browse appliances for maintenance context

## Setup

### 1. Install Dependencies
```bash
cd proveniq-ops/backend
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 3. Create Database
```bash
createdb proveniq_ops
```

### 4. Run Migrations
```bash
alembic upgrade head
```

### 5. Start Server
```bash
uvicorn app.main:app --reload --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Schema

### Core Tables
- `users` - Landlords and Tenants (role determined by relationships)
- `properties` - Buildings owned by landlords
- `units` - Individual rentable units
- `leases` - Tenant-to-unit assignments
- `inspections` - Move-in/move-out condition reports
- `inspection_items` - Individual items within inspections
- `maintenance_requests` - Tenant work orders
- `inventory_items` - Assets (appliances, fixtures)

## The "Trojan Horse" Flow

1. **Landlord uploads CSV** → Creates properties, units, tenants, leases
2. **Tenant receives invite** → Downloads app for move-in inspection
3. **Tenant completes inspection** → Photos timestamped, blockchain-hashed
4. **App nudges conversion** → "Now protect YOUR stuff"
5. **Tenant keeps app** → Becomes PROVENIQ Home user

## Pricing Tiers

| Tier | Price | Target |
|------|-------|--------|
| STARTER | Free (≤20 units) | Small landlords |
| PORTFOLIO | $1.00/unit/mo | Standard |
| ENTERPRISE | $0.50/unit/mo | REITs 5k+ units |

## License

Proprietary - PROVENIQ Inc.
