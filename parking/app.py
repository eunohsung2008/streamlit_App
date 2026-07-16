import math
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st


st.set_page_config(
    page_title="서울 공영주차장 찾기",
    page_icon="🅿️",
    layout="wide",
)


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------
DEFAULT_CSV_CANDIDATES = [
    Path("parking/seoul.csv"),  # app.py가 저장소 루트에 있을 때
    Path("seoul.csv"),          # app.py와 CSV가 같은 폴더에 있을 때
]

REQUIRED_COLUMNS = {
    "주차장명",
    "주소",
    "주차장 종류명",
    "총 주차면",
    "유무료구분명",
    "야간무료개방여부명",
    "평일 운영 시작시각(HHMM)",
    "평일 운영 종료시각(HHMM)",
    "주말 운영 시작시각(HHMM)",
    "주말 운영 종료시각(HHMM)",
    "공휴일 운영 시작시각(HHMM)",
    "공휴일 운영 종료시각(HHMM)",
    "토요일 유,무료 구분명",
    "공휴일 유,무료 구분명",
    "기본 주차 요금",
    "기본 주차 시간(분 단위)",
    "추가 단위 요금",
    "추가 단위 시간(분 단위)",
    "일 최대 요금",
    "위도",
    "경도",
}

NUMERIC_COLUMNS = [
    "총 주차면",
    "평일 운영 시작시각(HHMM)",
    "평일 운영 종료시각(HHMM)",
    "주말 운영 시작시각(HHMM)",
    "주말 운영 종료시각(HHMM)",
    "공휴일 운영 시작시각(HHMM)",
    "공휴일 운영 종료시각(HHMM)",
    "기본 주차 요금",
    "기본 주차 시간(분 단위)",
    "추가 단위 요금",
    "추가 단위 시간(분 단위)",
    "일 최대 요금",
    "위도",
    "경도",
]


# ---------------------------------------------------------
# 데이터 불러오기
# ---------------------------------------------------------
def read_csv_safely(source) -> pd.DataFrame:
    """UTF-8/CP949 등 여러 인코딩을 순서대로 시도한다."""
    last_error = None

    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            return pd.read_csv(source, encoding=encoding, low_memory=False)
        except (UnicodeDecodeError, UnicodeError) as error:
            last_error = error
        except Exception as error:
            last_error = error
            break

    raise ValueError(f"CSV 파일을 읽지 못했습니다: {last_error}")


@st.cache_data(show_spinner=False)
def load_default_csv(path_string: str) -> pd.DataFrame:
    return read_csv_safely(path_string)


def find_default_csv() -> Path | None:
    for candidate in DEFAULT_CSV_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------
# 데이터 전처리
# ---------------------------------------------------------
def clean_text(series: pd.Series, default: str = "정보 없음") -> pd.Series:
    return (
        series.astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "<NA>": default, "nan": default})
    )


def format_hhmm(value) -> str:
    """0, 900, 1330, 2400 등의 값을 시각 문자열로 바꾼다."""
    if pd.isna(value):
        return "정보 없음"

    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return "정보 없음"

    if number == 2400:
        return "24:00"

    hour = number // 100
    minute = number % 100

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return "정보 없음"

    return f"{hour:02d}:{minute:02d}"


def make_operation_text(row: pd.Series, prefix: str) -> str:
    start_col = f"{prefix} 운영 시작시각(HHMM)"
    end_col = f"{prefix} 운영 종료시각(HHMM)"
    return f"{format_hhmm(row.get(start_col))} ~ {format_hhmm(row.get(end_col))}"


def extract_district(address: str) -> str:
    """주소에서 서울시 자치구를 추출한다."""
    if not isinstance(address, str):
        return "구 정보 없음"

    for token in address.split():
        if token.endswith("구") and 2 <= len(token) <= 5:
            return token

    return "구 정보 없음"


