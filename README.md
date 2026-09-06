# dunnflow - Autonomous Revenue Recovery & Compliance Engine
**Track 03: Autonomous Financial Workflows & Compliance**


An agentic financial intelligence engine designed to intercept failed subscription payments, automate recovery routing, and prevent revenue churn—all bounded by zero-trust regulatory constraints and cryptographic auditability.

---

## 📌 Introduction

Subscription businesses lose up to 15% of recurring MRR due to silent payment failures, gateway timeouts, and expired cards. Traditional billing systems rely on static, blind retries that often trigger rate limits or higher failure rates.

**dunnflow** replaces blind retry systems with an intelligent, multi-agent orchestration layer. It dynamically classifies payment failure codes (e.g., transient gateway errors vs. hard issuer declines), runs deterministic policy checks, and determines optimal recovery actions (retry schedules, credit-cycle deferrals, or human escalation). Crucially, **dunnflow** enforces strict mathematical safety guardrails through a hash-linked cryptographic ledger—ensuring no non-deterministic model ever executes an unverified money-movement action.

---

## 📐 System Architecture

Below is the end-to-end operational architecture illustrating the flow from payment event ingestion to multi-agent reasoning, policy validation, and cryptographic audit execution:


elow is the end-to-end operational architecture illustrating the flow from payment event ingestion to multi-agent reasoning, policy validation, and cryptographic audit execution:


---


<p align="center">
  <img src="./assets/architecture-diagram.png" alt="dunnflow System Architecture" width="100%" />
</p>

> **Note:** Upload your diagram image to `./assets/architecture-diagram.png` in the repository to display it above.

---

## 🛠 Tech Stack

| Domain | Technologies / Frameworks Used |
| :--- | :--- |
| **Frontend Dashboard** | Next.js (React), TypeScript, Tailwind CSS, `shadcn/ui` components |
| **Backend & APIs** | FastAPI (Python), Async Processing, Pydantic data schemas |
| **Agentic AI & Orchestration** | LangGraph, LangChain, SLM/LLM Intent Classifiers |
| **Cryptographic Integrity Layer**| SHA-256 Hash-Linked Audit Chain (Append-only Ledger) |
| **Data & Storage Layer** | Vector Store (Qdrant / ChromaDB), PostgreSQL |
| **Development & Infra** | Docker, Python 3.11+ |



## 🔥 Key Features & Core Components

### 1. Dynamic Case Management & Live Recovery Analytics
* **Real-time Case Tracking:** Categorizes failed transactions into actionable states (`RECOVERED`, `DEFERRED`, `NEEDS_HUMAN`, `ESCALATED`).
* **Run Launcher Simulations:** Allows engineers to execute multi-arm A/B tests (`ARM_DUNNFLOW` vs. Control baseline) across custom sample sizes to quantify recovery uplift.

### 2. Human-in-the-Loop (HITL) Workflow
* Escalates edge cases, recurring errors, or high-value payment disputes to human operators.
* Includes single-click manual **Approve/Reject** controls with mandatory audit reasoning fields to ensure complete operational accountability.

### 3. SHA-256 Hash-Linked Audit Chain
* Every event, rule policy check, state transition, and model output is cryptographically signed and appended into a hash-linked ledger (`sha256(prev_hash || canonical_json(body))`).
* **Zero-LLM Direct Execution Constraint:** Enforces zero unverified actions by mathematically requiring non-deterministic model outputs to pass through validated rule policies before execution.

### 4. Policy Taxonomy Engine
* Classifies incoming failure codes into defined failure domains: *Transient/Gateway, Liquidity, Behavioral, or Issuer*.
* Applies deterministic execution directives like `RETRY_EXPONENTIAL`, `DEFER_TO_CREDIT_CYCLE`, or `HOLD`.

### 5. Diagnostics & Dry-Run Playground
* Interactive payload simulator allowing risk managers to inject synthetic failure scenarios (e.g., gateway timeouts, expired card details).
* Sanitizes sensitive fields, evaluates risk tiers, and predicts policy outcome routes without executing real money movements.



## 🚀 Getting Started

### Prerequisites
* Python 3.11+
* Node.js 18+ & npm/pnpm
* Docker (optional)

### Backend Setup
```bash
# Clone the repository
git clone [https://github.com/your-username/dunnflow.git](https://github.com/your-username/dunnflow.git)
cd dunnflow/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn main:app --reload --port 8000

```

### Frontend Setup
```

# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Start development server
npm run dev

```


[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14.0+-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org)
