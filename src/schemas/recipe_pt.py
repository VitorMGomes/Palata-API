from pydantic import BaseModel
from typing import Optional

class ReceitaPT(BaseModel):
    id: int
    titulo: str
    imagem: str
    resumo: Optional[str] = None
    instrucoes: Optional[str] = None
    url_fonte: Optional[str] = None
    pronto_em_minutos: Optional[int] = None
    porcoes: Optional[int] = None
