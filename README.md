# Football Betting Intelligence

> **Professional Football Betting Intelligence Platform** — Statistical modeling, value betting detection, and risk management for football (soccer) markets.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://postgresql.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

---

## 🎯 Overview

Football Betting Intelligence is a **quantitative analysis platform** for football betting markets. It implements professional-grade statistical models to:

- **Calculate true probabilities** for match outcomes, goals, corners, cards
- **Identify value bets** by comparing model probabilities with market odds
- **Manage risk** with Kelly criterion, exposure limits, and drawdown controls
- **Backtest strategies** with walk-forward validation
- **Monitor live matches** with real-time probability updates

> ⚠️ **Important**: This is an **analysis and simulation tool only**. It does not place bets, connect to betting APIs for execution, or guarantee profits. All outputs are for informational and educational purposes.

---

## 🏗️ Architecture

```
football-betting-intelligence/
├── backend/                 # FastAPI application
│   ├── api/                 # REST API endpoints
│   ├── core/                # Core utilities
│   ├── database/            # SQLAlchemy models & connections
│   ├── ingestion/           # Data synchronization from APIs
│   ├── models/              # Statistical models
│   │   ├── goals/           # Poisson, Dixon-Coles, Elo
│   │   ├── corners/         # Negative Binomial
│   │   ├── cards/           # Poisson with referee adjustment
│   │   └── live/            # In-play momentum models
│   ├── providers/           # API clients (API-Football, football-data.org, The Odds API)
│   ├── value_betting/       # Value betting engine
│   ├── risk_manager/        # Risk management & bankroll simulation
│   └── main.py              # FastAPI app entry point
├── frontend/
│   └── dashboard/           # Streamlit dashboard
├── config/                  # Configuration management
├── migrations/              # Alembic database migrations
├── tests/                   # Pytest test suite
├── docker-compose.yml       # Full stack deployment
└── Dockerfile               # Backend container
```

---

## 📊 Supported Markets

| Market | Model | Features |
|--------|-------|----------|
| **Match Winner (1X2)** | Poisson + Dixon-Coles + Elo | Home/Draw/Away probabilities |
| **Over/Under Goals** | Goal matrix from score distribution | Lines: 0.5, 1.5, 2.5, 3.5, 4.5, 5.5 |
| **Both Teams to Score** | Joint goal probability | Yes/No with implied probability |
| **Asian Handicap** | Score matrix convolution | Quarter/half/full goal lines |
| **Corners** | Negative Binomial | Over/Under + Asian Handicap |
| **Cards** | Poisson + Referee bias | Over/Under + Team totals |
| **Live/In-Play** | Dynamic xG + Momentum | Real-time probability updates |

---

## 🧮 Statistical Models

### Goals (Match Winner, O/U, BTTS)
- **Poisson Distribution** — Baseline goal modeling
- **Dixon-Coles Adjustment** — Corrects low-score (0-0, 0-1, 1-0, 1-1) dependence
- **Elo Ratings** — Dynamic team strength with home advantage
- **Combined Ensemble** — Weighted combination of all three

### Corners
- **Negative Binomial** — Handles overdispersion in corner counts
- **Team attack/defense profiles** — Home/away splits
- **Playing style adjustments** — Wide play, possession, shot ratios

### Cards
- **Poisson with referee adjustment** — Referee strictness factor
- **Match importance & rivalry** — Derby, cup final multipliers
- **Player aggression profiling** — Lineup-based adjustments

### Live/In-Play
- **Time-decay expected goals** — Remaining xG based on elapsed time
- **Momentum indicator** — Shots, possession, pressure index
- **Red card impact** — Immediate probability recalculation

---

## 💰 Value Betting Engine

```python
# Core calculations
Implied Probability = 1 / Odds (with margin removal)
Edge = Model Probability - Implied Probability
Expected Value = (Model Probability × Odds) - 1
Kelly Stake = (Edge × Odds) / (Odds - 1) × Fraction
```

**Filters applied:**
- Minimum edge threshold (default 2%)
- Minimum EV threshold (default 5%)
- Confidence threshold (default 60%)
- Data quality threshold (default 50%)
- Odds freshness check (30min pre-match, 5min live)

---

## ⚖️ Risk Management

| Limit | Default | Description |
|-------|---------|-------------|
| Per Match | 5% | Max exposure on single fixture |
| Per Market | 3% | Max exposure per market type |
| Per Bookmaker | 10% | Counterparty concentration |
| Daily | 20% | Daily turnover limit |
| Weekly | 50% | Weekly exposure cap |
| Max Drawdown | 15% | Circuit breaker |
| Concurrent Bets | 20 | Max simultaneous positions |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker (optional)

### 1. Clone & Configure
```bash
git clone <repository>
cd football-betting-intelligence
cp .env.example .env
# Edit .env with your API keys
```

