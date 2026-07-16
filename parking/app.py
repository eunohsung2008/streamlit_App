from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st


st.set_page_config(
    page_title="서울 공영주차장 찾기",
    page_icon="🅿️",
    layout="wide",
)

DEFAULT_CSV = Path(__file__).with_name("서울시 공영주차장 안내 정보.csv")
SEOUL_CENTER = {"lat": 37.5665, "lon": 126.9780}

REQUIRED_COLUMNS = [
    "주차장명",
    "주소",
    "유무료구분명",
    "기본 주차 요금",
    "기본 주차 시간(분 단위)",
    "토요일 유,무료 구분명",
    "공휴일 유,무료 구분명",
    "위도",
    "경도",
]


def read_csv_safely(file_or_path) -> tuple[pd.DataFrame, str]:
    """여러 한글 인코딩을 순서대로 시도해 CSV를 읽는다."""
    encodings = ("utf-8-sig", "cp949", "euc-kr", "utf-8")
    raw: bytes

    if hasattr(file_or_path, "getvalue"):
        raw = file_or_path.getvalue()
    else:
        raw = Path(file_or_path).read_bytes()

    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding), encoding
        except (UnicodeDecodeError, pd.errors.ParserError) as error:
            last_error = error

    raise ValueError(f"CSV 파일을 읽지 못했습니다: {last_error}")


def clean_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def format_hhmm(value) -> str:
    if pd.isna(value):
        return "정보 없음"
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return "정보 없음"

    # 2400은 자정 종료 의미로 그대로 표시한다.
    if number == 2400:
        return "24:00"
    hour, minute = divmod(number, 100)
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return "정보 없음"


def extract_district(address: str) -> str:
    match = re.search(r"([가-힣]+구)(?:\s|$)", str(address))
    return match.group(1) if match else "구 정보 없음"


def prepare_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in raw_df.columns]
    if missing:
        raise ValueError("필수 열이 없습니다: " + ", ".join(missing))

    df = raw_df.copy()
    df["주소"] = df["주소"].fillna("주소 정보 없음").astype(str).str.strip()
    df["주차장명"] = df["주차장명"].fillna("이름 정보 없음").astype(str).str.strip()
    df["자치구"] = df["주소"].map(extract_district)

    numeric_columns = [
        "위도",
        "경도",
        "기본 주차 요금",
        "기본 주차 시간(분 단위)",
        "추가 단위 요금",
        "추가 단위 시간(분 단위)",
        "일 최대 요금",
        "총 주차면",
        "월 정기권 금액",
    ]
    for column in numeric_columns:
        if column in df.columns:
            df[column] = clean_number(df[column])

    df["무료 여부"] = df["유무료구분명"].fillna("").astype(str).str.contains("무료")
    df["토요일 무료"] = (
        df["토요일 유,무료 구분명"].fillna("").astype(str).str.contains("무료")
    )
    df["공휴일 무료"] = (
        df["공휴일 유,무료 구분명"].fillna("").astype(str).str.contains("무료")
    )
    df["야간 무료"] = (
        df.get("야간무료개방여부명", pd.Series("", index=df.index))
        .fillna("")
        .astype(str)
        .str.contains("개방|무료")
    )

    base_fee = df["기본 주차 요금"].fillna(0).clip(lower=0)
    base_minutes = df["기본 주차 시간(분 단위)"].replace(0, pd.NA)
    hourly_fee = (base_fee / base_minutes * 60).round()
    hourly_fee = hourly_fee.where(~df["무료 여부"], 0)
    df["1시간 환산요금"] = hourly_fee

    df["기본요금 표시"] = df.apply(
        lambda row: (
            "무료"
            if row["무료 여부"]
            else (
                f"{int(row['기본 주차 요금']):,}원 / "
                f"{int(row['기본 주차 시간(분 단위)']):,}분"
                if pd.notna(row["기본 주차 요금"])
                and pd.notna(row["기본 주차 시간(분 단위)"])
                else "요금 정보 없음"
            )
        ),
        axis=1,
    )
    df["1시간요금 표시"] = df["1시간 환산요금"].map(
        lambda value: f"약 {int(value):,}원" if pd.notna(value) else "계산 불가"
    )
    df["주말정보"] = df.apply(
        lambda row: (
            f"토요일 {row.get('토요일 유,무료 구분명', '정보 없음')} · "
            f"공휴일 {row.get('공휴일 유,무료 구분명', '정보 없음')}"
        ),
        axis=1,
    )
    df["평일 운영시간"] = df.apply(
        lambda row: f"{format_hhmm(row.get('평일 운영 시작시각(HHMM)'))}~"
        f"{format_hhmm(row.get('평일 운영 종료시각(HHMM)'))}",
        axis=1,
    )
    df["주말 운영시간"] = df.apply(
        lambda row: f"{format_hhmm(row.get('주말 운영 시작시각(HHMM)'))}~"
        f"{format_hhmm(row.get('주말 운영 종료시각(HHMM)'))}",
        axis=1,
    )

    # 서울 범위를 크게 벗어난 좌표나 결측치는 지도에서 제외한다.
    df["지도표시가능"] = (
        df["위도"].between(37.3, 37.8)
        & df["경도"].between(126.7, 127.3)
    )
    return df


