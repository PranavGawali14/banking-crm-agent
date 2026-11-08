.PHONY: install seed chat ui demo test clean

install:
	pip install -r requirements.txt

seed:
	PYTHONPATH=src python -m crm_agent.data.seed

chat:
	PYTHONPATH=src python -m crm_agent.interfaces.cli --trace

ui:
	streamlit run src/crm_agent/interfaces/streamlit_app.py

demo:
	python scripts/run_demo.py --trace --save

test:
	python -m pytest

clean:
	rm -rf data/*.db models outputs .sessions .pytest_cache
