import streamlit as st
import requests
import pandas as pd
import time
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="📈 محلل الأسهم الذكي (مع تعامل مع Rate Limit)", layout="wide")

API_KEY = "LN6ZJE3WMZEGIZB9"  # مفتاح Alpha Vantage (يمكن تغييره)

# تخزين مؤقت لنتائج الجلب لتقليل الطلبات المتكررة (TTL = 60 ثانية - اضبط كما تريد)
@st.cache_data(ttl=60)
def fetch_from_alpha_vantage(symbol: str):
    """
    ترجع dict أو ترفع استثناء يتضمن رسالة الخطأ.
    """
    base_q = "https://www.alphavantage.co/query"
    # سنستخدم TIME_SERIES_DAILY_ADJUSTED لإظهار بيانات يومية
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": API_KEY
    }

    resp = requests.get(base_q, params=params, timeout=15)
    data = resp.json()

    # تعامل مع رسائل Alpha Vantage
    if "Note" in data:
        raise RuntimeError("Alpha Vantage: تجاوزت حد الطلبات (Note returned).")
    if "Error Message" in data:
        raise RuntimeError("Alpha Vantage: رمز السهم غير صحيح أو لم تجد بيانات.")
    if "Time Series (Daily)" not in data:
        raise RuntimeError("Alpha Vantage: لم يتم العثور على بيانات يومية في الاستجابة.")
    return data

def fetch_with_retries(symbol: str, max_attempts=3):
    """
    محاولة جلب من Alpha Vantage مع تأخير متصاعد. إذا فشل بسبب Rate Limit أو خطأ، نعيد رسالة الخطأ.
    """
    attempt = 0
    while attempt < max_attempts:
        try:
            return fetch_from_alpha_vantage(symbol)
        except Exception as e:
            # إذا كانت مشكلة مؤقتة (تجاوز حد الطلبات)، ننتظر ثم نعيد المحاولة
            attempt += 1
            # لا نعيد المحاولة كثيرًا لأن المفتاح قد يكون محظورًا مؤقتًا من API
            wait_seconds = 2 ** attempt  # 2, 4, 8 ...
            st.warning(f"محاولة {attempt}/{max_attempts} فشلت: {e}. إعادة المحاولة بعد {wait_seconds}s...")
            time.sleep(wait_seconds)
    # بعد المحاولات، نُشير إلى الفشل
    raise RuntimeError("فشل في جلب البيانات من Alpha Vantage بعد عدة محاولات.")

def av_to_dataframe(av_json):
    ts = av_json["Time Series (Daily)"]
    df = pd.DataFrame(ts).T
    df.index = pd.to_datetime(df.index)
    df = df.astype(float)
    df = df.rename(columns={
        "1. open": "Open",
        "2. high": "High",
        "3. low": "Low",
        "4. close": "Close",
        "5. adjusted close": "Adj Close",
        "6. volume": "Volume",
        "7. dividend amount": "Dividend",
        "8. split coefficient": "Split"
    })
    df = df.sort_index(ascending=False)
    return df

def fetch_from_yfinance(symbol: str, period="6mo"):
    """
    بديل مجاني عملي (بدون قيود Alpha Vantage الصارمة) باستخدام yfinance.
    يعيد dataframe مشابه.
    """
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist is None or hist.empty:
            raise RuntimeError("yfinance: لا توجد بيانات لهذه الفترة/الرمز.")
        df = hist.copy()
        df.index = pd.to_datetime(df.index)
        # توحيد أسماء الأعمدة لتطابق المتوقع
        df = df.rename(columns={
            "Open": "Open", "High": "High", "Low": "Low", "Close": "Close",
            "Volume": "Volume", "Dividends": "Dividend", "Stock Splits": "Split"
        })
        df = df.sort_index(ascending=False)
        return df
    except Exception as e:
        raise RuntimeError(f"yfinance error: {e}")

# ---------- واجهة المستخدم ----------
st.title("📊 محلل الأسهم الذكي — مع احتواء Rate Limit")
st.write("يدعم Alpha Vantage مع محاولات تلقائية، ويتحول إلى yfinance كخطة احتياطية عند الفشل.")

col1, col2 = st.columns([3,1])
with col1:
    symbol = st.text_input("أدخل رمز السهم (مثال: AAPL, MSFT, TSLA)", value="AAPL").upper().strip()
with col2:
    days = st.selectbox("رسم لـ", ("1mo","3mo","6mo","1y","2y"), index=2)

if st.button("جلب وتحليل"):
    if not symbol:
        st.error("الرجاء إدخال رمز السهم.")
    else:
        loader = st.info("جاري جلب البيانات...")
        df = None
        used_source = None
        # أولًا: نجرب Alpha Vantage مع محاولات
        try:
            av_json = fetch_with_retries(symbol, max_attempts=3)
            df = av_to_dataframe(av_json)
            used_source = "Alpha Vantage"
        except Exception as e_av:
            st.warning(f"Alpha Vantage فشل: {e_av}")
            st.info("الآن سنحاول جلب البيانات من مصدر بديل (yfinance).")
            # تجربة المصدر البديل
            try:
                df = fetch_from_yfinance(symbol, period=days)
                used_source = "yfinance"
            except Exception as e_yf:
                st.error(f"فشل الحصول على بيانات من كل المصادر. تفاصيل: {e_yf}")
                loader.empty()
                st.stop()

        loader.empty()

        # الآن نعرض النتائج
        if df is not None:
            # آخر سعر وتغير
            last_close = float(df["Close"].iloc[0])
            prev_close = float(df["Close"].iloc[1]) if len(df) > 1 else last_close
            change = last_close - prev_close
            percent = (change / prev_close * 100) if prev_close != 0 else 0.0

            st.metric(label=f"آخر سعر ({symbol}) — المصدر: {used_source}", value=f"${last_close:.2f}", delta=f"{percent:.2f}%")
            st.subheader("الرسم البياني لأسعار الإغلاق")
            st.line_chart(df["Close"])

            with st.expander("عرض بيانات الجدول (أول 50 صف)"):
                st.dataframe(df.head(50))

            # بعض المؤشرات البسيطة
            st.subheader("مؤشرات بسيطة")
            ma20 = df["Close"].rolling(window=20).mean().iloc[0] if len(df) >= 20 else None
            ma50 = df["Close"].rolling(window=50).mean().iloc[0] if len(df) >= 50 else None
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("MA20", f"{ma20:.2f}" if ma20 is not None else "غير متوفر")
            col_b.metric("MA50", f"{ma50:.2f}" if ma50 is not None else "غير متوفر")
            col_c.metric("حجم آخر يوم", f"{int(df['Volume'].iloc[0]):,}")

            st.info("ملاحظة: توقعات الأسعار غير مضمنة هنا — هذا تطبيق للاطلاع والتحليل السريع. للاستعلامات المكثفة/التلقائية، استخدم مفاتيح Alpha Vantage متعددة أو مصدر مدفوع.")
