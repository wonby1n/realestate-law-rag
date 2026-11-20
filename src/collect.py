"""1차 법령 원문 수집.

법령 이름으로 검색 → 이름이 정확히 같은 결과의 법령일련번호(MST)로 본문 조회
→ data/raw/{법령명}_{시행일자}.json 으로 원문 그대로 저장.
같은 법령·시행일자 파일이 이미 있으면 다시 받지 않는다(개정되면 시행일자가 바뀌어 새 파일로 저장).

사용법: python3 src/collect.py
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BASE = "https://www.law.go.kr/DRF"

LAWS_STAGE1 = [
    "주택임대차보호법",
    "주택임대차보호법 시행령",
    "민간임대주택에 관한 특별법",
    "민간임대주택에 관한 특별법 시행령",
    "공인중개사법",
    "공인중개사법 시행령",
    "공인중개사법 시행규칙",
]


def load_oc() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OC="):
            return line.split("=", 1)[1].strip()
    sys.exit(".env에 OC=... 를 넣어 주세요")


def get_json(endpoint: str, retries: int = 3, **params) -> dict:
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as res:
                body = res.read().decode("utf-8")
            return json.loads(body)
        except json.JSONDecodeError:
            sys.exit(f"JSON이 아닌 응답 (키·IP 확인):\n{body[:300]}")
        except OSError as e:  # 네트워크 오류만 재시도
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  재시도 {attempt + 1}/{retries - 1} ({e}), {wait}초 대기")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def find_exact(oc: str, name: str) -> dict:
    found = get_json("lawSearch.do", OC=oc, target="law", type="JSON", query=name)
    laws = found.get("LawSearch", {}).get("law", [])
    if isinstance(laws, dict):
        laws = [laws]
    exact = [law for law in laws if law.get("법령명한글") == name]
    if not exact:
        sys.exit(f"'{name}'와 이름이 정확히 같은 법령 없음: {[l.get('법령명한글') for l in laws]}")
    return exact[0]


def main() -> None:
    oc = load_oc()
    RAW.mkdir(parents=True, exist_ok=True)
    for name in LAWS_STAGE1:
        meta = find_exact(oc, name)
        out = RAW / f"{name}_{meta['시행일자']}.json"
        if out.exists():
            print(f"건너뜀 (이미 있음): {out.name}")
            continue
        detail = get_json("lawService.do", OC=oc, target="law", type="JSON", MST=meta["법령일련번호"])
        out.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
        n = len(detail.get("법령", {}).get("조문", {}).get("조문단위", []))
        print(f"저장: {out.name} (MST {meta['법령일련번호']}, 조문단위 {n}개)")
        time.sleep(0.5)  # 공용 API 예의상 간격


if __name__ == "__main__":
    main()
