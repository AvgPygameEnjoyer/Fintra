# Fintra

### **AI-Powered Financial Intelligence Platform**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-fintraio.vercel.app-blue?style=for-the-badge)](https://fintraio.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Google AI](https://img.shields.io/badge/Google%20AI-Gemini%2FGemma-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![Tests](https://img.shields.io/github/actions/workflow/status/AvgPygameEnjoyer/fintra/test.yml?branch=main&label=Tests&style=for-the-badge)](https://github.com/AvgPygameEnjoyer/fintra/actions/workflows/test.yml)
[![Data Pipeline](https://img.shields.io/github/actions/workflow/status/AvgPygameEnjoyer/fintra/data-update.yml?branch=main&label=Data%20Pipeline&style=for-the-badge)](https://github.com/AvgPygameEnjoyer/fintra/actions/workflows/data-update.yml)
[![Codecov](https://img.shields.io/codecov/c/github/AvgPygameEnjoyer/fintra?style=for-the-badge&logo=codecov)](https://codecov.io/gh/AvgPygameEnjoyer/fintra)

> **Production-grade quantitative analysis platform** combining real-time market data, AI-driven insights, and institutional-level backtesting with Monte Carlo validation.

![Fintra Dashboard](static/fintralogo.png)

---

## Table of Contents

- [Why Fintra Stands Out](#-why-fintra-stands-out)
- [Project Metrics](#-project-metrics)
- [Architecture](#️-architecture)
- [Technical Achievements](#-technical-achievements)
- [Core Features](#-core-features)
- [Technical Stack](#️-technical-stack)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [API Overview](#-api-overview)
- [Testing](#-testing)
- [SEBI Compliance](#-sebi-compliance)
- [For Recruiters](#-for-recruiters)
- [Environment Configuration](#️-environment-configuration)
- [License](#-license)

---

## 🎯 Why Fintra Stands Out

Fintra isn't just another stock dashboard—it's a **production-grade financial intelligence platform** built with institutional-level engineering practices:

- **10,000+ simulation Monte Carlo engine** for statistical backtest validation
- **Multi-model AI architecture** with intelligent load balancing across Gemini & Gemma
- **Event-driven backtesting** with ATR-based position sizing and dynamic risk management
- **Enterprise security** with JWT authentication, OAuth 2.0, and CSRF protection
- **Memory optimized** to run on 512MB RAM (Render free tier)

---

## 📊 Project Metrics

> **21,400+ lines of production code** across a full-stack financial platform

| Category | Metric | Details |
|----------|--------|---------|
| **Python Backend** | 7,154 lines | 21 core modules (routes, auth, analysis, backtesting, Monte Carlo) |
| **JavaScript Frontend** | 5,024 lines | 19 ES6 modules with dynamic imports |
| **CSS Styling** | 7,526 lines | Custom design system with CSS variables |
| **HTML Templates** | 820 lines | 3 responsive pages (landing + dashboard) |
| **Test Suite** | 924 lines | Authentication & validation coverage |
| **API Endpoints** | 24 routes | RESTful design with JWT protection |
| **Market Data** | 2,235 files | Parquet datasets covering NSE/BSE (India) equities |
| **AI Models** | 5 models | Gemini 2.0 Flash + 4 Gemma variants |

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Vanilla JS     │────▶│  Flask REST API  │────▶│  PostgreSQL DB  │
│  ES6+ Frontend  │     │  Python Backend  │     │  User Data      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
   ┌──────────┐          ┌──────────┐         ┌──────────────┐
   │ yfinance │          │  Gemini  │         │ Monte Carlo  │
   │   API    │          │   AI     │         │   Engine     │
   └──────────┘          └──────────┘         └──────────────┘
```

---

## 🏆 Technical Achievements

> Key engineering accomplishments demonstrating production-grade skills

### Memory Optimization
Engineered the application to run on **512MB RAM** (Render free tier):
- Reduced memory footprint from 700MB+ to **200-400MB** through lazy loading
- Disabled optional RAG services saving **200-500MB** of RAM
- Configured Gunicorn with 1 worker, 2 threads, max 100 requests for optimal recycling
- Implemented graceful degradation when heavy services are unavailable

### Security Hardening
Implemented enterprise-grade security measures:
- **OAuth State Validation**: Redis-backed CSRF protection with 5-minute TTL
- **JWT Signature Verification**: Upgraded from disabled verification to `google-auth` library
- **Hash Algorithm Upgrade**: Migrated cache keys from MD5 to SHA-256
- **Prompt Injection Protection**: Input sanitization, 500-char limits, newline stripping

### Performance Optimization
- Monte Carlo: **10,000 simulations in <5 seconds** via NumPy vectorization
- Reduced Monte Carlo JS from **800+ lines to 150 lines** while fixing module conflicts
- Implemented Redis-ready caching layer for market data
- Tree-shaken ES6 modules with dynamic imports for faster page loads

---

## 🚀 Core Features

### 📊 Real-Time Market Intelligence
- **Live Data Pipeline:** High-performance OHLCV streaming via `yfinance` with caching
- **Technical Analysis:** RSI (14), MACD (12/26/9), SMA (5/10/50/200), ATR, ADX
- **2,500+ Instruments:** Indian stocks (NSE/BSE) and ETFs
- **Interactive Charts:** Chart.js with real-time updates and date-range filtering

### 🤖 Multi-Model AI Architecture
- **5-Model Rotation:** Auto-failover across Gemini 2.0 Flash + 4 Gemma variants
- **Hybrid Analysis:** Rule-based technical scoring + LLM reasoning
- **Context-Aware Prompts:** Dynamic prompt engineering based on market regime
- **Position Insights:** Personalized AI summaries for each portfolio holding

### 💼 Portfolio Management
- **Real-Time P&L:** Live position valuation with intraday updates
- **Technical Health:** Per-position RSI, MACD, and MA status tracking
- **Sparkline Visualization:** 30-day mini-charts for each holding
- **AI Position Doctor:** Automated analysis of position risk/reward profiles

### 📈 Institutional-Grade Backtesting
- **Event-Driven Engine:** Next-day open execution (no look-ahead bias)
- **7 Strategies:** Golden Cross, RSI, MACD, Composite, Momentum, Mean Reversion, Breakout
- **Risk Management:** ATR-based position sizing, trailing stops, slippage modeling
- **Performance Analytics:** Sharpe ratio, max drawdown, win rate, benchmark comparison

### 🎲 Monte Carlo Simulation
- **10,000 Simulations:** Position shuffling, return permutation, bootstrap analysis
- **Risk Metrics:** VaR (95%), CVaR, probability of ruin
- **Performance:** ~2,000 sims/second via NumPy vectorization
- **Statistical Validation:** P-value calculation against random strategies

### 🔐 Enterprise Security
- **JWT Authentication:** Dual-token system (15-min access / 7-day refresh)
- **OAuth 2.0:** Google Sign-In with PKCE flow
- **Secure Cookies:** HttpOnly, Secure, SameSite=Strict policies
- **Input Validation:** SQL injection prevention, XSS protection, rate limiting

---

## 🛠️ Technical Stack

### Backend
| Component | Technology |
|-----------|------------|
| **Language** | Python 3.8+ |
| **Framework** | Flask + Flask-CORS |
| **Database** | SQLAlchemy ORM (SQLite dev / PostgreSQL prod) |
| **Data Processing** | Pandas, NumPy, PyArrow |
| **AI/ML** | Google Generative AI (Gemini API) |
| **Authentication** | PyJWT, Google OAuth 2.0 |
| **Market Data** | yfinance |

### Frontend
| Component | Technology |
|-----------|------------|
| **Language** | Vanilla JavaScript (ES6+) |
| **Build** | Native ES Modules |
| **Visualization** | Chart.js |
| **Styling** | CSS3 (Custom Properties, Flexbox, Grid) |

### DevOps
| Component | Technology |
|-----------|------------|
| **Containerization** | Docker + Docker Compose |
| **Deployment** | Vercel (Frontend) / Render (Backend) |
| **Monitoring** | Structured logging with Python logging |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Cloud Project with OAuth credentials
- Google Gemini API Key

### Installation

```bash
# Clone repository
git clone https://github.com/AvgPygameEnjoyer/fintra.git
cd fintra

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run application
python app.py
```

Visit `http://localhost:5000`

### Docker Setup (Alternative)

```bash
# Clone and start with Docker Compose
git clone https://github.com/AvgPygameEnjoyer/fintra.git
cd fintra
cp .env.template .env
docker-compose up -d
```

---

## 📁 Project Structure

```
fintra/
├── app.py                 # Application factory & configuration
├── routes.py              # 24 REST API endpoints
├── analysis.py            # Technical indicators & AI integration
├── backtesting.py         # Event-driven backtest engine
├── mc_engine.py           # Monte Carlo simulation (495 lines)
├── auth.py                # JWT & OAuth implementation
├── models.py              # Database schema (User, Position)
├── config.py              # Environment configuration
├── validation.py          # Input validation & XSS prevention
├── static/
│   ├── main.js            # Core application logic
│   ├── monte_carlo.js     # MC visualization frontend
│   ├── backtesting.js     # Strategy backtest UI
│   ├── charts.js          # Chart.js configuration
│   ├── portfolio.js       # Portfolio management
│   └── chat.js            # QuantAI chatbot
└── data/                  # Parquet market data (2,235 stocks)
```

---

## 🔌 API Overview

> **24 RESTful endpoints** with JWT authentication and comprehensive error handling

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Auth** | `POST /api/oauth2callback` | Google OAuth callback with state validation |
| **Auth** | `POST /api/auth/token/refresh` | Refresh access token |
| **Auth** | `POST /api/auth/logout` | Invalidate session and clear cookies |
| **Stock** | `GET /api/stock/<symbol>` | Fetch OHLCV data with SEBI-compliant lag |
| **Portfolio** | `GET /api/portfolio` | List all user positions |
| **Portfolio** | `POST /api/positions` | Add new position |
| **Portfolio** | `DELETE /api/positions/<id>` | Remove position |
| **Backtest** | `POST /api/backtest` | Run strategy backtest |
| **Monte Carlo** | `POST /api/backtest/monte_carlo` | Run statistical simulation |
| **AI** | `POST /api/chat` | QuantAI chatbot with context awareness |
| **Data** | `GET /api/data/availability` | Data freshness and compliance info |
| **Health** | `GET /api/health` | Service health check |

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=. --cov-report=html
```

### Test Coverage

| Module | Lines | Focus Areas |
|--------|-------|-------------|
| `test_auth.py` | 100 | JWT token generation, OAuth flow, token refresh |
| `test_validation.py` | 167 | XSS detection, SQL injection prevention, input sanitization |
| `conftest.py` | 163 | Pytest fixtures for Flask app, test client, mock data |
| `test_data_pipeline.py` | 350 | SEBI compliance, data update logic, pipeline integration |

---

## 🔄 Automated Data Pipeline

GitHub Actions automatically maintains the historical database with SEBI compliance:

### Daily Data Update Workflow
- **Schedule**: Runs daily at 2:00 AM UTC (after market close)
- **Smart Updates**: Only updates stocks approaching the 31-day SEBI deadline
- **7-Day Buffer**: Updates when data is within 7 days of the compliance threshold
- **Batch Processing**: Checks 100 random stocks per run to minimize API calls
- **Audit Trail**: All updates logged with timestamps for compliance

### Logic
```
Today = February 9, 2025
SEBI Deadline = January 9, 2025 (31 days ago)
Update Threshold = January 16, 2025 (7-day buffer)

If stock.last_date >= January 16, 2025:
    → Data is fresh, skip
Else:
    → Fetch and update data up to January 9, 2025
```

### CI/CD Testing
- **Matrix Testing**: Python 3.9, 3.10, 3.11
- **Coverage Target**: 90% minimum
- **Automated Checks**: Run on every PR and push to main
- **Linting**: flake8, black, isort

---

## 🔒 SEBI Compliance

Fintra adheres to **SEBI (Securities and Exchange Board of India)** regulations:

| Requirement | Implementation |
|-------------|----------------|
| **Data Delay** | 30-day mandatory lag on all market data |
| **No Investment Advice** | AI prompts prohibit "Buy/Sell/Recommend/Target" |
| **Disclaimers** | Every output includes educational-purpose disclaimer |
| **Transparency** | Data freshness indicator on all views |
| **Simulation Only** | All backtests labeled as hypothetical |

**Fintra IS:**
- An educational platform for learning technical analysis
- A historical data visualization tool
- A strategy backtesting simulator (hypothetical only)
- SEBI-compliant with 30-day data lag

**Fintra is NOT:**
- Investment advice or a trading platform
- A replacement for professional financial advisors

---

## 🎯 For Recruiters

### Project Scope

| Metric | Value |
|--------|-------|
| **Total Codebase** | 14,200+ lines of production code |
| **Development** | Solo-developed full-stack platform |
| **Live Demo** | [fintraio.vercel.app](https://fintraio.vercel.app) |
| **Technologies** | Python, Flask, JavaScript ES6+, PostgreSQL, Redis, Docker |

### Skills Demonstrated

**Full-Stack Engineering:**
- RESTful API design (24 endpoints), JWT/OAuth authentication, SQLAlchemy ORM
- Modular ES6+ architecture (17 modules), Chart.js visualizations, responsive CSS
- Docker containerization, Render/Vercel deployment, memory optimization

**Quantitative Finance:**
- Technical analysis indicators (RSI, MACD, ATR, ADX, Bollinger Bands)
- 7 backtesting strategies with event-driven execution
- Monte Carlo simulation (10K sims) with VaR/CVaR risk metrics

**Security & Performance:**
- OAuth state validation, JWT signature verification, XSS/SQLi prevention
- NumPy vectorization, lazy loading, 512MB RAM optimization

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory:

```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_SECRET_KEY=your_super_secret_key_here

# Database
# DATABASE_URL=postgresql://user:password@localhost:5432/fintra

# Google OAuth 2.0
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Google AI (Gemini API)
GEMINI_API_KEY=your_gemini_api_key

# JWT Secrets (generate strong random strings, min 32 chars)
ACCESS_TOKEN_JWT_SECRET=your_access_token_secret_min_32_chars
REFRESH_TOKEN_JWT_SECRET=your_refresh_token_secret_min_32_chars
```

---

## 📄 License

This project is open-source and available under the MIT License.