def bool_icon(value: bool) -> str:
    return "✅" if bool(value) else "—"


def make_map(data: pd.DataFrame) -> pdk.Deck:
    map_df = data[data["지도표시가능"]].copy()

    if map_df.empty:
        center = SEOUL_CENTER
        zoom = 10
    else:
        center = {
            "lat": float(map_df["위도"].median()),
            "lon": float(map_df["경도"].median()),
        }
        zoom = 11 if len(map_df) > 80 else 12

    # 무료는 초록 계열, 유료는 파랑 계열로 구분한다.
    map_df["marker_color"] = map_df["무료 여부"].map(
        lambda free: [46, 160, 67, 210] if free else [36, 99, 235, 195]
    )
    map_df["토요일표시"] = map_df["토요일 무료"].map(bool_icon)
    map_df["공휴일표시"] = map_df["공휴일 무료"].map(bool_icon)
    map_df["야간표시"] = map_df["야간 무료"].map(bool_icon)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[경도, 위도]",
        get_fill_color="marker_color",
        get_radius=45,
        radius_min_pixels=5,
        radius_max_pixels=12,
        pickable=True,
        auto_highlight=True,
    )

    tooltip = {
        "html": """
        <div style='font-size:13px; line-height:1.55'>
          <b style='font-size:15px'>{주차장명}</b><br/>
          📍 {주소}<br/>
          💳 기본요금: {기본요금 표시}<br/>
          ⏱️ 1시간 환산: {1시간요금 표시}<br/>
          🅿️ 주차면: {총 주차면}<br/>
          📅 토요일 무료 {토요일표시} · 공휴일 무료 {공휴일표시}<br/>
          🌙 야간 무료개방 {야간표시}<br/>
          🕒 평일 {평일 운영시간} · 주말 {주말 운영시간}
        </div>
        """,
        "style": {
            "backgroundColor": "rgba(20, 25, 35, 0.94)",
            "color": "white",
            "padding": "10px",
            "borderRadius": "8px",
        },
    }

    return pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=center["lat"],
            longitude=center["lon"],
            zoom=zoom,
            pitch=0,
        ),
        layers=[layer],
        tooltip=tooltip,
    )


def format_table(data: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "주차장명",
        "자치구",
        "주소",
        "유무료구분명",
        "기본요금 표시",
        "1시간 환산요금",
        "토요일 유,무료 구분명",
        "공휴일 유,무료 구분명",
        "야간무료개방여부명",
        "총 주차면",
        "평일 운영시간",
        "주말 운영시간",
    ]
    existing = [column for column in columns if column in data.columns]
    return data[existing].rename(
        columns={
            "유무료구분명": "평일 요금",
            "기본요금 표시": "기본요금",
            "1시간 환산요금": "1시간 환산요금(원)",
            "토요일 유,무료 구분명": "토요일",
            "공휴일 유,무료 구분명": "공휴일",
            "야간무료개방여부명": "야간 개방",
            "총 주차면": "주차면",
        }
    )


