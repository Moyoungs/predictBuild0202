"""
normalizer.py — 원본 레코드의 공종/단위/구조물을 표준 용어로 매핑

책임:
  1. work_type_raw → standard_work_type + category
  2. unit_raw → standard_unit
  3. quantities의 키(원본 구조물명) → standard_structure
  4. 사전에 없는 항목은 unmatched 리스트로 분리 (→ AI fallback 후보)
"""
from typing import Optional


def _norm(s: str) -> str:
    return "".join(str(s).split()) if s is not None else ""


def match_work_type(raw: str, terminology: dict) -> tuple[Optional[str], Optional[str]]:
    """원본 공종명 → (표준명, 카테고리). 실패 시 (None, None)"""
    n = _norm(raw)
    for wt in terminology["work_types"]:
        for alias in wt["aliases"]:
            if _norm(alias) == n:
                return wt["standard"], wt["category"]
    return None, None


def match_unit(raw: str, terminology: dict) -> Optional[str]:
    """원본 단위 → 표준 단위"""
    r = str(raw).strip() if raw else ""
    for std_unit, info in terminology["units"].items():
        if r in info["aliases"]:
            return std_unit
    return None


def match_structure(raw: str, terminology: dict) -> Optional[dict]:
    """
    원본 구조물명 → 구조물 정보
    반환: {'standard', 'output_column', 'aggregate_into'} 또는 None
    """
    r = str(raw).strip() if raw else ""
    for s in terminology["structures"]:
        if r in s["aliases"]:
            return s
    return None


def normalize_record(record: dict, terminology: dict) -> dict:
    """
    원본 레코드 하나를 정규화.
    결과에 'normalized' 키 추가:
      {
        'work_type_std': str | None,
        'category': str | None,
        'unit_std': str | None,
        'quantities_std': { structure_std: value, ... },
        'unmatched': [reason, ...]   # 매칭 실패 사유
      }
    """
    unmatched = []

    # 공종 매핑
    wt_std, category = match_work_type(record["work_type_raw"], terminology)
    if wt_std is None:
        unmatched.append(f"work_type_not_found: '{record['work_type_raw']}'")

    # 단위 매핑
    unit_std = match_unit(record["unit_raw"], terminology)
    if unit_std is None and record["unit_raw"]:
        unmatched.append(f"unit_not_found: '{record['unit_raw']}'")

    # 구조물 매핑
    quantities_std = {}
    for raw_struct, value in record["quantities"].items():
        struct_info = match_structure(raw_struct, terminology)
        if struct_info is None:
            # 구조물명 매칭 실패 → 원본 이름 그대로 남김 (AI 판단 대상)
            quantities_std[f"__unmatched__{raw_struct}"] = value
            unmatched.append(f"structure_not_found: '{raw_struct}'")
        else:
            # 'aggregate_into'가 있으면 그 구조물로 합산
            target = struct_info.get("aggregate_into") or struct_info["standard"]
            quantities_std[target] = quantities_std.get(target, 0.0) + value

    record["normalized"] = {
        "work_type_std": wt_std,
        "category": category,
        "unit_std": unit_std,
        "quantities_std": quantities_std,
        "unmatched": unmatched,
    }
    return record


def normalize_all(records: list[dict], terminology: dict) -> list[dict]:
    return [normalize_record(r, terminology) for r in records]


if __name__ == "__main__":
    import yaml
    from pathlib import Path
    from parser import parse_workbook

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    terminology_path = project_root / "data" / "terminology.yaml"
    fixtures_path = project_root / "tests" / "fixtures" / "galjeon7"

    with open(terminology_path, encoding="utf-8") as f:
        term = yaml.safe_load(f)

    files = sorted(fixtures_path.glob("*.xlsx")) + sorted(fixtures_path.glob("*.xls"))
    files = [f for f in files if not f.name.startswith("00_")]

    all_records = []
    for f in files:
        all_records.extend(parse_workbook(f, term))

    normalize_all(all_records, term)

    total = len(all_records)
    wt_matched = sum(1 for r in all_records if r["normalized"]["work_type_std"])
    unit_matched = sum(1 for r in all_records if r["normalized"]["unit_std"])
    all_unmatched = [u for r in all_records for u in r["normalized"]["unmatched"]]

    print(f"총 레코드: {total}")
    print(f"공종 매칭: {wt_matched}/{total} = {wt_matched/total*100:.1f}%")
    print(f"단위 매칭: {unit_matched}/{total} = {unit_matched/total*100:.1f}%")
    print(f"미매칭 이슈: {len(all_unmatched)}")

    if all_unmatched:
        from collections import Counter
        c = Counter(all_unmatched)
        print("\n[미매칭 Top 10]")
        for item, count in c.most_common(10):
            print(f"  ({count}회) {item}")