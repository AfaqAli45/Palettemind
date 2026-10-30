# PaletteMind — AI Color Palette Generator

An intelligent color-palette generator that **learns what makes a palette good** instead of
picking random colors. A gradient-boosted regression model scores thousands of candidate
palettes per request and returns only the best ones — with optional per-user personalization
driven by the palettes you like and dislike.

> Final Year Project — Machine Learning + FastAPI web application
> **Author:** [AFAQ ALI] · **Institution:** [Government College University Faisalabad (GCUF), Pakistan] · **Year:** 2026

---

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [How It Works](#how-it-works)
4. [Model & Data Pipeline](#model--data-pipeline)
5. [Tech Stack](#tech-stack)
6. [Project Structure](#project-structure)
7. [Getting Started](#getting-started)
8. [Environment Variables](#environment-variables)
9. [API Reference](#api-reference)
10. [Design Decisions](#design-decisions)
11. [Known Limitations & Roadmap](#known-limitations--roadmap)
12. [License](#license)

---

## Overview

Most "color palette generators" are just random number generators with a pretty UI.
PaletteMind instead treats palette quality as a **supervised regression problem**:

1. Every palette is represented in **CIELAB color space**, where Euclidean distance is
   perceptually meaningful (unlike raw RGB).
2. Candidate palettes are sampled from **50 KMeans clusters** of real-world colors.
3. Each candidate is **labelled with a contrast rank (1–5)**, derived from the mean pairwise
   perceptual distance between its five colors.
4. A **LightGBM regressor** learns to predict that rank from the palette's LAB features.
5. At request time, 40–100 palettes are generated, scored by the model, re-ranked by
   user preferences and feedback history, and the top-N are returned as hex codes.

The result: palettes that are not only visually harmonious, but **ranked**.

---

## Features

### 🎨 Palette generation
- Generate **1–15 palettes at once**, each with 5 hex colors.
- One-click **copy-to-clipboard** for any hex value.
- Each result shows its **AI quality score**.

### ⚡ Guest mode vs. member mode
| Capability | Guest | Member |
|---|---|---|
| Generate palettes | ✅ | ✅ |
| Copy hex codes | ✅ | ✅ |
| Style / temperature / brightness controls | ❌ | ✅ |
| Like / dislike feedback | ❌ | ✅ |
| Personalization from feedback history | ❌ | ✅ |

### 🧠 Preference controls (members only)
- **Style** — `vibrant` (high chroma), `pastel` (light + low chroma), `minimal` (low lightness variance)
- **Temperature** — `warm` / `cool` / `any` (derived from the LAB **a\* + b\*** axis)
- **Brightness** — `bright` / `dark` / `any` (derived from mean **L\***)

### ❤️ Feedback learning
- **Like** a palette → stored in MongoDB and worth **+0.35 × similarity** on future scores.
- **Dislike** a palette → worth **−0.20 × similarity**.
- Similarity is computed as normalized minimum-cost color matching (Hungarian-style greedy
  matching) between hex palettes, so near-duplicates inherit the same preference.
- Liking and disliking are **mutually exclusive** — liking a palette you previously disliked
  removes the dislike, and vice versa.

### 🔐 Authentication
- Email + password registration/login, **bcrypt** password hashing.
- Stateless sessions via **signed, time-limited cookies** (`itsdangerous`), HTTP-only + `SameSite=Lax`.
- 7-day session lifetime.

---

## How It Works

Copy
Browser (index.html + script.js + style_1.css) │ fetch /generate?n=&style=&temp=&bright= ▼ FastAPI app/main.py ──► app/auth.py (identify the session user) │ ├──► app/inference.py │ ├── sample N palettes app/palette_generator.py │ ├── build feature vector app/palette_generator.create_features() │ ├── model.predict(scores) Artifacts/model.pkl (LightGBM) │ ├── + preference bonus apply_preferences_batch() │ └── + history bonus apply_user_history_bonus() │ ├──► LAB → sRGB → hex conversion lab_to_hex_fast() └──► log the request app/database.py (MongoDB) ▼ Top-N palettes + scores returned as JSON

Copy
### Scoring formula

final_score = model.predict(features) + style_bonus + temperature_bonus + brightness_bonus (preference layer) + 0.35 · max_similarity_to_liked_palettes (history layer) − 0.20 · max_similarity_to_disliked_palettes (history layer)

Copy
The two bonus layers are **additive re-rankings** on top of the ML prediction — the model
decides "is this palette good?", the preference layer decides "is this palette good *for you*?".

---

## Model & Data Pipeline

### Stage 1 — Dataset construction (`src/`)
| Step | What happens |
|---|---|
| 1 | Load a ~100k-row CSV of real-world hex codes. |
| 2 | Convert every hex → **CIELAB** (`skimage.color.rgb2lab`), so distances are perceptual. |
| 3 | **KMeans clustering** (`k = 50`) over the LAB colors → a dictionary of 50 color clusters. |
| 4 | Sample candidate palettes in three contrast modes: **low** (all 5 from one cluster), **medium** (3 clusters + fill), **high** (5 distinct clusters). |
| 5 | Compute pairwise perceptual distances → **mean / min / max contrast**. |
| 6 | **Assign a rank 1–5** from mean contrast (>50 → 5, >40 → 4, >30 → 3, >20 → 2, else 1). |
| 7 | Build the feature vector, deduplicate with an **MD5 hash** of the rounded palette, and write balanced batches (4,000 samples per rank class) to CSV. |
| 8 | Concatenate the batch CSVs into one training set. |

### Stage 2 — Training (`Artifacts/`)
A **LightGBM** regressor is trained on the labelled features to predict the contrast rank.
The fitted pipeline (scaler + model) is serialized with `joblib` to `Artifacts/model.pkl`;
evaluation output is stored in `Artifacts/metrics.json`.

### Stage 3 — Inference (`app/inference.py`)
40–100 candidate palettes per request → model scores → preference re-ranking → history
re-ranking → `argsort` → top-N converted back to hex via a vectorized LAB→sRGB→hex routine.

### ⚠️ Feature-vector contract
`app/inference.py` validates the feature count at runtime and raises a descriptive
`ValueError` if `create_features()` disagrees with the loaded model, so a retrained model
can never silently serve wrong predictions. Keep the feature builder in
`src/feature_builder.py` and `app/palette_generator.create_features()` in sync — **the
two must produce the exact same columns in the exact same order.**

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.10+ |
| **ML** | LightGBM, scikit-learn, scikit-image, NumPy, pandas |
| **Clustering** | scikit-learn `KMeans` (k=50, LAB space) |
| **Serialization** | joblib |
| **Web framework** | FastAPI + Uvicorn |
| **Templating** | Jinja2 |
| **Database** | MongoDB (PyMongo) — users, likes, dislikes, generation log |
| **Auth** | passlib/bcrypt, itsdangerous signed cookies |
| **Frontend** | Vanilla HTML/CSS/JS (no framework, no build step) |
| **Visualization (offline)** | Matplotlib |

---

## Project Structure

Copy
palettemind/ │ ├── app/ # FastAPI application package │ ├── init.py │ ├── main.py # App entry point + all HTTP routes │ ├── auth.py # Register / login / logout / session cookies │ ├── database.py # MongoDB connection, collections, indexes │ ├── inference.py # Model loading, scoring, preference + history re-ranking │ ├── palette_generator.py # LAB sampling, feature builder, LAB→hex conversion │ └── schemas.py # Pydantic request/response models │ ├── Artifacts/ # Trained model + evaluation output │ ├── model.pkl # Serializated LightGBM model (Git LFS recommended) │ └── metrics.json # Training/evaluation metrics │ ├── src/ # Offline ML scripts (not imported by the API) │ └── feature_builder.py # Canonical feature vector definition │ ├── static/ # Frontend assets served at /static │ ├── script.js # Auth, generation, feedback, liked-palettes logic │ └── style_1.css # Glassmorphism dark theme │ ├── templates/ │ └── index.html # Single-page UI (Jinja2 template) │ ├── requirements.txt ├── .env.example ├── .gitignore └── README.md

Copy
> Excluded from version control: `.ipynb_checkpoints/`, `__pycache__/`, virtual
> environments, `.env`, and the large generated datasets (`Datasets/`, `batches/`).

---

## Getting Started

### Prerequisites
- Python 3.10 or newer
- MongoDB running locally **or** a MongoDB Atlas connection string
- Git

### 1. Clone
```bash
git clone https://github.com/<your-username>/palettemind.git
cd palettemind
2. Create a virtual environment
Copy# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
3. Install dependencies
Copypip install -r requirements.txt
4. Configure the environment
Copycopy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
Then edit .env (see Environment Variables).

5. Run the app
Copyuvicorn app.main:app --reload
Open http://127.0.0.1:8000 — the UI loads at /, interactive API docs at /docs.

The server starts even if MongoDB is unreachable; it prints ❌ MongoDB Connection Failed and runs in degraded mode (guest generation still works, login/feedback are disabled). No data is ever silently lost — writes are skipped with a logged error.

Environment Variables
All configuration is read from the environment, with safe local-development defaults.

Variable	Default	Purpose
MONGO_URI	mongodb://localhost:27017/	MongoDB connection string.
MONGO_DB_NAME	color_palette_db	Database name.
SECRET_KEY	change-this-secret-in-production	Signing key for session cookies. Must be overridden in production.
MODEL_PATH	Artifacts/model.pkl	Path to the trained model artifact.
.env.example:

CopyMONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=color_palette_db
SECRET_KEY=replace-with-a-long-random-string
MODEL_PATH=Artifacts/model.pkl
Generate a strong secret:

Copypython -c "import secrets; print(secrets.token_urlsafe(48))"
Note: python-dotenv is not used — export these variables in your shell or use uvicorn --env-file .env app.main:app.

API Reference
Method	Endpoint	Auth	Description
GET	/	—	Renders the single-page UI.
GET	/generate	optional	Generate palettes. Query params: n (1–15), style (vibrant/pastel/minimal), temp (any/warm/cool), bright (any/bright/dark). Preference params are ignored for guests.
POST	/register	—	Form fields email, password (min 6 chars). Sets the session cookie.
POST	/login	—	Form fields email, password. Sets the session cookie.
POST	/logout	—	Clears the session cookie.
GET	/me	optional	{ authenticated, user_id, email } — used by the frontend to decide UI state.
POST	/feedback/like	required	JSON body { "palette": ["#rrggbb", ... 5 colors] }. Upserts the like, removes any matching dislike.
POST	/feedback/dislike	required	Same body shape. Upserts the dislike, removes any matching like.
GET	/my-likes	required	{ liked_palettes: [[hex × 5], ...] }, newest first.
Example

Copycurl "http://127.0.0.1:8000/generate?n=3&style=pastel&temp=warm&bright=bright"
Copy{
  "palettes": [["#f2d6c9", "#e8b9a6", "#d99b8c", "#c77f73", "#b06a62"]],
  "scores": [3.87],
  "personalized": false
}
Error behaviour: /generate returns HTTP 500 with { "error": "..." } and never propagates a traceback to the client (details are logged server-side). Feedback routes return 401 when unauthenticated and 503 when the database is unavailable.

Database collections
Collection	Index	Purpose
users	email (unique)	Credentials + created_at.
likes	(user_id, palette_hash) unique	Liked palettes.
dislikes	(user_id, palette_hash) unique	Disliked palettes.
palettes	created_at	Generation audit log (input params, output, scores, timestamps).
palette_hash is sha256 of the lowercased, |-joined hex list — the same palette always maps to the same document regardless of color order formatting.

Design Decisions
Why CIELAB instead of RGB? Euclidean distance in RGB is perceptually wrong — two colors that look identical can be far apart numerically, and vice versa. CIELAB is designed so equal distances ≈ equal perceived differences, which makes the contrast rank labels meaningful and the KMeans clusters perceptually coherent.

Why synthetic labels instead of human ratings? Collecting thousands of human "good palette" ratings was out of scope. Mean pairwise perceptual distance is a defensible, reproducible proxy for contrast harmony, and the balanced 4,000-per-rank sampling prevents the model from collapsing onto the majority class.

Why re-rank instead of conditioning the model? Keeping the model fixed and applying bonuses afterwards means a single artifact serves every user — no per-user retraining. Guest and member requests hit the same inference path; the bonus layers simply contribute zero when no preferences exist.

Why signed cookies instead of JWTs? itsdangerous gives tamper-proof, expiring tokens with no extra dependency and no token-revocation database. HttpOnly + SameSite=Lax blocks XSS cookie theft and most CSRF vectors for this app's flow.

Known Limitations & Roadmap
 Contrast rank is a heuristic proxy for "quality" — no human preference data yet.
 Datasets and the training pipeline are run manually; no CI/CD or model registry.
 Session cookies are not Secure by default (local HTTP development).
 No rate limiting on /generate or the auth endpoints.
 No pagination on /my-likes.
 Offline scripts in src/ still need their dataset paths parameterized.
 Roadmap: export palettes as PNG/CSS/SCSS, accessibility (WCAG contrast) validation, multi-user collaborative filtering, Docker + deployment pipeline.
License
Released for academic and educational use. [Choose one: MIT / Apache-2.0 / CC BY-NC 4.0 — MIT is the most common choice for a portfolio project.]

Acknowledgements
LightGBM (Microsoft) for the gradient-boosting regressor
scikit-image for CIELAB conversion
FastAPI and MongoDB communities for documentation and examples
[SIR TAYYAB NAQVI / INFORMATION TECHNOLOGY] 
