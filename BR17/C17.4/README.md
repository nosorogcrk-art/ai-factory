# Skill Tester (C17.4)

Service for automated testing of skills in isolated environment.

## API
- `GET /health` – health check
- `GET /status` – status endpoint (specification)
- `POST /test/{skill_id}` – start a test
- `GET /results/{skill_id}` – get latest test results
- `POST /test/all` – test all skills (stub)

## Environment Variables
- `PORT` – service port (default 8091)

## Run
```bash
docker-compose up -d skill-tester