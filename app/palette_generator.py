import numpy as np


def generate_palette():
    palette = np.zeros((5, 3))

    base_lightness = np.random.uniform(35, 75)
    base_a = np.random.uniform(-25, 25)
    base_b = np.random.uniform(-25, 25)

    for i in range(5):
        L = np.clip(np.random.normal(base_lightness, 12), 20, 90)
        a = np.clip(np.random.normal(base_a, 28), -80, 80)
        b = np.clip(np.random.normal(base_b, 28), -80, 80)
        palette[i] = [L, a, b]

    return palette


def create_features(palette):
    # 5 colors × 3 LAB channels = 15 features
    features = palette.flatten().tolist()

    L_vals = palette[:, 0]
    a_vals = palette[:, 1]
    b_vals = palette[:, 2]
    chroma = np.sqrt(a_vals ** 2 + b_vals ** 2)

    # 3 summary features → total = 18 ✅ matches your model
    features.extend([
        float(np.mean(L_vals)),
        float(np.std(L_vals)),
        float(np.mean(chroma))
    ])

    return features
