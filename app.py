import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta
from google import genai

# ==========================================
# SECURE CREDENTIALS SETUP
# ==========================================
# We now pull the API key securely from Streamlit's hidden secrets vault
try:
    AI_API_KEY = st.secrets["GEMINI_API_KEY"]
    ai_client = genai.Client(api_key=AI_API_KEY)
except KeyError:
    st.error("API Key not found! Please add GEMINI_API_KEY to your Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Stock Insights App", layout="wide")

# Custom CSS for hover zoom effect on cards
st.markdown("""
<style>
div[data-testid="stVerticalBlockBorderWrapper"] {
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    border-radius: 12px;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.3);
    border-color: #2962ff;
}
</style>
""", unsafe_allow_html=True)

st.title("📈 Global Stock Insights App")

tab1, tab2 = st.tabs(["Dashboard (Cascade View)", "Insights Portal"])

# ==========================================
# TAB 1: READ-ONLY CASCADE DASHBOARD
# ==========================================
with tab1:
    st.header("Monitor Your Watchlist")
    st.caption("View-only market data. Enter any US ticker (e.g., AAPL) or Indian NSE ticker with '.NS' (e.g., RELIANCE.NS).")

    if "watchlist" not in st.session_state:
        st.session_state.watchlist = ['AAPL', 'MSFT', 'RELIANCE.NS', 'TCS.NS', 'TSLA']

    # Search and Add UI
    search_col, btn_col = st.columns([4, 1])
    with search_col:
        new_ticker = st.text_input(
            "Search and Add a Stock to Your Dashboard:", 
            placeholder="Type ticker symbol here..."
        ).strip().upper()
    with btn_col:
        st.write("") 
        st.write("")
        if st.button("➕ Add Stock", use_container_width=True):
            if new_ticker and new_ticker not in st.session_state.watchlist and len(st.session_state.watchlist) < 10:
                st.session_state.watchlist.append(new_ticker)
                st.rerun()

    selected_stocks = st.multiselect(
        "Active Dashboard Stocks:",
        options=st.session_state.watchlist,
        default=st.session_state.watchlist,
        max_selections=10
    )
    st.session_state.watchlist = selected_stocks

    # Global Controls
    ctrl_col1, ctrl_col2 = st.columns(2)
    with ctrl_col1:
        chart_type = st.radio("Select Chart Type:", ["Candlestick Chart", "Line Chart"], horizontal=True)
    with ctrl_col2:
        selected_interval = st.selectbox("Select Data Interval:", ["1d", "1h", "15m", "5m", "1m", "1wk"], index=0)

    cols = st.columns(5) 

    # Render Charts safely
    for index, ticker in enumerate(selected_stocks):
        is_indian = ticker.endswith(".NS") or ticker.endswith(".BO")
        
        with cols[index % 5]:
            with st.container(border=True):
                st.subheader(ticker)
                
                today = date.today()
                default_days = 7 if selected_interval in ["1m", "5m"] else 30
                
                date_range = st.date_input("Date Range:", value=(today - timedelta(days=default_days), today), key=f"date_{ticker}")
                
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(start=start_date, end=end_date + timedelta(days=1), interval=selected_interval).dropna(subset=['Close'])
                    except Exception:
                        hist = pd.DataFrame()

                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        
                        if len(hist) >= 2 and hist['Close'].iloc[-2] > 0:
                            percent_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                            delta_text = f"{percent_change:.2f}%"
                        else:
                            delta_text = "N/A" 
                            
                        currency = "₹" if is_indian else "$"
                        st.metric(label="Market Price", value=f"{currency}{current_price:.2f}", delta=delta_text)
                        
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                        
                        if chart_type == "Line Chart":
                            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='Close Price', line=dict(color='#2962ff')), row=1, col=1)
                        else:
                            fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='Candlestick'), row=1, col=1)
                        
                        volume_colors = ['#26a69a' if row['Close'] >= row['Open'] else '#ef5350' for _, row in hist.iterrows()]
                        fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name='Volume', marker_color=volume_colors), row=2, col=1)
                        
                        fig.update_layout(margin=dict(l=5, r=5, t=5, b=5), height=260, xaxis_rangeslider_visible=False, showlegend=False, hovermode="x unified")
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    else:
                        st.warning("No data found.")

# ==========================================
# TAB 2: INSIGHTS PORTAL WITH AI
# ==========================================
with tab2:
    st.header("🧠 AI Insights Portal")
    st.write("Search for a company and ask the AI a specific question about its current market position.")
    
    target_company = st.text_input("Enter a stock ticker (e.g., AAPL, TATAMOTORS.NS):", "TATAMOTORS.NS")
    user_question = st.text_area("What would you like the AI to analyze?", "What are its main strengths?")
    
    if st.button("Generate AI Insights"):
        with st.spinner(f"Fetching data and consulting AI for {target_company}..."):
            stock = yf.Ticker(target_company)
            info = stock.info
            
            industry = info.get('industry', 'N/A')
            current_price = info.get('currentPrice', 'N/A')
            
            st.subheader(f"Data for {info.get('longName', target_company)}")
            col1, col2 = st.columns(2)
            col1.write(f"**Industry:** {industry}")
            col2.write(f"**Current Price:** {current_price}")
            
            ai_prompt = f"Analyze stock {target_company}. Industry: {industry}. Price: {current_price}. Question: {user_question}"
            try:
                response = ai_client.models.generate_content(model='gemini-3.6-flash', contents=ai_prompt)
                st.subheader("🤖 AI Analysis")
                st.write(response.text)
            except Exception as e:
                st.error(f"An error occurred with the AI: {e}")