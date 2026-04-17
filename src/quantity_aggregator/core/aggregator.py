"""
aggregator.py — 정규화된 레코드를 총괄집계표 형태로 집계

MVP v1: 3개 시트 대상
  1. 구조물공총괄집계표 (category='structure')
  2. 토공총괄집계표 (category='earthwork')
  3. 철근총괄 (category='rebar' 또는 공종='철근가공조립')

집계 키: (work_type_std, spec1_raw, spec2_raw, unit_std)
집계 값: 구조물별 수량 합계 (본교/옹벽/가축도)
"""
from collections import defaultdict
from typing import Any


def aggregate_by_category(
    records: list[dict], category: str, terminology: dict
) -> list[dict]:
    """
    특정 카테고리의 레코드를 (공종, 규격1, 규격2, 단위) 단위로 집계.
    동일 키의 여러 레코드는 구조물별 수량을 합산.
    """
    # 키: (work_type_std, spec1, spec2, unit_std)
    # 값: { structure: total_qty }
    grouped: dict[tuple, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for r in records:
        n = r["normalized"]
        if n["category"] != category:
            continue
        if n["work_type_std"] is None:
            continue  # 매칭 실패 → 집계에서 제외 (AI fallback 필요)

        key = (
            n["work_type_std"],
            r["spec1_raw"],
            r["spec2_raw"],
            n["unit_std"] or r["unit_raw"],
        )

        for struct, qty in n["quantities_std"].items():
            if struct.startswith("__unmatched__"):
                continue
            grouped[key][struct] += qty

    # 결과를 리스트로 변환 + 총계 계산
    result = []
    for (wt, spec1, spec2, unit), struct_qtys in grouped.items():
        row = {
            "work_type": wt,
            "spec1": spec1,
            "spec2": spec2,
            "unit": unit,
            "structures": dict(struct_qtys),
            "total": sum(struct_qtys.values()),
        }
        result.append(row)

    # 정렬: 공종 → 규격1 → 규격2
    result.sort(key=lambda x: (x["work_type"], x["spec1"], x["spec2"]))
    return result


def aggregate_rebar(records: list[dict]) -> dict:
    """
    철근총괄: 공종별 × 직경별 매트릭스
    레코드 중 unit이 'ton'이고 공종명에 '철근'이 들어가는 것만 대상
    각 레코드의 spec2_raw에 Type 정보가 있을 수 있음
    """
    # 현재 프로젝트에서는 '철근가공조립' 하나에 Type-Ⅰ-1/Ⅱ-1 등으로만 분류됨
    # 실제 직경(H25 등)별 집계는 01번 파일의 '철근수량 집계표' 시트가 담당
    # → 이 시트는 별도 파서 필요 (MVP v2에서 처리)
    # 여기서는 현재 가능한 범위만
    rebar_records = []
    for r in records:
        n = r["normalized"]
        if n["work_type_std"] == "철근가공조립":
            rebar_records.append({
                "type": r["spec2_raw"],  # Type-Ⅰ-1 등
                "unit": n["unit_std"],
                "structures": n["quantities_std"],
                "total": sum(
                    v for k, v in n["quantities_std"].items()
                    if not k.startswith("__unmatched__")
                )
            })
    return {"by_type": rebar_records}


if __name__ == "__main__":
    import yaml
    from pathlib import Path
    from parser import parse_workbook
    from normalizer import normalize_all

    with open("/home/claude/terminology/terminology.yaml", encoding="utf-8") as f:
        term = yaml.safe_load(f)

    files = [
        Path("/mnt/user-data/uploads/01_갈전7교_일반수량_산출서.xlsx"),
        Path("/mnt/user-data/uploads/02_갈전7교_토공수량_산출서.xlsx"),
        Path("/mnt/user-data/uploads/03__갈전7교_가축도공_수량산출서.xlsx"),
        Path("/mnt/user-data/uploads/04_갈전7교_가시설공_251208_.xlsx"),
        Path("/home/claude/converted/05_갈전7교_지반개량공수량산출서.xlsx"),
    ]

    all_records = []
    for f in files:
        all_records.extend(parse_workbook(f, term))
    normalize_all(all_records, term)

    # ===== 구조물공 총괄 =====
    print("=" * 80)
    print("구조물공 총괄집계표 (MVP 재현)")
    print("=" * 80)
    print(f"{'공종':<12} {'규격1':<14} {'규격2':<20} {'단위':<5} {'본교':>12} {'옹벽':>8} {'총계':>12}")
    print("-" * 100)
    structure_agg = aggregate_by_category(all_records, "structure", term)
    for row in structure_agg:
        print(f"{row['work_type']:<12} {row['spec1']:<14} {row['spec2']:<20} "
              f"{row['unit'] or '':<5} "
              f"{row['structures'].get('본교', 0):>12,.3f} "
              f"{row['structures'].get('옹벽', 0):>8,.3f} "
              f"{row['total']:>12,.3f}")

    # ===== 토공 총괄 =====
    print()
    print("=" * 80)
    print("토공 총괄집계표 (MVP 재현)")
    print("=" * 80)
    print(f"{'공종':<10} {'규격1':<10} {'규격2':<10} {'단위':<5} {'본교':>12} {'가축도':>10} {'총계':>12}")
    print("-" * 80)
    earth_agg = aggregate_by_category(all_records, "earthwork", term)
    for row in earth_agg:
        print(f"{row['work_type']:<10} {row['spec1']:<10} {row['spec2']:<10} "
              f"{row['unit'] or '':<5} "
              f"{row['structures'].get('본교', 0):>12,.3f} "
              f"{row['structures'].get('가축도', 0):>10,.3f} "
              f"{row['total']:>12,.3f}")

    # ===== 가축도공 레코드 (별도 확인) =====
    print()
    print("=" * 80)
    print("가축도공 (temp_road)")
    print("=" * 80)
    temp_road_agg = aggregate_by_category(all_records, "temp_road", term)
    for row in temp_road_agg:
        print(f"  {row['work_type']:<20} {row['spec1']:<10} {row['unit'] or '':<5} "
              f"수량={row['structures']} 총계={row['total']:.3f}")

    # ===== 지반개량 =====
    print()
    print("=" * 80)
    print("지반개량공 (ground_improvement)")
    print("=" * 80)
    gi_agg = aggregate_by_category(all_records, "ground_improvement", term)
    for row in gi_agg:
        print(f"  {row['work_type']:<25} {row['spec1']:<25} {row['unit'] or '':<5} "
              f"총계={row['total']:.3f}")

    # ===== 철근 =====
    print()
    print("=" * 80)
    print("철근가공조립 (Type별)")
    print("=" * 80)
    rebar = aggregate_rebar(all_records)
    for r in rebar["by_type"]:
        if r["total"] > 0:
            print(f"  Type={r['type']:<15} 단위={r['unit']} 수량={r['structures']} 총계={r['total']:.3f}")
