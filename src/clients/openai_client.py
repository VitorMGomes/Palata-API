import json, random, re, time
from typing import Any, Dict, List, Optional
from collections import OrderedDict
from openai import OpenAI
from src.config import (
    OPENAI_API_KEY, OPENAI_MODEL, OPENAI_FALLBACK_MODEL,
    TRANSLATION_ENABLED, MAX_TRANSLATION_CHARS
)

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== PREÇOS (USD por 1.000 tokens) ======
OPENAI_PRICES = {
    "gpt-4o-mini":  {"input": 0.00015, "output": 0.00060},
    "gpt-4.1-mini": {"input": 0.00020, "output": 0.00080},
    # acrescente outros modelos se usar
}

# ====== CONTADORES GLOBAIS ======
TOKEN_USAGE = {"input": 0, "output": 0, "cost": 0.0}

def get_usage() -> Dict[str, float]:
    return {
        "input_tokens": TOKEN_USAGE["input"],
        "output_tokens": TOKEN_USAGE["output"],
        "cost_usd": round(TOKEN_USAGE["cost"], 6),
    }

def reset_usage() -> None:
    TOKEN_USAGE.update({"input": 0, "output": 0, "cost": 0.0})

# ====== HELPERS ======
def _extract_text(msg_content) -> str:
    if msg_content is None:
        return ""
    if isinstance(msg_content, str):
        return msg_content
    if isinstance(msg_content, list):
        parts = []
        for p in msg_content:
            txt = getattr(p, "text", None)
            if txt and hasattr(txt, "value"):
                parts.append(txt.value)
            elif isinstance(p, dict):
                parts.append(p.get("text") or "")
        return "".join(parts)
    return str(msg_content)

def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "…"

def _price_for(model: str) -> Dict[str, float]:
    return OPENAI_PRICES.get(model, {"input": 0.0, "output": 0.0})

def _strip_md_fences(s: str) -> str:
    """Remove cercas ```json ... ``` ou ``` ... ``` do modelo."""
    s = s.strip()
    s = re.sub(r"^\s*```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()

# ====== CORE ======
def _chat_with_retry(
    messages: List[Dict[str, Any]],
    model: str,
    temperature: float = 0.0,
    max_retries: int = 4,
) -> str:
    """Chama a API com retries; coleta tokens/custo; faz fallback no último retry."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )

            # --- Estatísticas de uso ---
            usage = getattr(resp, "usage", None)
            if usage:
                input_toks = getattr(usage, "prompt_tokens", 0) or 0
                output_toks = getattr(usage, "completion_tokens", 0) or 0
                prices = _price_for(model)
                cost = (input_toks * prices["input"] + output_toks * prices["output"]) / 1000.0

                TOKEN_USAGE["input"] += input_toks
                TOKEN_USAGE["output"] += output_toks
                TOKEN_USAGE["cost"]  += cost

                total_toks = input_toks + output_toks
                print(f"[TOKENS] {model}: +{total_toks} (in={input_toks}, out={output_toks}) | "
                      f"Custo ≈ ${cost:.5f} | Total ≈ ${TOKEN_USAGE['cost']:.4f}")

            content = resp.choices[0].message.content
            return _extract_text(content)

        except Exception as e:
            sleep_s = (2 ** (attempt - 1)) + random.random()
            print(f"[OpenAI] erro '{type(e).__name__}' (tentativa {attempt}) → aguardando {sleep_s:.1f}s")
            if attempt == max_retries and model != OPENAI_FALLBACK_MODEL:
                print(f"[OpenAI] trocando para fallback: {OPENAI_FALLBACK_MODEL}")
                model = OPENAI_FALLBACK_MODEL
            time.sleep(sleep_s)

    raise RuntimeError("Falha ao completar com OpenAI após retries.")

def _responses_with_retry(messages: List[Dict[str, Any]], *, temperature: float = 0.0) -> str:
    """Wrapper padrão usando o modelo principal configurado."""
    return _chat_with_retry(messages=messages, model=OPENAI_MODEL, temperature=temperature)

# ====== API DE TRADUÇÃO ======
async def translate_text(text: str) -> str:
    if not TRANSLATION_ENABLED:
        return text
    t = _truncate(text, MAX_TRANSLATION_CHARS)
    sys = "Traduza para PT-BR mantendo medidas e nomes próprios. Responda apenas com o texto traduzido."
    out = _chat_with_retry(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": t},
        ],
    )
    return out.strip()

async def translate_recipe_fields(detail: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Tradução em uma chamada → {titulo,resumo,instrucoes}."""
    title = detail.get("title") or ""
    summary = detail.get("summary") or ""
    instructions = detail.get("instructions") or ""

    if not TRANSLATION_ENABLED:
        return {"titulo": title, "resumo": summary, "instrucoes": instructions}

    sys = (
        "Traduza os campos da receita para PT-BR. "
        "Retorne APENAS um JSON com as chaves 'titulo', 'resumo' e 'instrucoes'. "
        "Não inclua comentários nem texto fora do JSON."
    )
    user_payload = {
        "title": _truncate(title, MAX_TRANSLATION_CHARS),
        "summary": _truncate(summary, MAX_TRANSLATION_CHARS),
        "instructions": _truncate(instructions, MAX_TRANSLATION_CHARS),
    }

    raw = _chat_with_retry(
        model=OPENAI_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    ).strip()

    print("\n=== RAW OPENAI RESPONSE ===")
    print(raw[:1200])
    print("===========================\n")

    cleaned = _strip_md_fences(raw)

    # 1) JSON puro
    try:
        data = json.loads(cleaned)
    except Exception:
        # 2) chave:valor por linha OU texto corrido
        data = {}
        for line in cleaned.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip().lower()] = v.strip()
        if not data:
            data = {"resumo": cleaned}

    def pick(d: dict, *keys: str) -> Optional[str]:
        for k in keys:
            if k in d and d[k]:
                return str(d[k]).strip()
        return None

    return {
        "titulo": pick(data, "titulo", "título") or title,
        "resumo": pick(data, "resumo") or summary,
        "instrucoes": pick(data, "instrucoes", "instruções") or instructions,
    }