st.title("🅿️ 서울 공영주차장 찾기")
st.caption("자치구·요금·주말 운영 조건을 비교하고 지도에서 위치를 확인하세요.")

with st.sidebar:
    st.header("데이터")
    uploaded_file = st.file_uploader(
        "공영주차장 CSV 업로드",
        type=["csv"],
        help="첨부 데이터와 같은 열 구조의 CSV를 올리면 즉시 교체됩니다.",
    )

try:
    source = uploaded_file if uploaded_file is not None else DEFAULT_CSV
    raw_df, used_encoding = read_csv_safely(source)
    df = prepare_data(raw_df)
except FileNotFoundError:
    st.error(
        "기본 CSV를 찾을 수 없습니다. GitHub 저장소에 app.py와 CSV를 함께 올리거나 "
        "왼쪽에서 CSV를 업로드해 주세요."
    )
    st.stop()
except Exception as error:
    st.error(str(error))
    st.stop()

with st.sidebar:
    st.success(f"{len(df):,}개 주차장 불러옴 · {used_encoding}")
    st.header("검색 조건")

    districts = sorted(df.loc[df["자치구"] != "구 정보 없음", "자치구"].unique())
    selected_district = st.selectbox("자치구", ["전체"] + districts)
    search_text = st.text_input("주차장명 또는 주소 검색", placeholder="예: 강남역, 개포동")

    fee_filter = st.radio(
        "평일 요금",
        ["전체", "무료만", "유료만"],
        horizontal=True,
    )
    saturday_free_only = st.checkbox("토요일 무료만")
    holiday_free_only = st.checkbox("공휴일 무료만")
    night_free_only = st.checkbox("야간 무료개방만")

    parking_types = sorted(
        df.get("주차장 종류명", pd.Series(dtype=str)).dropna().astype(str).unique()
    )
    selected_types = st.multiselect("주차장 종류", parking_types, default=[])

    max_hourly = int(df["1시간 환산요금"].dropna().quantile(0.95)) if df["1시간 환산요금"].notna().any() else 10000
    max_hourly = max(max_hourly, 1000)
    hourly_limit = st.slider(
        "1시간 환산요금 상한",
        min_value=0,
        max_value=max_hourly,
        value=max_hourly,
        step=100,
        help="극단적인 고액 요금의 영향을 줄이기 위해 데이터의 95백분위까지 표시합니다.",
    )

filtered = df.copy()
if selected_district != "전체":
    filtered = filtered[filtered["자치구"] == selected_district]
if search_text.strip():
    keyword = re.escape(search_text.strip())
    filtered = filtered[
        filtered["주차장명"].str.contains(keyword, case=False, na=False, regex=True)
        | filtered["주소"].str.contains(keyword, case=False, na=False, regex=True)
    ]
if fee_filter == "무료만":
    filtered = filtered[filtered["무료 여부"]]
elif fee_filter == "유료만":
    filtered = filtered[~filtered["무료 여부"]]
if saturday_free_only:
    filtered = filtered[filtered["토요일 무료"]]
if holiday_free_only:
    filtered = filtered[filtered["공휴일 무료"]]
if night_free_only:
    filtered = filtered[filtered["야간 무료"]]
if selected_types:
    filtered = filtered[filtered["주차장 종류명"].isin(selected_types)]
filtered = filtered[
    filtered["1시간 환산요금"].isna()
    | (filtered["1시간 환산요금"] <= hourly_limit)
]

