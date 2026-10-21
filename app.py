# 실행 방법 : 터미널에 `streamlit run app.py` (다른 폴더에서는 `streamlit run 경로/app.py`)

from datetime import date          # 날짜 다루기 (내역 추가 폼의 날짜 기본값·범위에 사용)

import pandas as pd                # 표(DataFrame) 다루기
import plotly.express as px        # 마우스를 올리면 값이 보이는 인터랙티브 그래프
import streamlit as st             # 웹 화면 만들기

# 같은 폴더의 finance.py에서 만들어 둔 상수와 함수 가져오기
# → 데이터 처리(finance.py)와 화면(app.py)을 파일로 나눠서 관리
from finance import (
    COLUMNS, MAX_AMOUNT, add_features, csv_bytes, empty_records,
    load_sample, read_csv_bytes, summarize, validate_records,
)

# 브라우저 탭 제목 / layout="wide" : 화면을 가로로 넓게 사용
# ⚠ 다른 st. 명령보다 반드시 먼저 실행되어야 함
st.set_page_config(page_title="나의 입출금 정리표", layout="wide")


# ═════════════════════════ 1. 세션 상태 준비 ═════════════════════════

# session_state : 화면이 다시 실행(rerun)돼도 값이 사라지지 않는 저장소 (딕셔너리처럼 사용)
# Streamlit은 버튼 클릭·입력 때마다 파일 전체를 처음부터 다시 실행하기 때문에
# 일반 변수는 매번 초기화됨 → 계속 유지할 데이터는 session_state에 저장
if "records" not in st.session_state:          # 처음 접속했을 때만 (records가 아직 없을 때)
    st.session_state.records = load_sample()   # 샘플 CSV를 읽어서 거래 내역으로 저장
    st.session_state.revision = 0              # 데이터 버전 번호 (데이터가 바뀔 때마다 +1)

# period : 조회 기간, view_kind : 수입 또는 지출 구분, view_categories : 조회할 항목
# 데이터가 새로 저장된 직후(reset_filters가 True)라면 필터 선택값을 지워서 기본값으로 되돌림
# pop(키, 기본값) : 값을 꺼내면서 동시에 삭제. 키가 없으면 기본값(False) 반환 → 한 번만 실행됨
if st.session_state.pop("reset_filters", False):
    for key in ["period", "view_kind", "view_categories"]:
        st.session_state.pop(key, None)        # 키가 없어도 에러 나지 않게 기본값 None

# 저장 직후에 남겨 둔 안내 메시지가 있으면 꺼내고, 없으면 None
# 꺼내면서 삭제하므로 안내 메시지는 딱 한 번만 화면에 표시됨 (표시는 본문 위쪽에서)
message = st.session_state.pop("message", None)


# 새 거래 내역을 검증한 뒤 저장하고, 화면을 새로 그리는 함수
# 내역 추가 / 표 수정 / 예제·빈 표 초기화 등 "데이터를 바꾸는 모든 곳"이 이 함수 하나를 거침
def save_records(frame: pd.DataFrame, message: str) -> None:   # -> None : 돌려주는 값 없음
    clean = validate_records(frame)          # 규칙 검사 (틀리면 ValueError → 아래 줄은 실행 안 됨)
    st.session_state.records = clean         # 검사 통과한 데이터로 교체
    st.session_state.revision += 1           # 데이터 버전 +1 (편집 표의 key가 바뀌어 새 데이터로 다시 그려짐)
    st.session_state.reset_filters = True    # 다음 실행 때 필터 초기화하라는 표시
    st.session_state.message = message       # 다음 실행 때 보여줄 안내 메시지 (예: "저장되었습니다")
    st.rerun()                               # 지금 바로 파일 전체를 다시 실행 → 바뀐 데이터로 화면 갱신


