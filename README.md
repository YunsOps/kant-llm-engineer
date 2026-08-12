# Private LLM Infra Engineer

목표 **LLM 엔지니어**
<br>기업 데이터로 자체 LLM을 구축하고 RAG·GPU 서빙까지 운영하는 엔지니어


![Role](https://img.shields.io/badge/목표-LLM_엔지니어-4B5563?style=flat-square)
![Hours](https://img.shields.io/badge/1%2C516h-4_STEP-4B5563?style=flat-square)
![Projects](https://img.shields.io/badge/실무_프로젝트-5회-4B5563?style=flat-square)
![Program](https://img.shields.io/badge/TEAM_SPARTA_×_고용노동부-4B5563?style=flat-square)

<br>

## 과정 개요

| STEP | 주제 | 시간 | 기간 |
|:--:|:--|:--:|:--:|
| **1** | LLM 개발 기본기 완성 | 200h | 26.08–09 |
| **2** | 오픈소스 LLM & RAG 서비스 구현 | 336h | 26.09–11 |
| **3** | Private LLM 통합 서비스 런칭 | 520h | 26.12–27.02 |
| **4** | 기업 실무 프로젝트 · 취업 | 460h | 27.03–05 |
<br>

## 커리큘럼

### STEP 1 · LLM 개발 기본기 완성 &nbsp;`200h` · 26.08–09

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)

- **온보딩 & 학습 환경 세팅**
  - 개강 OT 및 과정 운영 방식 안내
  - GitHub, 학습 도구, 협업 채널 세팅
- **개발 협업 & 생성형 AI 이해**
  - Git 저장소 관리, 브랜치, PR 협업 흐름
  - 생성형 AI 개념 이해
  - AI 윤리, 데이터 프라이버시, AI 규제 이해
- **선형대수 & 수학 기초**
  - 벡터·행렬 연산
  - 내적과 코사인 유사도
  - 고유값·특이값 분해
  - PCA 이해
  - NumPy 기반 구현
- **머신러닝 심화**
  - 앙상블 기법
  - 편향-분산 트레이드오프
  - 피처 엔지니어링
  - 정규화 / 교차 검증
  - 하이퍼파라미터 튜닝
- **딥러닝 모델 이해 및 활용**
  - 퍼셉트론
  - CNN, RNN, LSTM
  - Transformer 아키텍처
  - PyTorch 기반 학습 루프 구축
  - 데이터 파이프라인 구축

### STEP 2 · 오픈소스 LLM & RAG 서비스 구현 &nbsp;`336h` · 26.09–11

![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white)
![HuggingFace](https://img.shields.io/badge/Hugging_Face-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)

- **딥러닝 실전 & 프롬프트 엔지니어링**
  - Attention, Transformer 이해
  - PPO, RLHF 개념 이해
  - Structured Output / JSON Mode
  - Reasoning 모델 프롬프팅
  - System Prompt 설계
- **▶ Project 1 · 오픈소스 LLM 활용** `개인`
  - Ollama 기반 로컬 LLM 실행
  - Hugging Face Transformers 활용
  - Sentence Transformers 활용
  - 로컬 LLM과 클라우드 API 비교
- **데이터 수집 & API 서버 구축**
  - 공공데이터·소셜미디어 API 활용
  - Playwright 기반 동적 크롤링
  - FastAPI 및 Pydantic 활용
  - 비동기 처리 기반 로컬 LLM API 구현
- **LangChain**
  - LangChain 아키텍처와 LCEL 이해
  - 프롬프트 템플릿 활용
  - 출력 파서 / Memory / Callbacks
  - 스트리밍 활용
- **▶ Project 2 · 딥러닝 기초 프로젝트** `개인`
  - PyTorch 기반 모델 설계 및 구현
  - 데이터 전처리·학습·평가 파이프라인 경험
  - 팀 주제 택1: 의료 이미지 분류(CNN) · 텍스트 분류(Transformer) · Atari 게임 AI(강화학습)
- **RAG 기초/심화**
  - 청킹 전략
  - 문서 임베딩
  - Vector DB(ChromaDB, Qdrant) 활용
  - Hybrid Search / Re-ranking / Query Transformation
  - GraphRAG / 멀티모달 RAG / CAG 이해
  - RAGAS 평가 이해
- **Context Engineering**
  - Context 구조 설계 패턴 이해
  - Memory 시스템(Mem0)
  - Skills 패턴
  - Context 압축 및 최적화
- **LLMOps**
  - LangSmith 기반 트레이싱
  - 프롬프트 버전 관리
  - LLM 모니터링 / 평가 체계 구축
  - 가드레일 구현 / Prompt Injection 대응
  - OWASP LLM Top 10 이해
  - Red Teaming 개념 이해
- **LLM Fine-tuning**
  - Fine-tuning 데이터셋 준비
  - Synthetic Data 생성
  - SFT / LoRA / QLoRA / DPO
  - Hugging Face TRL 활용
- **▶ Project 3 · RAG 기반 Q&A 서비스** `팀`
  - 데이터 수집부터 고급 RAG 파이프라인 구축
  - Gradio 데모 구현
  - 고급 RAG 택1: Agentic · Self-RAG · Corrective · 멀티모달
  - 팀 주제 택1: 고객 상담 · 의료·건강 · 법률 상담 · 요리 레시피
  - Context Engineering·LLMOps 적용

### STEP 3 · Private LLM 통합 서비스 런칭 &nbsp;`520h` · 26.12–27.02

![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![GKE](https://img.shields.io/badge/GKE-4285F4?style=flat-square&logo=googlecloud&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white)

- **AI Agent**
  - Tool Calling 기반 Agent 구현
  - LangGraph 기반 Agent 구현
  - ReAct 추론 패턴
  - Plan-and-Execute 패턴
  - Reflection 패턴 / HITL 적용
  - MCP 서버 구축 / 외부 시스템 연동
  - Multi-Agent 시스템 설계
  - Agent 평가 및 디버깅
- **▶ Project 4 · 도메인 특화 Agent** `팀`
  - 도메인 특화 Fine-tuning(LoRA, QLoRA)
  - LangGraph 워크플로우 구현
  - Gradio 데모 UI 구현
  - 팀 주제 택1: 리서치 · 코드 생성·리뷰 · 멀티턴 상담 에이전트
- **클라우드 인프라**
  - On-prem / Cloud / Hybrid 비교
  - GCP 핵심 서비스 (Compute Engine, Cloud Run, GKE)
  - Docker 및 Kubernetes 기반 배포
  - Terraform 구성 관리
  - Ansible 구성 관리
  - GPU 인프라 구성
- **Private LLM 서빙**
  - LLM 서빙 아키텍처 이해
  - vLLM 기반 고성능 서빙
  - GPTQ, AWQ, GGUF 양자화
  - GKE 배포
  - GitHub Actions 기반 CI/CD
  - ArgoCD 기반 CI/CD
  - 모니터링 및 스케일링
- **▶ Project 5 · Private LLM 통합 서비스 런칭** `팀`
  - Fine-tuning 모델 + RAG + AI Agent 통합 서비스 개발
  - MCP 기반 외부 시스템 연동
  - GKE 배포 / CI/CD 파이프라인 구축
  - 팀 주제 택1: 기업 내부 지식관리 · 고객 응대 자동화 · 리서치 어시스턴트

### STEP 4 · 기업 실무 프로젝트 · 취업 &nbsp;`460h` · 27.03–05

- **기업 연계 AI 경진대회**
  - 기업 실제 데이터 기반 산업 문제 해결
  - AI 기반 분석·설계·구현
  - 고밀도 몰입형 프로젝트 수행
- **기업 초청 발표회**
  - 참여 기업 대상 최종 발표
  - 기업 피드백 및 질의응답
  - 우수 프로젝트 선정
- **취업지원**
  - 이력서 및 포트폴리오 정리
  - 커리어 모듈 운영 / 구직 활동 관리
  - 면접 대비 / 실무 과제형 채용 대비
  - 기업 연계 프로그램 운영
- **수료식**
  - 수료생 성과 공유 / 우수 훈련생 시상
  - 취업 로드맵 안내 / 네트워킹

---

## 프로젝트

과정 중 5개의 실무 프로젝트를 진행하며, 각 프로젝트는 **별도 저장소**로 관리합니다. (완료 시 링크 연결)

| # | 프로젝트 | 유형 | STEP | 저장소 |
|:--:|:--|:--:|:--:|:--:|
| 1 | 오픈소스 LLM 활용 | 개인 | 2 | 준비 중 |
| 2 | 딥러닝 기초 프로젝트 | 개인 | 2 | 준비 중 |
| 3 | RAG 기반 Q&A 서비스 | 팀 | 2 | 준비 중 |
| 4 | Fine-tuning 도메인 특화 Agent | 팀 | 3 | 준비 중 |
| 5 | Private LLM 통합 서비스 런칭 | 팀 | 3 | 준비 중 |