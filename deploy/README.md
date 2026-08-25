# Развёртывание Nova Cinema на своём сервере

Считаем, что сервер — Ubuntu 24.04, доступ по SSH под root. Всё ниже
выполняется на сервере, кроме первого шага.

## 1. Имя для сервера

Telegram открывает Mini App только по настоящему HTTPS-адресу с валидным
сертификатом. Значит, нужно имя, указывающее на IP сервера.

**Бесплатно:** [duckdns.org](https://www.duckdns.org) — вход через Google или
GitHub, придумываете имя вида `novacinema.duckdns.org`, вписываете IP сервера.
Сертификат Let's Encrypt на такое имя выпускается нормально.

**Свой домен:** A-запись на IP сервера. Красивее и не зависит от чужого
сервиса.

Проверить, что имя разошлось:

```bash
dig +short novacinema.duckdns.org
```

Должен ответить IP сервера. Пока не отвечает — дальше идти незачем,
сертификат не выпустится.

## 2. Подготовка сервера

```bash
apt update && apt install -y docker.io docker-compose-v2 git ufw
systemctl enable --now docker
```

Firewall: наружу нужны только SSH и веб.

```bash
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

## 3. Код и настройки

```bash
git clone <адрес репозитория> /opt/nova && cd /opt/nova
cp .env.example .env
```

Заполнить `.env`:

| Переменная | Чем заполнить |
|---|---|
| `NOVA_DOMAIN` | имя из шага 1, без `https://` |
| `WEBAPP_URL` | `https://` + то же имя |
| `LETSENCRYPT_EMAIL` | почта для уведомлений об истечении сертификата |
| `BOT_TOKEN` | токен от BotFather |
| `ADMIN_TELEGRAM_IDS` | Telegram ID администраторов через запятую |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` |

`DATABASE_URL` в `.env` не трогаем: compose собирает адрес базы сам из
`POSTGRES_*`.

## 4. Запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Первый запуск занимает несколько минут: собирается фронтенд и образ Python.
Caddy получит сертификат сам, как только имя из шага 1 начнёт указывать на
сервер.

Проверка:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://$NOVA_DOMAIN/api/settings
docker compose -f docker-compose.prod.yml ps
```

## 5. Наполнение

Схема создаётся миграциями при старте API. Каталог пуст — фильмы, расписание,
цену и контакты владелец заводит в админке. Для демонстрации можно засеять:

```bash
docker compose -f docker-compose.prod.yml exec api python seed_movies.py
```

Данные с ноутбука переносятся отдельно — см. «Перенос базы» ниже.

## 6. Telegram

Бот сам ставит кнопку меню на `WEBAPP_URL` при старте. Проверить:

```bash
docker compose -f docker-compose.prod.yml logs bot | tail -20
```

В логе должно быть `Telegram Bot API menu button URL=https://<ваше имя>/`.

## Обновление

```bash
cd /opt/nova && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Миграции применяются при старте API, откат не нужен.

## Перенос базы с ноутбука

Локальная разработка идёт на SQLite, сервер — на Postgres, поэтому файл базы
просто скопировать нельзя. Если данные нужны, переносите содержимое:

```bash
# на ноутбуке: выгрузить
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Проще и честнее — начать на сервере с чистой базы и завести настоящие фильмы
и расписание через админку: демо-данные всё равно придётся удалять.

## Резервная копия

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U nova nova_cinema | gzip > /root/nova-$(date +%F).sql.gz
```

Загруженные файлы лежат в томе `uploads`:

```bash
docker run --rm -v nova_uploads:/data -v /root:/backup alpine \
  tar czf /backup/nova-uploads-$(date +%F).tar.gz -C /data .
```

Обе команды стоит поставить в `cron` раз в сутки.

## Что смотреть, когда что-то не так

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f bot
docker compose -f docker-compose.prod.yml logs -f caddy
```

Сертификат не выпускается — почти всегда имя не указывает на сервер или закрыт
порт 80: Let's Encrypt проверяет владение через него.