# ═════════════════════════ 2. 사이드바 : 조회 조건 입력 ═════════════════════════
with st.sidebar:                     # 이 블록 안(들여쓴 부분)은 왼쪽 사이드바에 그려짐
    st.subheader("조회 설정")         # 작은 제목

    # 저장된 거래 내역의 날짜에서 "YYYY-MM"만 뽑아 → 중복 제거 → 리스트로 → 오름차순 정렬
    # 예: ["2026-01-05", "2026-01-08", "2026-02-03"] → ["2026-01", "2026-02"]
    months = sorted(st.session_state.records["날짜"].str[:7].unique().tolist())
    # key="period" : 위젯 이름
    # → 선택값이 st.session_state.period에도 자동 저장됨 (앞에서 필터 초기화할 때 이 이름으로 지움)
    # 선택지 = ["전체 기간"] + 월 목록 (리스트끼리 + 하면 이어 붙여짐)
    period = st.selectbox("조회 기간", ["전체 기간"] + months, key="period")

    # 숫자 입력
    # min/max_value : 입력 가능한 범위, value : 기본값, step : +/- 버튼 한 번에 바뀌는 크기
    threshold = st.number_input(
        label="큰 지출 기준 (원)", min_value=0, max_value=MAX_AMOUNT, value=100000, step=5000, key="threshold"
    )

    # 한 달에 이만큼은 남기고 싶다는 목표 금액 (요약 대시보드의 '월별 정리표'에서 비교)
    target = st.number_input(
        label="월별 남은금액 목표 (원)", min_value=0, max_value=MAX_AMOUNT, value=700000, step=5000, key="target"
    )

    st.divider()        # 가로 구분선
    st.caption("아래 버튼은 현재 세션 내역을 바꿉니다. 필요하면 먼저 전체 csv를 내려 받으세요")   # 작은 회색 안내글

    # 버튼 만들기
    # st.button은 "이번 실행에서 클릭됐으면 True"를 돌려줌 → 클릭한 그 순간에만 if 안이 실행됨
    # width="stretch" : 버튼을 사이드바 가로 폭에 꽉 차게
    if st.button("가상 예제로 되돌리기", key="reset_sample", width="stretch"):
        save_records(load_sample(), "가상 예제 18건을 불러왔습니다.")                    # 샘플 CSV로 교체

    if st.button("빈 정리표로 시작", key="start_empty", width="stretch"):
        save_records(empty_records(), "빈 정리표를 만들었습니다. 내역을 추가해주세요")   # 0행짜리 빈 표로 교체

    st.caption("세션 메모리 보관 브라우저 새로고침/연결 종료 시 초기화될 수 있습니다.")


# ═════════════════════════ 3. 본문 위쪽 : 제목 · 안내 · KPI ═════════════════════════
st.title("나의 입출금 정리표 만들기")                                # 큰 제목
st.write("내역을 입력하고, 월별 흐름과 지출 항목을 한눈에 확인하세요.")   # 일반 글
st.caption("처음 보이는 18건은 가상 학습 데이터 입니다. 남은 금액은 기간 내 수입-지출이며 통장 잔액이 아닙니다.")

# 저장 직후 한 번만 안내 메시지 표시 (위에서 꺼내 둔 message)
# st.success : 페이지 위쪽 초록색 박스 / st.toast : 화면 오른쪽 아래 팝업 (스크롤 위치와 상관없이 보임)
if message:
    st.success(message)
    st.toast(message)

# 파생변수 만들기
# 저장된 전체 내역에 "월", "표시" 열 추가 (큰 지출 기준은 사이드바에서 입력한 threshold)
# number_input은 소수(float)로 돌려줄 수 있어서 int()로 정수 변환
all_records = add_features(st.session_state.records, int(threshold))
# 조회 기간 필터 (조건 표현식 : A if 조건 else B)
# "전체 기간"이면 전체 복사본, 아니면 "월" 열이 선택한 달과 같은 행만 남김
filtered = all_records.copy() if period == "전체 기간" else all_records[all_records["월"] == period].copy()

# 항목별 지출 합계표, 월별 요약표 두 개를 한 번에 받기 (아래 요약 대시보드의 그래프/표에 사용)
categorise, monthly = summarize(filtered)
# .loc[행 조건, 열] : 구분이 "수입"인 행의 "금액" 열만 → 합계 → 정수로
total_income = int(filtered.loc[filtered["구분"] == "수입", "금액"].sum())
total_expense = int(filtered.loc[filtered["구분"] == "지출", "금액"].sum())
total_balance = total_income - total_expense   # 남은 금액 = 수입 - 지출

# KPI(핵심 지표) 카드 4개
kpi1, kpi2, kpi3, kpi4 = st.columns(4)            # 화면을 가로 4칸으로 나눔
kpi1.metric("수입 합계", f"{total_income:,}원")   # metric : 제목 + 큰 숫자 카드, :, → 천 단위 쉼표
kpi2.metric("지출 합계", f"{total_expense:,}원")
kpi3.metric("기간 내 남은 금액", f"{total_balance:,}원")
kpi4.metric("조회 내역", f"{len(filtered):,}건")  # len(표) = 행 개수 = 거래 건수

