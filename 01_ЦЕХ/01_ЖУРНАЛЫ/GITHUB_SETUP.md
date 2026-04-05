# Настройка GitHub и CI/CD

**Дата:** 2026-04-05
**Репозиторий:** https://github.com/nosorogcrk-art/ai-factory

## Статус
- [ ] Репозиторий создан (публичный)
- [ ] Код запушен
- [x] GitHub Actions workflow добавлен
- [ ] Первый запуск CI (проверить через Actions вкладку)

## Инструкция для пользователя
1. Создайте репозиторий на GitHub:
   - Название: `ai-factory`
   - Публичный репозиторий
   - Без README, .gitignore или лицензии (так как они уже есть локально)

2. После создания репозитория выполните команды:
   ```bash
   git remote add origin git@github.com:nosorogcrk-art/ai-factory.git
   git branch -M main
   git push -u origin main
   ```

3. Проверьте, что код успешно загружен на GitHub.

4. Перейдите на вкладку Actions в репозитории, чтобы увидеть первый запуск CI/CD pipeline.

## Примечания
- SSH-аутентификация уже настроена и работает (проверено: `ssh -T git@github.com`)
- Git уже инициализирован, создан .gitignore, сделан первый коммит
- GitHub Actions workflow создан в `.github/workflows/ci.yml`
- Ветка `main` будет защищена после настройки правил в настройках репозитория