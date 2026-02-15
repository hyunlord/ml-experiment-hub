# ML Experiment Hub

.PHONY: up down rebuild reset logs status health

up:
	docker compose up -d --build

down:
	docker compose down

rebuild:
	docker compose up -d --build --force-recreate

reset:
	docker compose down -v
	docker compose up -d --build

logs:
	docker compose logs backend --tail 50 -f

status:
	docker compose ps
	@echo ""
	@curl -s http://localhost:3000/api/projects | python3 -m json.tool 2>/dev/null || echo "(backend not responding)"

health:
	@curl -sf http://localhost:8002/api/system/health | python3 -m json.tool 2>/dev/null || echo "Backend unhealthy"