# 지금 어떤 기간을 보고 있는지 안내 (f-string으로 period 값을 끼워 넣음)
st.caption(f"현재 조회: {period}. 내역 관리, 전체 csv 백업은 기간 필터와 관계없이 전체 데이터를 사용합니다.")

# 탭 4개 만들기 : 각 변수에 `with 변수:`로 들어가면 그 탭 안에 그려짐
overview, management, files, lesson = st.tabs(["요약 대시보드", "내역관리", "CSV 가져오기,다운로드", "코드 학습"])


# ═════════════════════════ 4. 탭① 요약 대시보드 (기간 필터 적용된 filtered 사용) ═════════════════════════
with overview:
    if filtered.empty:
        st.info("조회할 내역이 없습니다. '내역관리'에서 거래를 추가하세요.")
    else:
        # 화면을 왼쪽:오른쪽 = 1 : 1.2 비율로 나눔
        left, right = st.columns([1, 1.2])

        # ── 왼쪽 : 항목별 지출 가로 막대그래프 ──
        with left:
            st.subheader("항목별 지출")
            if categorise.empty:            # 수입만 있는 기간이면 지출 표가 비어 있음
                st.info("이 기간에는 지출 내역이 없습니다.")
            else:
                # orientation='h' : 가로 막대 / labels : 축 이름을 바꿔서 표시
                # ⚠ x 열 이름은 finance.py의 summarize()가 만든 "지출 합계"와 띄어쓰기까지 똑같아야 함
                fig = px.bar(
                    categorise, x="지출 합계", y="항목", orientation="h",
                    color_discrete_sequence=["#0F766E"], labels={"지출 합계": "지출 금액(원)"},
                )
                # categoryorder="total ascending" : 금액이 큰 항목이 위로 오게 정렬
                # margin : 그래프 바깥 여백(px)
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=360, margin=dict(l=10, r=10, t=10, b=10))
                # 마우스를 올렸을 때 "항목 / 12,345원" 형태로 표시 (<extra></extra> : 옆에 붙는 회색 상자 숨김)
                fig.update_traces(hovertemplate="%{y}<br>%{x:,.0f}원<extra></extra>")
                st.plotly_chart(fig, width="stretch")

        # ── 오른쪽 : 월별 수입·지출 묶음 막대그래프 ──
        with right:
            st.subheader("월별 수입·지출")
            # melt : 옆으로 넓은 표 → 세로로 긴 표 (plotly에서 color로 구분하려면 이 모양이 필요)
            #   월 | 수입 | 지출          월 | 구분 | 금액
            #   01 | 300  | 200    →     01 | 수입 | 300
            #                            01 | 지출 | 200
            chart = monthly.melt(id_vars="월", value_vars=["수입", "지출"], var_name="구분", value_name="금액")
            # barmode="group" : 같은 달의 수입·지출 막대를 나란히 / color_discrete_map : 구분별 색 지정
            fig = px.bar(
                chart, x="월", y="금액", color="구분", barmode="group",
                color_discrete_map={"수입": "#0F766E", "지출": "#EA580C"},
                labels={"금액": "금액 (원)"},
            )
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
            st.plotly_chart(fig, width="stretch")

        # ── 그래프 아래(전체 너비) : 월별 정리표 ──
        st.subheader("월별 정리표")
        report = monthly.copy()                                         # 원본 monthly는 그대로 두고 복사본에 열 추가
        report["목표 금액"] = int(target)                               # 모든 행에 같은 값(사이드바 목표 금액)
        report["목표와 차이"] = report["남은 금액"] - report["목표 금액"]  # +면 목표 달성, -면 부족
        # column_config : 열마다 표시 형식 지정 → 남은 비율을 "12.3%" 모양으로
        st.dataframe(report, hide_index=True, width="stretch", column_config={
            "남은 비율(%)": st.column_config.NumberColumn(format="%.1f%%"),
        })
        st.caption("수입이 0원인 달의 남은비율은 계산하지 않습니다. 빈칸은 0%가 아니라 계산 불가입니다.")

        # ── 큰 지출 목록 : 지출이면서 금액이 기준 이상인 행만 ──
        st.subheader(f"큰 지출 - {int(threshold):,}원 이상")
        # 조건 두 개를 & 로 묶을 때는 각각 괄호로 감싸야 함
        big = filtered[(filtered["구분"] == "지출") & (filtered["금액"] >= threshold)]
        if big.empty:
            st.info("기준을 넘는 지출이 없습니다.")
        else:
            st.dataframe(big[COLUMNS + ["표시"]], hide_index=True, width="stretch")   # 필수 4열 + 표시 열만


