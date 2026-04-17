"""
교량 수량집계표 자동화 시스템 — Streamlit UI
"""
import streamlit as st
import tempfile
import shutil
from pathlib import Path
from io import BytesIO

# 프로젝트 루트 경로 계산
APP_DIR = Path(__file__).resolve().parent  # ui/
SRC_DIR = APP_DIR.parent                   # quantity_aggregator/
PROJECT_ROOT = SRC_DIR.parent.parent       # quantity-aggregator/

# 모듈 경로 추가
import sys
sys.path.insert(0, str(SRC_DIR / "core"))

from parser import parse_workbook
from normalizer import normalize_all
from aggregator import aggregate_by_category, aggregate_rebar
from reporter import generate_report

import yaml


def load_terminology():
    """용어 사전 로드"""
    term_path = PROJECT_ROOT / "data" / "terminology.yaml"
    if not term_path.exists():
        st.error(f"❌ 용어 사전을 찾을 수 없습니다: {term_path}")
        st.stop()
    with open(term_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_uploaded_files(uploaded_files, tmp_dir: Path) -> list[Path]:
    """업로드된 파일을 임시 디렉토리에 저장"""
    saved = []
    for uf in uploaded_files:
        file_path = tmp_dir / uf.name
        with open(file_path, "wb") as f:
            f.write(uf.getbuffer())
        saved.append(file_path)
    return saved


def run_pipeline(files: list[Path], terminology: dict):
    """전체 파이프라인 실행: 파싱 → 정규화 → 집계"""
    # 1. 파싱
    all_records = []
    parse_log = []
    for f in files:
        records = parse_workbook(f, terminology)
        parse_log.append({"file": f.name, "records": len(records)})
        all_records.extend(records)

    # 2. 정규화
    normalize_all(all_records, terminology)

    # 3. 통계
    total = len(all_records)
    wt_matched = sum(1 for r in all_records if r["normalized"]["work_type_std"])
    unit_matched = sum(1 for r in all_records if r["normalized"]["unit_std"])
    all_unmatched = [
        {"file": r["source_file"], "sheet": r["sheet_name"],
         "work_type": r["work_type_raw"], "spec1": r["spec1_raw"],
         "unit": r["unit_raw"], "reason": u}
        for r in all_records for u in r["normalized"]["unmatched"]
    ]

    # 4. 집계
    structure_agg = aggregate_by_category(all_records, "structure", terminology)
    earthwork_agg = aggregate_by_category(all_records, "earthwork", terminology)
    temp_road_agg = aggregate_by_category(all_records, "temp_road", terminology)
    ground_imp_agg = aggregate_by_category(all_records, "ground_improvement", terminology)
    temp_struct_agg = aggregate_by_category(all_records, "temp_structure", terminology)
    rebar_agg = aggregate_rebar(all_records)

    return {
        "all_records": all_records,
        "parse_log": parse_log,
        "total": total,
        "wt_matched": wt_matched,
        "unit_matched": unit_matched,
        "unmatched": all_unmatched,
        "structure_agg": structure_agg,
        "earthwork_agg": earthwork_agg,
        "temp_road_agg": temp_road_agg,
        "ground_imp_agg": ground_imp_agg,
        "temp_struct_agg": temp_struct_agg,
        "rebar_agg": rebar_agg,
    }


def generate_excel(result: dict, terminology: dict) -> bytes:
    """집계 결과를 Excel 바이트로 생성"""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    generate_report(
        tmp_path,
        result["structure_agg"],
        result["earthwork_agg"],
        result["temp_road_agg"],
        result["ground_imp_agg"],
        result["temp_struct_agg"],
        result["rebar_agg"],
        result["all_records"],
    )

    with open(tmp_path, "rb") as f:
        data = f.read()

    Path(tmp_path).unlink(missing_ok=True)
    return data


def agg_to_table(agg_rows: list[dict]) -> list[dict]:
    """집계 결과를 테이블 형태로 변환"""
    table = []
    for row in agg_rows:
        r = {
            "공종": row["work_type"],
            "규격1": row["spec1"],
            "규격2": row["spec2"],
            "단위": row["unit"],
        }
        for struct, qty in row["structures"].items():
            r[struct] = qty
        r["총계"] = row["total"]
        table.append(r)
    return table


# ================================================================
# 메인 UI
# ================================================================
def main():
    st.set_page_config(
        page_title="교량 수량집계표 자동화",
        page_icon="🏗️",
        layout="wide",
    )

    st.title("🏗️ 교량 수량집계표 자동화")
    st.caption("수량산출서 Excel 파일을 업로드하면 총괄수량집계표를 자동 생성합니다.")

    # 사이드바
    with st.sidebar:
        st.header("📋 사용법")
        st.markdown("""
        1. 공종별 수량산출서 파일 업로드
        2. 파싱 결과 확인
        3. 집계 결과 미리보기
        4. Excel 다운로드
        
        **지원 형식:** `.xlsx`, `.xls`  
        **주의:** `.xls` 파일은 Excel에서 `.xlsx`로 변환 후 업로드하세요.
        """)

        st.divider()
        st.header("⚙️ 정보")
        term = load_terminology()
        st.metric("등록 공종 수", f"{len(term['work_types'])}개")
        st.metric("등록 단위 수", f"{len(term['units'])}개")

    # ---- 섹션 1: 파일 업로드 ----
    st.header("1️⃣ 파일 업로드")

    project_name = st.text_input(
        "프로젝트명",
        placeholder="예: 갈전7교",
        help="결과 파일명에 사용됩니다."
    )

    uploaded_files = st.file_uploader(
        "수량산출서 파일 선택 (여러 개 가능)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="총괄집계표(00번)는 업로드하지 마세요. 입력용 산출서만 올려주세요."
    )

    if not uploaded_files:
        st.info("👆 위에서 파일을 업로드하세요.")
        st.stop()

    st.success(f"✅ {len(uploaded_files)}개 파일 업로드됨")
    for uf in uploaded_files:
        st.caption(f"  📄 {uf.name} ({uf.size / 1024:.0f} KB)")

    # ---- 섹션 2: 파싱 & 집계 실행 ----
    st.header("2️⃣ 파싱 & 집계")

    if st.button("🚀 집계 시작", type="primary", use_container_width=True):
        terminology = load_terminology()

        # 임시 디렉토리에 파일 저장
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            with st.status("처리 중...", expanded=True) as status:
                st.write("📂 파일 저장 중...")
                files = save_uploaded_files(uploaded_files, tmp_dir)

                st.write("📊 파싱 중...")
                result = run_pipeline(files, terminology)

                st.write("✅ 완료!")
                status.update(label="처리 완료!", state="complete")

            # 결과를 세션에 저장
            st.session_state["result"] = result
            st.session_state["terminology"] = terminology
            st.session_state["project_name"] = project_name or "프로젝트"

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ---- 섹션 3: 결과 표시 ----
    if "result" not in st.session_state:
        st.stop()

    result = st.session_state["result"]
    terminology = st.session_state["terminology"]
    proj_name = st.session_state["project_name"]

    st.header("3️⃣ 결과")

    # 요약 메트릭
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 레코드", f"{result['total']}개")
    col2.metric("공종 매칭", f"{result['wt_matched']}/{result['total']}")
    col3.metric("단위 매칭", f"{result['unit_matched']}/{result['total']}")
    col4.metric("미매칭 이슈", f"{len(result['unmatched'])}건",
                delta=None if not result['unmatched'] else "확인 필요",
                delta_color="inverse")

    # 파싱 로그
    with st.expander("📋 파일별 파싱 결과"):
        for log in result["parse_log"]:
            st.write(f"  📄 **{log['file']}**: {log['records']}개 레코드")

    # 탭으로 집계 결과 표시
    tabs = st.tabs(["구조물공", "토공", "가시설공", "가축도공", "지반개량공",
                    "철근가공조립", "미매칭 항목"])

    with tabs[0]:
        if result["structure_agg"]:
            st.dataframe(agg_to_table(result["structure_agg"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("해당 데이터가 없습니다.")

    with tabs[1]:
        if result["earthwork_agg"]:
            st.dataframe(agg_to_table(result["earthwork_agg"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("해당 데이터가 없습니다.")

    with tabs[2]:
        if result["temp_struct_agg"]:
            st.dataframe(agg_to_table(result["temp_struct_agg"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("해당 데이터가 없습니다.")

    with tabs[3]:
        if result["temp_road_agg"]:
            st.dataframe(agg_to_table(result["temp_road_agg"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("해당 데이터가 없습니다.")

    with tabs[4]:
        if result["ground_imp_agg"]:
            st.dataframe(agg_to_table(result["ground_imp_agg"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("해당 데이터가 없습니다.")

    with tabs[5]:
        rebar = result["rebar_agg"]
        if rebar["by_type"]:
            rebar_table = []
            seen = set()
            for r in rebar["by_type"]:
                if r["total"] > 0 and r["type"] not in seen:
                    seen.add(r["type"])
                    row = {"Type": r["type"]}
                    for struct, qty in r["structures"].items():
                        if not struct.startswith("__"):
                            row[struct] = qty
                    row["총계(ton)"] = r["total"]
                    rebar_table.append(row)
            st.dataframe(rebar_table, use_container_width=True, hide_index=True)
        else:
            st.info("해당 데이터가 없습니다.")

    with tabs[6]:
        if result["unmatched"]:
            st.warning(f"⚠️ {len(result['unmatched'])}건의 미매칭 항목이 있습니다.")
            st.caption("용어 사전(data/terminology.yaml)에 추가하면 다음부터 자동 매칭됩니다.")
            st.dataframe(result["unmatched"],
                         use_container_width=True, hide_index=True)
        else:
            st.success("✅ 모든 항목이 정상 매칭되었습니다!")

    # ---- 섹션 4: Excel 다운로드 ----
    st.header("4️⃣ 다운로드")

    excel_data = generate_excel(result, terminology)
    filename = f"{proj_name}_총괄수량집계표.xlsx"

    st.download_button(
        label="📥 총괄수량집계표 Excel 다운로드",
        data=excel_data,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

    st.caption(f"파일명: `{filename}`")


if __name__ == "__main__":
    main()