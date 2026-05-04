"""Routes du module sales."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def placeholder() -> dict[str, str]:
    """Placeholder. À remplacer lors de l'implémentation."""
    return {"module": "sales", "status": "to_be_implemented"}
