# ML Experiment Hub - DGX Spark convenience targets

.PHONY: deploy reset-db logs status health

deploy:
	./scripts/deploy.sh

reset-db:
	./scripts/reset-db.sh

logs:
	docker compose logs backend --tail 50 -f

status:
	docker compose ps
	@echo ""
	@curl -s http://localhost:3000/api/projects | python3 -m json.tool 2>/dev/null || echo "(backend not responding)"

health:
	@curl -sf http://localhost:8002/api/system/health | python3 -m json.tool 2>/dev/null || echo "Backend unhealthy"
