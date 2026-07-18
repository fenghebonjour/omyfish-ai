# 📝 Memo: CORS & Same-Origin Policy (SOP) Quick Reference

### 🚨 The Golden Rule
**NEVER use `allow_origins=["*"]` in Production.** 
It strips away the browser's default security guard, exposing user sessions to data theft and unauthorized actions.

---

### 🧱 Core Concepts Breakdown

| Concept | What it is | Real-World Analogy |
| :--- | :--- | :--- |
| **SOP** *(Same-Origin Policy)* | Browser security that blocks Site B from reading data from Site A. | **Building Guard:** Stops a stranger from walking into your apartment to read your mail. |
| **CORS** *(Cross-Origin Resource Sharing)* | A controlled loophole to let trusted external sites bypass SOP. | **Guest List:** An approved list at the front desk telling the guard who is allowed inside. |
| **`allow_origins=["*"]`** | Bypassing all origin checks completely. | **No Doors:** Removing the building security guard entirely; anyone can walk in. |

---

### 💥 Production Risks of `["*"]`

1. **CSRF (Session Hijacking):** Malicious sites can use the victim's active browser cookies to force commands on your API (e.g., password resets, transfers).
2. **Data Scraping:** Competitors or attackers can host malicious frontends that cleanly fetch and steal your database content via users' browsers.
3. **Internal Network Bridging:** If your app is inside a corporate VPN, external malicious sites can use an employee's browser as a proxy to attack internal servers.

---

### 🛠️ Production Best Practices

* **Environment Separation:** Use wildcard `["*"]` *only* in local `development`. Use strict, explicit domain lists in `production`.
* **Credential Safety:** If `allow_credentials=True` (for cookies/sessions), browsers **prohibit** the use of `["*"]`. You *must* specify explicit domains.
* **Least Privilege:** Only allow the HTTP methods (`GET`, `POST`) and headers (`Content-Type`, `Authorization`) that your frontend actually requires.

---

### 💻 FastAPI Safe Implementation

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
env = os.getenv("APP_ENV", "production")

if env == "development":
    # Loose settings for local coding comfort
    allowed_origins = ["*"]
else:
    # Strict settings for the real world
    allowed_origins = [
        "https://yourdomain.com",
        "https://yourdomain.com",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=(env != "development"), # Must be False if origin is ["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE"], # Explicit > Wildcard
    allow_headers=["Content-Type", "Authorization"],
)