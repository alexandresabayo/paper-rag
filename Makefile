SHELL := /bin/bash
CONDA_ACTIVATE := source ~/conda/etc/profile.d/conda.sh && conda activate paper-rag reset-db

.PHONY: install dev-backend dev-worker dev-frontend dev test clean 

install:
	source ~/conda/etc/profile.d/conda.sh && conda create -n paper-rag python=3.12 -y
	$(CONDA_ACTIVATE) && cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev-backend:
	$(CONDA_ACTIVATE) && cd backend && uvicorn app.main:app --reload

# Must stay at exactly one worker -- see app/pipeline/huey_app.py
dev-worker:
	$(CONDA_ACTIVATE) && cd backend && huey_consumer app.pipeline.tasks.huey -w 1

dev-frontend:
	cd frontend && npm run dev

dev:
	@$(MAKE) -j3 dev-backend dev-worker dev-frontend

test:
	$(CONDA_ACTIVATE) && cd backend && python -m pytest -q

clean:
	find . -name __pycache__ -o -name .pytest_cache | xargs rm -rf

reset-db:
	rm -f backend/storage/paper_rag.sqlite3 backend/storage/paper_rag.sqlite3-wal backend/storage/paper_rag.sqlite3-shm