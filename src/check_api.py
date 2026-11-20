"""국가법령정보센터 공개 API 연결 확인.

1) 법령 이름으로 검색해 법령일련번호(MST)·시행일자를 확인하고
2) 첫 번째 결과의 본문을 받아 data/raw/에 그대로 저장한다.

사용법:
    .env 파일에 OC=<신청할 때 쓴 이메일의 @ 앞부분>
    python3 src/check_api.py 주택임대차보호법
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.law.go.kr/DRF"


def load_oc() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("OC="):
                return line.split("=", 1)[1].strip()
    sys.exit(".env에 OC=... 를 넣어 주세요")


def get_json(endpoint: str, **params) -> dict:
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as res:
        body = res.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # 키가 틀리거나 IP 미등록이면 JSON 대신 안내 문구(HTML)가 온다
        sys.exit(f"JSON이 아닌 응답:\n{body[:500]}")


def main() -> None:
    oc = load_oc()
    query = sys.argv[1] if len(sys.argv) > 1 else "주택임대차보호법"

    found = get_json("lawSearch.do", OC=oc, target="law", type="JSON", query=query)
    laws = found.get("LawSearch", {}).get("law", [])
    if isinstance(laws, dict):  # 결과가 1건이면 리스트가 아니라 객체로 온다
        laws = [laws]
    if not laws:
        sys.exit(f"검색 결과 없음: {json.dumps(found, ensure_ascii=False)[:500]}")

    print(f"'{query}' 검색 결과 {len(laws)}건")
    for law in laws:
        print(f"  {law.get('법령명한글')} | MST {law.get('법령일련번호')} | 시행 {law.get('시행일자')} | {law.get('법령구분명')}")

    mst = laws[0]["법령일련번호"]
    detail = get_json("lawService.do", OC=oc, target="law", type="JSON", MST=mst)

    out = ROOT / "data" / "raw" / f"{laws[0]['법령명한글']}_{laws[0]['시행일자']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    articles = detail.get("법령", {}).get("조문", {}).get("조문단위", [])
    print(f"\n본문 저장: {out.relative_to(ROOT)}")
    print(f"최상위 키: {list(detail.keys())}, 조문단위 {len(articles)}개")


if __name__ == "__main__":
    main()
