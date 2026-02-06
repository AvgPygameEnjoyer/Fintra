# Fintra 🚀

### **AI-Powered Financial Intelligence Platform**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-fintraio.vercel.app-blue?style=for-the-badge)](https://fintraio.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Google AI](https://img.shields.io/badge/Google%20AI-Gemini%2FGemma-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)

> **Production-grade quantitative analysis platform** combining real-time market data, AI-driven insights, and institutional-level backtesting with Monte Carlo validation.

![Fintra Dashboard](static/fintralogo.png)

---

## 🎯 Why Fintra Stands Out

Fintra isn't just another stock dashboard—it's a **production-grade financial intelligence platform** built with institutional-level engineering practices. What started as a personal tool has evolved into a comprehensive system featuring:

- **10,000+ simulation Monte Carlo engine** for statistical backtest validation
- **Multi-model AI architecture** with intelligent load balancing across Gemini & Gemma
- **Event-driven backtesting** with ATR-based position sizing and dynamic risk management
- **Enterprise security** with JWT authentication, OAuth 2.0, and role-based access control

---

## 🏗️ Architecture Highlights

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React/Vue     │────▶│  Flask REST API  │────▶│  PostgreSQL DB  │
│  Frontend (JS)  │     │  Python Backend  │     │  User Data      │
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

## 🚀 Core Features

### 📊 Real-Time Market Intelligence Engine
- **Live Data Pipeline:** High-performance OHLCV streaming via `yfinance` with intelligent caching
- **Advanced Technical Analysis:**
  - RSI (14) with trend velocity detection and dynamic zone coloring
  - MACD (12/26/9) with crossover signal detection
  - Multi-timeframe Moving Averages (SMA-5, SMA-10, SMA-50, SMA-200)
  - Average True Range (ATR) for volatility analysis
  - ADX for trend strength measurement
- **2,500+ Instruments:** Comprehensive coverage of Indian stocks, US equities, and ETFs
- **Interactive Visualization:** Chart.js with real-time updates, multi-layer overlays, and date-range filtering

### 🤖 Multi-Model AI Architecture
- **Intelligent Model Rotation:** Auto-failover across 5 models (Gemini 2.0 Flash + 4 Gemma variants)
- **Hybrid Analysis System:** Rule-based technical scoring + LLM reasoning for maximum accuracy
- **Context-Aware Prompting:** Dynamic prompt engineering based on current market regime
- **Position-Specific Insights:** Personalized AI summaries for each portfolio holding

### 💼 Portfolio Management Suite
- **Real-Time P&L Tracking:** Live position valuation with intraday updates
- **Technical Health Monitoring:** Per-position RSI, MACD, and MA status tracking
- **Sparkline Visualization:** 30-day mini-charts for each holding
- **AI Position Doctor:** Automated analysis of individual position risk/reward profiles

### 📈 Institutional-Grade Backtesting
- **Event-Driven Engine:** Next-day open execution to eliminate look-ahead bias
- **7 Strategy Implementations:**
  - Golden Cross (MA crossover)
  - RSI Overbought/Oversold
  - MACD Signal Crossover
  - **Composite Strategy** (MA + MACD + Volume + ADX trend filter)
  - Momentum Breakout
  - Mean Reversion (Bollinger Bands)
  - Volume-Confirmed Breakout
- **Risk Management:**
  - ATR-based position sizing (2% risk per trade)
  - Dynamic trailing stop-losses
  - Slippage and transaction cost modeling
- **Performance Analytics:** Sharpe ratio, max drawdown, win rate, benchmark comparison

### 🎲 Monte Carlo Simulation Engine
> **Statistical validation to distinguish skill from luck**

- **10,000 Simulations:** Position shuffling, return permutation, and bootstrap analysis
- **P-Value Calculation:** Statistical significance testing against random strategies
- **Risk Metrics:**
  - Value at Risk (VaR) at 95% confidence
  - Conditional VaR (CVaR) for tail risk
  - Probability of ruin analysis
