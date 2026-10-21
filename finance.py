from io import BytesIO      # bytes를 파일처럼 다루는 도구 (업로드 CSV 읽을 때)
from pathlib import Path    # 경로를 Path("폴더") / "파일" 처럼 이어 붙이는 도구

import numpy as np          # 숫자 계산
import pandas as pd         # 표(DataFrame) 다루기

# 상수 : 프로그램 전체에서 쓰는 기준값 (대문자 이름)
COLUMNS = ['날짜', '구분', '항목', '금액']   # 필수 컬럼
MAX_ROWS = 5000                              # 최대 행 수
MAX_AMOUNT = 1000000000000                   # 거래 1건 최대 금액 : 1조 원
MAX_FILE_BYTES = 5 * 1024 * 1024             # 업로드 CSV 최대 크기 : 5MB


# 행은 0개지만 컬럼과 자료형은 정해진 "빈 표 틀"을 만든다
# → 데이터가 없어도 df['금액'] 같은 코드가 에러 나지 않게
def empty_records() -> pd.DataFrame:     # -> : 반환 자료형 표시(타입 힌트)
    return pd.DataFrame({
        '날짜': pd.Series(dtype="string"),
        '구분': pd.Series(dtype="string"),
        '항목': pd.Series(dtype="string"),
        '금액': pd.Series(dtype="int64"),    # 정수
    })
    
    # 데이터가 규칙에 맞는지 검사 → 틀리면 ValueError, 맞으면 정리된 표 반환
def validate_records(frame:pd.DataFrame) -> pd.DataFrame:

    # 1) 중복 컬럼 : 같은 이름이 하나라도 있으면 에러
    if frame.columns.duplicated().any():
        raise ValueError("동일한 컬럼 이름이 중복되었습니다.")

    # 2) 필수 컬럼 : COLUMNS 중 frame에 없는 이름만 모으기 (다 있으면 [])
    missing = [name for name in COLUMNS if name not in frame.columns]
    if missing:      # 빈 리스트면 False
        raise ValueError("필수 컬럼이 없습니다: " + ", " .join(missing))   # ['금액'] → "금액"

    # 3) 최대 행 수
    if len(frame) > MAX_ROWS:
        raise ValueError(f"내역은 최대{MAX_ROWS:,}행까지 입력할 수 있습니다.")

    # 4) 0행이면 빈 표 틀 반환
    if frame.empty:
        return empty_records()

    # 5) 필수 열만, 복사본으로, 행 번호는 0부터 새로
    clean = frame[COLUMNS].copy().reset_index(drop=True)

    # 6) 글자 열 앞뒤 공백 제거 (" 월급 " → "월급")
    for name in ["날짜",'구분', '항목']:
        clean[name] = clean[name].astype("string").str.strip()


    # 7) 값 검사 : 행마다 True(정상)/False(오류) 마스크 만들기
    # [날짜] coerce : 변환 못 하면 에러 대신 NaT(빈 날짜)
    date_text = clean["날짜"]
    dates = pd.to_datetime(date_text, format="%Y-%m-%d", errors="coerce")
    valid_dates = (
        date_text.str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)  # 0000-00-00 모양
        & dates.notna()                                            # 실제 있는 날짜 (2026-02-30 X)
        & dates.between("1900-01-01","2100-12-31")                 # 허용 범위
    )

    # [구분] 수입/지출만
    valid_kind = clean["구분"].isin(['수입','지출'])
    # [항목] 비어 있지 않고 1~40글자
    valid_category = clean['항목'].notna() & clean["항목"].str.len().between(1,40)
    # [금액] 글자 → 숫자 (못 바꾸면 NaN)
    raw_amount = clean['금액'].astype("string").str.strip()
    amount = pd.to_numeric(raw_amount, errors="coerce")
    valid_amount = (
        amount.notna() & np.isfinite(amount)                    # 숫자이고 무한대 아님
        & amount.between(1, MAX_AMOUNT) & amount.mod(1).eq(0)   # 1원~1조 원, 정수
    ).fillna(False)


    # 8) (설명, 마스크) 쌍을 하나씩 확인 → False가 있으면 에러
    for label, mask in[
        ("날짜: YYYY-MM-DD의 실제 날짜 (1900~2100년)",valid_dates),
        ("구분: 수입 또는 지출",valid_kind),
        ("항목: 1~40글자의 이름", valid_category),
        ("금액: 1원~1조원 양의 정수",valid_amount),
    ]:
        if not mask.all():   # 하나라도 False면
            # ~mask : 뒤집기 → 틀린 행 번호(1부터), 최대 10개
            rows= [str(i + 1) for i in clean. index[~mask ] [ : 10] ]
            raise ValueError(f"[{label}] 조건을 확인하세요. 잘못된 데이터 행: {', '.join(rows)}")

    # 9) 통과 → 날짜는 "YYYY-MM-DD" 글자로, 금액은 정수로
    clean['날짜'] = dates.dt.strftime("%Y-%m-%d").astype("string")
    clean['금액'] = amount.astype("int64")
    return clean


