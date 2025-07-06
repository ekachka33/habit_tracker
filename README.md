# Habit Tracker - Приложение для отслеживания привычек

## Описание проекта

Проект "Habit Tracker" - это веб-приложение для управления привычками, позволяющее пользователям создавать, отслеживать и получать напоминания о своих привычках. Backend реализован на Django Rest Framework, использует PostgreSQL для базы данных, Redis для кэширования и брокера Celery, а Nginx выступает в качестве прокси-сервера.

## Ссылки

* **Репозиторий GitHub:** `https://github.com/ekachka33/habit_tracker`
* **Развернутое приложение (Production):** http://158.160.169.118

## Локальный запуск проекта (Docker Compose)

Для запуска проекта локально вам понадобится установленный Docker и Docker Compose.

1.  **Клонируйте репозиторий:**
    ```bash
    git clone [https://github.com/ekachka33/habit_tracker](https://github.com/ekachka33/habit_tracker)
    cd habit_tracker
    ```

2.  **Создайте файл `.env`:**
    Скопируйте файл `.env.example` в `.env` и заполните необходимые переменные окружения.
    ```bash
    cp .env.example .env
    ```
    *Пример содержимого .env (замените значения на свои):*
    ```
    SECRET_KEY='your_very_secret_key_here'
    POSTGRES_DB=habit_db
    POSTGRES_USER=habit_user
    POSTGRES_PASSWORD=strong_password
    POSTGRES_HOST=db
    POSTGRES_PORT=5432
    CELERY_BROKER_URL=redis://redis:6379/0
    CELERY_RESULT_BACKEND=redis://redis:6379/0
    DEBUG=True
    ALLOWED_HOSTS=127.0.0.1,localhost,158.160.169.118
    ```

3.  **Запустите все сервисы с помощью Docker Compose:**
    ```bash
    docker compose up -d --build
    ```

4.  **Выполните миграции базы данных:**
    ```bash
    docker compose exec backend python manage.py migrate --noinput
    ```

5.  **Создайте суперпользователя (для доступа к админ-панели):**
    ```bash
    docker compose exec backend python manage.py createsuperuser
    ```

6.  **Соберите статические файлы:**
    ```bash
    docker compose exec backend python manage.py collectstatic --noinput
    ```

7.  **Приложение будет доступно по адресу:**
    * Backend API (через Nginx): `http://127.0.0.1/`
    * Админ-панель Django: `http://127.0.0.1/admin/`

## Деплой на удаленный сервер (GitHub Actions CI/CD)

Проект настроен на автоматический деплой на удаленный сервер (Yandex Cloud VM) при пуше в ветку `develop`.

### Настройка удаленного сервера (Yandex Cloud VM)

1.  **Создайте виртуальную машину:**
    В Yandex Cloud создайте VM (например, на Ubuntu 20.04 LTS или 22.04 LTS). При создании VM настройте SSH-доступ, добавив свой публичный SSH-ключ. Убедитесь, что для VM открыты порты: `22` (SSH), `80` (HTTP) в правилах сетевой безопасности (Security Groups) Yandex Cloud.

2.  **Установите Docker и Docker Compose на VM:**
    Подключитесь к VM по SSH и выполните следующие команды:
    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install ca-certificates curl gnupg -y
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL [https://download.docker.com/linux/ubuntu/gpg](https://download.docker.com/linux/ubuntu/gpg) | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] [https://download.docker.com/linux/ubuntu](https://download.docker.com/linux/ubuntu) \
      "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt update
    sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
    sudo usermod -aG docker ${USER}
    newgrp docker
    docker run hello-world
    docker compose version
    ```

3.  **Создайте целевую директорию на сервере:**
    Скрипт деплоя ожидает, что проект будет клонирован в `/home/ubuntu/habit_tracker_project`. Директория будет создана автоматически, но если вы хотите другую, обновите `SSH_TARGET_DIR` в GitHub Actions.

### Настройка GitHub Actions

1.  **Добавьте SSH-ключ в GitHub Secrets:**
    Перейдите в настройки репозитория на GitHub: `Settings` -> `Secrets and variables` -> `Actions`. Нажмите `New repository secret`.
    * `Name`: `SSH_PRIVATE_KEY`
    * `Secret`: Вставьте сюда полное содержимое вашего приватного SSH-ключа (например, из файла `~/.ssh/id_ed25519` или вашего `.pem` файла).

2.  **Добавьте переменные сервера в GitHub Secrets:**
    * `Name`: `SSH_HOST` , `Secret`: `158.160.169.118`
    * `Name`: `SSH_USERNAME` , `Secret`: `ubuntu`

3.  **Файл GitHub Actions Workflow (`.github/workflows/main.yml`):**
    Убедитесь, что ваш файл workflow находится в директории `.github/workflows/` вашего репозитория и содержит следующую логику:

    ```yaml
    name: CI/CD Pipeline

    on:
      push:
        branches:
          - develop # Ветка для деплоя

    jobs:
      build-and-test:
        runs-on: ubuntu-latest
        steps:
          - name: Checkout code
            uses: actions/checkout@v4

          - name: Set up Python
            uses: actions/setup-python@v5
            with:
              python-version: '3.11'

          - name: Install dependencies
            run: |
              python -m pip install --upgrade pip
              pip install -r requirements.txt

          - name: Run Linting (Flake8)
            run: |
              pip install flake8
              flake8 .

          - name: Run Tests
            env:
              SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
              DEBUG: False
            run: |
              python manage.py test

          - name: Check Docker Build
            run: docker compose build --no-cache

      deploy:
        needs: build-and-test
        runs-on: ubuntu-latest
        env:
          SERVER_IP: ${{ secrets.SSH_HOST }}
          SERVER_USER: ${{ secrets.SSH_USERNAME }}
          SSH_TARGET_DIR: /home/ubuntu/habit_tracker_project
        steps:
          - name: Checkout code
            uses: actions/checkout@v4

          - name: Set up SSH
            uses: webfactory/ssh-agent@v0.9.0
            with:
              ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}

          - name: Deploy with Rsync and Docker Compose
            run: |
              echo "Ensuring project directory exists and has correct permissions on server..."
              ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} "mkdir -p ${SSH_TARGET_DIR} && sudo chown -R ${SERVER_USER}:${SERVER_USER} ${SSH_TARGET_DIR}"

              echo "Synchronizing project files to server using rsync..."
              rsync -avz --exclude '.git' --exclude 'node_modules' --exclude '__pycache__' --exclude '.env' \
                    ./ ${SERVER_USER}@${SERVER_IP}:${SSH_TARGET_DIR}/

              echo "Executing Docker Compose commands on the remote server..."
              ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << 'EOF'
                cd "${SSH_TARGET_DIR}"

                echo "Stopping and removing old containers..."
                docker compose down --remove-orphans

                echo "Pulling latest changes from Git..."
                git pull origin develop

                echo "Building Docker images..."
                docker compose build --no-cache

                echo "Starting containers..."
                docker compose up -d

                echo "Running database migrations..."
                docker compose exec backend python manage.py migrate --noinput

                echo "Collecting static files..."
                docker compose exec backend python manage.py collectstatic --noinput --clear

                echo "Deployment finished successfully!"
              EOF
    ```