def calculate_hourly_fee(df: pd.DataFrame) -> pd.Series:
    """
    기본 주차 요금을 60분 기준으로 환산한다.
    무료 주차장은 0원으로 처리한다.
    """
    base_fee = pd.to_numeric(df["기본 주차 요금"], errors="coerce")
    base_minutes = pd.to_numeric(
        df["기본 주차 시간(분 단위)"], errors="coerce"
    )

    valid_minutes = base_minutes.where(base_minutes > 0, np.nan)
    hourly_fee = base_fee.div(valid_minutes).mul(60)

    free_mask = df["유무료구분명"].astype("string").str.contains(
        "무료", na=False
    )
    hourly_fee = hourly_fee.mask(free_mask, 0)

    return pd.to_numeric(hourly_fee, errors="coerce").astype("float64")


def preprocess_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df.columns = [str(column).strip() for column in df.columns]

    missing_columns = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(
            "필수 열이 없습니다: " + ", ".join(missing_columns)
        )

    # 숫자형 열을 명시적으로 변환
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # 문자열 열 정리
    text_columns = [
        "주차장명",
        "주소",
        "주차장 종류명",
        "유무료구분명",
        "야간무료개방여부명",
        "토요일 유,무료 구분명",
        "공휴일 유,무료 구분명",
        "전화번호",
    ]

    for column in text_columns:
        if column in df.columns:
            df[column] = clean_text(df[column])

    df["자치구"] = df["주소"].map(extract_district)
    df["1시간 환산요금"] = calculate_hourly_fee(df)

    df["평일 운영시간"] = df.apply(
        lambda row: make_operation_text(row, "평일"), axis=1
    )
    df["주말 운영시간"] = df.apply(
        lambda row: make_operation_text(row, "주말"), axis=1
    )
    df["공휴일 운영시간"] = df.apply(
        lambda row: make_operation_text(row, "공휴일"), axis=1
    )

    df["평일 무료"] = (
        df["유무료구분명"].astype("string").str.contains("무료", na=False)
    )
    df["토요일 무료"] = (
        df["토요일 유,무료 구분명"]
        .astype("string")
        .str.contains("무료", na=False)
    )
    df["공휴일 무료"] = (
        df["공휴일 유,무료 구분명"]
        .astype("string")
        .str.contains("무료", na=False)
    )
    df["야간 무료개방"] = (
        df["야간무료개방여부명"]
        .astype("string")
        .str.contains("개방", na=False)
        & ~df["야간무료개방여부명"]
        .astype("string")
        .str.contains("미개방", na=False)
    )

    # 서울시 주변 범위를 벗어난 좌표 제거
    valid_coordinates = (
        df["위도"].between(37.0, 38.0, inclusive="both")
        & df["경도"].between(126.0, 128.0, inclusive="both")
    )
    df["지도 표시 가능"] = valid_coordinates

    return df


# ---------------------------------------------------------
# 표시용 함수
# ---------------------------------------------------------
def won(value) -> str:
    if pd.isna(value):
        return "정보 없음"
    return f"{int(round(float(value))):,}원"


