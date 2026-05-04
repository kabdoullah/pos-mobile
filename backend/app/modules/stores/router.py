"""Routes du module stores."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def placeholder() -> dict[str, str]:
    """Placeholder. À remplacer lors de l'implémentation."""
    return {"module": "stores", "status": "to_be_implemented"}
