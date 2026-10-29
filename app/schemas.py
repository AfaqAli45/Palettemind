from pydantic import BaseModel, Field
from typing import List


class Palette(BaseModel):
    colors: List[str]
    score: float


class PaletteResponse(BaseModel):
    palettes: List[List[str]]
    scores: List[float]
    personalized: bool = False


class GenerateRequest(BaseModel):
    n: int = 5
    style: str = "vibrant"
    temperature: str = "any"
    brightness: str = "any"


class FeedbackRequest(BaseModel):
    palette: List[str] = Field(..., min_length=5, max_length=5)
