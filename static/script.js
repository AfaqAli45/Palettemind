let currentUser = null;

document.addEventListener("DOMContentLoaded", async () => {
    await refreshSession();
});

async function refreshSession() {
    try {
        const res = await fetch("/me");
        const data = await res.json();

        currentUser = data.authenticated ? data : null;
        updateAuthUI();

        if (currentUser) {
            await loadLikedPalettes();
        } else {
            document.getElementById("likedPalettes").innerHTML = "";
            document.getElementById("likedSection").style.display = "none";
        }
    } catch (err) {
        console.error(err);
    }
}

function updateAuthUI() {
    const personalization = document.getElementById("personalizationGroup");
    const authStatus = document.getElementById("authStatus");
    const authButtons = document.getElementById("authButtons");
    const likedSection = document.getElementById("likedSection");

    if (currentUser) {
        personalization.style.display = "grid";
        likedSection.style.display = "block";

        authStatus.innerHTML = `
            <div class="status-pill success">
                Logged in as <strong>${currentUser.email}</strong>
            </div>
            <p class="sub-note">
                Personalization and feedback learning are enabled for your account.
            </p>
        `;

        authButtons.innerHTML = `
            <button class="primary-btn" onclick="logout()">Logout</button>
        `;
    } else {
        personalization.style.display = "none";
        likedSection.style.display = "none";

        authStatus.innerHTML = `
            <div class="status-pill guest">
                Guest mode
            </div>
            <p class="sub-note">
                Guests can generate palettes. Sign in to unlock style, temperature, brightness, and learning from likes.
            </p>
        `;

        authButtons.innerHTML = `
            <button class="primary-btn" onclick="login()">Login</button>
            <button class="secondary-btn" onclick="register()">Register</button>
        `;
    }
}

async function login() {
    const form = new FormData();
    form.append("email", document.getElementById("email").value);
    form.append("password", document.getElementById("password").value);

    try {
        const res = await fetch("/login", { method: "POST", body: form });
        const data = await res.json();

        if (res.ok) {
            showToast("✅ Login successful");
            await refreshSession();
        } else {
            showToast(data.error || "Login failed", true);
        }
    } catch (err) {
        console.error(err);
        showToast("Server error during login", true);
    }
}

async function register() {
    const form = new FormData();
    form.append("email", document.getElementById("email").value);
    form.append("password", document.getElementById("password").value);

    try {
        const res = await fetch("/register", { method: "POST", body: form });
        const data = await res.json();

        if (res.ok) {
            showToast("✅ Registered and logged in");
            await refreshSession();
        } else {
            showToast(data.error || "Registration failed", true);
        }
    } catch (err) {
        console.error(err);
        showToast("Server error during register", true);
    }
}

async function logout() {
    try {
        await fetch("/logout", { method: "POST" });
        currentUser = null;
        updateAuthUI();
        document.getElementById("likedPalettes").innerHTML = "";
        showToast("Logged out successfully");
    } catch (err) {
        console.error(err);
        showToast("Logout failed", true);
    }
}

async function generatePalette() {
    const container = document.getElementById("palette");
    container.innerHTML = `<div class="loading-card">Generating AI palettes...</div>`;

    try {
        const n = document.getElementById("numPalettes").value;
        let url = `/generate?n=${n}`;

        if (currentUser) {
            const style = document.getElementById("style").value;
            const temp = document.getElementById("temperature").value;
            const bright = document.getElementById("brightness").value;

            url += `&style=${encodeURIComponent(style)}`;
            url += `&temp=${encodeURIComponent(temp)}`;
            url += `&bright=${encodeURIComponent(bright)}`;
        }

        const res = await fetch(url);
        const data = await res.json();

        container.innerHTML = "";

        if (!res.ok) {
            const msg = data.error || "Generation failed";
            showToast(msg, true);
            container.innerHTML = `<div class="loading-card error">${msg}</div>`;
            return;
        }

        if (!data.palettes || data.palettes.length === 0) {
            container.innerHTML = `<div class="loading-card error">No palettes generated</div>`;
            return;
        }


        data.palettes.forEach((palette, index) => {
            const score = data.scores?.[index] ?? 0;
            container.appendChild(buildPaletteCard(palette, score, index));
        });

        if (currentUser) {
            await loadLikedPalettes();
        }
    } catch (error) {
        console.error("❌ Frontend Error:", error);
        container.innerHTML = `<div class="loading-card error">Something went wrong</div>`;
    }
}

