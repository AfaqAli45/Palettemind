import os
import math
import joblib
import numpy as np
import pandas as pd

from app.palette_generator import generate_palette, create_features
from app.database import likes_collection, dislikes_collection

MODEL_PATH = os.getenv("MODEL_PATH", "Artifacts/model.pkl")
model = joblib.load(MODEL_PATH)


def _pivot_xyz(value: float) -> float:
    if value > 0.206893:
        return value ** 3
    return (value - 16 / 116) / 7.787


def lab_to_hex_fast(lab):
    L, a_value, b_value = lab

    y = (L + 16) / 116
    x = a_value / 500 + y
    z = y - b_value / 200

    x = 95.047 * _pivot_xyz(x)
    y = 100.000 * _pivot_xyz(y)
    z = 108.883 * _pivot_xyz(z)

    x /= 100
    y /= 100
    z /= 100

    r = x * 3.2406 + y * -1.5372 + z * -0.4986
    g = x * -0.9689 + y * 1.8758 + z * 0.0415
    b = x * 0.0557 + y * -0.2040 + z * 1.0570

    def gamma_correct(c):
        if c > 0.0031308:
            return 1.055 * (c ** (1 / 2.4)) - 0.055
        return 12.92 * c

    r = max(0, min(255, int(round(gamma_correct(r) * 255))))
    g = max(0, min(255, int(round(gamma_correct(g) * 255))))
    b = max(0, min(255, int(round(gamma_correct(b) * 255))))

    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def color_distance(hex_a: str, hex_b: str) -> float:
    a = hex_to_rgb(hex_a)
    b = hex_to_rgb(hex_b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def palette_similarity(candidate_palette, liked_palette) -> float:
    distances = []
    for color in candidate_palette:
        min_distance = min(color_distance(color, liked) for liked in liked_palette)
        distances.append(min_distance)

    avg_distance = float(np.mean(distances))
    similarity = 1 - min(avg_distance / 441.67295593, 1)
    return similarity


def apply_user_history_bonus(palettes, scores, user_id):
    if not user_id or likes_collection is None:
        return scores

    liked_docs = list(likes_collection.find({"user_id": user_id}))
    disliked_docs = list(dislikes_collection.find({"user_id": user_id})) if dislikes_collection is not None else []

    liked_palettes = [doc.get("palette", []) for doc in liked_docs if doc.get("palette")]
    disliked_palettes = [doc.get("palette", []) for doc in disliked_docs if doc.get("palette")]

    if not liked_palettes and not disliked_palettes:
        return scores

    adjusted_scores = []
    for palette, score in zip(palettes, scores):
        candidate_hex = [lab_to_hex_fast(c) for c in palette]
        bonus = 0.0

        if liked_palettes:
            best_like_similarity = max(palette_similarity(candidate_hex, liked) for liked in liked_palettes)
            bonus += 0.35 * best_like_similarity

        if disliked_palettes:
            worst_dislike_similarity = max(palette_similarity(candidate_hex, disliked) for disliked in disliked_palettes)
            bonus -= 0.20 * worst_dislike_similarity

        adjusted_scores.append(score + bonus)

    return np.array(adjusted_scores)


def apply_preferences_batch(palettes, scores, style, temperature, brightness):
    adjusted_scores = []

    for palette, score in zip(palettes, scores):
        L_values = palette[:, 0]
        chroma = np.sqrt((palette[:, 1] ** 2) + (palette[:, 2] ** 2))
        warmth = np.mean(palette[:, 1] + palette[:, 2])
        avg_lightness = float(np.mean(L_values))
        avg_chroma = float(np.mean(chroma))

        bonus = 0.0

        if style == "vibrant":
            bonus += avg_chroma / 180
        elif style == "pastel":
            bonus += (avg_lightness / 100) * 0.20
            bonus += max(0.0, 1 - (avg_chroma / 120)) * 0.20
        elif style == "minimal":
            bonus += max(0.0, 1 - np.std(L_values) / 40) * 0.18

        if temperature == "warm":
            bonus += max(0.0, warmth / 160) * 0.20
        elif temperature == "cool":
            bonus += max(0.0, -warmth / 160) * 0.20

        if brightness == "bright":
            bonus += (avg_lightness / 100) * 0.20
        elif brightness == "dark":
            bonus += max(0.0, (100 - avg_lightness) / 100) * 0.20

        adjusted_scores.append(score + bonus)

    return np.array(adjusted_scores)


def generate_best_palettes(
    n_return=5,
    n_samples=None,
    style="vibrant",
    temperature="any",
    brightness="any",
    user_id=None
):
    if n_samples is None:
        n_samples = min(max(n_return * 8, 40), 100)

    palettes = [generate_palette() for _ in range(n_samples)]
    features = [create_features(palette) for palette in palettes]

    actual_count = len(features[0]) if features else 0
    expected_count = (
        len(model.feature_names_in_)
        if hasattr(model, "feature_names_in_")
        else actual_count
    )

    if actual_count != expected_count:
        raise ValueError(
            f"Feature mismatch: model expects {expected_count}, "
            f"but create_features() returned {actual_count}. "
            f"Either align create_features() or retrain model.pkl."
        )

    if hasattr(model, "feature_names_in_"):
        df = pd.DataFrame(features, columns=model.feature_names_in_)
    else:
        df = pd.DataFrame(features)

    scores = model.predict(df)
    scores = apply_preferences_batch(palettes, scores, style, temperature, brightness)
    scores = apply_user_history_bonus(palettes, scores, user_id)

    top_indices = np.argsort(scores)[::-1][:n_return]

    top_palettes = []
    top_scores = []

    for index in top_indices:
        hex_palette = [lab_to_hex_fast(color) for color in palettes[index]]
        top_palettes.append(hex_palette)
        top_scores.append(float(scores[index]))

    return top_palettes, top_scores
