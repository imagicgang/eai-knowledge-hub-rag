# EAI Knowledge Hub RAG

## Project Overview

`eai-knowledge-hub-rag` is an enterprise knowledge platform powered by RAG, GraphRAG, and LLMs.

The system ingests heterogeneous enterprise data sources, normalizes and indexes their contents and relationships, and exposes that knowledge through an AI-powered chatbot.

The system should support data sources such as:

- XLSX / CSV
- Draw.io XML diagrams
- YAML / JSON
- Source code and repositories
- Documentation
- Service catalogs
- Architecture diagrams
- EAI diagrams
- Other structured and unstructured enterprise data

The project is **not limited to EAI diagrams or Draw.io**. EAI diagrams are only one type of enterprise knowledge source.

---

# High-Level Architecture

```text
Enterprise Data Sources
│
├── XLSX / CSV
├── Draw.io
├── YAML / JSON
├── Source Code
├── Documents
├── Service Catalogs
└── Other Enterprise Data
        │
        ▼
┌─────────────────────────┐
│   Ingestion / Parsers   │
│       Python AI         │
└────────────┬────────────┘
             │
             ▼
       Normalization
             │
      ┌──────┴──────┐
      ▼             ▼
 Knowledge Graph   Vector
                  Embeddings
      │             │
      └──────┬──────┘
             ▼
       Hybrid Retrieval
        RAG / GraphRAG
             │
             ▼
        AI Agent / LLM
             │
             ▼
          Go API
             │
             ▼
   Next.js + Tailwind
```

The application consists of three major components:

1. **Frontend — Next.js + Tailwind CSS**
2. **Application Backend — Go**
3. **AI / Agent Backend — Python**

Keep responsibilities between these components clearly separated.

---

# Frontend

## Required Stack

The frontend **must use**:

- Next.js
- TypeScript
- Tailwind CSS

Do not replace these technologies with another frontend framework unless explicitly requested.

## Responsibilities

The frontend is responsible for:

- Chat interface
- Suggested questions / follow-up questions
- Conversation UI
- Knowledge source management
- File upload
- Indexing status
- Workspace management
- Knowledge/entity exploration
- Application settings
- LLM/provider configuration UI when applicable

The frontend should communicate with the **Go backend**, not directly with the Python AI service.

```text
Next.js
   │
   ▼
Go Backend
   │
   ▼
Python AI
```

Avoid exposing internal AI services directly to the browser.

---

# Go Application Backend

Go is the **main application backend**.

Do not move general application or business logic into Python simply because the project contains AI functionality.

## Responsibilities

The Go backend should handle:

- HTTP API
- Authentication
- Authorization / RBAC
- Users
- Workspaces
- Data source management
- File metadata
- Conversation management
- Chat history
- Application configuration
- Business logic
- Request validation
- Knowledge source access control
- Communication with the Python AI service
- Streaming AI responses to the frontend where appropriate

Possible API structure:

```text
/api/v1/auth
/api/v1/users
/api/v1/workspaces

/api/v1/data-sources
/api/v1/documents

/api/v1/chat
/api/v1/conversations
/api/v1/conversations/:id/messages

/api/v1/knowledge/entities
/api/v1/knowledge/relationships
```

These routes are examples and may evolve with the application design.

For streaming chatbot responses, prefer an appropriate streaming mechanism such as **Server-Sent Events (SSE)** unless another approach is justified.

Typical request flow:

```text
Browser
   │
   ▼
Next.js
   │
   ▼
Go API
   │
   ▼
Python AI Service
   │
   ├── Retrieval
   ├── Graph traversal
   ├── Agent
   └── LLM
   │
   ▼
Go API
   │
   ▼
Next.js
```

---

# Python AI Service

Python owns the **AI-specific workload**.

## Responsibilities

The Python service should handle:

- AI agents
- RAG
- GraphRAG
- Hybrid retrieval
- Embeddings
- Vector search
- Knowledge graph retrieval
- Data ingestion
- Document parsing
- Data normalization
- Chunk generation
- Semantic entity extraction
- Relationship extraction
- LLM communication
- Suggested question generation
- AI-specific orchestration

General application business logic should remain in Go.

---

# LLM Provider Architecture

The AI system **must not be tightly coupled to OpenAI or any single LLM provider**.

Design the AI layer around provider abstractions.

The architecture should be capable of supporting providers such as:

- OpenAI
- Google Gemini
- Anthropic Claude
- Local LLMs
- OpenAI-compatible APIs
- Enterprise/internal LLM platforms
- Additional providers added in the future

A conceptual provider interface could look like:

```python
class LLMProvider:
    async def generate(self, messages, **options):
        ...

    async def stream(self, messages, **options):
        ...
```

Embedding providers should also be abstracted when appropriate.

For example:

```python
class EmbeddingProvider:
    async def embed(self, texts):
        ...
```

Provider implementations may then include:

```text
providers/
├── openai.py
├── gemini.py
├── anthropic.py
├── local.py
└── enterprise.py
```

The exact implementation may differ, but the architectural principle must remain:

> Core RAG, GraphRAG, retrieval, and agent logic must not depend directly on a specific LLM vendor.

Avoid scattering provider SDK calls throughout the codebase.

Provider-specific code should remain behind a defined adapter/interface.

---

# Enterprise Knowledge Model

Enterprise information should be normalized into meaningful entities and relationships where possible.

Possible entities include:

- System
- Application
- Service
- API
- Database
- Table
- Queue
- Topic
- Repository
- Module
- Function
- Class
- Team
- Document
- Data Source
- Environment
- Infrastructure Component

Possible relationships include:

- CALLS
- DEPENDS_ON
- CONNECTS_TO
- READS_FROM
- WRITES_TO
- PUBLISHES_TO
- CONSUMES_FROM
- OWNED_BY
- PART_OF
- IMPLEMENTS
- CONTAINS
- SENDS_DATA_TO
- RECEIVES_DATA_FROM
- DEPLOYED_TO

Do not assume this list is exhaustive.

The knowledge schema should remain extensible.

---

# Retrieval

The system should eventually support **hybrid retrieval**.

Use vector retrieval for semantic similarity:

```text
User Question
     │
     ▼
Embedding
     │
     ▼
Vector Search
     │
     ▼
Relevant Knowledge
```

Use graph retrieval when relationships matter:

```text
Payment Service
      │
      ├── CALLS ────────► Fraud Service
      │
      ├── WRITES_TO ────► Payment DB
      │
      └── PUBLISHES_TO ─► payment.completed
```

Graph retrieval should make questions such as these possible:

- What systems depend on Payment Service?
- Which applications communicate with SAP?
- What are the upstream dependencies of this service?
- What would be affected if this Kafka topic became unavailable?
- Which repository implements this API?
- What database tables are used by this service?

Vector and graph retrieval may be combined before providing context to the LLM.

---

# Data Ingestion

Design ingestion as an extensible pipeline.

Conceptually:

```text
Source
  │
  ▼
Parser
  │
  ▼
Normalized Document / Entities
  │
  ├──► Chunking
  │       │
  │       ▼
  │    Embeddings
  │       │
  │       ▼
  │   Vector Store
  │
  └──► Entities + Relationships
          │
          ▼
      Knowledge Graph
```

Each data format should have an isolated parser where practical.

For example:

```text
ingestion/
├── drawio/
├── xlsx/
├── csv/
├── yaml/
├── json/
├── code/
└── document/
```

Adding a new source type should not require rewriting the entire ingestion pipeline.

---

# Draw.io / EAI Diagram Ingestion

Draw.io is one supported enterprise data source.

For Draw.io XML, begin with deterministic extraction.

Typical mapping:

```text
mxCell vertex
    ↓
Potential Graph Node

mxCell edge
    ↓
Potential Relationship

source / target
    ↓
Graph Connection

value
    ↓
Label / Description
```

Possible pipeline:

```text
.drawio XML
     │
     ▼
XML Parser
     │
     ▼
Raw mxCell Model
     │
     ▼
Semantic Mapper
     │
     ├──► Entity
     │
     └──► Relationship
```

Do not automatically treat every Draw.io object as an enterprise entity.

Draw.io files may contain:

- Decorative shapes
- Containers
- Swimlanes
- Labels
- Notes
- Icons
- Groups
- Business entities
- Connections

Prefer explicit metadata over AI inference whenever metadata is available.

For example, if a Draw.io element explicitly specifies:

```text
type=application
system=payment
owner=payment-team
protocol=REST
```

use that metadata instead of attempting to infer the entity solely from its visual appearance.

AI-assisted classification may be added later for ambiguous elements.

---

# Source Code Ingestion

Source code should be treated as structured enterprise knowledge rather than plain text whenever practical.

Potential entities include:

