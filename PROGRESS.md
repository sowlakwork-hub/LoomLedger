
# LoomLedger — Project Progress

## Week 1 — Project Foundation

Completed the initial LoomLedger project setup using the Examate starter repository.

- Created the public GitHub repository.
- Defined the product, target user, problem statement and signature feature.
- Prepared the README and documented 10 real analyst questions.
- Implemented and tested the FastAPI health endpoint.
- Collected annual reports from five Tamil Nadu textile companies.
- Established the initial project structure and dataset documentation.

**Status: Completed**

## Week 2 — Backend and Database Foundation

Completed the core backend development and containerized database setup.

- Developed the FastAPI backend and application structure.
- Integrated the Gemini API for AI-powered responses.
- Implemented structured API request and response handling.
- Configured Docker and Docker Compose.
- Set up PostgreSQL with pgvector for vector storage.
- Integrated database connectivity and application configuration.

**Status: Completed**

## Week 3 — Document Intelligence and RAG

Completed the document ingestion and retrieval pipeline.

- Developed a PDF parser that preserves page numbers and headings.
- Implemented OCR for scanned annual-report pages.
- Built document chunking and embedding generation.
- Stored 765 document chunks with embeddings in PostgreSQL/pgvector.
- Processed 665 unique embedded pages across three annual reports.
- Implemented semantic retrieval for document-based questions.
- Integrated the POST /ask endpoint with page-level citations.
- Created and completed the 10-question evaluation report in `docs/EVAL_v0.md`.
- Achieved an evaluation score of 91/100.

**Status: Completed**

## Overall Progress

Weeks 1, 2 and 3 development milestones have been completed. The project now has a working document ingestion, embedding, retrieval and question-answering pipeline.

The next phase focuses on GitHub milestone publishing, cloud deployment and making LoomLedger accessible through a public live link.


## Daily log

| Date | What I did today | Commit |
|---|---|---|
| 07 Nov 2026 | Completed Weeks 1–3 development, including backend integration, document ingestion, OCR, chunking, embeddings, pgvector storage, semantic retrieval, page-level citations and evaluation. | Complete Weeks 1–3 |