function buildPaletteCard(palette, score, index) {
    const card = document.createElement("div");
    card.className = "palette-card";

    const title = document.createElement("div");
    title.className = "palette-header";
    title.innerHTML = `
        <h3>Palette ${index + 1}</h3>
        <span class="score-badge">AI Score: ${Number(score).toFixed(2)}</span>
    `;
    card.appendChild(title);

    const row = document.createElement("div");
    row.className = "colors-row";

    palette.forEach(hex => {
        const box = document.createElement("div");
        box.className = "color-box";
        box.style.backgroundColor = hex;

        const label = document.createElement("button");
        label.className = "hex-chip";
        label.innerText = hex;
        label.onclick = () => copyHex(hex);

        box.appendChild(label);
        row.appendChild(box);
    });

    card.appendChild(row);

    if (currentUser) {
        const actions = document.createElement("div");
        actions.className = "feedback-row";
        actions.innerHTML = `
            <button class="like-btn">👍 Like</button>
        `;

        actions.querySelector(".like-btn").onclick = () => sendFeedback("like", palette);
        

        card.appendChild(actions);
    }

    return card;
}

async function sendFeedback(type, palette) {
    try {
        const res = await fetch(`/feedback/${type}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ palette })
        });

        const data = await res.json();

        if (res.ok) {
            showToast(type === "like" ? "Palette liked" : "Palette disliked");
            await loadLikedPalettes();
        } else {
            showToast(data.error || "Feedback failed", true);
        }
    } catch (err) {
        console.error(err);
        showToast("Feedback request failed", true);
    }
}

async function loadLikedPalettes() {
    if (!currentUser) return;

    try {
        const res = await fetch("/my-likes");
        const data = await res.json();

        const container = document.getElementById("likedPalettes");
        container.innerHTML = "";

        const palettes = data.liked_palettes || [];

        if (palettes.length === 0) {
            container.innerHTML = `<div class="empty-liked">No liked palettes yet. Start liking palettes to train your recommendations.</div>`;
            return;
        }

        palettes.forEach((palette, index) => {
            const wrapper = document.createElement("div");
            wrapper.className = "liked-palette-card";

            const title = document.createElement("div");
            title.className = "liked-title";
            const text = document.createElement("div")
            text.innerText = `Liked Palette ${index + 1}`;
            title.appendChild(text);
            const dislikeBtn = document.createElement("button");
            dislikeBtn.innerText = "👎 Dislike"
            dislikeBtn.className = "dislike-btn"
            title.appendChild(dislikeBtn)
            wrapper.appendChild(title);

            title.querySelector(".dislike-btn").onclick = () => sendFeedback("dislike", palette);

            
            const row = document.createElement("div");
            row.className = "mini-colors-row";

            palette.forEach(hex => {
                const item = document.createElement("div");
                item.className = "mini-color";
                item.style.backgroundColor = hex;
                item.title = hex;
                row.appendChild(item);
            });

            wrapper.appendChild(row);
            container.appendChild(wrapper);
        });
    } catch (err) {
        console.error(err);
    }
}

async function copyHex(hex) {
    try {
        await navigator.clipboard.writeText(hex);
        showToast(`Copied ${hex}`);
    } catch (err) {
        console.error(err);
    }
}

function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    toast.innerText = message;
    toast.className = isError ? "toast error show" : "toast show";

    setTimeout(() => {
        toast.className = "toast";
    }, 2200);
}