- **Performance:** ~2,000 simulations/second via NumPy vectorization

### 💬 QuantAI Trading Chatbot
- **Multi-Context Awareness:** Analyzes current stock + portfolio positions simultaneously
- **Comparative Analysis:** Multi-stock benchmarking and correlation analysis
- **Conversational Interface:** Natural language queries with professional trader persona
- **Safety Controls:** Explicit context indicators and response validation

### 🔐 Enterprise Security Stack
- **JWT Authentication:** Dual-token system (15-min access / 7-day refresh)
- **OAuth 2.0 Integration:** Google Sign-In with PKCE flow
- **Secure Cookies:** HttpOnly, Secure, SameSite=Strict policies
- **CORS Protection:** Whitelist-based origin validation
- **Input Validation:** SQL injection prevention, XSS protection, rate limiting

### 📱 Modern Frontend Architecture
- **Vanilla JavaScript ES6+:** Modular architecture with dynamic imports
- **Responsive Design:** Mobile-first with collapsible navigation
- **Real-Time Updates:** WebSocket-ready architecture for live data
- **Dark Mode:** Professional financial dashboard aesthetic

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
| **Market Data** | yfinance, yahooquery |

### Frontend
| Component | Technology |
|-----------|------------|
| **Language** | Vanilla JavaScript (ES6+) |
| **Build** | Native ES Modules |
| **Visualization** | Chart.js, Chart.js Adapter Date-fns |
| **Styling** | CSS3 (Custom Properties, Flexbox, Grid) |
| **Markdown** | Marked.js |
| **Typography** | Plus Jakarta Sans, Space Grotesk |

### DevOps & Infrastructure
| Component | Technology |
|-----------|------------|
| **Containerization** | Docker + Docker Compose |
| **CI/CD** | GitHub Actions ready |
| **Deployment** | Vercel (Frontend) / Render (Backend) |
| **Monitoring** | Structured logging with Python logging |

---

## 📊 Key Engineering Achievements

### Performance Optimizations
- **Efficient Data Caching:** Redis-ready caching layer for market data
- **Vectorized Computations:** NumPy-based Monte Carlo (10K sims in <5s)
- **Lazy Loading:** On-demand technical indicator calculation
- **Bundle Optimization:** Tree-shaken JS modules with dynamic imports

### Code Quality
- **Modular Architecture:** 15+ ES6 modules with clear separation of concerns
- **Type Safety:** Dataclasses for Monte Carlo simulation structures
- **Error Handling:** Comprehensive exception handling with structured logging
- **Documentation:** Docstrings and inline comments throughout codebase

### Scalability Features
- **Stateless Design:** Horizontal scaling ready with JWT authentication
- **Database Abstraction:** SQLAlchemy ORM for easy DB switching
- **API Versioning:** Blueprint-based route organization
- **Rate Limiting:** Built-in protection against API abuse

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Cloud Project with OAuth credentials
- Google Gemini API Key

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/fintra.git
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

Visit `http://localhost:5000` 🎉

---

## 📁 Project Structure

```
fintra/
├── app.py                 # Application factory & configuration
├── routes.py              # 40+ REST API endpoints
├── analysis.py            # Technical indicators & AI integration
├── backtesting.py         # Event-driven backtest engine
├── mc_engine.py           # Monte Carlo simulation (495 lines)
├── auth.py                # JWT & OAuth implementation
├── models.py              # Database schema (User, Position)
├── config.py              # Environment configuration
├── static/
│   ├── main.js           # Core application logic
│   ├── monte_carlo.js    # MC visualization frontend
│   ├── backtesting.js    # Strategy backtest UI
│   ├── charts.js         # Chart.js configuration
│   ├── portfolio.js      # Portfolio management
│   └── chat.js           # QuantAI chatbot
└── data/                 # Parquet market data (2500+ stocks)
```

---

## 🎯 Why This Matters for Recruiters

