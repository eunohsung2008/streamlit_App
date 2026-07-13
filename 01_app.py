import streamlit as st
import requests

# ==============================
# 페이지 설정
# ==============================

st.set_page_config(
    page_title="🎬 Cinema Gallery",
    page_icon="🎥",
    layout="wide"
)

# ==============================
# CSS
# ==============================

st.markdown("""
<style>

.stApp{
    background: linear-gradient(to bottom,#090909,#1a0000,#000000);
    color:white;
}

.title{
    text-align:center;
    font-size:60px;
    font-weight:bold;
    color:#FFD700;
    letter-spacing:4px;
    text-shadow:
        0px 0px 10px red,
        0px 0px 25px gold;
}

.subtitle{
    text-align:center;
    font-size:22px;
    color:white;
    margin-bottom:40px;
}

.movie_card{
    background:#1b1b1b;
    border-radius:20px;
    padding:20px;
    box-shadow:0px 0px 20px #770000;
    transition:0.3s;
}

.movie_card:hover{
    box-shadow:0px 0px 35px gold;
}

.poster{
    border-radius:15px;
}

</style>
""", unsafe_allow_html=True)

# ==============================
# 제목
# ==============================

st.markdown('<div class="title">🎬 CINEMA NOW 🎬</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="subtitle">현재 국내 영화관에서 상영 중인 영화</div>',
    unsafe_allow_html=True
)

# ==============================
# API KEY
# ==============================

API_KEY = st.secrets["f63c3349f673e39737a62d58ee80169b"]

headers = {
    "accept": "application/json"
}

# ==============================
# 현재 상영작
# ==============================

url = f"https://api.themoviedb.org/3/movie/now_playing?language=ko-KR&page=1&api_key={API_KEY}"

movies = requests.get(url, headers=headers).json()["results"]

poster_base = "https://image.tmdb.org/t/p/w500"

cols = st.columns(4)

for i, movie in enumerate(movies[:12]):

    movie_id = movie["id"]

    detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}?language=ko-KR&append_to_response=credits&api_key={API_KEY}"

    detail = requests.get(detail_url).json()

    director = "정보 없음"

    for crew in detail["credits"]["crew"]:
        if crew["job"] == "Director":
            director = crew["name"]
            break

    actors = []

    for actor in detail["credits"]["cast"][:3]:
        actors.append(actor["name"])

    with cols[i % 4]:

        st.markdown('<div class="movie_card">', unsafe_allow_html=True)

        if movie["poster_path"]:
            st.image(
                poster_base + movie["poster_path"],
                use_container_width=True
            )

        st.markdown(f"## {movie['title']}")

        st.write("🎬 감독")
        st.write(director)

        st.write("⭐ 주연 배우")

        for actor in actors:
            st.write(f"• {actor}")

        st.markdown("</div>", unsafe_allow_html=True)