def build_map_records(map_df: pd.DataFrame) -> list[dict]:
    """
    PyDeck에 DataFrame을 직접 넘기지 않고,
    Python의 float/int/str만 들어 있는 목록으로 변환한다.
    """
    records: list[dict] = []

    for _, row in map_df.iterrows():
        latitude = row["위도"]
        longitude = row["경도"]

        if pd.isna(latitude) or pd.isna(longitude):
            continue

        latitude = float(latitude)
        longitude = float(longitude)

        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            continue

        is_free = bool(row["평일 무료"])

        records.append(
            {
                "lat": latitude,
                "lon": longitude,
                "parking_name": str(row["주차장명"]),
                "address": str(row["주소"]),
                "district": str(row["자치구"]),
                "fee_text": (
                    "무료"
                    if is_free
                    else f"1시간 환산 {won(row['1시간 환산요금'])}"
                ),
                "base_fee_text": (
                    f"{won(row['기본 주차 요금'])} / "
                    f"{int(row['기본 주차 시간(분 단위)'])}분"
                    if pd.notna(row["기본 주차 요금"])
                    and pd.notna(row["기본 주차 시간(분 단위)"])
                    and row["기본 주차 시간(분 단위)"] > 0
                    else "정보 없음"
                ),
                "weekday_text": str(row["평일 운영시간"]),
                "weekend_text": str(row["주말 운영시간"]),
                "saturday_fee": str(row["토요일 유,무료 구분명"]),
                "holiday_fee": str(row["공휴일 유,무료 구분명"]),
                "night_open": str(row["야간무료개방여부명"]),
                "spaces": (
                    int(row["총 주차면"])
                    if pd.notna(row["총 주차면"])
                    else 0
                ),
                # 무료: 초록 계열 / 유료: 파랑 계열
                "red": 40 if is_free else 45,
                "green": 160 if is_free else 105,
                "blue": 80 if is_free else 210,
                "alpha": 190,
            }
        )

    return records


def create_map(map_records: list[dict]) -> pdk.Deck:
    latitudes = [record["lat"] for record in map_records]
    longitudes = [record["lon"] for record in map_records]

    center_latitude = sum(latitudes) / len(latitudes)
    center_longitude = sum(longitudes) / len(longitudes)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_records,
        get_position="[lon, lat]",
        get_fill_color="[red, green, blue, alpha]",
        get_radius=55,
        radius_min_pixels=4,
        radius_max_pixels=12,
        pickable=True,
        auto_highlight=True,
    )

    tooltip = {
        "html": """
        <div style="max-width:330px;">
            <b>{parking_name}</b><br/>
            주소: {address}<br/>
            요금: {fee_text}<br/>
            기본요금: {base_fee_text}<br/>
            주차면: {spaces}면<br/>
            평일: {weekday_text}<br/>
            주말: {weekend_text}<br/>
            토요일 요금: {saturday_fee}<br/>
            공휴일 요금: {holiday_fee}<br/>
            야간 개방: {night_open}
        </div>
        """,
        "style": {
            "backgroundColor": "rgba(25, 25, 25, 0.92)",
            "color": "white",
            "fontSize": "13px",
        },
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=center_latitude,
            longitude=center_longitude,
            zoom=11,
            pitch=0,
        ),
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip=tooltip,
    )


# ---------------------------------------------------------
# 화면
# ---------------------------------------------------------
st.title("🅿️ 서울 공영주차장 찾기")
st.caption(
    "자치구와 이용 조건을 선택해 공영주차장을 지도에서 확인하고, "
    "1시간 환산요금이 가장 저렴한 주차장을 찾을 수 있습니다."
)

with st.sidebar:
    st.header("데이터")
    uploaded_file = st.file_uploader(
        "공영주차장 CSV 업로드",
        type=["csv"],
        help="업로드하지 않으면 GitHub 저장소의 seoul.csv를 사용합니다.",
    )

try:
    if uploaded_file is not None:
        raw_df = read_csv_safely(uploaded_file)
        data_source_text = f"업로드 파일: {uploaded_file.name}"
    else:
        default_path = find_default_csv()

        if default_path is None:
            st.error(
                "기본 CSV 파일을 찾을 수 없습니다. "
                "`parking/seoul.csv` 또는 `seoul.csv` 위치를 확인해 주세요."
            )
            st.stop()

        raw_df = load_default_csv(str(default_path))
        data_source_text = f"기본 파일: {default_path.as_posix()}"

    df = preprocess_dataframe(raw_df)

except Exception as error:
    st.error(str(error))
    st.stop()


