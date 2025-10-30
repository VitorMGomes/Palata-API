from fastapi import FastAPI, Query
from typing import List
from src.clients.spoonacular import find_by_ingredients, get_recipe_information
from src.clients.openai_client import translate_recipe_fields, translate_spoonacular_like_strict
from src.utils.translate import strip_html
from src.schemas.recipe_pt import ReceitaPT

app = FastAPI(title="Agente Spoonacular PT-BR (OpenAI)")

@app.get("/recipes/by-ingredients", response_model=List[ReceitaPT])
async def recipes_by_ingredients(
    ingredients: List[str] = Query(..., description="Lista de ingredientes (PT ou EN)"),
    number: int = Query(2, ge=1, le=10),
    ranking: int = Query(1, ge=1, le=2),
    ignore_pantry: bool = Query(True),
):
    """
    Endpoint principal — retorna receitas traduzidas e resumidas.
    Traduz título, resumo e instruções via OpenAI.
    """
    items = await find_by_ingredients(ingredients, number=number, ranking=ranking, ignore_pantry=ignore_pantry)

    results: list[ReceitaPT] = []
    for it in items:
        detail = await get_recipe_information(it["id"])

        # limpa HTML do summary/instructions antes de traduzir
        if detail.get("summary"):
            detail["summary"] = strip_html(detail["summary"])
        if detail.get("instructions"):
            detail["instructions"] = strip_html(detail["instructions"])

        # tradução direta dos campos principais
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


@app.get("/recipes/findByIngredients-pt")
async def recipes_full_structured_translation(
    ingredients: List[str] = Query(..., description="Lista de ingredientes (PT ou EN)"),
    number: int = Query(2, ge=1, le=10),
    ranking: int = Query(1, ge=1, le=2),
    ignore_pantry: bool = Query(True),
):
    """
    Endpoint espelho do Spoonacular → mesma estrutura JSON original,
    mas com todos os textos traduzidos para PT-BR.
    """
    raw = await find_by_ingredients(ingredients, number=number, ranking=ranking, ignore_pantry=ignore_pantry)
    translated = await translate_spoonacular_like_strict(raw)
    return translated


@app.get("/usage")
def get_token_usage():
    """Consulta o uso de tokens acumulado (para monitorar custo)."""
    from src.clients.openai_client import get_usage
    return get_usage()
