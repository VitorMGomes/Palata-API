from pydantic import BaseModel
from typing import Optional

class IngredientEN(BaseModel):
    id: int
    name: str
    amount: Optional[float] = None
    unit: Optional[str] = None
    original: Optional[str] = None

class RecipeListItemEN(BaseModel):
    id: int
    title: str
    image: str

class RecipeDetailEN(BaseModel):
    id: int
    title: str
    image: str
    summary: str | None = None
    instructions: str | None = None
    sourceUrl: str | None = None
    readyInMinutes: int | None = None
    servings: int | None = None