### 2. API Keys Required
| Provider | Free Tier | Get Key |
|----------|-----------|---------|
| API-Football | 100 req/day | [api-football.com](https://www.api-football.com/) |
| football-data.org | 10 req/min | [football-data.org](https://www.football-data.org/) |
| The Odds API | 500 req/mo | [the-odds-api.com](https://the-odds-api.com/) |

### 3. Run with Docker (Recommended)
```bash
docker-compose up -d
# Backend: http://localhost:8000
# Dashboard: http://localhost:8501
# API Docs: http://localhost:8000/docs
```

### 4. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start backend
uvicorn backend.main:app --reload --port 8000

# Start dashboard (separate terminal)
cd frontend/dashboard
pip install -r requirements.txt
streamlit run app.py
```

---

## 📡 API Endpoints

### Core
- `GET /api/v1/health` — Health check
- `GET /api/v1/providers` — Available data providers
- `GET /api/v1/competitions` — List competitions

### Fixtures & Data
- `GET /api/v1/fixtures` — Filtered fixture list
- `GET /api/v1/fixtures/{id}` — Fixture details with events/stats/odds
- `POST /api/v1/sync/competitions` — Sync competitions
- `POST /api/v1/sync/fixtures` — Sync fixtures for competition
- `POST /api/v1/sync/full` — Full synchronization pipeline

### Predictions & Analysis
- `GET /api/v1/predictions/{fixture_id}` — Model predictions
- `GET /api/v1/value-bets` — Value betting opportunities
- `GET /api/v1/live/{fixture_id}` — Live match analysis

### Backtesting
- `POST /api/v1/backtest` — Run backtest
- `GET /api/v1/backtest/{id}` — Backtest results

---

## 🖥️ Dashboard Features

The Streamlit dashboard provides:

1. **Dashboard** — System overview, key metrics, upcoming matches
2. **Jogos do Dia** — Calendar view with match listings
3. **Scanner** — Automated opportunity scanning with filters
4. **Value Betting** — Detailed EV analysis, Kelly stakes, arbitrage detection
5. **Análise de Partida** — Complete match report with probabilities
6. **Ao Vivo** — Real-time probability updates during matches
7. **Backtesting** — Historical strategy validation
8. **Simulador de Banca** — Monte Carlo bankroll simulation
9. **Relatórios** — Performance tracking and export
10. **Configurações** — API keys, model params, risk limits

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_models.py -v
pytest tests/test_value_betting.py -v
pytest tests/test_risk_manager.py -v

# With coverage
pytest tests/ --cov=backend --cov-report=html
```

---

## 📈 Model Validation Framework

The platform implements rigorous validation:

| Metric | Purpose |
|--------|---------|
| **Brier Score** | Probabilistic calibration quality |
| **Log Loss** | Penalizes confident wrong predictions |
| **Reliability Diagrams** | Visual calibration assessment |
| **ROI (Walk-Forward)** | Financial performance out-of-sample |
| **Max Drawdown** | Risk assessment |
| **CLV (Closing Line Value)** | Market efficiency measurement |
| **Yield** | Return on turnover |

**Methodology:** Strict chronological walk-forward — never using future data to predict past.

---

## 🔒 Security & Ethics

- **No automated betting** — Human decision required for any action
- **API keys encrypted** — Stored in environment variables
- **Rate limiting** — Respects provider limits
- **Audit trail** — All predictions logged with timestamps
- **Gambling awareness** — Built-in risk warnings and limits

---

## 📝 Configuration

Key settings in `.env`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# API Keys
API_FOOTBALL_KEY=your_key
FOOTBALL_DATA_KEY=your_key
ODDS_API_KEY=your_key

# Model params
MIN_EDGE_PERCENT=2.0
MIN_EV_PERCENT=5.0
MAX_KELLY_FRACTION=0.25
CONFIDENCE_THRESHOLD=0.6

# Risk limits
MAX_EXPOSURE_PER_MATCH=0.05
MAX_DAILY_EXPOSURE=0.20
MAX_DRAWDOWN_PERCENT=15.0
```

---

## 🗺️ Roadmap

- [ ] **Phase 1** ✅ — Core models, API integration, dashboard
- [ ] **Phase 2** — Machine learning models (xGBoost, Neural Networks)
- [ ] **Phase 3** — Advanced live modeling (possession chains, pressure)
- [ ] **Phase 4** — Portfolio optimization (correlation, hedging)
- [ ] **Phase 5** — Mobile app (React Native / Capacitor)
- [ ] **Phase 6** — Multi-sport expansion (Basketball, Tennis)

---

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

**This software is for educational and research purposes only.**

- Past performance does not guarantee future results
- Betting involves substantial risk of loss
- Never bet more than you can afford to lose
- Seek professional help if gambling becomes problematic
- The authors are not responsible for any financial losses

**Resources for responsible gambling:**
- [GamCare](https://www.gamcare.org.uk/)
- [BeGambleAware](https://www.begambleaware.org/)
- [Gambling Therapy](https://www.gamblingtherapy.org/)

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email**: your-email@example.com

---

**Built with ❤️ for quantitative football analytics**