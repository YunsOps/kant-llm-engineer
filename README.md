# KANT · LLM Engineer — Learning Portfolio

**임윤성** · 목표 직무 **LLM Engineer**

오픈소스 LLM · RAG · Private LLM 서비스까지 전 과정을 직접 구현하는 9개월 실무 부트캠프의 학습·프로젝트 아카이브입니다.

![Role](https://img.shields.io/badge/목표-LLM_Engineer-4B5563?style=flat-square)
![Hours](https://img.shields.io/badge/1%2C516h-4_STEP-4B5563?style=flat-square)
![Projects](https://img.shields.io/badge/실무_프로젝트-5회-4B5563?style=flat-square)
![Program](https://img.shields.io/badge/TEAM_SPARTA_×_고용노동부-4B5563?style=flat-square)

---

## 핵심 역량

과정을 마칠 때 아래 역량을 코드와 프로젝트로 증명하는 것을 목표로 합니다.

- **모델링** &nbsp; PyTorch 기반 딥러닝 모델 설계·학습·평가
- **파인튜닝** &nbsp; LoRA · QLoRA · DPO 도메인 특화 튜닝
- **RAG** &nbsp; 임베딩 · Vector DB · Advanced RAG 파이프라인 구축
- **서빙·배포** &nbsp; vLLM 고성능 서빙 · 양자화 · GKE 배포 · CI/CD

> 역량 흐름 &nbsp;`PyTorch 모델 설계·학습` → `LoRA·QLoRA 파인튜닝` → `vLLM 서빙·배포`

---

## 커리큘럼

### STEP 1 · LLM 개발 기본기 완성 &nbsp;`200h` · 26.08–09

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)

선형대수·수학(벡터·행렬, 코사인 유사도, SVD, PCA) · 머신러닝(앙상블, 정규화, 교차검증, 튜닝) · 딥러닝(CNN/RNN/LSTM, Transformer, PyTorch 학습 루프·데이터 파이프라인)

### STEP 2 · 오픈소스 LLM & RAG 서비스 구현 &nbsp;`336h` · 26.09–11

![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white)
![HuggingFace](https://img.shields.io/badge/Hugging_Face-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)

로컬 LLM 실행(Ollama·HF Transformers) · 데이터 수집·API(크롤링, FastAPI) · RAG(청킹·임베딩, Vector DB, Hybrid Search, Re-ranking, RAGAS) · LLMOps(LangSmith, 가드레일) · 파인튜닝(SFT·LoRA·QLoRA·DPO)

### STEP 3 · Private LLM 통합 서비스 런칭 &nbsp;`520h` · 26.12–27.02

![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![GKE](https://img.shields.io/badge/GKE-4285F4?style=flat-square&logo=googlecloud&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white)

AI Agent(Tool Calling, LangGraph, ReAct, MCP 서버, Multi-Agent) · 클라우드 인프라(GCP, Docker·K8s, Terraform) · 서빙(vLLM, GPTQ/AWQ/GGUF 양자화, GKE 배포, CI/CD)

### STEP 4 · 기업 실무 프로젝트 · 취업 포트폴리오 &nbsp;`460h` · 27.03–05

기업 연계 AI 경진대회(실제 데이터 기반 산업 문제 해결) · 기업 초청 최종 발표·피드백 · 포트폴리오 및 채용 대비

---

## 프로젝트

| # | 프로젝트 | 유형 | 핵심 스택 |
|:--:|:--|:--:|:--|
| 1 | 오픈소스 LLM 활용 | 개인 | Ollama · HF Transformers · Sentence Transformers |
| 2 | 딥러닝 모델 구현 | 개인 | PyTorch · CNN · Transformer · RL |
| 3 | RAG 기반 Q&A 서비스 | 팀 | RAG · Advanced RAG · Context Eng · LLMOps · Gradio |
| 4 | Fine-tuning 도메인 특화 Agent | 팀 | LoRA · QLoRA · LangGraph · Gradio |
| 5 | Private LLM 통합 서비스 런칭 | 팀 | Private LLM · RAG · AI Agent · GKE · CI/CD · MCP |

<details>
<summary>프로젝트 상세</summary>

<br>

**1 · 오픈소스 LLM 활용** (개인) — 로컬 LLM 실행 + 클라우드 API 비교로 모델 선택 기준 이해, Sentence Transformers 임베딩 적용

**2 · 딥러닝 모델 구현** (개인) — PyTorch 전체 파이프라인(전처리→학습→평가) 구현 · 주제(택1): 의료 이미지 분류(CNN) / 텍스트 분류(Transformer) / 강화학습

**3 · RAG 기반 Q&A 서비스** (팀) — 데이터 수집→고급 RAG 파이프라인→Gradio 데모 · RAG(택1): Agentic / Self-RAG / Corrective / 멀티모달

**4 · Fine-tuning 도메인 특화 Agent** (팀) — 도메인 특화 Fine-tuning + LangGraph 워크플로우 + Gradio UI

**5 · Private LLM 통합 서비스 런칭** (팀) — Fine-tuning + RAG + AI Agent 통합, GKE 배포 & CI/CD, MCP 외부 연동

</details>