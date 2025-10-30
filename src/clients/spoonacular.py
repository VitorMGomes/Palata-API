import httpx
from src.config import SPOONACULAR_API_KEY

BASE_URL = "https://api.spoonacular.com"

async def find_by_ingredients(ingredients: list[str], number: int = 5, ranking: int = 1, ignore_pantry: bool = True):
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "ingredients": ",".join(ingredients),
        "number": number,
        "ranking": ranking,
        "ignorePantry": str(ignore_pantry).lower(),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{BASE_URL}/recipes/findByIngredients", params=params)
        r.raise_for_status()
        return r.json()

async def get_recipe_information(recipe_id: int):
    params = {"apiKey": SPOONACULAR_API_KEY, "includeNutrition": "false"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{BASE_URL}/recipes/{recipe_id}/information", params=params)
        r.raise_for_status()
        return r.json()