- Repository
- Package
- Module
- Class
- Function
- API endpoint
- Database model
- Dependency

Relationships may include:

```text
Repository
   └── CONTAINS → Module

Module
   └── CONTAINS → Function

API Endpoint
   └── IMPLEMENTED_BY → Function

Service
   └── DEPENDS_ON → Package
```

Do not rely exclusively on raw text chunking when deterministic structural information can be extracted from source code.

---

# Embedding Strategy

Do not blindly embed raw source formats such as Draw.io XML.

Prefer converting structured information into meaningful textual representations.

For example:

```text
Entity: Order Service
Type: Backend Service
Owner: Commerce Team

Relationships:
- Receives REST requests from API Gateway
- Publishes order.created to Kafka
- Writes to Order PostgreSQL
- Calls Payment Service
```

This representation may then be embedded for semantic retrieval while the original relationships remain available in the knowledge graph.

---

# Chatbot

The chatbot should answer questions using indexed enterprise knowledge.

It should:

- Retrieve relevant context
- Use graph relationships when useful
- Use semantic/vector retrieval when useful
- Combine multiple knowledge sources
- Cite or identify relevant sources when possible
- Avoid inventing enterprise information that does not exist in retrieved context
- Clearly indicate when information cannot be found
- Generate relevant suggested follow-up questions

Example suggested questions:

```text
What systems depend on this service?

Which repositories implement this application?

What database does this service use?

Show the upstream and downstream dependencies.

Which team owns this component?

What would be affected if this service failed?
```

---

# Suggested Repository Structure

```text
eai-knowledge-hub-rag/
│
├── web/                       # Next.js + Tailwind
│
├── api/                       # Go application backend
│   ├── cmd/
│   └── internal/
│       ├── auth/
│       ├── chat/
│       ├── datasource/
│       ├── knowledge/
│       └── workspace/
│
├── ai/                        # Python AI service
│   ├── agent/
│   ├── ingestion/
│   │   ├── drawio/
│   │   ├── xlsx/
│   │   ├── yaml/
│   │   ├── code/
│   │   └── document/
│   ├── retrieval/
│   ├── graph/
│   ├── embedding/
│   └── providers/
│
├── docs/
├── docker-compose.yml
├── AGENTS.md
└── README.md
```

This structure is a starting point, not an immutable requirement.

Prefer clear boundaries and maintainability over following the example structure exactly.

---

# Engineering Principles

## 1. Start Simple

Build the smallest working end-to-end pipeline first.

For example:

```text
Upload
  ↓
Parse
  ↓
Normalize
  ↓
Index
  ↓
Retrieve
  ↓
LLM
  ↓
Answer
```

Do not introduce unnecessary infrastructure before the basic flow works.

## 2. Prefer Deterministic Parsing

If information can be reliably extracted from:

- XML
- AST
- YAML
- JSON
- XLSX columns
- Explicit metadata

prefer deterministic parsing before asking an LLM to infer it.

Use AI where semantic reasoning actually provides value.

## 3. Keep AI Provider-Agnostic

Never assume OpenAI is the only model provider.

Provider-specific implementations must remain replaceable.

## 4. Separate Application and AI Responsibilities

```text
Go
→ application/business backend

Python
→ AI/RAG/agent/ingestion

Next.js
→ user interface
```

Do not blur these boundaries without a clear architectural reason.

## 5. Design for Extensibility

New:

- Data source formats
- LLM providers
- Embedding providers
- Retrieval strategies
- Graph entity types

should be addable without major rewrites.

## 6. Avoid Premature Complexity

This is initially an experimental project.

Prioritize:

1. Working implementation
2. Clear architecture
3. Testability
4. Extensibility
5. Optimization

Do not prematurely introduce complex distributed architecture, unnecessary microservices, or advanced AI classification unless the current problem requires them.

---

# Initial Development Direction

For the first implementation, prioritize an end-to-end vertical slice:

```text
One Data Source
      ↓
Parser
      ↓
Normalized Knowledge
      ↓
Vector / Graph Index
      ↓
Retriever
      ↓
LLM Provider
      ↓
Go API
      ↓
Next.js Chat
```

Once the basic pipeline works, expand support for additional enterprise data sources and more advanced GraphRAG capabilities.

The long-term goal is a **unified enterprise knowledge hub** capable of answering questions across heterogeneous organizational data while preserving the relationships between systems, applications, code, documents, and infrastructure.