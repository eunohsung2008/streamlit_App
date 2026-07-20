import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from kiwipiepy import Kiwi
from wordcloud import WordCloud


# ---------------------------------------------------------
# Streamlit 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="YouTube 댓글 분석기",
    page_icon="▶️",
    layout="wide",
)


# ---------------------------------------------------------
# 디자인
# ---------------------------------------------------------
st.markdown(
    """
    <style>
        .block-container {
            max-width: 1250px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        .main-title {
            font-size: 2.65rem;
            font-weight: 800;
            letter-spacing: -0.04em;
            margin-bottom: 0.35rem;
        }

        .sub-title {
            color: #777777;
            font-size: 1.05rem;
            margin-bottom: 1.8rem;
        }

        .section-title {
            font-size: 1.45rem;
            font-weight: 750;
            margin-top: 0.6rem;
            margin-bottom: 0.8rem;
        }

        .comment-card {
            padding: 1rem 1.1rem;
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 14px;
            margin-bottom: 0.8rem;
        }

        .comment-author {
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        .comment-meta {
            color: #888888;
            font-size: 0.88rem;
            margin-top: 0.55rem;
        }

        div[data-testid="stMetric"] {
            border: 1px solid rgba(128, 128, 128, 0.18);
            padding: 1rem;
            border-radius: 14px;
        }

        .stButton > button {
            width: 100%;
            border-radius: 10px;
            font-weight: 700;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# 상수
# ---------------------------------------------------------
FONT_PATH = Path("fonts/NanumGothic.ttf")

KOREAN_STOPWORDS = {
    "영상",
    "댓글",
    "유튜브",
    "사람",
    "생각",
    "진짜",
    "정말",
    "너무",
    "지금",
    "이거",
    "저거",
    "그거",
    "여기",
    "거기",
    "때문",
    "정도",
    "부분",
    "오늘",
    "이번",
    "그냥",
    "뭔가",
    "하나",
    "모두",
    "여러분",
    "자신",
    "우리",
    "관련",
    "이유",
    "경우",
    "내용",
    "느낌",
    "ㅋㅋ",
    "ㅎㅎ",
    "ㅠㅠ",
    "ㅇㅇ",
}

REACTION_LABELS = [
    "반응 없음",
    "낮은 반응",
    "보통 반응",
    "높은 반응",
    "매우 높은 반응",
]


# ---------------------------------------------------------
# 유틸리티 함수
# ---------------------------------------------------------
def extract_video_id(url_or_id: str) -> str | None:
    """
    다양한 형식의 유튜브 URL 또는 영상 ID에서 영상 ID를 추출한다.
    """
    value = url_or_id.strip()

    if not value:
        return None

    # 영상 ID만 입력한 경우
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    try:
        parsed = urlparse(value)
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        path_parts = [part for part in parsed.path.split("/") if part]

        # https://youtu.be/VIDEO_ID
        if hostname in {"youtu.be", "www.youtu.be"}:
            if path_parts:
                return path_parts[0]

        # youtube.com/watch?v=VIDEO_ID
        if hostname in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
        }:
            if parsed.path == "/watch":
                query = parse_qs(parsed.query)
                video_ids = query.get("v")

                if video_ids:
                    return video_ids[0]

            # shorts, embed, live
            if path_parts and path_parts[0] in {"shorts", "embed", "live"}:
                if len(path_parts) >= 2:
                    return path_parts[1]

    except (ValueError, AttributeError):
        return None

    # URL 내부에서 ID 패턴을 한 번 더 탐색
    pattern = (
        r"(?:youtu\.be/|youtube\.com/(?:watch\?.*v=|embed/|shorts/|live/))"
        r"([A-Za-z0-9_-]{11})"
    )
    match = re.search(pattern, value)

    return match.group(1) if match else None


def format_number(value: int | str | None) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


@st.cache_resource
def get_youtube_client(api_key: str):
    """
    YouTube API 클라이언트를 한 번 생성한 후 재사용한다.
    """
    return build(
        "youtube",
        "v3",
        developerKey=api_key,
        cache_discovery=False,
    )


@st.cache_resource
def load_kiwi():
    return Kiwi()


@st.cache_data(ttl=3600, show_spinner=False)
def get_video_information(api_key: str, video_id: str) -> dict:
    youtube = get_youtube_client(api_key)

    response = (
        youtube.videos()
        .list(
            part="snippet,statistics",
            id=video_id,
        )
        .execute()
    )

    if not response.get("items"):
        raise ValueError(
            "영상을 찾을 수 없습니다. 비공개 영상이거나 링크가 올바르지 않을 수 있습니다."
        )

    item = response["items"][0]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})

    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = ""

    for size in ["maxres", "standard", "high", "medium", "default"]:
        if size in thumbnails:
            thumbnail_url = thumbnails[size].get("url", "")
            break

    return {
        "video_id": video_id,
        "title": snippet.get("title", "제목 없음"),
        "channel_title": snippet.get("channelTitle", "채널 정보 없음"),
        "published_at": snippet.get("publishedAt"),
        "description": snippet.get("description", ""),
        "thumbnail_url": thumbnail_url,
        "view_count": int(statistics.get("viewCount", 0)),
        "like_count": int(statistics.get("likeCount", 0)),
        "comment_count": int(statistics.get("commentCount", 0)),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_comments(
    api_key: str,
    video_id: str,
    requested_count: int,
    order: str,
) -> pd.DataFrame:
    """
    영상의 최상위 댓글을 페이지 단위로 수집한다.

    YouTube API의 commentThreads.list는 한 요청당 최대 100개를
    반환하므로 nextPageToken을 이용해 반복 요청한다.
    """
    youtube = get_youtube_client(api_key)

    comments = []
    next_page_token = None

    while len(comments) < requested_count:
        remaining = requested_count - len(comments)
        page_size = min(100, remaining)

        request = youtube.commentThreads().list(
            part="snippet,replies",
            videoId=video_id,
            maxResults=page_size,
            order=order,
            textFormat="plainText",
            pageToken=next_page_token,
        )

        response = request.execute()

        for item in response.get("items", []):
            thread_snippet = item.get("snippet", {})
            top_comment = thread_snippet.get("topLevelComment", {})
            comment_snippet = top_comment.get("snippet", {})

            comments.append(
                {
                    "comment_id": top_comment.get("id", ""),
                    "author": comment_snippet.get(
                        "authorDisplayName",
                        "작성자 정보 없음",
                    ),
                    "comment": comment_snippet.get("textOriginal", ""),
                    "published_at_utc": comment_snippet.get("publishedAt"),
                    "updated_at_utc": comment_snippet.get("updatedAt"),
                    "like_count": int(comment_snippet.get("likeCount", 0)),
                    "reply_count": int(thread_snippet.get("totalReplyCount", 0)),
                }
            )

            if len(comments) >= requested_count:
                break

        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            break

    df = pd.DataFrame(comments)

    if df.empty:
        return df

    # UTC 시간을 한국 시간으로 변환
    df["published_at_utc"] = pd.to_datetime(
        df["published_at_utc"],
        utc=True,
        errors="coerce",
    )

    df["published_at_kst"] = df["published_at_utc"].dt.tz_convert(
        "Asia/Seoul"
    )

    df["date"] = df["published_at_kst"].dt.date
    df["hour"] = df["published_at_kst"].dt.hour
    df["weekday"] = df["published_at_kst"].dt.day_name()

    weekday_korean = {
        "Monday": "월요일",
        "Tuesday": "화요일",
        "Wednesday": "수요일",
        "Thursday": "목요일",
        "Friday": "금요일",
        "Saturday": "토요일",
        "Sunday": "일요일",
    }

    df["weekday_korean"] = df["weekday"].map(weekday_korean)

    # 반응 점수:
    # 좋아요와 답글 수를 그대로 합치면 좋아요가 지나치게 큰 영향을 줄 수 있어
    # 로그 변환 후 답글에 약간 더 높은 가중치를 준다.
    df["reaction_score"] = (
        df["like_count"].apply(lambda x: 0 if x <= 0 else 1 + pd.np.log1p(x))
        if False
        else 0
    )

    # pd.np가 제거된 버전에서도 작동하도록 별도 계산
    import numpy as np

    df["reaction_score"] = (
        np.log1p(df["like_count"])
        + 1.5 * np.log1p(df["reply_count"])
    ).round(2)

    df["reaction_level"] = create_reaction_levels(df["reaction_score"])

    return df


def create_reaction_levels(scores: pd.Series) -> pd.Series:
    """
    표본 내부의 반응 점수 분포에 따라 댓글을 5단계로 구분한다.
    동일한 점수가 많아 분위 구분이 불가능할 경우 고정 기준을 사용한다.
    """
    if scores.empty:
        return pd.Series(dtype="object")

    try:
        ranked = scores.rank(method="first")

        return pd.qcut(
            ranked,
            q=5,
            labels=REACTION_LABELS,
        ).astype(str)

    except ValueError:
        bins = [-0.01, 0, 1, 2, 4, float("inf")]

        return pd.cut(
            scores,
            bins=bins,
            labels=REACTION_LABELS,
            include_lowest=True,
        ).astype(str)


@st.cache_data(show_spinner=False)
def extract_korean_words(
    comments: tuple[str, ...],
    min_length: int,
    extra_stopwords: tuple[str, ...],
) -> dict[str, int]:
    """
    Kiwi로 댓글을 형태소 분석하여 일반명사·고유명사를 추출한다.
    """
    kiwi = load_kiwi()

    stopwords = KOREAN_STOPWORDS.union(
        word.strip()
        for word in extra_stopwords
        if word.strip()
    )

    frequencies: dict[str, int] = {}

    for text in comments:
        if not isinstance(text, str):
            continue

        # URL과 불필요한 기호 제거
        cleaned = re.sub(r"https?://\S+", " ", text)
        cleaned = re.sub(r"www\.\S+", " ", cleaned)
        cleaned = re.sub(r"[^가-힣A-Za-z0-9\s]", " ", cleaned)

        for token in kiwi.tokenize(cleaned):
            # NNG: 일반 명사, NNP: 고유 명사
            if token.tag not in {"NNG", "NNP"}:
                continue

            word = token.form.strip()

            if len(word) < min_length:
                continue

            if word in stopwords:
                continue

            if word.isdigit():
                continue

            frequencies[word] = frequencies.get(word, 0) + 1

    return frequencies


def make_wordcloud(
    frequencies: dict[str, int],
    max_words: int,
):
    if not FONT_PATH.exists():
        raise FileNotFoundError(
            "fonts/NanumGothic.ttf 파일을 찾을 수 없습니다."
        )

    wordcloud = WordCloud(
        font_path=str(FONT_PATH),
        width=1400,
        height=750,
        background_color="white",
        max_words=max_words,
        collocations=False,
        prefer_horizontal=0.9,
        min_font_size=8,
        random_state=42,
    ).generate_from_frequencies(frequencies)

    fig, ax = plt.subplots(figsize=(14, 7.5))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout(pad=0)

    return fig


def escape_html(text: str) -> str:
    """
    댓글을 HTML 카드에 안전하게 출력하기 위한 최소 이스케이프 처리.
    """
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def convert_dataframe_to_csv(df: pd.DataFrame) -> bytes:
    export_df = df.copy()

    if "published_at_kst" in export_df.columns:
        export_df["published_at_kst"] = export_df[
            "published_at_kst"
        ].astype(str)

    if "published_at_utc" in export_df.columns:
        export_df["published_at_utc"] = export_df[
            "published_at_utc"
        ].astype(str)

    return export_df.to_csv(index=False).encode("utf-8-sig")


# ---------------------------------------------------------
# API 키 확인
# ---------------------------------------------------------
try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except KeyError:
    st.error(
        "YouTube API 키가 설정되지 않았습니다. "
        "Streamlit Cloud의 Settings → Secrets에 "
        '`YOUTUBE_API_KEY = "API 키"` 형식으로 등록해 주세요.'
    )
    st.stop()


# ---------------------------------------------------------
# 화면 상단
# ---------------------------------------------------------
st.markdown(
    '<div class="main-title">▶️ YouTube 댓글 분석기</div>',
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="sub-title">
        유튜브 댓글의 작성 시점, 반응도와 주요 키워드를 한눈에 분석합니다.
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# 입력 폼
# ---------------------------------------------------------
with st.form("analysis_form"):
    video_url = st.text_input(
        "유튜브 영상 링크",
        placeholder="https://www.youtube.com/watch?v=...",
    )

    setting_col1, setting_col2 = st.columns(2)

    with setting_col1:
        requested_count = st.slider(
            "분석할 댓글 수",
            min_value=10,
            max_value=1000,
            value=200,
            step=10,
            help=(
                "영상에 존재하는 최상위 댓글 수가 설정값보다 적으면 "
                "수집 가능한 댓글까지만 분석합니다."
            ),
        )

    with setting_col2:
        order_label = st.selectbox(
            "댓글 수집 기준",
            options=["최신순", "관련도순"],
            help=(
                "최신순은 최근 댓글부터, 관련도순은 YouTube가 "
                "관련성이 높다고 판단한 댓글부터 불러옵니다."
            ),
        )

    submitted = st.form_submit_button(
        "댓글 분석 시작",
        type="primary",
    )


# ---------------------------------------------------------
# 분석 실행
# ---------------------------------------------------------
if submitted:
    video_id = extract_video_id(video_url)

    if not video_id:
        st.error("올바른 유튜브 영상 링크 또는 11자리 영상 ID를 입력해 주세요.")
        st.stop()

    order = "time" if order_label == "최신순" else "relevance"

    try:
        with st.spinner("영상 정보와 댓글을 불러오고 있습니다..."):
            video_info = get_video_information(
                YOUTUBE_API_KEY,
                video_id,
            )

            comments_df = fetch_comments(
                YOUTUBE_API_KEY,
                video_id,
                requested_count,
                order,
            )

    except HttpError as error:
        error_text = str(error)

        if "commentsDisabled" in error_text:
            st.error("이 영상은 댓글 기능이 비활성화되어 있습니다.")
        elif "quotaExceeded" in error_text:
            st.error(
                "YouTube API의 일일 할당량을 모두 사용했습니다. "
                "Google Cloud Console에서 할당량을 확인해 주세요."
            )
        elif "keyInvalid" in error_text:
            st.error("YouTube API 키가 올바르지 않습니다.")
        elif "forbidden" in error_text.lower():
            st.error(
                "댓글에 접근할 수 없습니다. 비공개 영상이거나 "
                "API 접근이 제한되었을 수 있습니다."
            )
        else:
            st.error(f"YouTube API 요청 중 오류가 발생했습니다: {error}")

        st.stop()

    except ValueError as error:
        st.error(str(error))
        st.stop()

    except Exception as error:
        st.error(f"분석 중 예상하지 못한 오류가 발생했습니다: {error}")
        st.stop()

    if comments_df.empty:
        st.warning(
            "가져올 수 있는 댓글이 없습니다. "
            "댓글이 없거나 댓글 공개가 제한된 영상일 수 있습니다."
        )
        st.stop()

    # 다음 재실행 전까지 결과 유지
    st.session_state["video_info"] = video_info
    st.session_state["comments_df"] = comments_df
    st.session_state["video_url"] = (
        f"https://www.youtube.com/watch?v={video_id}"
    )


# ---------------------------------------------------------
# 분석 결과 출력
# ---------------------------------------------------------
if (
    "video_info" in st.session_state
    and "comments_df" in st.session_state
):
    video_info = st.session_state["video_info"]
    comments_df = st.session_state["comments_df"]
    canonical_video_url = st.session_state["video_url"]

    st.divider()

    # 영상 표시
    video_col, info_col = st.columns([1.45, 1])

    with video_col:
        st.video(canonical_video_url)

    with info_col:
        st.markdown("### 영상 정보")
        st.markdown(f"#### {video_info['title']}")
        st.caption(f"채널: {video_info['channel_title']}")

        if video_info["published_at"]:
            video_date = pd.to_datetime(
                video_info["published_at"],
                utc=True,
            ).tz_convert("Asia/Seoul")

            st.caption(
                "게시일: "
                f"{video_date.strftime('%Y년 %m월 %d일 %H:%M')} KST"
            )

        st.write(
            video_info["description"][:350]
            + ("..." if len(video_info["description"]) > 350 else "")
        )

    # 핵심 지표
    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:
        st.metric(
            "영상 조회 수",
            format_number(video_info["view_count"]),
        )

    with metric2:
        st.metric(
            "영상 좋아요 수",
            format_number(video_info["like_count"]),
        )

    with metric3:
        st.metric(
            "영상 전체 댓글 수",
            format_number(video_info["comment_count"]),
        )

    with metric4:
        st.metric(
            "실제 분석 댓글 수",
            format_number(len(comments_df)),
        )

    st.caption(
        "영상 전체 댓글 수는 YouTube 영상 통계이며, 실제 분석 수는 "
        "설정한 개수와 API에서 가져올 수 있었던 최상위 댓글 수에 따라 달라집니다."
    )

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🕒 작성 추이",
            "👍 댓글 반응도",
            "☁️ 한글 워드클라우드",
            "💬 댓글 데이터",
        ]
    )

    # -----------------------------------------------------
    # 탭 1: 시간대별 작성 추이
    # -----------------------------------------------------
    with tab1:
        st.markdown(
            '<div class="section-title">시간대별 댓글 작성 추이</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "댓글 작성 시각은 UTC에서 한국 표준시(KST)로 변환했습니다."
        )

        hourly_counts = (
            comments_df.groupby("hour")
            .size()
            .reindex(range(24), fill_value=0)
            .reset_index(name="comment_count")
        )

        hourly_counts["time_label"] = hourly_counts["hour"].apply(
            lambda hour: f"{hour:02d}시"
        )

        hourly_fig = px.bar(
            hourly_counts,
            x="time_label",
            y="comment_count",
            labels={
                "time_label": "작성 시간대",
                "comment_count": "댓글 수",
            },
            text="comment_count",
        )

        hourly_fig.update_traces(
            hovertemplate=(
                "시간대: %{x}<br>"
                "댓글 수: %{y:,}개"
                "<extra></extra>"
            )
        )

        hourly_fig.update_layout(
            height=470,
            xaxis_title="작성 시간대(KST)",
            yaxis_title="댓글 수",
            showlegend=False,
        )

        st.plotly_chart(hourly_fig, width="stretch")

        peak_hour_row = hourly_counts.loc[
            hourly_counts["comment_count"].idxmax()
        ]

        st.info(
            f"분석한 댓글은 **{int(peak_hour_row['hour']):02d}시대**에 "
            f"가장 많이 작성되었습니다 "
            f"({int(peak_hour_row['comment_count']):,}개)."
        )

        st.markdown("#### 날짜별 댓글 작성 추이")

        daily_counts = (
            comments_df.groupby("date")
            .size()
            .reset_index(name="comment_count")
            .sort_values("date")
        )

        daily_counts["cumulative_count"] = daily_counts[
            "comment_count"
        ].cumsum()

        daily_fig = px.line(
            daily_counts,
            x="date",
            y="comment_count",
            markers=True,
            labels={
                "date": "작성 날짜",
                "comment_count": "댓글 수",
            },
        )

        daily_fig.update_traces(
            hovertemplate=(
                "날짜: %{x}<br>"
                "댓글 수: %{y:,}개"
                "<extra></extra>"
            )
        )

        daily_fig.update_layout(
            height=430,
            xaxis_title="작성 날짜(KST)",
            yaxis_title="댓글 수",
        )

        st.plotly_chart(daily_fig, width="stretch")

        with st.expander("요일별 댓글 작성 분포 보기"):
            weekday_order = [
                "월요일",
                "화요일",
                "수요일",
                "목요일",
                "금요일",
                "토요일",
                "일요일",
            ]

            weekday_counts = (
                comments_df.groupby("weekday_korean")
                .size()
                .reindex(weekday_order, fill_value=0)
                .reset_index(name="comment_count")
            )

            weekday_fig = px.bar(
                weekday_counts,
                x="weekday_korean",
                y="comment_count",
                labels={
                    "weekday_korean": "요일",
                    "comment_count": "댓글 수",
                },
                text="comment_count",
            )

            weekday_fig.update_layout(
                height=400,
                showlegend=False,
            )

            st.plotly_chart(weekday_fig, width="stretch")

    # -----------------------------------------------------
    # 탭 2: 댓글 반응도
    # -----------------------------------------------------
    with tab2:
        st.markdown(
            '<div class="section-title">댓글 반응도 분석</div>',
            unsafe_allow_html=True,
        )

        average_likes = comments_df["like_count"].mean()
        median_likes = comments_df["like_count"].median()
        total_replies = comments_df["reply_count"].sum()
        reacted_ratio = (
            (
                (comments_df["like_count"] > 0)
                | (comments_df["reply_count"] > 0)
            ).mean()
            * 100
        )

        reaction_metric1, reaction_metric2, reaction_metric3, reaction_metric4 = (
            st.columns(4)
        )

        with reaction_metric1:
            st.metric(
                "댓글당 평균 좋아요",
                f"{average_likes:,.1f}",
            )

        with reaction_metric2:
            st.metric(
                "좋아요 중앙값",
                f"{median_likes:,.0f}",
            )

        with reaction_metric3:
            st.metric(
                "분석 댓글의 총 답글 수",
                format_number(total_replies),
            )

        with reaction_metric4:
            st.metric(
                "반응이 있는 댓글 비율",
                f"{reacted_ratio:.1f}%",
            )

        st.caption(
            "반응이 있는 댓글은 좋아요가 1개 이상이거나 답글이 1개 이상인 댓글입니다. "
            "반응 점수는 `log(1+좋아요 수) + 1.5×log(1+답글 수)`로 계산해 "
            "극단적으로 큰 좋아요 수의 영향을 줄였습니다."
        )

        reaction_counts = (
            comments_df["reaction_level"]
            .value_counts()
            .reindex(REACTION_LABELS, fill_value=0)
            .reset_index()
        )

        reaction_counts.columns = [
            "reaction_level",
            "comment_count",
        ]

        reaction_col1, reaction_col2 = st.columns([1, 1.5])

        with reaction_col1:
            reaction_level_fig = px.bar(
                reaction_counts,
                x="reaction_level",
                y="comment_count",
                labels={
                    "reaction_level": "반응 단계",
                    "comment_count": "댓글 수",
                },
                text="comment_count",
            )

            reaction_level_fig.update_layout(
                height=470,
                xaxis_title="반응 단계",
                yaxis_title="댓글 수",
                showlegend=False,
            )

            st.plotly_chart(
                reaction_level_fig,
                width="stretch",
            )

        with reaction_col2:
            scatter_df = comments_df.copy()
            scatter_df["comment_preview"] = (
                scatter_df["comment"].str.replace(
                    r"\s+",
                    " ",
                    regex=True,
                ).str.slice(0, 80)
            )

            reaction_scatter = px.scatter(
                scatter_df,
                x="published_at_kst",
                y="like_count",
                size="reply_count",
                size_max=35,
                hover_name="author",
                hover_data={
                    "comment_preview": True,
                    "published_at_kst": True,
                    "like_count": ":,",
                    "reply_count": ":,",
                    "reaction_score": True,
                },
                labels={
                    "published_at_kst": "댓글 작성 시각",
                    "like_count": "좋아요 수",
                    "reply_count": "답글 수",
                    "comment_preview": "댓글",
                    "reaction_score": "반응 점수",
                },
            )

            reaction_scatter.update_layout(
                height=470,
                xaxis_title="댓글 작성 시각(KST)",
                yaxis_title="좋아요 수",
            )

            st.plotly_chart(
                reaction_scatter,
                width="stretch",
            )

        st.markdown("#### 반응이 높은 댓글")

        top_comment_count = st.slider(
            "표시할 댓글 수",
            min_value=3,
            max_value=min(20, len(comments_df)),
            value=min(5, len(comments_df)),
            key="top_comment_count",
        )

        top_comments = comments_df.sort_values(
            ["reaction_score", "like_count", "reply_count"],
            ascending=False,
        ).head(top_comment_count)

        for _, row in top_comments.iterrows():
            comment_text = escape_html(row["comment"]).replace(
                "\n",
                "<br>",
            )
            author = escape_html(row["author"])

            published_text = row["published_at_kst"].strftime(
                "%Y-%m-%d %H:%M"
            )

            st.markdown(
                f"""
                <div class="comment-card">
                    <div class="comment-author">{author}</div>
                    <div>{comment_text}</div>
                    <div class="comment-meta">
                        👍 좋아요 {int(row["like_count"]):,}개 ·
                        💬 답글 {int(row["reply_count"]):,}개 ·
                        반응 점수 {row["reaction_score"]:.2f} ·
                        {published_text} KST
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------
    # 탭 3: 한글 워드클라우드
    # -----------------------------------------------------
    with tab3:
        st.markdown(
            '<div class="section-title">한글 댓글 워드클라우드</div>',
            unsafe_allow_html=True,
        )

        word_setting1, word_setting2 = st.columns(2)

        with word_setting1:
            min_word_length = st.slider(
                "최소 단어 길이",
                min_value=1,
                max_value=5,
                value=2,
            )

        with word_setting2:
            max_word_count = st.slider(
                "워드클라우드 최대 단어 수",
                min_value=20,
                max_value=200,
                value=100,
                step=10,
            )

        additional_stopwords_text = st.text_input(
            "추가로 제외할 단어",
            placeholder="예: 채널, 이름, 노래",
            help="쉼표로 여러 단어를 구분할 수 있습니다.",
        )

        additional_stopwords = tuple(
            word.strip()
            for word in additional_stopwords_text.split(",")
            if word.strip()
        )

        try:
            with st.spinner("한글 댓글에서 주요 명사를 추출하고 있습니다..."):
                word_frequencies = extract_korean_words(
                    tuple(comments_df["comment"].fillna("").tolist()),
                    min_word_length,
                    additional_stopwords,
                )

            if not word_frequencies:
                st.warning(
                    "워드클라우드에 사용할 한글 명사를 찾지 못했습니다. "
                    "최소 단어 길이나 제외 단어 설정을 조정해 주세요."
                )
            else:
                wordcloud_fig = make_wordcloud(
                    word_frequencies,
                    max_word_count,
                )

                st.pyplot(
                    wordcloud_fig,
                    width="stretch",
                )
                plt.close(wordcloud_fig)

                st.markdown("#### 주요 키워드 빈도")

                keyword_df = pd.DataFrame(
                    sorted(
                        word_frequencies.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[:30],
                    columns=["keyword", "frequency"],
                )

                keyword_fig = px.bar(
                    keyword_df.head(20).sort_values("frequency"),
                    x="frequency",
                    y="keyword",
                    orientation="h",
                    labels={
                        "keyword": "키워드",
                        "frequency": "등장 횟수",
                    },
                    text="frequency",
                )

                keyword_fig.update_layout(
                    height=620,
                    xaxis_title="등장 횟수",
                    yaxis_title="키워드",
                    showlegend=False,
                )

                st.plotly_chart(
                    keyword_fig,
                    width="stretch",
                )

                st.dataframe(
                    keyword_df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "keyword": st.column_config.TextColumn(
                            "키워드"
                        ),
                        "frequency": st.column_config.NumberColumn(
                            "등장 횟수",
                            format="%d회",
                        ),
                    },
                )

        except FileNotFoundError:
            st.error(
                "`fonts/NanumGothic.ttf` 파일을 찾을 수 없습니다. "
                "GitHub 저장소에 `fonts` 폴더를 만들고 "
                "나눔고딕 TTF 파일을 업로드해 주세요."
            )

        except Exception as error:
            st.error(
                f"워드클라우드를 만드는 중 오류가 발생했습니다: {error}"
            )

    # -----------------------------------------------------
    # 탭 4: 댓글 데이터
    # -----------------------------------------------------
    with tab4:
        st.markdown(
            '<div class="section-title">수집한 댓글 데이터</div>',
            unsafe_allow_html=True,
        )

        search_keyword = st.text_input(
            "댓글 검색",
            placeholder="댓글 내용 또는 작성자 이름 검색",
        )

        display_df = comments_df.copy()

        if search_keyword.strip():
            keyword = search_keyword.strip()

            display_df = display_df[
                display_df["comment"].str.contains(
                    keyword,
                    case=False,
                    na=False,
                    regex=False,
                )
                | display_df["author"].str.contains(
                    keyword,
                    case=False,
                    na=False,
                    regex=False,
                )
            ]

        display_columns = [
            "author",
            "comment",
            "published_at_kst",
            "like_count",
            "reply_count",
            "reaction_score",
            "reaction_level",
        ]

        st.dataframe(
            display_df[display_columns],
            width="stretch",
            hide_index=True,
            column_config={
                "author": st.column_config.TextColumn("작성자"),
                "comment": st.column_config.TextColumn(
                    "댓글",
                    width="large",
                ),
                "published_at_kst": st.column_config.DatetimeColumn(
                    "작성 시각(KST)",
                    format="YYYY-MM-DD HH:mm",
                ),
                "like_count": st.column_config.NumberColumn(
                    "좋아요",
                    format="%d",
                ),
                "reply_count": st.column_config.NumberColumn(
                    "답글",
                    format="%d",
                ),
                "reaction_score": st.column_config.NumberColumn(
                    "반응 점수",
                    format="%.2f",
                ),
                "reaction_level": st.column_config.TextColumn(
                    "반응 단계"
                ),
            },
        )

        csv_data = convert_dataframe_to_csv(comments_df)

        st.download_button(
            "댓글 분석 결과 CSV 다운로드",
            data=csv_data,
            file_name=f"youtube_comments_{video_info['video_id']}.csv",
            mime="text/csv",
            width="stretch",
        )

        st.caption(
            "다운로드한 CSV 파일은 한글이 깨지지 않도록 UTF-8-SIG 형식으로 저장됩니다."
        )