**Full-Stack Engineering Excellence:** This project demonstrates production-grade skills across the entire stack:
- **Backend:** RESTful API design, authentication, database management
- **Frontend:** Modern JavaScript, responsive design, data visualization
- **Data Engineering:** Financial data processing, caching strategies
- **AI/ML Integration:** LLM orchestration, prompt engineering, load balancing
- **DevOps:** Docker containerization, environment management

**Quantitative Finance Knowledge:** Deep understanding of:
- Technical analysis indicators and their implementations
- Portfolio management and risk metrics
- Statistical backtesting methodologies
- Monte Carlo simulation for strategy validation

**Software Engineering Best Practices:**
- Clean code architecture with modular design
- Comprehensive error handling and logging
- Security-first approach (JWT, OAuth, input validation)
- Performance optimization and scalability planning

---

## 🔒 SEBI Compliance & Regulatory Framework

Fintra is designed with strict adherence to **SEBI (Securities and Exchange Board of India)** regulations and international financial compliance standards. This ensures the platform operates within legal boundaries while providing educational value.

### 📋 Regulatory Compliance Features

#### 1. **30-Day Mandatory Data Lag**
To comply with SEBI regulations regarding non-advisory financial platforms, Fintra implements a strict 30-day data lag:
- **No Real-Time Data**: All market data displayed is minimum 30 days old
- **Historical Analysis Only**: Platform analyzes only historical patterns and trends
- **Automatic Enforcement**: Data filtering is applied at the API level, ensuring no recent data can be accidentally displayed
- **Transparency**: Users are clearly informed about the data lag through:
  - Data informatics panel showing available date range
  - Compliance notices on all analysis outputs
  - Clear labeling of "effective date" vs actual date

**Implementation** (`backtesting.py`):
```python
DATA_LAG_DAYS = 30

def get_data_lag_date() -> datetime:
    """Get the effective date with 30-day SEBI compliance lag."""
    return datetime.now() - pd.Timedelta(days=DATA_LAG_DAYS)

def apply_sebi_lag(df: pd.DataFrame) -> pd.DataFrame:
    """Filter data to exclude anything newer than 30 days."""
    lag_date = get_data_lag_date()
    return df[df.index <= lag_date].copy()
```

#### 2. **No Investment Advice or Recommendations**
Fintra strictly avoids providing investment advice as per SEBI regulations:
- **Educational Purpose Only**: All outputs are labeled as educational and informational
- **No Buy/Sell Recommendations**: AI prompts explicitly prohibit words like "Buy," "Sell," "Hold," "Recommend," or "Target"
- **No Price Targets**: Analysis focuses on historical levels, not future predictions
- **No Trading Calls**: Platform does not provide "tips" or "calls" of any kind
- **Neutral Language**: AI responses use descriptive, factual language without directional bias

**AI Prompt Safeguards** (`analysis.py`):
```python
### MANDATORY CONSTRAINTS:
- **AVOID ADVISORY VERBS:** Never use "Recommend," "Suggest," "Buy," "Sell," "Should," or "Target."
- **NO PREDICTIONS:** Use terms like "Historically," "Technically indicated," or "Data suggests a historical tendency."
- **NO DIRECTIVES:** Never use words like "Buy," "Sell," "Hold," "Trim," or "Stance."
```

#### 3. **Data Availability Transparency**
Users have full visibility into what data is available and how fresh it is:
- **Data Range Display**: Shows exact date range of available historical data
- **Freshness Indicator**: Displays how old the data is (e.g., "Data is 45 days old")
- **Compliance Status**: Visual indicator showing SEBI compliance status
- **Parquet File Monitoring**: System checks the last date across all parquet files (2,500+ stocks)
- **API Endpoint**: `/api/data/availability` provides real-time data status

**Data Informatics Display**:
```
📊 Data Informatics
├── Data Range: 2020-01-01 to 2025-01-15 (1,827 trading days)
├── Total History: 1,827 trading days
├── SEBI Compliance: 30-day mandatory lag
├── Effective Date: 2024-12-16 (30 days ago)
├── Data Freshness: 22 days old
└── Status: ✅ Compliant
```

