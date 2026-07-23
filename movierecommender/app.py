from __future__ import annotations

import random
from datetime import date
from typing import Any

import requests
import streamlit as st


# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="CINEMA ARCHIVE",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
PLACEHOLDER_POSTER = "https://placehold.co/500x750/171717/e5e5e5?text=NO+POSTER"
CURRENT_YEAR = date.today().year
CURRENT_DECADE = (CURRENT_YEAR // 10) * 10

try:
    TMDB_API_KEY = st.secrets["TMDB_API_KEY"]
except KeyError:
    st.error(
        "TMDB API 키가 설정되지 않았습니다. "
        "Streamlit Cloud의 App settings → Secrets에 "
        '`TMDB_API_KEY = "발급받은_API_키"`를 입력해 주세요.'
    )
    st.stop()


# =========================================================
# 영화관 스타일
# =========================================================
st.markdown(
    """
    <style>
    :root {
        --cinema-red: #b20710;
        --cinema-red-light: #e50914;
        --cinema-gold: #d8b25c;
        --screen-white: #f5f1e8;
        --panel: rgba(20, 20, 24, 0.92);
    }

    .stApp {
        background:
            radial-gradient(circle at 50% 0%, rgba(95, 16, 23, 0.30), transparent 34rem),
            linear-gradient(180deg, #070709 0%, #111116 52%, #08080b 100%);
        color: #f5f5f5;
    }

    [data-testid="stSidebar"] {
        background:
            linear-gradient(180deg, rgba(64, 5, 10, 0.97), rgba(12, 12, 16, 0.99));
        border-right: 1px solid rgba(216, 178, 92, 0.26);
    }

    [data-testid="stHeader"] {
        background: rgba(0, 0, 0, 0);
    }

    .block-container {
        max-width: 1500px;
        padding-top: 1.4rem;
        padding-bottom: 4rem;
    }

    .cinema-screen {
        position: relative;
        margin: 0 auto 2rem auto;
        padding: 3.8rem 2rem 4.3rem;
        text-align: center;
        color: #18181b;
        background:
            linear-gradient(rgba(255,255,255,0.90), rgba(238,232,218,0.96)),
            repeating-linear-gradient(
                0deg,
                rgba(0,0,0,0.025) 0px,
                rgba(0,0,0,0.025) 1px,
                transparent 1px,
                transparent 3px
            );
        border-radius: 4px;
        border: 7px solid #29292e;
        box-shadow:
            0 0 0 2px #6f6f74,
            0 22px 65px rgba(0,0,0,0.78),
            inset 0 0 40px rgba(0,0,0,0.10);
        clip-path: polygon(2% 0, 98% 0, 100% 100%, 0 100%);
    }

    .cinema-screen::before,
    .cinema-screen::after {
        content: "";
        position: absolute;
        top: 0;
        width: 14%;
        height: 100%;
        background: linear-gradient(90deg, #51070c, #b20710 55%, #47060a);
        box-shadow: inset 0 0 25px rgba(0,0,0,0.65);
        z-index: -1;
    }

    .cinema-screen::before { left: -10%; }
    .cinema-screen::after  { right: -10%; transform: scaleX(-1); }

    .cinema-screen h1 {
        margin: 0;
        font-size: clamp(2.1rem, 5vw, 4.8rem);
        letter-spacing: 0.16em;
        font-weight: 900;
    }

    .cinema-screen p {
        margin: 0.9rem auto 0;
        max-width: 800px;
        color: #4a4140;
        font-size: 1.03rem;
        letter-spacing: 0.04em;
    }

    .section-title {
        margin: 2rem 0 1rem;
        padding-bottom: 0.55rem;
        border-bottom: 1px solid rgba(216, 178, 92, 0.35);
        color: #f8e6b4;
        font-size: 1.5rem;
        font-weight: 800;
        letter-spacing: 0.05em;
    }

    .movie-card {
        height: 100%;
        min-height: 555px;
        padding: 0.85rem;
        background: linear-gradient(180deg, rgba(28,28,34,0.98), rgba(12,12,16,0.98));
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 12px;
        box-shadow: 0 12px 30px rgba(0,0,0,0.34);
        transition: transform 0.18s ease, border-color 0.18s ease;
    }

    .movie-card:hover {
        transform: translateY(-4px);
        border-color: rgba(216, 178, 92, 0.52);
    }

    .poster-wrap {
        width: 100%;
        aspect-ratio: 2 / 3;
        overflow: hidden;
        border-radius: 8px;
        background: #222;
    }

    .poster-wrap img {
        width: 100%;
        height: 100%;
        display: block;
        object-fit: cover;
    }

    .movie-title {
        margin-top: 0.85rem;
        min-height: 3.1rem;
        color: white;
        font-size: 1.06rem;
        font-weight: 800;
        line-height: 1.35;
    }

    .movie-meta {
        margin-top: 0.25rem;
        color: #d6c48f;
        font-size: 0.88rem;
    }

    .movie-overview {
        margin-top: 0.62rem;
        min-height: 5.8rem;
        color: #c8c8ce;
        font-size: 0.86rem;
        line-height: 1.55;
    }

    .metric-chip {
        display: inline-block;
        margin: 0.22rem 0.22rem 0 0;
        padding: 0.24rem 0.52rem;
        border-radius: 999px;
        background: rgba(178, 7, 16, 0.20);
        border: 1px solid rgba(229, 9, 20, 0.35);
        color: #ffd9db;
        font-size: 0.77rem;
    }

    .info-banner {
        margin: 1rem 0 1.4rem;
        padding: 0.8rem 1rem;
        background: rgba(216,178,92,0.09);
        border: 1px solid rgba(216,178,92,0.22);
        border-radius: 10px;
        color: #e8ddbd;
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        width: 100%;
        border: 1px solid #cf2730;
        border-radius: 8px;
        background: linear-gradient(180deg, #ca111b, #8f060d);
        color: white;
        font-weight: 800;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        border-color: #f15d65;
        color: white;
        box-shadow: 0 0 22px rgba(229,9,20,0.25);
    }

    .stTextInput input,
    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div {
        background-color: rgba(25,25,30,0.95);
        color: white;
    }

    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# TMDB API
# =========================================================
class TMDBError(RuntimeError):
    pass


@st.cache_data(ttl=60 * 60, show_spinner=False)
def tmdb_get(endpoint: str, params_items: tuple[tuple[str, Any], ...] = ()) -> dict[str, Any]:
    """TMDB API GET 요청. 캐싱 가능하도록 params를 tuple로 받는다."""
    params = dict(params_items)
    params["api_key"] = TMDB_API_KEY

    try:
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            params=params,
            timeout=12,
        )
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise TMDBError("영화 서버의 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.") from exc
    except requests.RequestException as exc:
        raise TMDBError(f"영화 정보를 불러오지 못했습니다: {exc}") from exc
    except ValueError as exc:
        raise TMDBError("영화 서버에서 올바르지 않은 응답을 받았습니다.") from exc


def api_call(endpoint: str, **params: Any) -> dict[str, Any]:
    clean_params = tuple(
        sorted((key, value) for key, value in params.items() if value not in (None, "", []))
    )
    return tmdb_get(endpoint, clean_params)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_genres() -> dict[str, int]:
    data = api_call("/genre/movie/list", language="ko-KR")
    return {
        genre["name"]: genre["id"]
        for genre in data.get("genres", [])
    }


def poster_url(path: str | None) -> str:
    return f"{IMAGE_BASE_URL}/w500{path}" if path else PLACEHOLDER_POSTER


def backdrop_url(path: str | None) -> str | None:
    return f"{IMAGE_BASE_URL}/original{path}" if path else None


def release_year(movie: dict[str, Any]) -> str:
    release_date = movie.get("release_date") or ""
    return release_date[:4] if len(release_date) >= 4 else "연도 미상"


def safe_overview(text: str | None, max_length: int = 135) -> str:
    if not text:
        return "등록된 줄거리가 없습니다."
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= max_length else cleaned[:max_length].rstrip() + "…"


def unique_movies(movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    result: list[dict[str, Any]] = []
    for movie in movies:
        movie_id = movie.get("id")
        if movie_id and movie_id not in seen:
            seen.add(movie_id)
            result.append(movie)
    return result


def discover_movies(
    decade: int,
    genre_ids: list[int],
    sort_by: str,
    min_votes: int,
    page: int,
) -> list[dict[str, Any]]:
    start_date = f"{decade}-01-01"
    decade_end = min(decade + 9, CURRENT_YEAR)
    end_date = (
        date.today().isoformat()
        if decade == CURRENT_DECADE
        else f"{decade_end}-12-31"
    )

    # TMDB의 날짜·평가 수 필터 이름에는 밑줄(_)이 아니라 점(.)이 들어간다.
    # 예: primary_release_date.gte, vote_count.gte
    params = {
        "language": "ko-KR",
        "include_adult": "false",
        "include_video": "false",
        "primary_release_date.gte": start_date,
        "primary_release_date.lte": end_date,
        "with_genres": ",".join(map(str, genre_ids)) if genre_ids else None,
        "sort_by": sort_by,
        "vote_count.gte": min_votes,
        "page": page,
    }
    clean_params = tuple(
        sorted(
            (key, value)
            for key, value in params.items()
            if value not in (None, "", [])
        )
    )
    data = tmdb_get("/discover/movie", clean_params)

    # API 응답에 잘못된 연도의 작품이 섞이더라도 화면에 표시되지 않도록
    # ISO 형식의 개봉일을 다시 한 번 엄격하게 검사한다.
    filtered_results: list[dict[str, Any]] = []
    for movie in data.get("results", []):
        movie_release_date = movie.get("release_date") or ""
        if len(movie_release_date) == 10 and start_date <= movie_release_date <= end_date:
            filtered_results.append(movie)

    return filtered_results


def search_movies_by_title(query: str) -> list[dict[str, Any]]:
    data = api_call(
        "/search/movie",
        query=query,
        language="ko-KR",
        include_adult="false",
        page=1,
    )
    return data.get("results", [])


def search_people_movies(query: str) -> tuple[list[dict[str, Any]], list[str]]:
    people_data = api_call(
        "/search/person",
        query=query,
        language="ko-KR",
        include_adult="false",
        page=1,
    )

    movies: list[dict[str, Any]] = []
    matched_names: list[str] = []

    # API 호출량과 화면 과밀화를 막기 위해 상위 4명까지만 처리
    for person in people_data.get("results", [])[:4]:
        person_id = person.get("id")
        if not person_id:
            continue

        matched_names.append(person.get("name", "이름 미상"))
        credits = api_call(
            f"/person/{person_id}/movie_credits",
            language="ko-KR",
        )

        # 배우 출연작
        for movie in credits.get("cast", []):
            movie["search_role"] = f"출연 · {person.get('name', '')}"
            movies.append(movie)

        # 감독 작품만 선별
        for movie in credits.get("crew", []):
            if movie.get("job") == "Director":
                movie["search_role"] = f"감독 · {person.get('name', '')}"
                movies.append(movie)

    movies = unique_movies(movies)
    movies.sort(
        key=lambda item: (
            item.get("popularity", 0),
            item.get("vote_count", 0),
        ),
        reverse=True,
    )
    return movies, matched_names


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def get_movie_detail(movie_id: int) -> dict[str, Any]:
    return api_call(
        f"/movie/{movie_id}",
        language="ko-KR",
        append_to_response="credits,videos",
    )


# =========================================================
# 화면 구성 요소
# =========================================================
def render_movie_card(movie: dict[str, Any], index: int, key_prefix: str) -> None:
    title = movie.get("title") or movie.get("original_title") or "제목 미상"
    year = release_year(movie)
    rating = float(movie.get("vote_average") or 0)
    votes = int(movie.get("vote_count") or 0)
    role = movie.get("search_role")

    st.markdown(
        f"""
        <div class="movie-card">
            <div class="poster-wrap">
                <img src="{poster_url(movie.get('poster_path'))}" alt="{title}">
            </div>
            <div class="movie-title">{title}</div>
            <div class="movie-meta">{year} · ★ {rating:.1f} · 평가 {votes:,}개</div>
            <div>
                {'<span class="metric-chip">' + role + '</span>' if role else ''}
                <span class="metric-chip">인기도 {float(movie.get('popularity') or 0):.0f}</span>
            </div>
            <div class="movie-overview">{safe_overview(movie.get('overview'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("상세 정보 보기"):
        try:
            detail = get_movie_detail(int(movie["id"]))
            runtime = detail.get("runtime")
            genres = ", ".join(item["name"] for item in detail.get("genres", [])) or "정보 없음"
            credits = detail.get("credits", {})
            cast_names = ", ".join(
                member.get("name", "")
                for member in credits.get("cast", [])[:5]
            ) or "정보 없음"
            directors = ", ".join(
                member.get("name", "")
                for member in credits.get("crew", [])
                if member.get("job") == "Director"
            ) or "정보 없음"

            st.markdown(f"**감독:** {directors}")
            st.markdown(f"**주요 출연진:** {cast_names}")
            st.markdown(f"**장르:** {genres}")
            st.markdown(f"**상영 시간:** {runtime}분" if runtime else "**상영 시간:** 정보 없음")
            st.write(detail.get("overview") or "등록된 줄거리가 없습니다.")

            homepage = detail.get("homepage")
            if homepage:
                st.link_button(
                    "공식 홈페이지",
                    homepage,
                    use_container_width=True,
                )
        except TMDBError as error:
            st.warning(str(error))


def render_movie_grid(
    movies: list[dict[str, Any]],
    key_prefix: str,
    max_items: int = 12,
) -> None:
    shown = movies[:max_items]
    if not shown:
        st.warning("조건에 맞는 영화를 찾지 못했습니다. 조건을 조금 넓혀 보세요.")
        return

    columns_per_row = 4
    for row_start in range(0, len(shown), columns_per_row):
        columns = st.columns(columns_per_row)
        for offset, movie in enumerate(shown[row_start:row_start + columns_per_row]):
            with columns[offset]:
                render_movie_card(movie, row_start + offset, key_prefix)


def sort_label_to_api(label: str) -> str:
    return {
        "인기순": "popularity.desc",
        "평점순": "vote_average.desc",
        "최신 개봉순": "primary_release_date.desc",
        "오래된 개봉순": "primary_release_date.asc",
    }[label]


# =========================================================
# 메인 화면
# =========================================================
st.markdown(
    """
    <div class="cinema-screen">
        <h1>CINEMA ARCHIVE</h1>
        <p>
            1900년대부터 최신작까지, 시대와 장르를 골라 발견하는 나만의 영화관
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    genres = get_genres()
except TMDBError as error:
    st.error(str(error))
    st.stop()

decades = list(range(1900, CURRENT_DECADE + 1, 10))
decade_labels = {
    decade: (
        f"{decade}년대"
        if decade < CURRENT_DECADE
        else f"{decade}년대 · 현재까지"
    )
    for decade in decades
}

with st.sidebar:
    st.markdown("## 🎟️ 상영관 설정")
    st.caption("추천받을 시대와 장르를 선택하세요.")

    with st.form("recommendation_form"):
        selected_decade = st.selectbox(
            "개봉 연대",
            decades,
            index=len(decades) - 1,
            format_func=lambda value: decade_labels[value],
        )
        selected_genres = st.multiselect(
            "장르",
            options=list(genres.keys()),
            placeholder="장르를 선택하세요",
        )
        selected_sort = st.selectbox(
            "정렬 기준",
            ["인기순", "평점순", "최신 개봉순", "오래된 개봉순"],
        )
        min_votes = st.slider(
            "최소 평가 수",
            min_value=0,
            max_value=1000,
            value=30,
            step=10,
            help="평가 수를 높이면 잘 알려진 작품 중심으로 추천됩니다.",
        )
        surprise_me = st.checkbox(
            "추천 결과를 매번 섞기",
            value=True,
            help="여러 결과 페이지 중 하나를 골라 새로운 작품을 보여줍니다.",
        )
        recommend_clicked = st.form_submit_button(
            "🎬 영화 추천받기",
            use_container_width=True,
        )

    st.markdown("---")
    st.caption("영화 정보 및 이미지는 TMDB를 이용합니다.")

# 처음 접속했을 때도 최신 2020년대 결과 표시
if "recommendation_options" not in st.session_state:
    st.session_state.recommendation_options = {
        "decade": CURRENT_DECADE,
        "genre_ids": [],
        "sort_by": "popularity.desc",
        "min_votes": 30,
        "page": 1,
    }

if recommend_clicked:
    page = random.randint(1, 8) if surprise_me else 1
    st.session_state.recommendation_options = {
        "decade": selected_decade,
        "genre_ids": [genres[name] for name in selected_genres],
        "sort_by": sort_label_to_api(selected_sort),
        "min_votes": min_votes,
        "page": page,
    }

# 탭 구성
recommend_tab, search_tab = st.tabs(
    ["🍿 시대·장르 추천", "🔎 작품·감독·출연진 검색"]
)

with recommend_tab:
    options = st.session_state.recommendation_options
    decade_text = decade_labels[options["decade"]]

    st.markdown(
        f'<div class="section-title">오늘의 상영작 · {decade_text}</div>',
        unsafe_allow_html=True,
    )

    genre_text = (
        ", ".join(selected_genres)
        if recommend_clicked and selected_genres
        else "전체 장르"
    )
    st.markdown(
        f"""
        <div class="info-banner">
            선택 조건: <b>{decade_text}</b> · <b>{genre_text}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("영사기를 준비하고 있습니다…"):
            recommendation_results = discover_movies(**options)

        # 랜덤 페이지가 비어 있으면 첫 페이지로 한 번 더 시도
        if not recommendation_results and options["page"] != 1:
            fallback_options = {**options, "page": 1}
            recommendation_results = discover_movies(**fallback_options)

        render_movie_grid(
            recommendation_results,
            key_prefix="recommend",
            max_items=12,
        )
    except TMDBError as error:
        st.error(str(error))

with search_tab:
    st.markdown(
        '<div class="section-title">통합 영화 검색</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="info-banner">
            영화 제목뿐 아니라 감독명과 배우 이름도 검색할 수 있습니다.
            인물 검색 결과에서는 해당 인물의 출연작과 감독 작품을 함께 보여줍니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("search_form", clear_on_submit=False):
        search_query = st.text_input(
            "검색어",
            placeholder="예: 인터스텔라, 봉준호, 송강호, Christopher Nolan",
        )
        search_clicked = st.form_submit_button(
            "검색",
            use_container_width=True,
        )

    if search_clicked:
        clean_query = search_query.strip()

        if not clean_query:
            st.warning("검색어를 입력해 주세요.")
        else:
            try:
                with st.spinner(f"'{clean_query}'와 관련된 상영작을 찾고 있습니다…"):
                    title_results = search_movies_by_title(clean_query)
                    people_results, matched_people = search_people_movies(clean_query)

                combined_results = unique_movies(title_results + people_results)
                combined_results.sort(
                    key=lambda item: (
                        1 if item in title_results else 0,
                        item.get("popularity", 0),
                    ),
                    reverse=True,
                )

                if matched_people:
                    st.caption(
                        "검색된 인물: " + ", ".join(matched_people)
                    )

                st.markdown(
                    f"### ‘{clean_query}’ 검색 결과 {len(combined_results)}개"
                )
                render_movie_grid(
                    combined_results,
                    key_prefix="search",
                    max_items=16,
                )
            except TMDBError as error:
                st.error(str(error))
