"""
claude_client.py — 미매칭 항목을 Claude API로 자동 매핑

기능:
  1. 미매칭 항목 배치를 Claude에 전달
  2. Tool use로 구조화된 JSON 응답 강제
  3. 신뢰도 90% 이상 → 자동 저장
  4. 신뢰도 90% 미만 → 사람 확인 요청
  5. 승인된 매핑을 terminology.yaml에 자동 추가
"""
import os
import json
import yaml
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


def get_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY가 .env에 설정되어 있지 않습니다.")
    return Anthropic(api_key=api_key)


# Tool use 스키마: Claude가 이 형식으로만 응답하도록 강제
MAPPING_TOOL = {
    "name": "submit_mappings",
    "description": "미매칭 항목들에 대한 매핑 결과를 제출합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original": {
                            "type": "string",
                            "description": "원본 항목명"
                        },
                        "standard_name": {
                            "type": "string",
                            "description": "매핑할 표준 공종명 (기존 사전에 있는 것 우선, 없으면 새로 제안)"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["structure", "earthwork", "temp_structure",
                                     "ground_improvement", "temp_road", "material"],
                            "description": "대분류 카테고리"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "매핑 신뢰도 (0.0 ~ 1.0)"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "판단 근거 (한국어)"
                        }
                    },
                    "required": ["original", "standard_name", "category",
                                 "confidence", "reasoning"]
                }
            }
        },
        "required": ["mappings"]
    }
}


def build_system_prompt(terminology: dict) -> str:
    """시스템 프롬프트: 용어 사전 전체를 컨텍스트로 포함"""
    # 기존 공종 목록 요약
    existing_types = []
    for wt in terminology["work_types"]:
        aliases_str = ", ".join(wt["aliases"][:5])
        existing_types.append(f"  - {wt['standard']} ({wt['category']}): {aliases_str}")
    existing_list = "\n".join(existing_types)

    # 카테고리 설명
    categories_desc = "\n".join(
        f"  - {c['id']}: {c['name']} — {c['description']}"
        for c in terminology["categories"]
    )

    return f"""당신은 한국 토목/건축 수량집계표 전문가입니다.

주어진 미매칭 항목(공종명)을 분석하여 적절한 표준 공종명과 카테고리로 매핑해주세요.

## 카테고리 목록
{categories_desc}

## 기존 등록된 공종 (참고용)
{existing_list}

## 매핑 규칙
1. 기존 사전에 있는 표준 공종명과 동일하거나 유사하면 그 이름으로 매핑
2. 기존에 없는 완전히 새로운 공종이면 적절한 표준 이름을 새로 제안
3. 공종명에 규격 정보가 포함된 경우 (예: "경사 버팀보(L=4.400m)") 규격을 제거한 표준명 사용
4. 약어/영문/한글 혼용을 고려하여 매핑
5. 신뢰도는 다음 기준으로 판단:
   - 1.0: 기존 사전의 변형 표기임이 확실
   - 0.9: 도메인 지식상 매핑이 거의 확실
   - 0.7~0.8: 합리적 추정이지만 확인 필요
   - 0.5 이하: 모호하거나 판단 근거 부족

반드시 submit_mappings 도구를 사용하여 결과를 제출하세요."""


