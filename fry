import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="📈 محلل الأسهم الذكي", layout="wide")

st.title("📊 تطبيق تحليل الأسهم")
st.write("تحليل بيانات الأسهم باستخدام واجهة Alpha Vantage API")

# إدخال رمز السهم
symbol = st.text_input("أدخل رمز السهم (مثال: AAPL، MSFT، TSLA):").upper()

# مفتاح API المجاني
API_KEY = "LN6ZJE3WMZEGIZB9"

if symbol:
    try:
        # جلب البيانات من Alpha Vantage
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}&apikey={API_KEY}"
        response = requests.get(url)
        data = response.json()

        if "Time Series (Daily)" not in data:
            st.error("حدث خطأ أثناء جلب البيانات أو تجاوزت الحد المسموح.")
        else:
            df = pd.DataFrame(data["Time Series (Daily)"]).T
            df.index = pd.to_datetime(df.index)
            df = df.astype(float)
            df = df.rename(columns={
                "1. open": "Open",
                "2. high": "High",
                "3. low": "Low",
                "4. close": "Close",
                "5. adjusted close": "Adj Close",
                "6. volume": "Volume"
            })

            # عرض آخر سعر
            last_close = df["Close"].iloc[0]
            prev_close = df["Close"].iloc[1]
            change = last_close - prev_close
            percent = (change / prev_close) * 100

            st.metric(label=f"آخر سعر ({symbol})", value=f"${last_close:.2f}", delta=f"{percent:.2f}%")

            # رسم بياني للسعر
            st.line_chart(df["Close"])

            # عرض جدول البيانات
            with st.expander("عرض البيانات التفصيلية"):
                st.dataframe(df.head(20))

    except Exception as e:
        st.error(f"حدث خطأ: {e}")
else:
    st.info("يرجى إدخال رمز السهم للبدء.")