# ====== LÓGICA DE TRADUÇÃO ESTRUTURAL (STRICT) ======
def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")

def _is_image_like(s: str) -> bool:
    s2 = s.lower()
    return any(s2.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"))

async def _translate_batch(strings: list[str]) -> list[str]:
    """Traduz uma lista de strings mantendo a ordem. Retorna lista do mesmo tamanho."""
    if not strings:
        return []
    messages = [
        {
            "role": "system",
            "content": (
                "Você receberá um array JSON de strings. Traduza cada item para PT-BR e "
                "retorne APENAS um array JSON com o MESMO número de itens, na MESMA ordem. "
                "Não use markdown. Mantenha nomes próprios; traduza unidades culinárias."
            ),
        },
        {"role": "user", "content": json.dumps(strings, ensure_ascii=False)},
    ]
    raw = _responses_with_retry(messages)
    cleaned = _strip_md_fences(raw)
    try:
        arr = json.loads(cleaned)
        if isinstance(arr, list) and len(arr) == len(strings):
            return [("" if x is None else str(x)).strip() for x in arr]
    except Exception:
        pass
    return strings  # fallback seguro

async def translate_spoonacular_like_strict(obj: Any) -> Any:
    """
    Preserva a estrutura 1:1 do Spoonacular e traduz SOMENTE valores textuais relevantes.
    Mantém ordem das chaves e não altera tipos (ids, números, URLs, etc.).
    """
    TRANSLATABLE_KEYS = {
        "title", "name", "original", "originalName", "extendedName",
        "aisle", "unitLong", "unitShort", "consistency", "summary", "instructions"
    }

    # 1) coletar caminhos + textos
    paths: list[tuple] = []
    texts: list[str] = []

    def walk_collect(node: Any, path: tuple):
        if isinstance(node, dict):
            for k in node.keys():
                v = node[k]
                if isinstance(v, str) and (k in TRANSLATABLE_KEYS or k.lower() in TRANSLATABLE_KEYS):
                    if not _is_url(v) and not _is_image_like(v):
                        paths.append(path + (k,))
                        texts.append(v)
                walk_collect(v, path + (k,))
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk_collect(item, path + (i,))

    walk_collect(obj, ())

    # 2) traduzir em lote
    translated = await _translate_batch(texts)
    it = iter(translated)

    # 3) aplicar de volta preservando ordem
    def walk_apply(node: Any, path: tuple) -> Any:
        if isinstance(node, dict):
            out = OrderedDict()
            for k, v in node.items():
                if isinstance(v, str) and (k in TRANSLATABLE_KEYS or k.lower() in TRANSLATABLE_KEYS):
                    if not _is_url(v) and not _is_image_like(v):
                        out[k] = next(it)
                    else:
                        out[k] = v
                else:
                    out[k] = walk_apply(v, path + (k,))
            return out
        elif isinstance(node, list):
            return [walk_apply(x, path + (i,)) for i, x in enumerate(node)]
        else:
            return node

    return walk_apply(obj, ())
