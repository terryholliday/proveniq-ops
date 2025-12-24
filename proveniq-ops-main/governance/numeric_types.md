# PROVENIQ Ops - Numeric Types Contract

**No floats allowed for money or quantities.**

---

## The Rules

1. **Money**: Integer micros (1 USD = 1,000,000 micros)
2. **Quantities**: `Decimal` (serialized as string in JSON)
3. **Rates/Percentages**: `Decimal` 0-1 or 0-100 (serialized as string)
4. **Floats**: **REJECTED** - validators will raise `ValueError`

## Why Micros for Money?

```python
# Float disaster
>>> 0.1 + 0.2
0.30000000000000004

# Micros: always exact
>>> 100_000 + 200_000
300000  # $0.30 exactly
```

## Type Reference

| Type | Storage | JSON | Use Case |
|------|---------|------|----------|
| `MoneyMicros` | `int` | `integer` | All money values |
| `Quantity` | `Decimal` | `string` | Fractional quantities (2.5 lbs) |
| `IntQuantity` | `int` | `integer` | Whole units only |
| `Rate` | `Decimal` | `string` | Rates 0-1 (confidence, reliability) |
| `Percentage` | `Decimal` | `string` | Percentages 0-100 |

## Import

```python
from app.core.types import MoneyMicros, Quantity, IntQuantity, Rate, Money
```

## Usage Examples

### Money

```python
from app.core.types import MoneyMicros, Money

class Order(BaseModel):
    total_micros: MoneyMicros  # int, rejects floats

# Convert dollars to micros
price = Money.from_dollars("19.99")  # 19_990_000

# Display
display = Money.to_dollars_str(19_990_000)  # "19.99"

# Arithmetic (always exact)
total = Money.add(price, tax)
line_total = Money.multiply(unit_price, quantity)
```

### Quantity

```python
from app.core.types import Quantity, IntQuantity

class InventorySnapshot(BaseModel):
    on_hand_qty: IntQuantity  # Whole units
    weight_lbs: Quantity      # Fractional OK

# In JSON:
# { "on_hand_qty": 42, "weight_lbs": "2.5" }
```

### Rates

```python
from app.core.types import Rate

class StockoutRisk(BaseModel):
    confidence: Rate  # 0.0 to 1.0

# Rejects values outside range
# Serializes as string: "0.87"
```

## Database Mapping

| Pydantic Type | SQLAlchemy | PostgreSQL |
|---------------|------------|------------|
| `MoneyMicros` | `BigInteger` | `BIGINT` |
| `Quantity` | `Numeric(12, 4)` | `NUMERIC(12,4)` |
| `IntQuantity` | `Integer` | `INTEGER` |
| `Rate` | `Numeric(5, 4)` | `NUMERIC(5,4)` |

## Validation

All types validate on input and reject floats:

```python
# These FAIL with ValueError
MoneyMicros.validate(19.99)  # Float rejected
Quantity.validate(2.5)       # Float rejected

# These SUCCEED
MoneyMicros.validate(19990000)     # int OK
MoneyMicros.validate("19.99")      # Parsed to micros
Quantity.validate("2.5")           # string OK
Quantity.validate(Decimal("2.5"))  # Decimal OK
```

## Migration Guide

### Before (WRONG)

```python
class Order(BaseModel):
    total: float  # NO!
    price: Decimal  # Ambiguous

class Response(BaseModel):
    confidence: float  # NO!
```

### After (CORRECT)

```python
from app.core.types import MoneyMicros, Rate

class Order(BaseModel):
    total_micros: MoneyMicros  # Explicit, safe
    price_micros: MoneyMicros

class Response(BaseModel):
    confidence: Rate  # Decimal 0-1, string serialization
```

## API Contract

All money fields in API responses use `_micros` suffix:

```json
{
  "total_amount_micros": 19990000,
  "unit_price_micros": 2550000,
  "variance_value_micros": -1250000
}
```

Clients convert for display:

```typescript
const displayPrice = (micros: number) => 
  `$${(micros / 1_000_000).toFixed(2)}`;
```

---

**Remember: If you see a `float` for money or quantity, it's a bug.**