# data 폴더의 샘플 CSV를 읽고 검증까지 해서 반환
def load_sample() -> pd.DataFrame:
    path = Path(__file__).parent / "data" / "sample_transactions.csv"   # (이 파일이 있는 폴더)/data/파일
    # __file__ : 지금 실행 중인 파이썬 파일의 경로 → 어느 폴더에서 실행해도 샘플을 찾을 수 있음
    if not path.exists():    # 파일이 없으면 알아보기 쉬운 에러
        raise FileNotFoundError(
            f"샘플 파일을 찾을 수 없습니다. {path}\n"
            "data/sample_transactions.csv파일을 준비해 주세요"
        )
    return validate_records(pd.read_csv(path, encoding="utf-8-sig"))   # utf-8-sig : 엑셀 CSV의 BOM 처리

def read_csv_bytes(content: bytes) -> pd.DataFrame:
    if len(content) > MAX_FILE_BYTES:    # 5MB 초과 거절
        raise ValueError("CSV 파일은 최대 5MB까지 사용할 수 있습니다.")
    if not content:                      # 빈 파일 거절
        raise ValueError("CSV 파일이 비어 있습니다.")

    # utf-8-sig로 읽어 보고, 글자가 깨지면 cp949(옛 한글 엑셀)로 다시 시도
    for encoding in ["utf-8-sig", "cp949"]:
        try:
            # BytesIO : bytes를 파일처럼 / nrows : 5,001행까지만 읽어서 초과 여부만 판단
            frame = pd.read_csv(BytesIO(content), encoding=encoding, nrows=MAX_ROWS + 1)
            return validate_records (frame)
        except UnicodeDecodeError:
            continue     # 다음 인코딩으로
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
            # 어려운 pandas 에러 → 쉬운 메시지로 바꿔서 다시 발생
            raise ValueError("CSV 형식이 올바르지 않습니다. 쉼표 구분 파일을 사용하세요.") from exc
    raise ValueError("파일 인코딩을 읽을 수 없습니다. UTF-8또는 CP949 CSV로 저장하세요")   # 둘 다 실패


# 월, 표시 열 추가. threshold(큰 지출 기준)는 생략하면 10만 원
def add_features(frame: pd.DataFrame, threshold: int = 100000) -> pd.DataFrame:
    result = frame.copy()   # 원본 보호

    # 월 : "2026-01-05" → "2026-01" (앞 7글자)
    result["월"] = result["날짜"].apply(lambda d: d[:7])

    # 표시 : 수입 / 큰 지출 / 일반 지출 (axis=1 → 행 하나씩)
    result["표시"] = result.apply(
        lambda row: "수입" if row["구분"] == "수입"
        else ("큰 지출" if row["금액"] >= threshold else "일반 지출"),
        axis=1,
    ) if len(result) else pd.Series(dtype="string")   # 빈 표면 apply 대신 빈 열

    return result

# 항목별 지출 합계, 월별 요약 두 개를 반환
def summarize(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # 지출만 남기기
    mask = frame["구분"] == "지출"
    expenses = frame[mask]

    # 항목별 지출 합계 → 큰 금액부터
    categories = (
        expenses.groupby("항목")["금액"].sum()
        .sort_values(ascending=False)
        .rename("지출 합계")
        .reset_index()                  # Series → 표
    )

    # 월별 수입/지출 합계 (행=월, 열=구분)
    monthly = frame.pivot_table(
        index="월",
        columns="구분",
        values="금액",
        aggfunc="sum",
        fill_value=0,        # 빈 칸은 0
    )
    # 수입이나 지출 열이 없어도 0으로 만들어 두기
    monthly = monthly.reindex(columns=["수입", "지출"], fill_value=0)

    monthly["남은 금액"] = monthly["수입"] - monthly["지출"]
    # 수입 0원이면 0으로 나누지 않게 NaN으로
    monthly["남은 비율(%)"] = (monthly["남은 금액"] / monthly["수입"].replace(0, np.nan) * 100).round(1)

    monthly = monthly.reset_index()
    return categories, monthly           # 두 개 반환 (튜플)


# 표 → CSV bytes (엑셀 수식 방지 + 한글 깨짐 방지)
def csv_bytes(frame:pd.DataFrame) -> bytes:
    safe = frame.copy()

    # 글자 열에서 = + - @ 등으로 시작하면 앞에 ' 를 붙여 엑셀이 수식으로 실행하지 못하게 (CSV 인젝션 방지)
    for name in safe.select_dtypes(include=['object','string']).columns:
        safe[name] = safe[name].map(
            lambda value: "'" + value
            if isinstance(value,str) and value.lstrip().startswith(("=",'+','-','@','\t','\r'))
            else value
        )
    # index=False : 행 번호 빼기 / na_rep='' : 빈 값은 빈칸
    # utf-8-sig : 엑셀에서 한글이 안 깨지게 (맨 앞에 BOM)
    return safe.to_csv(index= False, na_rep='',encoding=None).encode("utf-8-sig")