# ═════════════════════════ 5. 탭② 내역관리 (기간과 관계없이 전체 records 사용) ═════════════════════════
with management:
    # ── 새 내역 1건 추가 ──
    st.subheader("새 내역 추가")
    # form의 역할 : 위젯은 값이 바뀔 때마다 화면이 다시 실행되는데,
    #              form 안의 위젯은 값을 모았다가 제출 버튼을 누를 때 한꺼번에 전송됨
    # clear_on_submit=True : 제출 후 입력칸 초기화 / False : 입력값 유지
    with st.form("add_form", clear_on_submit=True):
        a, b, c, d = st.columns([1.2, 1, 1.4, 1.4])     # 입력칸 4개를 가로로 배치
        entered_date = a.date_input("날짜", value=date(2026, 3, 26), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), key="new_date")
        kind = b.selectbox("구분", ["지출", "수입"], key="new_kind")
        category = c.text_input("항목", placeholder="예: 식비", max_chars=40, key="new_category")
        amount = d.number_input("금액 (원)", min_value=1, max_value=MAX_AMOUNT, value=10000, step=1000, key="new_amount")

        # type="primary" : 강조 버튼 / "secondary" : 일반 버튼 / disabled=True : 비활성화
        submitted = st.form_submit_button("내역 추가", key="add_record", type="primary")

    if submitted:
        try:
            # 입력값 1건 → 1행짜리 표 (날짜는 isoformat()으로 "YYYY-MM-DD" 글자로)
            row = pd.DataFrame([[entered_date.isoformat(), kind, category, amount]], columns=COLUMNS)
            # 기존 내역 아래에 붙여서 저장 (ignore_index=True : 행 번호를 0부터 새로)
            save_records(pd.concat([st.session_state.records, row], ignore_index=True), "내역 1건을 추가했습니다.")
        except ValueError as exc:       # validate_records 검사에 걸리면 빨간 박스로 이유 표시
            st.error(str(exc))

    # ── 전체 내역 수정·삭제 ──
    st.subheader("전체 내역 수정삭제")
    st.caption("셀을 편집하거나 행을 추가 삭제 한 뒤 '수정 내용 반영'을 눌러야 요약에 적용됩니다.")
    editor_source = st.session_state.records.copy()
    # 날짜 글자 → 날짜 값으로 바꿔야 편집 표에서 달력으로 고를 수 있음
    editor_source["날짜"] = pd.to_datetime(editor_source["날짜"]).dt.date

    # st.data_editor : 엑셀처럼 직접 고칠 수 있는 표. form 안에 넣어서 버튼을 눌러야 반영되게 함
    with st.form("edit_form"):
        edited = st.data_editor(
            # num_rows="dynamic" : 행 추가/삭제 가능, hide_index=True : 행 번호 숨김, width="stretch" : 가로 꽉 채움
            editor_source, num_rows="dynamic", hide_index=True, width="stretch",
            # key에 revision을 넣음 → 저장할 때마다 key가 바뀌어 편집 표가 새 데이터로 처음부터 다시 그려짐
            key=f"editor__{st.session_state.revision}",
            # 열마다 입력 방식·규칙 지정 (required=True : 빈칸 허용 안 함)
            column_config={
                "날짜": st.column_config.DateColumn(format="YYYY-MM-DD", required=True),
                "구분": st.column_config.SelectboxColumn(options=["수입", "지출"], required=True),
                "항목": st.column_config.TextColumn(max_chars=40, required=True),
                "금액": st.column_config.NumberColumn(min_value=1, max_value=MAX_AMOUNT, step=1, format="%d", required=True),
            },
        )
        edit_submitted = st.form_submit_button("수정 내용 반영", key="save_edits", type="primary")

    if edit_submitted:
        try:
            save_records(edited, "수정 내용을 반영했습니다.")   # 표 전체를 검증 후 통째로 교체
        except ValueError as exc:
            st.error(str(exc))

    duplicate_count = int(st.session_state.records.duplicated(). sum())
    if duplicate_count:
        st.warning(f"완전히 같은 내역 {duplicate_count}건이 있습니다. 실제 반복 거래일 수도 있어 자동 삭제하지 않습니다.")


    with st.expander("조회 내역만 필터링하기"):
        view_kind = st.selectbox("조회 구분",["전체","수입","지출"],key="view_kind")
        view_categories = st.multiselect("조회 항목(비우면 전체)",sorted(filtered["항목"].unique()),key="view_categories")
        
        view=filtered.copy()
        if view_kind != "전체":
            view = view[view["구분"] == view_kind]
            
        if view_categories:
            view = view[view["항목"].isin(view_categories)]
        
        st.dataframe(view, hide_index=True,width="stretch")
        st.caption("이 두 필터는 위의 조회 표에만 적용됩니다. 상단 KPI 요약 다운로드는 기간 필터만 적용됩니다.")
        
