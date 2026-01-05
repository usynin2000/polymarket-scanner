# Деплой Polymarket Scanner через Docker

## Быстрый старт

### 1. Создайте `.env` файл

```bash
# Скопируйте шаблон или создайте файл вручную
cat > .env << 'EOF'
# Логирование
SCANNER_LOG_LEVEL=INFO

# Минимальный размер сделки в USD
SCANNER_MIN_TRADE_SIZE_USD=2000

# Telegram уведомления (опционально)
SCANNER_TELEGRAM_BOT_TOKEN=
SCANNER_TELEGRAM_CHAT_ID=
SCANNER_TELEGRAM_ENABLED=false

# Приватный ключ для аутентифицированного доступа к CLOB API (опционально)
# ВНИМАНИЕ: Держите в секрете! Никогда не коммитьте в git!
SCANNER_PRIVATE_KEY=
EOF
```

### 2. Соберите и запустите

```bash
# Собрать образ
docker compose build

# Запустить в фоне (live режим)
docker compose up -d

# Посмотреть логи
docker compose logs -f scanner
```

## Режимы работы

### Live режим (реальные данные с Polymarket)
```bash
docker compose up -d
```

### Mock режим (тестовые данные)
```bash
docker compose --profile dev up scanner-mock
```

## Управление контейнером

```bash
# Статус
docker compose ps

# Логи в реальном времени
docker compose logs -f

# Остановить
docker compose down

# Перезапустить
docker compose restart

# Пересобрать и перезапустить (после изменений кода)
docker compose up -d --build
```

## Деплой на сервер

### Вариант 1: Копирование исходников

```bash
# На локальной машине
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    . user@server:/opt/polymarket-scanner/

# На сервере
cd /opt/polymarket-scanner
nano .env  # Настроить переменные
docker compose up -d
```

### Вариант 2: Docker Registry

```bash
# Собрать и запушить образ
docker build -t your-registry/polymarket-scanner:latest .
docker push your-registry/polymarket-scanner:latest

# На сервере - создать docker-compose.yml с образом из реджистри
# и запустить docker compose up -d
```

## Настройка Telegram уведомлений

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота
3. Узнайте свой chat_id через [@userinfobot](https://t.me/userinfobot)
4. Добавьте в `.env`:

```bash
SCANNER_TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
SCANNER_TELEGRAM_CHAT_ID=123456789
SCANNER_TELEGRAM_ENABLED=true
```

## Мониторинг

### Просмотр ресурсов
```bash
docker stats polymarket-scanner
```

### Проверка здоровья
```bash
docker inspect --format='{{.State.Health.Status}}' polymarket-scanner
```

### Автоматический перезапуск при падении
Уже настроен через `restart: unless-stopped` в docker-compose.yml

## Systemd интеграция (опционально)

Для автозапуска при загрузке сервера:

```bash
# Создать systemd сервис
sudo cat > /etc/systemd/system/polymarket-scanner.service << 'EOF'
[Unit]
Description=Polymarket Scanner
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/polymarket-scanner
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Включить автозапуск
sudo systemctl daemon-reload
sudo systemctl enable polymarket-scanner
sudo systemctl start polymarket-scanner
```

## Troubleshooting

### Контейнер не запускается
```bash
# Проверить логи
docker compose logs scanner

# Проверить .env файл
docker compose config
```

### Нет данных / WebSocket не подключается
- Проверьте сетевое подключение
- Убедитесь что SCANNER_PRIVATE_KEY задан для аутентифицированного доступа
- Без private_key используется публичный API с ограничениями

### Telegram не отправляет сообщения
- Проверьте правильность токена и chat_id
- Убедитесь что бот добавлен в чат/группу
- Установите `SCANNER_TELEGRAM_ENABLED=true`