#### 4. **Mandatory Disclaimers**
Every AI-generated analysis includes comprehensive disclaimers:
- **Educational Purpose**: Clear statement that content is for education only
- **Not Financial Advice**: Explicit disclaimer that output is not investment advice
- **Past Performance**: Warning that past performance doesn't guarantee future results
- **Consult Professionals**: Recommendation to consult licensed financial advisors
- **Risk Acknowledgment**: Clear statement that all trading involves risk

**Standard Disclaimer**:
> "Fintra is a data visualization and interpretation tool. This output is generated by AI based on historical technical indicators and is for educational purposes only. It does not account for fundamental factors, news, or individual financial situations. This is NOT financial advice. Past performance is not indicative of future results."

#### 5. **Strategy Backtesting - Simulation Only**
Backtesting features are clearly labeled as historical simulations:
- **Hypothetical Results**: All backtest results are labeled as hypothetical
- **No Live Trading**: System cannot execute actual trades
- **Educational Scenarios**: Strategies are for learning pattern recognition only
- **Performance Warnings**: Users warned that historical results ≠ future performance

### 🛡️ SEBI Regulation Alignment

| SEBI Requirement | Fintra Implementation |
|-----------------|----------------------|
| **No Investment Advice** | AI prompts strictly prohibit recommendations; educational tone only |
| **No Guaranteed Returns** | Disclaimers explicitly state no guarantees; historical data only |
| **Data Delay** | 30-day mandatory lag ensures no current market data |
| **Transparency** | Full disclosure of data sources, lag, and limitations |
| **Risk Warnings** | Comprehensive disclaimers on every analysis output |
| **No Tips/Calls** | Platform never provides trading tips or calls |
| **Educational Purpose** | All features designed for learning, not trading decisions |

### 📊 Data Compliance Architecture

```
┌─────────────────┐
│  User Request   │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Load Parquet    │
│ Data File       │
└────────┬────────┘
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Check Last Date │────▶│ Compare with    │
│ in File         │     │ Current Date-30 │
└─────────────────┘     └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │ Apply Lag Filter│
                        │ (SEBI Compliant)│
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │ Return Filtered │
                        │ Historical Data │
                        └─────────────────┘
```

### 🎯 Why This Matters

**Legal Compliance**: Operating without SEBI registration requires strict adherence to non-advisory principles. Fintra's architecture ensures compliance at the code level.

**User Protection**: By providing only historical data and avoiding recommendations, users are protected from making decisions based on outdated information or unlicensed advice.

**Educational Value**: The platform focuses on teaching technical analysis concepts through historical examples, helping users learn without the pressure of real-time trading.

**Audit Trail**: Comprehensive logging and transparency features provide a clear audit trail demonstrating compliance efforts.

### ⚠️ Important Notice

**Fintra is NOT**:
- ❌ An investment advisory service
- ❌ A stock tipping platform
- ❌ A real-time trading tool
- ❌ A guarantee of future performance
- ❌ A replacement for professional financial advice

**Fintra IS**:
- ✅ An educational platform for learning technical analysis
- ✅ A historical data visualization tool
- ✅ A strategy backtesting simulator (hypothetical only)
- ✅ SEBI-compliant with 30-day data lag
- ✅ Transparent about limitations and data freshness

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory:

```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_SECRET_KEY=your_super_secret_key_here

# Database (SQLite used by default for development)
# DATABASE_URL=postgresql://user:password@localhost:5432/fintra

# Google OAuth 2.0
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Google AI (Gemini API)
GEMINI_API_KEY=your_gemini_api_key

# JWT Secrets (generate strong random strings)
ACCESS_TOKEN_JWT_SECRET=your_access_token_secret_min_32_chars
REFRESH_TOKEN_JWT_SECRET=your_refresh_token_secret_min_32_chars

# Optional Configuration
DATA_DIR=./data
```

---

## 📄 License

This project is open-source and available under the MIT License.
