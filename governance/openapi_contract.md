# PROVENIQ Ops - OpenAPI Contract

**OpenAPI is the single source of truth.**

If it's not in `/openapi.json`, it doesn't exist.

---

## The Rule

All API consumers (mobile, web, integrations) MUST use the OpenAPI specification for:

1. **Code Generation** — Generate typed clients from spec
2. **Contract Validation** — Validate requests/responses against schema
3. **Documentation** — Auto-generate docs from spec
4. **Testing** — Generate test cases from spec

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/openapi.json` | Raw OpenAPI 3.1 specification |
| `/docs` | Swagger UI (interactive) |
| `/redoc` | ReDoc (readable) |
| `/api/v1/openapi/export` | Programmatic spec export |
| `/api/v1/openapi/endpoints` | List all registered endpoints |

## Client Generation

### TypeScript (Mobile/Web)

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```

### Python

```bash
openapi-python-client generate --url http://localhost:8000/openapi.json
```

### Swift (iOS)

```bash
swagger-codegen generate -i http://localhost:8000/openapi.json -l swift5 -o ./ProveniqClient
```

## Versioning

- API version is in the path: `/api/v1/...`
- Version bumps follow semver
- Breaking changes = major version bump
- Old versions deprecated with 90-day notice
- Deprecation marked in OpenAPI spec with `deprecated: true`

## Adding New Endpoints

1. **Define Pydantic models first** — Request/Response schemas
2. **Add endpoint with full documentation** — Summary, description, examples
3. **Tag appropriately** — Use existing tags or propose new ones
4. **Verify in /docs** — Check Swagger UI renders correctly
5. **Export and commit spec** — `curl localhost:8000/openapi.json > docs/openapi.json`

## Response Models

All endpoints MUST have typed response models:

```python
from pydantic import BaseModel

class StockoutAlert(BaseModel):
    """Stockout risk alert from Bishop."""
    alert_type: str
    product_id: UUID
    confidence: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "PREDICTIVE_STOCKOUT",
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "confidence": 0.87,
            }
        }

@router.get("/alerts", response_model=list[StockoutAlert])
async def get_alerts() -> list[StockoutAlert]:
    ...
```

## Validation

Before deployment, validate:

1. **Schema completeness** — All endpoints have request/response models
2. **Examples present** — All models have realistic examples
3. **Tags assigned** — All endpoints are tagged
4. **No undocumented endpoints** — Every route appears in spec

```bash
# Check for undocumented endpoints
curl -s localhost:8000/api/v1/openapi/endpoints | jq '.endpoints[] | select(.tags | length == 0)'
```

## Integration Testing

Generate tests from OpenAPI spec:

```python
from schemathesis import from_uri

schema = from_uri("http://localhost:8000/openapi.json")

@schema.parametrize()
def test_api(case):
    response = case.call()
    case.validate_response(response)
```

---

**Remember: If it's not in OpenAPI, it doesn't exist.**
