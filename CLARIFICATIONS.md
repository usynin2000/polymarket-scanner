# Структура проекта

polymarket-scanner/
├── scanner/
│   ├── domain/         # Доменные модели (Trade, Alert, Signal, etc.)
│   ├── filters/        # Фильтры для отсева сделок
│   ├── signals/        # Детекторы сигналов
│   ├── services/       # Сервисы обогащения данных
│   ├── transport/      # WebSocket и mock-генератор
│   ├── output/         # Вывод алертов
│   ├── config.py       # Конфигурация
│   ├── pipeline.py     # Основной пайплайн обработки
│   └── main.py         # Точка входа
└── pyproject.toml      # Зависимости для uv




1. Transport Layer (transport/)
- PolymarketWebSocket — подключение к реальному WebSocket Polymarket
- MockTradeGenerator — генератор тестовых сделок для разработки

2. Фильтры (filters/)
- MarketFilter — отсекает спорт, крипто, time-based рынки
- SizeFilter — отсекает сделки меньше $2,000
- LPFilter — обнаруживает LP (сбалансированные позиции, паттерны)

3. Детекторы сигналов (signals/)
- FreshWalletDetector — новые кошельки (< 5 сделок)
- SizeAnomalyDetector — аномально большие сделки
- TimingDetector — время сделки (выходные, ночь, перед закрытием рынка)
- OddsMovementDetector — корреляция с движением коэффициентов
- ContrarianDetector — ставки против консенсуса
- ClusteringDetector — кластеризация сделок от разных кошельков

4. Обогащение (services/enrichment.py)
- Загружает профиль кошелька (win rate, история)
- Запускает все детекторы
- Рассчитывает confidence score

5. Вывод (output/console.py)
- Форматированный вывод в консоль с цветами
- Базовый класс для расширения (Telegram, Discord, БД)