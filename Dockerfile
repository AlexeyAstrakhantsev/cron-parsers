FROM python:3.10

WORKDIR /app

COPY run_parsers.py /app/
COPY crontab /etc/cron.d/parsers_cron
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Устанавливаем зависимости (если база PostgreSQL, добавь psycopg2)
RUN apt-get update && apt-get install -y cron sqlite3 psycopg2

# Настраиваем крон
RUN chmod 0644 /etc/cron.d/parsers_cron && \
    crontab /etc/cron.d/parsers_cron && \
    touch /var/log/cron.log

CMD ["/entrypoint.sh"]
