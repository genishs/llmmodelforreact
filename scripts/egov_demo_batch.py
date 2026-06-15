# -*- coding: utf-8 -*-
"""egovGeoportal 데모 배치: 모델 1회 로드로 생성/리뷰/변환 여러 건 실행."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from model_loader import generate

BASE = r"C:\Users\user\Documents\workspace\twinspace_platform\egovGeoportal"


def rd(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


JOBS = [
    ("[생성] 지도 레이어 토글 훅",
     "지도 레이어를 표시/숨김 토글하는 useLayerToggle 커스텀 훅을 TypeScript로 만들어줘.", "", 170),
    ("[생성] useFetch 로딩상태 훅",
     "API 데이터를 가져오면서 로딩/에러/데이터 상태를 관리하는 useFetch 훅을 TypeScript로 만들어줘.", "", 200),
    ("[생성] CheckboxGroup 컴포넌트",
     "여러 옵션을 선택하는 CheckboxGroup 컴포넌트를 TypeScript로 만들어줘.", "", 200),
    ("[리뷰] EgovRadioButtonGroup.jsx",
     "다음 React 컴포넌트를 검토하고 개선점을 제안해줘.",
     rd(r"src\components\EgovRadioButtonGroup.jsx"), 180),
    ("[TS변환] EgovImageGallery.jsx",
     "다음 JavaScript React 코드를 TypeScript로 변환해줘.",
     rd(r"src\components\EgovImageGallery.jsx"), 200),
    ("[리뷰] EgovError.jsx",
     "다음 React 컴포넌트를 검토하고 개선점을 제안해줘.",
     rd(r"src\components\EgovError.jsx"), 180),
]

for title, instr, code, mx in JOBS:
    r = generate(instr, input_text=code, max_new_tokens=mx)
    print("\n" + "=" * 70 + f"\n## {title}\n" + "-" * 70)
    print(r)
