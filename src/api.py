from typing import List
import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from src.clients.spoonacular import (
    find_by_ingredients,
    get_recipe_information,
)
from src.clients.openai_client import (
    translate_recipe_fields,
    translate_spoonacular_like_strict,
    translate_ingredients_pt_to_en,
    get_usage as get_openai_usage,
)
from src.utils.translate import strip_html
from src.schemas.recipe_pt import ReceitaPT


app = FastAPI(title="Palata API • Spoonacular PT-BR (OpenAI)")

# ---------- CORS (libera para app/emulador) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restrinja para domínios do app, se quiser
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Favicon opcional ----------
FAVICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "favicon.ico")

@app.get("/favicon.ico")
async def favicon():
    if os.path.exists(FAVICON_PATH):
        return FileResponse(FAVICON_PATH)
    return Response(status_code=204)


# =====================================================
# 1) Versão RESUMIDA em PT-BR (nosso schema ReceitaPT)
#    - Busca por ingredientes
#    - Para cada ID, carrega os detalhes e traduz título/resumo/instruções
# =====================================================
@app.get("/recipes/by-ingredients", response_model=List[ReceitaPT])
async def recipes_by_ingredients(
    ingredients: List[str] = Query(..., description="Lista de ingredientes (PT ou EN)"),
    number: int = Query(2, ge=1, le=10),
    ranking: int = Query(1, ge=1, le=2),
    ignore_pantry: bool = Query(True),
):
    # traduz PT->EN para a busca na Spoonacular (melhora recall)
    ingredients_en = await translate_ingredients_pt_to_en(ingredients)

    items = await find_by_ingredients(
        ingredients_en, number=number, ranking=ranking, ignore_pantry=ignore_pantry
    )

    results: list[ReceitaPT] = []
    for it in items:
        detail = await get_recipe_information(it["id"])

        # limpa HTML antes de traduzir (economiza tokens e ruído)
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


# =====================================================
# 2) Espelho do Spoonacular em PT (mesma estrutura)
#    - findByIngredients equivalente em PT
# =====================================================
@app.get("/recipes/findByIngredients-pt")
async def recipes_full_structured_translation(
    ingredients: List[str] = Query(..., description="Lista de ingredientes (PT ou EN)"),
    number: int = Query(2, ge=1, le=50),
    ranking: int = Query(1, ge=1, le=2),
    ignore_pantry: bool = Query(True),
):
    ingredients_en = await translate_ingredients_pt_to_en(ingredients)

    raw = await find_by_ingredients(
        ingredients_en, number=number, ranking=ranking, ignore_pantry=ignore_pantry
    )
    translated = await translate_spoonacular_like_strict(raw)
    return translated


# =====================================================
# 3) Detalhes por ID (mesmo schema do Spoonacular) em PT
#    - compatível com o app móvel: /recipes/{id}/information
# =====================================================
@app.get("/recipes/{recipe_id}/information")
async def recipe_information_pt(recipe_id: int):
    raw = await get_recipe_information(recipe_id)
    translated = await translate_spoonacular_like_strict(raw)
    return translated


# =====================================================
# 4) Telemetria de tokens/custo (para monitorar os US$ 8)
# =====================================================
@app.get("/usage")
def usage():
    return get_openai_usage()
