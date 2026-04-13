.PHONY: test test-v test-cov lint

# Запустить все тесты
test:
	docker-compose exec api pytest

# Тесты с подробным выводом
test-v:
	docker-compose exec api pytest -v

# Тесты с покрытием
test-cov:
	docker-compose exec api pytest --cov=. --cov-report=term-missing

# Только юнит тесты (без API)
test-unit:
	docker-compose exec api pytest tests/test_parser.py -v

# Только API тесты
test-api:
	docker-compose exec api pytest tests/test_companies.py tests/test_persons.py -v
