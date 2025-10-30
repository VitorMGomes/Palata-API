from fastapi import FastAPI, Query
from typing import List
from src.clients.spoonacular import find_by_ingredients, get_recipe_information
from src.clients.openai_client import translate_recipe_fields, get_usage
from src.utils.translate import strip_html
from src.schemas.recipe_pt import ReceitaPT

app = FastAPI(title="Spoonacular PT-BR (OpenAI)")

@app.get("/recipes/by-ingredients", response_model=List[ReceitaPT])
async def recipes_by_ingredients(
    ingredients: List[str] = Query(..., description="Ingredientes (EN/PT)"),
    number: int = Query(2, ge=1, le=10),
    ranking: int = Query(1, ge=1, le=2),
    ignore_pantry: bool = Query(True),
):
    items = await find_by_ingredients(ingredients, number=number, ranking=ranking, ignore_pantry=ignore_pantry)

    results: list[ReceitaPT] = []
    for it in items:
        detail = await get_recipe_information(it["id"])
        if detail.get("summary"):
            detail["summary"] = strip_html(detail["summary"])
        if detail.get("instructions"):
            detail["instructions"] = strip_html(detail["instructions"])

        pt = await translate_recipe_fields(detail)

        results.append(
            ReceitaPT(
                id=detail["id"],
                titulo=pt.get("titulo") or detail.get("title", ""),
                imagem=detail.get("image", ""),
                resumo=pt.get("resumo"),
                instrucoes=pt.get("instrucoes"),
                url_fonte=detail.get("sourceUrl"),
                pronto_em_minutos=detail.get("readyInMinutes"),
                porcoes=detail.get("servings"),
            )
        )
    return results

@app.get("/usage")
async def usage():
    """Retorna tokens e custo acumulados desde que o servidor iniciou."""
    return get_usage()