# 무료 → 1시간 환산요금 → 기본요금 → 주차면 많은 순서
filtered = filtered.sort_values(
    by=["무료 여부", "1시간 환산요금", "기본 주차 요금", "총 주차면"],
    ascending=[False, True, True, False],
    na_position="last",
)

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("검색 결과", f"{len(filtered):,}곳")
metric2.metric("무료", f"{int(filtered['무료 여부'].sum()):,}곳")
metric3.metric("토요일 무료", f"{int(filtered['토요일 무료'].sum()):,}곳")
metric4.metric("지도 표시 가능", f"{int(filtered['지도표시가능'].sum()):,}곳")

if filtered.empty:
    st.warning("선택한 조건에 맞는 주차장이 없습니다. 필터를 완화해 보세요.")
    st.stop()

recommendation_pool = filtered[filtered["1시간 환산요금"].notna()]
if not recommendation_pool.empty:
    best = recommendation_pool.iloc[0]
    district_text = selected_district if selected_district != "전체" else best["자치구"]
    st.success(
        f"💡 **{district_text} 최저요금 추천:** {best['주차장명']} · "
        f"{best['기본요금 표시']} · 1시간 환산 {best['1시간요금 표시']} · "
        f"{best['주소']}"
    )
else:
    st.info("현재 검색 결과에는 비교 가능한 요금 정보가 없습니다.")

map_tab, list_tab, ranking_tab = st.tabs(["🗺️ 지도", "📋 목록", "🏆 추천 순위"])

with map_tab:
    st.pydeck_chart(make_map(filtered), use_container_width=True)
    no_coordinate_count = int((~filtered["지도표시가능"]).sum())
    if no_coordinate_count:
        st.caption(
            f"좌표가 없거나 서울 범위를 벗어난 {no_coordinate_count:,}곳은 지도에서 제외되지만 목록에는 표시됩니다."
        )
    st.caption("초록 마커는 평일 무료, 파랑 마커는 유료 주차장입니다. 마커에 마우스를 올리면 상세 정보가 나타납니다.")

with list_tab:
    table_df = format_table(filtered)
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "1시간 환산요금(원)": st.column_config.NumberColumn(format="%d원"),
            "주차면": st.column_config.NumberColumn(format="%d면"),
        },
    )

    csv_bytes = table_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "필터 결과 CSV 내려받기",
        data=csv_bytes,
        file_name="공영주차장_검색결과.csv",
        mime="text/csv",
    )

with ranking_tab:
    st.subheader("조건에 맞는 저렴한 주차장 TOP 10")
    top10 = filtered[filtered["1시간 환산요금"].notna()].head(10).copy()
    if top10.empty:
        st.info("요금 정보가 있는 주차장이 없습니다.")
    else:
        top10.insert(0, "순위", range(1, len(top10) + 1))
        ranking_columns = [
            "순위",
            "주차장명",
            "자치구",
            "주소",
            "기본요금 표시",
            "1시간 환산요금",
            "총 주차면",
            "토요일 유,무료 구분명",
            "공휴일 유,무료 구분명",
        ]
        st.dataframe(
            top10[ranking_columns].rename(
                columns={
                    "기본요금 표시": "기본요금",
                    "1시간 환산요금": "1시간 환산요금(원)",
                    "총 주차면": "주차면",
                    "토요일 유,무료 구분명": "토요일",
                    "공휴일 유,무료 구분명": "공휴일",
                }
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "1시간 환산요금(원)": st.column_config.NumberColumn(format="%d원"),
                "주차면": st.column_config.NumberColumn(format="%d면"),
            },
        )

with st.expander("요금 계산 기준과 데이터 안내"):
    st.markdown(
        """
- **1시간 환산요금** = 기본 주차 요금 ÷ 기본 주차 시간 × 60분입니다.
- 평일 무료 주차장은 0원으로 계산해 최우선 추천합니다.
- 실제 결제액은 추가요금, 일 최대요금, 할인, 운영시간에 따라 달라질 수 있습니다.
- 주소만 있고 위·경도가 없는 행은 외부 지오코딩 API를 사용하지 않기 때문에 지도에는 표시되지 않습니다.
- 업로드 CSV는 기본 파일과 같은 열 이름을 가져야 합니다.
        """
    )
