## Paper RAG 

> **Status:** Not feature-complete: core capabilities are still being perfected.  
> Also currently only runs on the machine it was built on; actively working on that.

<br>
A self-hosted RAG system for a personal corpus of scientific PDFs, plus the pipeline dashboard that ingests them.

Two route areas in one Vue app, one FastAPI backend:

- **Research** (`/research`): the researcher-facing chat/query interface.
- **Ingestion** (`/ingestion`): the single-admin pipeline dashboard.

### Requirements

* **conda** ([download Miniforge3](https://github.com/conda-forge/miniforge)) to create and manage the Python environment.
* **npm** ([download Node.js](https://nodejs.org/en/download)) to install dependencies and run the frontend.
* **A model serving solution**: any OpenAI-compatible endpoint, local (Ollama, vLLM) or remote (Mistral, OpenAI, etc.).
* **A configured GPU** is required to run local models.

### Quick start

To enable real retrieval, copy `.env.example` to `.env`, choose a model provider, and set `MOCK_MODE=false`.

```bash
make install   # Create the Conda environment and install backend/frontend dependencies
make dev       # Start the backend (:8000) and frontend (:5173)
```

The DB is created automatically on first startup at
`backend/storage/paper_rag.sqlite3`. The ingestion worker must stay at
exactly one; see `app/pipeline/huey_app.py` for why. Without this running,
uploaded documents will sit at `status: "pending"` forever, the API
enqueues ingestion, it doesn't do it inline.

Run the test suite:

```bash
make test
```