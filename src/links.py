"""국가법령정보센터 조문 링크.

한글 주소 https://www.law.go.kr/법령/{법령명}/{제N조} 형식. 법령명은 띄어쓰기를 빼도 열린다 (2026-11-20 확인).
링크는 항상 '현행' 조문을 연다. 수집한 시행일과 다를 수 있어서 화면에 시행일을 함께 보여 준다.
"""

from urllib.parse import quote


def law_url(law: str, article: str | None = None) -> str:
    path = law.replace(" ", "")
    if article:
        path += "/" + article
    return "https://www.law.go.kr/법령/" + quote(path)
