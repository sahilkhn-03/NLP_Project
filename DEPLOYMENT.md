# 🚀 Deployment Guide — NL → SQL Query Engine

This project supports **two seamless cloud deployment targets**:
1. **Vercel** — Serverless Python API + Modern Glassmorphism Web App
2. **Streamlit Community Cloud** — 1-Click Python App with Interactive Dataframes

---

## 🅰️ Option 1: Deploy to Vercel (Recommended for Web Portfolios)

Vercel hosts the web app with a Serverless Python backend (`api/index.py`) and a static glassmorphism frontend (`public/`).

### Method A: Deploy via GitHub & Vercel Dashboard (Easiest)
1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Deploy NL to SQL engine"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
   git push -u origin main
   ```
2. Go to **[vercel.com](https://vercel.com)** and log in with your GitHub account.
3. Click **"Add New..."** → **"Project"**.
4. Select your `NLP_Project` repository and click **"Import"**.
5. Leave all build settings at default (`vercel.json` automatically configures the serverless routes).
6. Click **"Deploy"**.
7. In ~30 seconds, your application will be live at `https://<your-project>.vercel.app`!

### Method B: Deploy using Vercel CLI from Terminal
Run the following in the project root directory:
```bash
npx vercel
```
- When asked `Set up and deploy?` → type `y`
- Follow the interactive prompts to link your Vercel account
- For production deployment:
  ```bash
  npx vercel --prod
  ```

---

## 🅱️ Option 2: Deploy to Streamlit Community Cloud (Free & 1-Click)

Streamlit Community Cloud natively hosts `app.py` directly from GitHub.

1. **Push your repository to GitHub** (if not already done).
2. Visit **[share.streamlit.io](https://share.streamlit.io)** and log in with GitHub.
3. Click **"New app"**.
4. Fill in:
   - **Repository:** `<YOUR_USERNAME>/<YOUR_REPO>`
   - **Branch:** `main` (or `master`)
   - **Main file path:** `app.py`
5. Click **"Deploy!"**.
6. The database and UI initialize automatically on cold start.

---

## 🛠️ Verification Checklist Before Deploying

- [x] Input query text is styled in high-visibility **Electric Cyan (`#38bdf8`)**
- [x] Input background is glassmorphism dark indigo (`#15132f`), not white
- [x] Enter key submits queries instantly
- [x] Database initializes automatically in serverless / temp directories (`/tmp`)
- [x] Security validator blocks SQL injection, DROP, UPDATE, and multi-statements
- [x] 87 unit tests passing with pytest (`python -m pytest tests/`)
