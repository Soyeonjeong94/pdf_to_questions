# 📚 문제집 PDF → 문제별 이미지 변환기

문제집 PDF 파일을 문제 번호별로 자동 인식하여 개별 이미지로 저장하는 프로그램입니다.

---

## ✨ 주요 기능

- **자동 문제 번호 감지** : 폰트 크기 기반으로 문제 번호를 자동 탐지
- **1단 / 2단 구성 자동 감지** : 문제집 레이아웃을 자동으로 인식
- **샘플 이미지 미리보기** : 변환 전 결과물을 눈으로 확인
- **GUI 인터페이스** : 터미널 없이 누구나 쉽게 사용 가능

---

## 🖥️ 실행 화면

| STEP 1 | STEP 2 | STEP 3 |
|--------|--------|--------|
| PDF 선택 | 1단/2단 확인 | 문제 번호 그룹 선택 |

---

## ⚙️ 설치 방법

### 1. Python 설치
[python.org](https://www.python.org/downloads/) 에서 Python 3.8 이상 설치

### 2. 저장소 클론
```bash
git clone https://github.com/Soyeonjeong94/SYJ_-repo
cd YOUR_REPO_NAME
```

### 3. 가상환경 생성 및 활성화
```bash
# 가상환경 생성
python -m venv .venv

# 활성화 (Windows)
.venv\Scripts\activate

# 활성화 (Mac/Linux)
source .venv/bin/activate
```

### 4. 라이브러리 설치
```bash
pip install -r requirements.txt
```

---

## 🚀 실행 방법

```bash
python pdf_to_questions.py
```

---

## 📋 사용 순서

1. **STEP 1** : 변환할 PDF 파일 선택
2. **STEP 2** : 1단/2단 구성 확인 (자동 감지 후 수동 조정 가능)
3. **STEP 3** : 문제 번호 그룹 선택 (샘플 이미지 3개로 확인)
4. **STEP 4** : 저장 폴더 선택
5. **STEP 5** : 변환 완료 🎉

---

## 📦 사용 라이브러리

| 라이브러리 | 용도 |
|-----------|------|
| [PyMuPDF](https://pymupdf.readthedocs.io/) | PDF 텍스트/이미지 처리 |
| [Pillow](https://pillow.readthedocs.io/) | 이미지 편집 및 저장 |
| tkinter | GUI (Python 기본 내장) |

---

## 📝 참고사항

- 텍스트 기반 PDF에서만 작동합니다 (스캔본 PDF 불가)
- 문제 번호가 숫자로만 구성된 경우에 최적화되어 있습니다
