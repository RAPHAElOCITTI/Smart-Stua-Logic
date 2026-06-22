---
# Rule Name: 04-Agent Behavior & Safety Guardrails

## Context & Scope
This rule applies to all operations performed by AI agents in this repository. It guides modification strategies, validation workflows, environment variables, and safety guardrails.

## Core Directives
1. **Preserve Documentation**: NEVER remove existing comments, annotations, or docstrings unless they are directly invalidated by new changes or explicitly requested. Maintain all header blocks and explanation strings.
2. **Environment Variable Guardrails**:
   - NEVER commit plain API keys, passwords, database credentials, or secret keys to git.
   - Any new configuration variable MUST be documented in `/backend/.env.example` or `/simulator/.env.example`.
   - Local environments must read from `.env` files which must remain listed in `.gitignore`.
3. **Database Migration Verifications**:
   - When updating Django models, always run `python manage.py makemigrations` followed by `python manage.py migrate` inside the container or virtual environment to verify database schema integrity.
   - Verify that migrations do not introduce circular dependencies or break model constraints.
4. **Testing Before Completion**: Always run the Django test suite (`python manage.py test`) before marking a backend task as complete. Ensure no existing tests are broken.
5. **Verify Docker and Container Builds**: When editing dependencies (`requirements.txt`, `package.json`), Dockerfiles, or docker-compose files, verify that the container builds run successfully using `docker compose build`.

---

## Code Examples

### ❌ Bad Pattern
```python
# In backend/monitoring/models.py
# BAD: Removing the comprehensive header documentation during model field updates
- """
- Smart-Stua monitoring app — Django models.
- 
- Matches the ER diagram exactly:
-   Users, SensorNodes, Readings, AlertLogs, Thresholds
- """
# [Code modifications here without restoring the documentation header]
```

### ❌ Bad Pattern
```python
# In backend/monitoring/tasks.py
# BAD: Hardcoding secret credentials directly into the code instead of pulling from settings/os.environ
# and updating .env.example
TWILIO_ACCOUNT_SID = 'AC_PLACEHOLDER_SID_DO_NOT_HARDCODE' # BAD: Hardcoded secret key
TWILIO_AUTH_TOKEN = 'PLACEHOLDER_AUTH_TOKEN_DO_NOT_HARDCODE'   # BAD: Hardcoded secret key
```