with st.sidebar:
    st.success(data_source_text)

    st.header("검색 조건")

    district_options = ["전체"] + sorted(
        district
        for district in df["자치구"].dropna().unique().tolist()
        if district != "구 정보 없음"
    )
    selected_district = st.selectbox("자치구", district_options)

    keyword = st.text_input(
        "주차장명 또는 주소 검색",
        placeholder="예: 성동구, 마장동, 공영주차장",
    )

    parking_type_options = sorted(
        df["주차장 종류명"].dropna().unique().tolist()
    )
    selected_types = st.multiselect(
        "주차장 종류",
        parking_type_options,
        default=parking_type_options,
    )

    st.subheader("무료 이용 조건")
    weekday_free_only = st.checkbox("평일 무료만")
    saturday_free_only = st.checkbox("토요일 무료만")
    holiday_free_only = st.checkbox("공휴일 무료만")
    night_open_only = st.checkbox("야간 무료개방만")

    valid_fees = df["1시간 환산요금"].dropna()
    if not valid_fees.empty:
        maximum_fee = int(max(1000, math.ceil(valid_fees.max() / 1000) * 1000))
        selected_max_fee = st.slider(
            "1시간 환산요금 상한",
            min_value=0,
            max_value=maximum_fee,
            value=maximum_fee,
            step=500,
            format="%d원",
        )
    else:
        selected_max_fee = None


# ---------------------------------------------------------
# 필터
# ---------------------------------------------------------
filtered_df = df.copy()

if selected_district != "전체":
    filtered_df = filtered_df[
        filtered_df["자치구"].eq(selected_district)
    ]

if keyword.strip():
    search_text = keyword.strip()
    keyword_mask = (
        filtered_df["주차장명"].str.contains(
            search_text, case=False, na=False, regex=False
        )
        | filtered_df["주소"].str.contains(
            search_text, case=False, na=False, regex=False
        )
    )
    filtered_df = filtered_df[keyword_mask]

if selected_types:
    filtered_df = filtered_df[
        filtered_df["주차장 종류명"].isin(selected_types)
    ]
else:
    filtered_df = filtered_df.iloc[0:0]

if weekday_free_only:
    filtered_df = filtered_df[filtered_df["평일 무료"]]

if saturday_free_only:
    filtered_df = filtered_df[filtered_df["토요일 무료"]]

if holiday_free_only:
    filtered_df = filtered_df[filtered_df["공휴일 무료"]]

if night_open_only:
    filtered_df = filtered_df[filtered_df["야간 무료개방"]]

if selected_max_fee is not None:
    fee_mask = (
        filtered_df["1시간 환산요금"].isna()
        | filtered_df["1시간 환산요금"].le(selected_max_fee)
    )
    filtered_df = filtered_df[fee_mask]


# ---------------------------------------------------------
# 요약
# ---------------------------------------------------------
map_df = filtered_df[filtered_df["지도 표시 가능"]].copy()
map_records = build_map_records(map_df)

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("검색 결과", f"{len(filtered_df):,}곳")
metric2.metric("지도 표시 가능", f"{len(map_records):,}곳")
metric3.metric("평일 무료", f"{int(filtered_df['평일 무료'].sum()):,}곳")
metric4.metric("토요일 무료", f"{int(filtered_df['토요일 무료'].sum()):,}곳")


# ---------------------------------------------------------
# 최저요금 추천
# ---------------------------------------------------------
st.subheader("💰 가장 저렴한 주차장")

recommendation_df = filtered_df[
    filtered_df["1시간 환산요금"].notna()
].sort_values(
    by=["1시간 환산요금", "기본 주차 요금", "주차장명"],
    ascending=[True, True, True],
)

if recommendation_df.empty:
    st.info("현재 조건에서는 요금을 비교할 수 있는 주차장이 없습니다.")