def map_unmatched_items(
        unmatched_items: list[dict],
        terminology: dict,
        model: str = "claude-haiku-4-5-20251001"
) -> list[dict]:
    """
    미매칭 항목 배치를 Claude API에 전달하여 매핑 제안을 받음.

    Args:
        unmatched_items: [{"work_type": "...", "unit": "...", "context": "..."}, ...]
        terminology: 용어 사전
        model: 사용할 Claude 모델

    Returns:
        [{"original", "standard_name", "category", "confidence", "reasoning"}, ...]
    """
    if not unmatched_items:
        return []

    client = get_client()

    # 중복 제거 (같은 공종명은 한 번만 질의)
    unique_items = {}
    for item in unmatched_items:
        key = item.get("work_type", "")
        if key and key not in unique_items:
            unique_items[key] = item

    # 사용자 메시지 구성
    items_text = "\n".join(
        f"  - \"{name}\" (단위: {item.get('unit', '불명')}, 출처: {item.get('file', '불명')})"
        for name, item in unique_items.items()
    )

    user_message = f"""다음 {len(unique_items)}개의 미매칭 공종명을 분석하여 매핑해주세요:

{items_text}

각 항목에 대해 표준 공종명, 카테고리, 신뢰도, 판단 근거를 제출해주세요."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=build_system_prompt(terminology),
            tools=[MAPPING_TOOL],
            tool_choice={"type": "tool", "name": "submit_mappings"},
            messages=[{"role": "user", "content": user_message}]
        )

        # Tool use 응답 파싱
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_mappings":
                return block.input.get("mappings", [])

        return []

    except Exception as e:
        print(f"❌ Claude API 호출 실패: {e}")
        return []


def classify_mappings(mappings: list[dict], threshold: float = 0.9):
    """
    매핑 결과를 신뢰도 기준으로 분류.

    Returns:
        (auto_approved, needs_review)
        - auto_approved: 신뢰도 >= threshold → 자동 저장 대상
        - needs_review: 신뢰도 < threshold → 사람 확인 필요
    """
    auto_approved = [m for m in mappings if m.get("confidence", 0) >= threshold]
    needs_review = [m for m in mappings if m.get("confidence", 0) < threshold]
    return auto_approved, needs_review


def apply_mappings_to_terminology(
        mappings: list[dict],
        terminology: dict,
        terminology_path: Path
) -> int:
    """
    승인된 매핑을 terminology.yaml에 추가.

    Returns:
        추가된 항목 수
    """
    added = 0

    for m in mappings:
        original = m["original"]
        standard = m["standard_name"]
        category = m["category"]

        # 이미 있는 공종의 alias로 추가할지, 새 공종으로 추가할지 판단
        found_existing = False
        for wt in terminology["work_types"]:
            if wt["standard"] == standard:
                # 기존 공종에 alias 추가
                if original not in wt["aliases"]:
                    wt["aliases"].append(original)
                    found_existing = True
                    added += 1
                break

        if not found_existing:
            # 새 공종 추가
            terminology["work_types"].append({
                "standard": standard,
                "category": category,
                "aliases": [original]
            })
            added += 1

    # YAML 파일에 저장
    if added > 0:
        with open(terminology_path, "w", encoding="utf-8") as f:
            yaml.dump(terminology, f, allow_unicode=True, default_flow_style=False,
                      sort_keys=False, width=120)

    return added


def process_unmatched(
        unmatched_items: list[dict],
        terminology: dict,
        terminology_path: Path,
        threshold: float = 0.9,
        model: str = "claude-haiku-4-5-20251001"
) -> dict:
    """
    미매칭 항목 전체 처리 파이프라인.

    1. Claude API로 매핑 제안 받기
    2. 신뢰도 기준 분류 (자동/수동)
    3. 자동 승인 항목은 사전에 바로 저장
    4. 결과 반환

    Returns:
        {
            "total": int,
            "auto_approved": [mapping, ...],
            "needs_review": [mapping, ...],
            "auto_saved_count": int,
            "api_called": bool,
        }
    """
    if not unmatched_items:
        return {
            "total": 0, "auto_approved": [], "needs_review": [],
            "auto_saved_count": 0, "api_called": False
        }

    # 1. work_type_not_found만 필터 (단위/구조물 미매칭은 제외)
    work_type_unmatched = [
        item for item in unmatched_items
        if "work_type_not_found" in item.get("reason", "")
    ]

    if not work_type_unmatched:
        return {
            "total": 0, "auto_approved": [], "needs_review": [],
            "auto_saved_count": 0, "api_called": False
        }

    # 2. Claude API 호출
    mappings = map_unmatched_items(work_type_unmatched, terminology, model)

    # 3. 신뢰도 분류
    auto_approved, needs_review = classify_mappings(mappings, threshold)

    # 4. 자동 승인 항목 사전에 저장
    auto_saved = 0
    if auto_approved:
        auto_saved = apply_mappings_to_terminology(
            auto_approved, terminology, terminology_path
        )

    return {
        "total": len(mappings),
        "auto_approved": auto_approved,
        "needs_review": needs_review,
        "auto_saved_count": auto_saved,
        "api_called": True,
    }


# 단독 테스트용
if __name__ == "__main__":
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    term_path = project_root / "data" / "terminology.yaml"

    with open(term_path, encoding="utf-8") as f:
        term = yaml.safe_load(f)

    # 테스트: 임의의 미매칭 항목
    test_items = [
        {"work_type": "숏크리트", "unit": "m3", "file": "test.xlsx",
         "reason": "work_type_not_found: '숏크리트'"},
        {"work_type": "PHC말뚝", "unit": "m", "file": "test.xlsx",
         "reason": "work_type_not_found: 'PHC말뚝'"},
        {"work_type": "프리캐스트 옹벽", "unit": "EA", "file": "test.xlsx",
         "reason": "work_type_not_found: '프리캐스트 옹벽'"},
    ]

    print("🔍 Claude API로 미매칭 항목 매핑 중...")
    result = process_unmatched(test_items, term, term_path)

    print(f"\n총 매핑: {result['total']}개")
    print(f"자동 승인 (≥90%): {len(result['auto_approved'])}개")
    print(f"수동 확인 필요 (<90%): {len(result['needs_review'])}개")
    print(f"사전에 저장: {result['auto_saved_count']}개")

    if result['auto_approved']:
        print("\n[자동 승인]")
        for m in result['auto_approved']:
            print(f"  ✅ '{m['original']}' → {m['standard_name']} ({m['category']}) "
                  f"신뢰도={m['confidence']} | {m['reasoning']}")

    if result['needs_review']:
        print("\n[수동 확인 필요]")
        for m in result['needs_review']:
            print(f"  ⚠️ '{m['original']}' → {m['standard_name']} ({m['category']}) "
                  f"신뢰도={m['confidence']} | {m['reasoning']}")