# ═════════════════════════ 6. 탭③ CSV 가져오기·다운로드 ═════════════════════════
with files:
    # read_csv_bytes(업로드), csv_bytes(다운로드)를 여기서 사용
    st.subheader("CSV 가져오기")
    st.info("공유 미리보기에는 실제 거래·이름·계좌번호를 올리지 마세요. 개인 자료는 로컬 실행에서 비식별화 후 사용하세요.")
    st.caption("필수 컬럼: 날짜, 구분, 항목, 금액 / 쉼표 구분 / UTF-8 또는 CP949 / 최대 5MB·5,000행. 추가 컬럼은 버립니다.")      
    uploaded = st.file_uploader("입출금 csv 선택",type=["csv"], key="upload")
    if uploaded is not None:
        try:
            candidate = read_csv_bytes(uploaded.getvalue())
            st.dataframe(candidate.head(10), hide_index=True, width="stretch")
            st.caption(f"검증 완료: {len(candidate):,}건. 적용 버튼을 눌러야 현재 내역에 반영됩니다.")
            mode = st.radio("반영 방식", ["기존 내역에 추가","전체 내역 교체"],horizontal=True, key="import_mode")
            if st.button("CSV 반영", key="apply_csv", type="primary"):
                result = candidate if mode == "전체 내역 교체" else pd.concat([st.session_state.records, candidate])
                save_records(result ,f"CSV {len(candidate):,}건을 반영했습니다.")
        except ValueError as exc:
            st.error(str(exc))
            
    st.subheader("다운로드")
    st.caption("전체 백업은 모든 내역, 요약 파일 3개는 사이드바에서 고른 기간 기준입니다.")
    x,y = st.columns(2)
    x.download_button("전체 내역 CSV 백업", csv_bytes(st.session_state.records),"입출금_전체내역.csv","text/csv",\
        key="download_all",width="stretch")
    y.download_button("가상 예제 CSV", csv_bytes(load_sample()),"입출금_연습용.csv","text/csv",\
        key="download_sample",width="stretch")
    
    p, q, r = st.columns(3)
    p.download_button("조회 내역 CSV", csv_bytes(filtered), "입출금_조회내역.csv", "text/csv", key="download_filtered", width="stretch")
    q.download_button("항목별 지출 CSV", csv_bytes(categorise), "항목별지출.csv", "text/csv", key="download_categories", width="stretch")
    r.download_button("월별 요약 CSV", csv_bytes(monthly), "월별요약.csv", "text/csv", key="download_monthly", width="stretch")
    st.caption("영구 저장 DB는 없습니다. 새로고침·연결 종료에 대비해 전체 CSV를 내려받으세요.")

# ═════════════════════════ 7. 탭④ 코드 학습 ═════════════════════════
with lesson:
    st.subheader("기존 pandas 수업과의 연결")
    st.code('''# 수입 / 지출 분리
income = df[df["구분"] == "수입"]
expenses = df[df["구분"] == "지출"]

# 항목별 지출 합계
totals = expenses.groupby("항목")["금액"].sum()

# 월별 수입 / 지출 피벗
df["월"] = df["날짜"].str[:7]
monthly = df.pivot_table(index="월", columns="구분",
                        values="금액", aggfunc="sum", fill_value=0)
monthly = monthly.reindex(columns=["수입", "지출"], fill_value=0)
monthly["남은금액"] = monthly["수입"] - monthly["지출"]''', language="python")
    st.write("app.py는 화면·세션 상태를, finance.py는 검증·파생열·집계·CSV 변환을 담당합니다.")
    st.caption("프런트 코드이지만 Streamlit 특성상 화면과 Python 계산은 서버에서 함께 실행됩니다. 별도 API·인증·계좌 연동은 없습니다.")
