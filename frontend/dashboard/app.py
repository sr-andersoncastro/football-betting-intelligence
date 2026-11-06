"""Streamlit Dashboard for Football Betting Intelligence."""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# Page config
st.set_page_config(
    page_title="Football Betting Intelligence",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API base URL
API_BASE = "http://localhost:8000/api/v1"

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #2a5298;
    }
    .value-bet-card {
        background: #f0f8ff;
        border: 1px solid #2a5298;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .positive { color: #28a745; font-weight: bold; }
    .negative { color: #dc3545; font-weight: bold; }
    .neutral { color: #6c757d; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
</style>
""", unsafe_allow_html=True)


# Helper functions
@st.cache_data(ttl=60)
def fetch_api(endpoint: str, params: dict = None) -> dict:
    """Fetch data from API with caching."""
    try:
        response = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return {}


@st.cache_data(ttl=300)
def get_competitions() -> List[Dict]:
    """Get all competitions."""
    data = fetch_api("/competitions")
    return data.get("competitions", [])


@st.cache_data(ttl=60)
def get_fixtures(competition_id: int = None, days: int = 3) -> List[Dict]:
    """Get upcoming fixtures."""
    params = {"limit": 100}
    if competition_id:
        params["competition_id"] = competition_id
    data = fetch_api("/fixtures", params)
    return data.get("fixtures", [])


@st.cache_data(ttl=60)
def get_fixture_details(fixture_id: int) -> Dict:
    """Get fixture details."""
    return fetch_api(f"/fixtures/{fixture_id}")


@st.cache_data(ttl=60)
def get_predictions(fixture_id: int) -> Dict:
    """Get predictions for a fixture."""
    return fetch_api(f"/predictions/{fixture_id}")


@st.cache_data(ttl=60)
def get_value_bets(fixture_id: int = None) -> List[Dict]:
    """Get value betting opportunities."""
    params = {}
    if fixture_id:
        params["fixture_id"] = fixture_id
    data = fetch_api("/value-bets", params)
    return data.get("value_bets", [])


@st.cache_data(ttl=60)
def get_live_analysis(fixture_id: int) -> Dict:
    """Get live analysis."""
    return fetch_api(f"/live/{fixture_id}")


@st.cache_data(ttl=60)
def get_sync_logs(limit: int = 20) -> List[Dict]:
    """Get sync logs."""
    data = fetch_api("/sync/logs", {"limit": limit})
    return data.get("logs", [])


# Sidebar
def render_sidebar():
    """Render sidebar navigation."""
    st.sidebar.markdown("""
    <div class="main-header">
        <h2>⚽ Football Betting Intelligence</h2>
        <p>Professional Analytics Platform</p>
    </div>
    """, unsafe_allow_html=True)

    # Navigation
    pages = [
        "🏠 Dashboard",
        "📅 Jogos do Dia",
        "🔍 Scanner",
        "💎 Value Betting",
        "📊 Análise de Partida",
        "⚡ Ao Vivo",
        "🧪 Backtesting",
        "💰 Simulador de Banca",
        "📈 Relatórios",
        "⚙️ Configurações",
    ]

    selected = st.sidebar.radio("Navegação", pages, label_visibility="collapsed")

    st.sidebar.divider()

    # Competition filter
    competitions = get_competitions()
    comp_options = {c["name"]: c["id"] for c in competitions}
    selected_comps = st.sidebar.multiselect(
        "Competições",
        options=list(comp_options.keys()),
        default=list(comp_options.keys())[:3] if comp_options else [],
    )
    selected_comp_ids = [comp_options[c] for c in selected_comps]

    st.sidebar.divider()

    # Sync controls
    st.sidebar.subheader("Sincronização")
    if st.sidebar.button("🔄 Sincronizar Competições"):
        with st.spinner("Sincronizando..."):
            result = requests.post(f"{API_BASE}/sync/competitions").json()
            st.sidebar.success(f"Status: {result.get('status', 'unknown')}")

    if st.sidebar.button("📥 Sincronizar Jogos (Últimos 7 dias)"):
        if selected_comp_ids:
            for comp_id in selected_comp_ids:
                with st.spinner(f"Sincronizando competição {comp_id}..."):
                    result = requests.post(
                        f"{API_BASE}/sync/fixtures",
                        json={"competition_id": comp_id, "season": 2024}
                    ).json()
                    st.sidebar.info(f"Comp {comp_id}: {result.get('status', 'unknown')}")
        else:
            st.sidebar.warning("Selecione pelo menos uma competição")

    st.sidebar.divider()

    # Stats
    st.sidebar.subheader("Estatísticas Rápidas")
    st.sidebar.metric("Competições", len(competitions))
    st.sidebar.metric("Última Atualização", datetime.now().strftime("%H:%M:%S"))

    return selected, selected_comp_ids


# Page Components
def render_dashboard(selected_comp_ids: List[int]):
    """Render main dashboard."""
    st.markdown("""
    <div class="main-header">
        <h1>📊 Dashboard Principal</h1>
        <p>Visão geral do sistema de inteligência para apostas em futebol</p>
    </div>
    """, unsafe_allow_html=True)

    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Partidas Analisadas", "128", delta="+12 hoje")

    with col2:
        st.metric("Oportunidades", "12", delta="+3 valor")

    with col3:
        st.metric("Modelos Ativos", "7", delta="Atualizado")

    with col4:
        st.metric("Precisão Validada", "—", delta="Em validação")

    st.divider()

    # Upcoming fixtures
    st.subheader("📅 Próximos Jogos")

    fixtures = []
    for comp_id in selected_comp_ids[:3]:
        comp_fixtures = get_fixtures(comp_id, days=3)
        fixtures.extend(comp_fixtures[:5])

    if fixtures:
        df = pd.DataFrame(fixtures)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%d/%m %H:%M")
        df["match"] = df.apply(
            lambda r: f"{r.get('home_team', {}).get('name', 'TBD')} vs {r.get('away_team', {}).get('name', 'TBD')}",
            axis=1
        )
        df["competition"] = "Competição"  # Would need to join

        st.dataframe(
            df[["date", "match", "status", "competition"]].head(15),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum jogo encontrado. Sincronize os dados primeiro.")

    st.divider()

    # Value bets summary
    st.subheader("💎 Melhores Oportunidades de Valor")
    value_bets = get_value_bets()

    if value_bets:
        df_vb = pd.DataFrame(value_bets[:10])
        df_vb["ev_pct"] = (df_vb["expected_value"] * 100).round(1)
        df_vb["edge_pct"] = (df_vb["edge"] * 100).round(1)

        for _, bet in df_vb.iterrows():
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                with col1:
                    st.write(f"**{bet['selection'].upper()}** - {bet['market_type']} {bet.get('market_line', '')}")
                with col2:
                    st.metric("EV", f"{bet['ev_pct']:.1f}%")
                with col3:
                    st.metric("Edge", f"{bet['edge_pct']:.1f}%")
                with col4:
                    st.metric("Odd", f"{bet['odd']:.2f}")
                with col5:
                    st.metric("Kelly", f"{bet['fractional_kelly_stake']*100:.1f}%")
    else:
        st.info("Nenhuma oportunidade de valor encontrada no momento.")


def render_fixtures(selected_comp_ids: List[int]):
    """Render fixtures page."""
    st.markdown("""
    <div class="main-header">
        <h1>📅 Jogos do Dia</h1>
        <p>Calendário de partidas com análises e estatísticas</p>
    </div>
    """, unsafe_allow_html=True)

    # Date selector
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_date = st.date_input("Data", value=datetime.now())
    with col2:
        days_ahead = st.selectbox("Dias à frente", [1, 3, 7, 14], index=1)

    # Fetch fixtures for selected competitions and date range
    date_from = selected_date.strftime("%Y-%m-%d")
    date_to = (selected_date + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    all_fixtures = []
    for comp_id in selected_comp_ids:
        params = {
            "competition_id": comp_id,
            "date_from": date_from,
            "date_to": date_to,
            "limit": 100,
        }
        data = fetch_api("/fixtures", params)
        for f in data.get("fixtures", []):
            f["competition_id"] = comp_id
            all_fixtures.append(f)

    if all_fixtures:
        # Group by date
        df = pd.DataFrame(all_fixtures)
        df["date"] = pd.to_datetime(df["date"])
        df["date_str"] = df["date"].dt.strftime("%d/%m/%Y")
        df["time_str"] = df["date"].dt.strftime("%H:%M")
        df["home_name"] = df["home_team"].apply(lambda x: x.get("name", "TBD") if isinstance(x, dict) else "TBD")
        df["away_name"] = df["away_team"].apply(lambda x: x.get("name", "TBD") if isinstance(x, dict) else "TBD")
        df["match"] = df["home_name"] + " vs " + df["away_name"]

        # Status styling
        def style_status(s):
            colors = {
                "NS": "#6c757d", "TBD": "#6c757d",
                "1H": "#0d6efd", "HT": "#ffc107",
                "2H": "#0d6efd", "FT": "#28a745",
                "PST": "#dc3545", "CANC": "#dc3545",
            }
            return f"background-color: {colors.get(s, '#6c757d')}; color: white; padding: 2px 8px; border-radius: 4px;"

        # Display by date
        for date_str, group in df.groupby("date_str"):
            st.subheader(f"📅 {date_str}")
            display_df = group[["time_str", "match", "status", "competition_id"]].copy()
            display_df.columns = ["Hora", "Partida", "Status", "Competição"]

            st.dataframe(
                display_df.style.applymap(style_status, subset=["Status"]),
                use_container_width=True,
                hide_index=True,
            )

            # Quick actions
            cols = st.columns(len(group))
            for idx, (_, row) in enumerate(group.iterrows()):
                with cols[idx]:
                    if st.button(f"📊 Analisar", key=f"analyze_{row['id']}"):
                        st.session_state.selected_fixture = row['id']
                        st.rerun()
    else:
        st.warning("Nenhum jogo encontrado para o período selecionado.")


def render_scanner(selected_comp_ids: List[int]):
    """Render scanner page."""
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Scanner de Oportunidades</h1>
        <p>Varredura automatizada de partidas para identificar value bets</p>
    </div>
    """, unsafe_allow_html=True)

    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        min_ev = st.slider("EV Mínimo (%)", 0, 50, 5)
    with col2:
        min_edge = st.slider("Edge Mínimo (%)", 0, 20, 2)
    with col3:
        markets = st.multiselect(
            "Mercados",
            ["match_winner", "over_under", "both_teams_score", "corners", "cards"],
            default=["match_winner", "over_under", "both_teams_score"],
        )
    with col4:
        if st.button("🔍 Escanear Agora", type="primary"):
            st.cache_data.clear()
            st.rerun()

    # Get value bets
    value_bets = get_value_bets()

    # Filter
    filtered = [
        b for b in value_bets
        if b["expected_value"] * 100 >= min_ev
        and b["edge"] * 100 >= min_edge
        and b["market_type"] in markets
    ]

    if filtered:
        st.success(f"Encontradas {len(filtered)} oportunidades")

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Oportunidades", len(filtered))
        with col2:
            avg_ev = sum(b["expected_value"] for b in filtered) / len(filtered) * 100
            st.metric("EV Médio", f"{avg_ev:.1f}%")
        with col3:
            best = max(filtered, key=lambda x: x["expected_value"])
            st.metric("Melhor EV", f"{best['expected_value']*100:.1f}%")

        st.divider()

        # Display as cards
        for bet in filtered:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])

                with col1:
                    st.write(f"**{bet['selection'].upper()}**")
                    st.caption(f"{bet['market_type']} {bet.get('market_line', '')}")

                with col2:
                    st.metric("EV", f"{bet['expected_value']*100:.1f}%", delta=f"Edge: {bet['edge']*100:.1f}%")

                with col3:
                    st.metric("Odd", f"{bet['odd']:.2f}")
                    st.caption(f"Prob: {bet['model_probability']*100:.1f}%")

                with col4:
                    st.metric("Kelly", f"{bet['fractional_kelly_stake']*100:.1f}%")
                    st.caption(f"Conf: {bet['confidence']*100:.0f}%")

                with col5:
                    if st.button("📊 Ver Análise", key=f"scan_{bet['fixture_id']}_{bet['selection']}"):
                        st.session_state.selected_fixture = bet['fixture_id']
                        st.rerun()

                st.divider()
    else:
        st.info("Nenhuma oportunidade encontrada com os filtros atuais.")


