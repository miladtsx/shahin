.PHONY: seed-db web

seed-db:
	PYTHONPATH=. python -m scripts.seed_db.seed

web:
	@echo "Setting up frontend venv if missing..."
	@test -d ./frontend/venv || python3 -m venv ./frontend/venv
	@echo "Installing requirements..."
	@./frontend/venv/bin/pip install --upgrade pip
	@./frontend/venv/bin/pip install -r ./frontend/requirements.txt
	@echo "Running app..."
	@bash -c '\
		. ./frontend/venv/bin/activate && \
		python ./frontend/app.py --debug=True & \
		PID=$$!; \
		sleep 2; \
		python -c "import webbrowser; webbrowser.open(\"http://localhost:5000\")"; \
		trap "echo Killing server...; kill $$PID; exit 0" INT; \
		wait $$PID \
	'