# Запуск «Графа денег» из чистого клона

Нужны Git, Docker и Docker Compose 2.24 или новее.

```bash
git clone https://github.com/BAITC-Hacks/hack-c4dedb1a-ker1mgo.git
cd hack-c4dedb1a-ker1mgo
docker compose up --build
```

Откройте **http://localhost:8501**. При первом запуске скачиваются зависимости;
затем сервис `pipeline` рассчитывает материалы и завершается с кодом 0,
а `app` запускает интерфейс. Ключ API для этого не нужен.

Начните с «Обзора дела» и откройте первого кандидата. В «Исследовании» можно
искать по полному ID или последним цифрам, выбирать узлы мышью либо Tab + Enter,
менять глубину связей и проверять обоснование роли. Строка в «Приоритетах»
или «Запросах данных» сразу открывает досье. Основной интерфейс — на русском;
технические поля и CSV сохраняют английские названия.

Проверить состояние: `docker compose ps -a`. Остановить: `docker compose down`.
Если порт занят: `MONEYGRAPH_PORT=8502 docker compose up --build`, затем
откройте http://localhost:8502.

## Без Docker

Нужны Python 3.12 и `make`. После клонирования, из корня проекта:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make run
make app
```

Адрес тот же: **http://localhost:8501**. Для проверки разработки:

```bash
pip install -r requirements-dev.txt
make check
```

Ассистент подключается отдельно: см. [настройку ассистента](assistant.md).
Остальные разделы работают офлайн после установки зависимостей.