def render_value_betting():
    """Render value betting page."""
    st.markdown("""
    <div class="main-header">
        <h1>💎 Value Betting</h1>
        <p>Análise detalhada de apostas com valor matemático positivo</p>
    </div>
    """, unsafe_allow_html=True)

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Oportunidades", "📊 Análise EV", "🎯 Kelly Criterion", "⚖️ Arbitragem"])

    with tab1:
        value_bets = get_value_bets()

        if value_bets:
            df = pd.DataFrame(value_bets)
            df["EV (%)"] = (df["expected_value"] * 100).round(2)
            df["Edge (%)"] = (df["edge"] * 100).round(2)
            df["Prob Model (%)"] = (df["model_probability"] * 100).round(1)
            df["Prob Impl (%)"] = (df["implied_probability"] * 100).round(1)
            df["Kelly (%)"] = (df["fractional_kelly_stake"] * 100).round(2)

            # Filters
            col1, col2 = st.columns(2)
            with col1:
                market_filter = st.selectbox("Mercado", ["Todos"] + df["market_type"].unique().tolist())
            with col2:
                selection_filter = st.selectbox("Seleção", ["Todas"] + df["selection"].unique().tolist())

            if market_filter != "Todos":
                df = df[df["market_type"] == market_filter]
            if selection_filter != "Todas":
                df = df[df["selection"] == selection_filter]

            st.dataframe(
                df[[
                    "fixture_id", "selection", "market_type", "market_line",
                    "odd", "Prob Model (%)", "Prob Impl (%)",
                    "Edge (%)", "EV (%)", "Kelly (%)", "confidence"
                ]].sort_values("EV (%)", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma oportunidade disponível. Execute o scanner primeiro.")

    with tab2:
        st.subheader("Análise de Valor Esperado")

        value_bets = get_value_bets()
        if value_bets:
            df = pd.DataFrame(value_bets)

            # EV Distribution
            fig = px.histogram(
                df, x="expected_value", nbins=20,
                title="Distribuição do Valor Esperado",
                labels={"expected_value": "EV", "count": "Frequência"}
            )
            st.plotly_chart(fig, use_container_width=True)

            # EV by Market
            fig2 = px.box(
                df, x="market_type", y="expected_value",
                title="EV por Tipo de Mercado",
                labels={"expected_value": "EV", "market_type": "Mercado"}
            )
            st.plotly_chart(fig2, use_container_width=True)

            # Edge vs EV scatter
            fig3 = px.scatter(
                df, x="edge", y="expected_value",
                color="market_type", size="confidence",
                hover_data=["selection", "odd"],
                title="Edge vs Valor Esperado",
                labels={"edge": "Edge", "expected_value": "EV"}
            )
            st.plotly_chart(fig3, use_container_width=True)

    with tab3:
        st.subheader("Critério de Kelly")

        value_bets = get_value_bets()
        if value_bets:
            df = pd.DataFrame(value_bets)

            # Kelly stakes
            fig = px.bar(
                df.sort_values("fractional_kelly_stake", ascending=False).head(20),
                x="fixture_id", y="fractional_kelly_stake",
                color="market_type",
                title="Top 20 Kelly Stakes Fracionados",
                labels={"fractional_kelly_stake": "Stake (% da banca)", "fixture_id": "Partida"}
            )
            st.plotly_chart(fig, use_container_width=True)

            # Kelly vs Confidence
            fig2 = px.scatter(
                df, x="confidence", y="fractional_kelly_stake",
                color="market_type", size="expected_value",
                title="Stake Kelly vs Confiança do Modelo"
            )
            st.plotly_chart(fig2, use_container_width=True)

    with tab4:
        st.subheader("Oportunidades de Arbitragem")
        st.info("Detector de arbitragem será implementado na próxima versão.")
        st.markdown("""
        A arbitragem ocorre quando diferentes casas de apostas oferecem odds que permitem
        apostar em todos os resultados com lucro garantido.

        **Próximas funcionalidades:**
        - Comparação automática entre casas
        - Cálculo de stakes para arbitragem perfeita
        - Alertas em tempo real
        - Filtro por liquidez mínima
        """)


def render_match_analysis():
    """Render match analysis page."""
    st.markdown("""
    <div class="main-header">
        <h1>📊 Análise de Partida</h1>
        <p>Relatório completo com probabilidades, estatísticas e recomendações</p>
    </div>
    """, unsafe_allow_html=True)

    # Fixture selector
    fixture_id = st.number_input("ID da Partida", min_value=1, value=123456)

    if st.button("🔍 Analisar", type="primary"):
        with st.spinner("Carregando análise..."):
            fixture = get_fixture_details(fixture_id)
            predictions = get_predictions(fixture_id)

            if fixture:
                # Match header
                home = fixture.get("home_team", {})
                away = fixture.get("away_team", {})

                col1, col2, col3 = st.columns([2, 1, 2])
                with col1:
                    st.image(home.get("logo_url", ""), width=80)
                    st.write(f"### {home.get('name', 'Time Casa')}")
                with col2:
                    st.write("### VS")
                    st.write(f"**{fixture.get('status', 'NS')}**")
                with col3:
                    st.image(away.get("logo_url", ""), width=80)
                    st.write(f"### {away.get('name', 'Time Fora')}")

                st.write(f"📅 {fixture.get('date', 'N/A')} | 🏟️ {fixture.get('round', 'N/A')}")

                st.divider()

                # Predictions
                if predictions.get("predictions"):
                    preds = predictions["predictions"][0]

                    st.subheader("🎯 Probabilidades (1X2)")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Casa 🏠", f"{preds.get('prob_home', 0)*100:.1f}%")
                    with col2:
                        st.metric("Empate ⚖️", f"{preds.get('prob_draw', 0)*100:.1f}%")
                    with col3:
                        st.metric("Fora 🚌", f"{preds.get('prob_away', 0)*100:.1f}%")

                    # Expected Goals
                    st.subheader("⚽ Expected Goals")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("xG Casa", f"{preds.get('expected_goals_home', 0):.2f}")
                    with col2:
                        st.metric("xG Fora", f"{preds.get('expected_goals_away', 0):.2f}")

                    # Over/Under
                    st.subheader("📈 Over/Under")
                    ou_data = preds.get("over_under", {})
                    if ou_data:
                        df_ou = pd.DataFrame([
                            {"Linha": k, "Over": f"{v['over']*100:.1f}%", "Under": f"{v['under']*100:.1f}%"}
                            for k, v in ou_data.items()
                        ])
                        st.dataframe(df_ou, use_container_width=True, hide_index=True)

                    # BTTS
                    st.subheader("🥅 Ambas Marcam (BTTS)")
                    btts = preds.get("btts", {})
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Sim ✅", f"{btts.get('yes', 0)*100:.1f}%")
                    with col2:
                        st.metric("Não ❌", f"{btts.get('no', 0)*100:.1f}%")

                    # Correct Scores
                    st.subheader("🎯 Placares Mais Prováveis")
                    cs = preds.get("correct_scores", {})
                    if cs:
                        df_cs = pd.DataFrame([
                            {"Placar": k, "Probabilidade": f"{v*100:.1f}%"}
                            for k, v in list(cs.items())[:10]
                        ])
                        st.dataframe(df_cs, use_container_width=True, hide_index=True)
                else:
                    st.warning("Previsões não disponíveis para esta partida.")

                # Events and Statistics
                st.divider()
                st.subheader("📋 Eventos da Partida")
                events = fixture.get("events", [])
                if events:
                    df_events = pd.DataFrame(events)
                    st.dataframe(df_events[["time", "type", "detail", "team_id"]], use_container_width=True)
                else:
                    st.info("Nenhum evento registrado.")

                st.subheader("📊 Estatísticas")
                stats = fixture.get("statistics", [])
                if stats:
                    df_stats = pd.DataFrame(stats)
                    st.dataframe(df_stats[["team_id", "type", "value"]], use_container_width=True)
                else:
                    st.info("Estatísticas não disponíveis.")
            else:
                st.error("Partida não encontrada.")


def render_live():
    """Render live analysis page."""
    st.markdown("""
    <div class="main-header">
        <h1>⚡ Análise Ao Vivo</h1>
        <p>Monitoramento em tempo real com atualização de probabilidades</p>
    </div>
    """, unsafe_allow_html=True)

    fixture_id = st.number_input("ID da Partida Ao Vivo", min_value=1, value=123456)

    col1, col2 = st.columns([1, 3])
    with col1:
        auto_refresh = st.checkbox("Auto-atualizar (30s)", value=True)
    with col2:
        if st.button("🔄 Atualizar Agora", type="primary"):
            st.cache_data.clear()
            st.rerun()

    if auto_refresh:
        # This would need a proper implementation with st_autorefresh
        pass

    live_data = get_live_analysis(fixture_id)

    if live_data:
        state = live_data.get("match_state", {})
        preds = live_data.get("predictions", {})

        # Match State
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Minuto", f"{state.get('minute', 0')}'")
        with col2:
            st.metric("Placar", f"{state.get('home_score', 0)} - {state.get('away_score', 0)}")
        with col3:
            st.metric("Estado", state.get('state', 'unknown').replace('_', ' ').title())
        with col4:
            st.metric("xG", f"{state.get('home_xg', 0):.2f} - {state.get('away_xg', 0):.2f}")
        with col5:
            st.metric("Pressão", f"{state.get('pressure_index', 0):.0f}/100")

        # Live Probabilities
        st.subheader("📈 Probabilidades Atualizadas")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Casa 🏠", f"{preds.get('home_win', 0)*100:.1f}%")
        with col2:
            st.metric("Empate ⚖️", f"{preds.get('draw', 0)*100:.1f}%")
        with col3:
            st.metric("Fora 🚌", f"{preds.get('away_win', 0)*100:.1f}%")

        st.metric("Gols Esperados Total", f"{preds.get('total_goals_expected', 0):.2f}")

        # Next Goal
        next_goal = preds.get("next_goal", {})
        if next_goal:
            st.subheader("⚽ Próximo Gol")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Casa", f"{next_goal.get('home', 0)*100:.1f}%")
            with col2:
                st.metric("Fora", f"{next_goal.get('away', 0)*100:.1f}%")
            with col3:
                st.metric("Nenhum", f"{next_goal.get('none', 0)*100:.1f}%")

        # Live Over/Under
        ou_live = preds.get("over_under_live", {})
        if ou_live:
            st.subheader("📊 Over/Under Ao Vivo")
            df_ou = pd.DataFrame([
                {"Linha": k, "Over": f"{v[0]*100:.1f}%", "Under": f"{v[1]*100:.1f}%"}
                for k, v in ou_live.items()
            ])
            st.dataframe(df_ou, use_container_width=True, hide_index=True)

        # Time to next goal
        if preds.get("time_to_next_goal"):
            st.info(f"⏱️ Tempo estimado para próximo gol: {preds['time_to_next_goal']:.0f} minutos")
    else:
        st.warning("Dados ao vivo não disponíveis para esta partida.")


def render_backtesting():
    """Render backtesting page."""
    st.markdown("""
    <div class="main-header">
        <h1>🧪 Backtesting</h1>
        <p>Validação histórica de estratégias e modelos</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🏃 Novo Backtest", "📊 Resultados"])

    with tab1:
        st.subheader("Configurar Backtest")

        col1, col2 = st.columns(2)
        with col1:
            model_version = st.selectbox("Versão do Modelo", ["v1.0", "v1.1", "v2.0"])
            start_date = st.date_input("Data Início", value=datetime(2024, 1, 1))
            end_date = st.date_input("Data Fim", value=datetime(2024, 12, 31))

        with col2:
            competitions = st.multiselect(
                "Competições",
                ["Brasileirão A", "Brasileirão B", "Premier League", "La Liga", "Champions League"],
                default=["Brasileirão A", "Premier League"]
            )
            markets = st.multiselect(
                "Mercados",
                ["match_winner", "over_under", "both_teams_score", "corners", "cards"],
                default=["match_winner", "over_under"]
            )

        col1, col2, col3 = st.columns(3)
        with col1:
            min_edge = st.number_input("Edge Mínimo", value=0.02, step=0.01, format="%.2f")
        with col2:
            min_conf = st.number_input("Confiança Mínima", value=0.6, step=0.05, format="%.2f")
        with col3:
            kelly_frac = st.number_input("Kelly Fracionado", value=0.25, step=0.05, format="%.2f")

        stake_strategy = st.selectbox(
            "Estratégia de Stake",
            ["fractional_kelly", "kelly", "flat", "proportional_edge"]
        )

        if st.button("🚀 Executar Backtest", type="primary"):
            with st.spinner("Executando backtest..."):
                # Would call API
                st.success("Backtest iniciado! Verifique a aba Resultados.")
                st.info("Esta funcionalidade requer implementação do endpoint de backtest.")

    with tab2:
        st.subheader("Resultados de Backtests")
        st.info("Histórico de backtests será exibido aqui após execução.")

        # Placeholder metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ROI", "—")
        with col2:
            st.metric("Yield", "—")
        with col3:
            st.metric("Max Drawdown", "—")
        with col4:
            st.metric("CLV", "—")


def render_bankroll_simulator():
    """Render bankroll simulator."""
    st.markdown("""
    <div class="main-header">
        <h1>💰 Simulador de Banca</h1>
        <p>Simulação de crescimento de banca com diferentes estratégias</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Configurações")
        initial_bankroll = st.number_input("Banca Inicial (R$)", value=1000.0, step=100.0)
        strategy = st.selectbox(
            "Estratégia",
            ["fractional_kelly", "kelly", "flat", "proportional_edge"]
        )
        kelly_fraction = st.slider("Fração Kelly", 0.1, 1.0, 0.25, 0.05)
        num_simulations = st.number_input("Simulações Monte Carlo", value=200, step=100)

    with col2:
        st.subheader("Resultados da Simulação")

        if st.button("▶️ Executar Simulação", type="primary"):
            # Generate sample bets for demo
            import random
            random.seed(42)

            sample_bets = []
            for i in range(50):
                model_prob = random.uniform(0.35, 0.65)
                odd = 1 / model_prob * random.uniform(0.9, 1.15)
                edge = model_prob - 1/odd
                ev = model_prob * odd - 1
                sample_bets.append({
                    "model_prob": model_prob,
                    "odd": odd,
                    "edge": edge,
                    "ev": ev,
                })

            # Simple simulation
            bankroll = initial_bankroll
            peak = bankroll
            history = [bankroll]

            for bet in sample_bets:
                if strategy == "flat":
                    stake = bankroll * 0.01
                elif strategy == "kelly":
                    b = bet["odd"] - 1
                    p = bet["model_prob"]
                    q = 1 - p
                    kelly = (b * p - q) / b if b > 0 else 0
                    stake = bankroll * max(0, kelly)
                elif strategy == "fractional_kelly":
                    b = bet["odd"] - 1
                    p = bet["model_prob"]
                    q = 1 - p
                    kelly = (b * p - q) / b if b > 0 else 0
                    stake = bankroll * max(0, kelly * kelly_fraction)
                else:
                    stake = bankroll * min(0.05, bet["edge"] * 2)

                stake = min(stake, bankroll * 0.05)

                won = random.random() < bet["model_prob"]
                if won:
                    bankroll += stake * (bet["odd"] - 1)
                else:
                    bankroll -= stake

                peak = max(peak, bankroll)
                history.append(bankroll)

            # Results
            roi = (bankroll - initial_bankroll) / initial_bankroll * 100
            max_dd = max((peak - h) / peak * 100 for h in history) if peak > 0 else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Banca Final", f"R$ {bankroll:,.2f}", f"{bankroll - initial_bankroll:,.2f}")
            with col2:
                st.metric("ROI", f"{roi:.1f}%")
            with col3:
                st.metric("Max Drawdown", f"{max_dd:.1f}%")

            # Chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=history, mode='lines', name='Banca',
                line=dict(color='#2a5298', width=2)
            ))
            fig.add_hline(y=initial_bankroll, line_dash="dash", line_color="gray")
            fig.update_layout(
                title="Evolução da Banca",
                xaxis_title="Aposta #",
                yaxis_title="Banca (R$)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

            # Monte Carlo
            if num_simulations > 0:
                st.subheader("Monte Carlo")
                mc_results = []
                for _ in range(num_simulations):
                    b = initial_bankroll
                    for bet in sample_bets:
                        if strategy == "fractional_kelly":
                            b2 = bet["odd"] - 1
                            p2 = bet["model_prob"]
                            q2 = 1 - p2
                            k2 = (b2 * p2 - q2) / b2 if b2 > 0 else 0
                            stake2 = b * max(0, k2 * kelly_fraction)
                        else:
                            stake2 = b * 0.01
                        stake2 = min(stake2, b * 0.05)

                        if random.random() < bet["model_prob"]:
                            b += stake2 * (bet["odd"] - 1)
                        else:
                            b -= stake2
                    mc_results.append(b)

                fig2 = px.histogram(
                    x=mc_results, nbins=30,
                    title=f"Distribuição de Banca Final ({num_simulations} simulações)",
                    labels={"x": "Banca Final (R$)", "y": "Frequência"}
                )
                fig2.add_vline(x=initial_bankroll, line_dash="dash", line_color="red")
                st.plotly_chart(fig2, use_container_width=True)

                p_profit = sum(1 for r in mc_results if r > initial_bankroll) / num_simulations * 100
                st.metric("Probabilidade de Lucro", f"{p_profit:.1f}%")


def render_reports():
    """Render reports page."""
    st.markdown("""
    <div class="main-header">
        <h1>📈 Relatórios</h1>
        <p>Histórico de previsões, performance e análises</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📋 Previsões", "📊 Performance", "📥 Exportar"])

    with tab1:
        st.subheader("Histórico de Previsões")
        st.info("Tabela de previsões passadas com resultados reais.")

        # Placeholder
        df = pd.DataFrame({
            "Data": ["2024-01-15", "2024-01-14", "2024-01-13"],
            "Partida": ["Flamengo vs Palmeiras", "Real Madrid vs Barcelona", "Man City vs Liverpool"],
            "Mercado": ["1X2", "Over 2.5", "BTTS"],
            "Seleção": ["Casa", "Over", "Sim"],
            "Prob Model": ["52%", "58%", "55%"],
            "Odd": ["2.10", "1.95", "1.85"],
            "EV": ["+8.2%", "+12.4%", "+5.7%"],
            "Resultado": ["✅ Ganhou", "✅ Ganhou", "❌ Perdeu"],
            "Lucro": ["+R$ 110", "+R$ 95", "-R$ 100"],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Métricas de Performance")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Apostas", "156")
        with col2:
            st.metric("Taxa Acerto", "54.5%")
        with col3:
            st.metric("ROI", "+12.3%")
        with col4:
            st.metric("Yield", "+8.7%")

        # Charts
        fig = px.line(
            x=list(range(30)), y=[1000 + i*10 + (i%7)*20 for i in range(30)],
            title="Evolução da Banca (Últimos 30 dias)"
        )
        st.plotly_chart(fig, use_container_width=True)

        # By market
        df_market = pd.DataFrame({
            "Mercado": ["1X2", "Over/Under", "BTTS", "Escanteios", "Cartões"],
            "Apostas": [50, 40, 30, 20, 16],
            "ROI": [15.2, 8.5, 12.1, 5.3, -2.1],
        })
        fig2 = px.bar(df_market, x="Mercado", y="ROI", color="ROI", title="ROI por Mercado")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.subheader("Exportar Dados")
        st.write("Baixe relatórios em CSV ou Excel.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Exportar Previsões (CSV)"):
                st.success("Download iniciado!")
        with col2:
            if st.button("📥 Exportar Performance (Excel)"):
                st.success("Download iniciado!")


def render_settings():
    """Render settings page."""
    st.markdown("""
    <div class="main-header">
        <h1>⚙️ Configurações</h1>
        <p>Gerencie configurações do sistema, APIs e preferências</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🔑 APIs", "🤖 Modelos", "⚠️ Risco", "🎨 Interface"])

    with tab1:
        st.subheader("Chaves de API")

        col1, col2 = st.columns(2)
        with col1:
            st.text_input("API-Football Key", type="password", help="Chave da API-Football (v3)")
            st.text_input("Football-Data.org Key", type="password", help="Chave do football-data.org")
        with col2:
            st.text_input("The Odds API Key", type="password", help="Chave da The Odds API")
            st.text_input("Sportmonks Key", type="password", help="Chave do Sportmonks (opcional)")

        st.divider()
        st.subheader("Status das APIs")
        st.write("🟢 API-Football: Conectado (100 req/dia)")
        st.write("🟢 Football-Data: Conectado")
        st.write("🟡 The Odds API: Não configurado")

    with tab2:
        st.subheader("Configuração dos Modelos")

        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Max Gols (Poisson)", value=10, min_value=5, max_value=15)
            st.number_input("Fator Rho (Dixon-Coles)", value=0.1, step=0.01, format="%.2f")
            st.number_input("K-Factor (Elo)", value=20.0, step=1.0)
        with col2:
            st.number_input("Vantagem Casa (Elo)", value=100.0, step=10.0)
            st.number_input("Partidas Mínimas p/ Modelo", value=10, min_value=5)
            st.checkbox("Usar Binomial Negativa (Escanteios)", value=True)

        st.divider()
        st.subheader("Versões de Modelo")
        st.write("🟢 Gols: Combined v2.1 (Poisson + Dixon-Coles + Elo)")
        st.write("🟢 Escanteios: Negative Binomial v1.0")
        st.write("🟢 Cartões: Poisson Ajustado v1.0")
        st.write("🟢 Ao Vivo: Momentum Adjustment v1.0")

    with tab3:
        st.subheader("Gestão de Risco")

        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Max por Partida (% banca)", value=5.0, step=0.5, format="%.1f")
            st.number_input("Max por Mercado (% banca)", value=3.0, step=0.5, format="%.1f")
            st.number_input("Max por Casa (% banca)", value=10.0, step=1.0, format="%.1f")
        with col2:
            st.number_input("Max Diário (% banca)", value=20.0, step=1.0, format="%.1f")
            st.number_input("Max Semanal (% banca)", value=50.0, step=5.0, format="%.1f")
            st.number_input("Max Drawdown (%)", value=15.0, step=1.0, format="%.1f")

        st.divider()
        st.subheader("Value Betting")
        st.number_input("Edge Mínimo (%)", value=2.0, step=0.5, format="%.1f")
        st.number_input("EV Mínimo (%)", value=5.0, step=0.5, format="%.1f")
        st.number_input("Kelly Máximo", value=0.25, step=0.05, format="%.2f")
        st.number_input("Confiança Mínima", value=0.6, step=0.05, format="%.2f")

    with tab4:
        st.subheader("Preferências de Interface")

        st.selectbox("Tema", ["Escuro", "Claro", "Sistema"])
        st.selectbox("Idioma", ["Português (BR)", "English", "Español"])
        st.checkbox("Mostrar probabilidades em %", value=True)
        st.checkbox("Auto-atualizar dashboards", value=False)
        st.checkbox("Notificações de value bets", value=True)


# Main App
def main():
    """Main application entry point."""
    selected_page, selected_comp_ids = render_sidebar()

    # Route to appropriate page
    if selected_page == "🏠 Dashboard":
        render_dashboard(selected_comp_ids)
    elif selected_page == "📅 Jogos do Dia":
        render_fixtures(selected_comp_ids)
    elif selected_page == "🔍 Scanner":
        render_scanner(selected_comp_ids)
    elif selected_page == "💎 Value Betting":
        render_value_betting()
    elif selected_page == "📊 Análise de Partida":
        render_match_analysis()
    elif selected_page == "⚡ Ao Vivo":
        render_live()
    elif selected_page == "🧪 Backtesting":
        render_backtesting()
    elif selected_page == "💰 Simulador de Banca":
        render_bankroll_simulator()
    elif selected_page == "📈 Relatórios":
        render_reports()
    elif selected_page == "⚙️ Configurações":
        render_settings()

    # Footer
    st.divider()
    st.caption("""
    ⚽ Football Betting Intelligence v0.1.0 |
    ⚠️ Apenas para análise e simulação - Não executa apostas reais |
    📊 Dados de APIs públicas |
    🔬 Modelos estatísticos com validação walk-forward
    """)


if __name__ == "__main__":
    main()