else:
    cheapest_fee = recommendation_df.iloc[0]["1시간 환산요금"]
    cheapest_group = recommendation_df[
        recommendation_df["1시간 환산요금"].eq(cheapest_fee)
    ]

    cheapest = cheapest_group.iloc[0]

    if cheapest_fee == 0:
        price_message = "무료"
    else:
        price_message = f"1시간 환산 {won(cheapest_fee)}"

    st.success(
        f"**{cheapest['주차장명']}** · {price_message}\n\n"
        f"주소: {cheapest['주소']}  \n"
        f"주차면: {int(cheapest['총 주차면']) if pd.notna(cheapest['총 주차면']) else '정보 없음'}면  \n"
        f"토요일: {cheapest['토요일 유,무료 구분명']} · "
        f"공휴일: {cheapest['공휴일 유,무료 구분명']} · "
        f"야간: {cheapest['야간무료개방여부명']}"
    )

    if len(cheapest_group) > 1:
        st.caption(
            f"동일한 최저요금의 주차장이 총 {len(cheapest_group)}곳 있습니다."
        )


# ---------------------------------------------------------
# 지도
# ---------------------------------------------------------
st.subheader("🗺️ 주차장 지도")
st.caption("초록색은 평일 무료, 파란색은 평일 유료 주차장입니다.")

if map_records:
    st.pydeck_chart(create_map(map_records), use_container_width=True)
else:
    st.warning(
        "현재 조건에서 지도에 표시할 수 있는 좌표가 없습니다. "
        "필터를 완화하거나 다른 자치구를 선택해 주세요."
    )


# ---------------------------------------------------------
# 저렴한 주차장 TOP 10
# ---------------------------------------------------------
st.subheader("🏆 저렴한 주차장 TOP 10")

top10 = recommendation_df.head(10).copy()

if top10.empty:
    st.info("표시할 요금 정보가 없습니다.")
else:
    top10_display = top10[
        [
            "자치구",
            "주차장명",
            "주소",
            "주차장 종류명",
            "총 주차면",
            "유무료구분명",
            "1시간 환산요금",
            "토요일 유,무료 구분명",
            "공휴일 유,무료 구분명",
            "야간무료개방여부명",
        ]
    ].copy()

    # Streamlit 표의 numeric dtype 오류를 막기 위해 명시적으로 float64로 유지
    top10_display["1시간 환산요금"] = pd.to_numeric(
        top10_display["1시간 환산요금"], errors="coerce"
    ).astype("float64")

    st.dataframe(
        top10_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "1시간 환산요금": st.column_config.NumberColumn(
                "1시간 환산요금",
                format="%,.0f원",
            ),
            "총 주차면": st.column_config.NumberColumn(
                "총 주차면",
                format="%d면",
            ),
        },
    )


# ---------------------------------------------------------
# 전체 결과 및 다운로드
# ---------------------------------------------------------
with st.expander("필터링된 전체 주차장 목록"):
    result_columns = [
        "자치구",
        "주차장명",
        "주소",
        "주차장 종류명",
        "총 주차면",
        "유무료구분명",
        "기본 주차 요금",
        "기본 주차 시간(분 단위)",
        "1시간 환산요금",
        "평일 운영시간",
        "주말 운영시간",
        "토요일 유,무료 구분명",
        "공휴일 유,무료 구분명",
        "야간무료개방여부명",
        "위도",
        "경도",
    ]

    display_df = filtered_df[result_columns].copy()

    for numeric_column in [
        "총 주차면",
        "기본 주차 요금",
        "기본 주차 시간(분 단위)",
        "1시간 환산요금",
        "위도",
        "경도",
    ]:
        display_df[numeric_column] = pd.to_numeric(
            display_df[numeric_column], errors="coerce"
        )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    csv_bytes = display_df.to_csv(
        index=False,
        encoding="utf-8-sig",
    ).encode("utf-8-sig")

    st.download_button(
        "필터링 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="filtered_seoul_parking.csv",
        mime="text/csv",
    )


st.caption(
    "요금 비교는 기본 주차 요금을 60분 기준으로 환산한 값입니다. "
    "실제 요금은 추가요금, 일 최대요금, 할인 조건 등에 따라 달라질 수 있습니다."
)
