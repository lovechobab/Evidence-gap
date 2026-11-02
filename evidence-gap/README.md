# 🔬 Evidence Gap

건강 주장의 **말의 세기(주장 강도)** 와 **실제 연구 근거의 세기(근거 강도)** 사이의 차이를 보여주는 AI 앱.

> "커피를 마시면 치매가 **예방된다**" → 주장 강도 4/5 (인과 단정)
> 실제 근거: 관찰연구 메타분석 (연관성만 확인) → 근거 강도 3.5/5
> **Evidence Gap 37% · 약간 과장**

## 동작 흐름

```
입력 문장
  │ ① LLM: 원인/결과, 과장 표현, 주장 강도(1~5), 영어 PubMed 검색식
  ▼
PubMed E-utilities (esearch → efetch)        ← 실제 논문만 사용
  │ ② 규칙 기반: 연구 설계 → 근거 수준 (메타분석 5 … 동물실험 1)
  │ ③ LLM: 각 초록이 주장을 지지/반박/무관한지 판정
  ▼
Gap 점수 계산 + ④ LLM: 근거에 맞게 고친 문장 제안
```

AI는 **검색된 초록을 읽고 판정만** 합니다. 논문을 새로 만들어내지 않습니다.

## 폴더 구조

```
evidence-gap/
├── app.py                 # Streamlit UI
├── core/
│   ├── llm.py             # Claude / OpenAI 공급자 전환
│   ├── claim.py           # 주장 분석 · 지지/반박 판정 · 문장 교정 (프롬프트 포함)
│   ├── pubmed.py          # PubMed 검색·파싱
│   ├── evidence.py        # 연구 설계 → 근거 수준 분류 (규칙 기반)
│   └── scoring.py         # Gap 점수 공식
├── data/examples.json     # 시연용 예시 문장 + 검증된 검색식
├── requirements.txt
└── .streamlit/secrets.toml.example
```

## 실행

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # API 키 입력
streamlit run app.py
```

키 없이 실행하면 **데모 모드**로 동작합니다 (예시 문장만, 규칙 기반 판정).

## Streamlit Cloud 배포

1. 이 폴더를 GitHub 저장소에 push (`secrets.toml`은 `.gitignore`로 제외됨)
2. share.streamlit.io → New app → 저장소/`app.py` 선택
3. Advanced settings → Secrets에 `secrets.toml` 내용 붙여넣기

## 역할 분담 예시

| 담당 | 파일 | 할 일 |
|---|---|---|
| 프롬프트 | `core/claim.py` | 강도 판정 일관성 튜닝, 예시 20개로 테스트 |
| 데이터 | `core/pubmed.py`, `data/examples.json` | 검색식 품질 개선, 시연 예시 검증 |
| 알고리즘 | `core/evidence.py`, `core/scoring.py` | 분류 규칙·점수 공식 근거 정리 |
| UI/발표 | `app.py` | 화면 다듬기, 시연 시나리오 |

## 다음 단계 아이디어

- 기사 URL 입력 → 본문에서 주장 문장 자동 추출
- 지역 어르신 대상 "카톡으로 받은 건강정보 확인" 모드 (큰 글씨, 음성 입력)
- 결과 카드 이미지로 저장·공유
