import os
import subprocess
import psycopg2  # Используем PostgreSQL
from datetime import datetime
import croniter
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "parsers_db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_TABLE = os.getenv("DB_TABLE", "parsers")
DOCKER_COMPOSE_PATH = os.getenv("DOCKER_COMPOSE_PATH", ".")  # Путь к docker-compose.yml

def get_parsers_to_run():
    """Получает список парсеров, которые должны запуститься в этот момент"""
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    now = datetime.now()
    
    cursor.execute(f"SELECT database_name, update_period FROM {DB_TABLE}")
    parsers = cursor.fetchall()
    
    to_run = []
    for database_name, update_period in parsers:
        base_time = datetime(2024, 1, 1)  # Фиксированная точка для croniter
        cron = convert_update_period_to_cron(update_period)
        
        if cron and croniter.croniter(cron, base_time).get_next(datetime) <= now:
            to_run.append(database_name)

    cursor.close()
    conn.close()
    return to_run


def convert_update_period_to_cron(update_period):
    """Конвертирует наше представление расписания в формат cron"""
    if update_period.startswith("daily"):
        _, hour = update_period.split()
        return f"0 {hour} * * *"
    elif update_period.startswith("weekly"):
        _, day, hour = update_period.split()
        days_map = {"mo": 1, "tu": 2, "we": 3, "th": 4, "fr": 5, "sa": 6, "su": 0}
        return f"0 {hour} * * {days_map.get(day, 1)}"
    elif update_period.startswith("hourly"):
        _, value = update_period.split()
        if "." in value:
            minutes = int(float(value) * 60)
            return f"*/{minutes} * * * *"
        else:
            return f"0 */{value} * * *"
    return None


def is_container_running(container_name):
    """Проверяет, запущен ли контейнер"""
    result = subprocess.run(["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"], capture_output=True, text=True)
    return container_name in result.stdout.strip().split("\n")


def run_parsers():
    """Запускает нужные парсеры через docker-compose, если они не запущены"""
    parsers = get_parsers_to_run()
    for parser in parsers:
        if not is_container_running(parser):
            print(f"Запускаем парсер {parser}")
            subprocess.run([
                "docker", "compose",
                "-f", f"{DOCKER_COMPOSE_PATH}/docker-compose.yml",
                "--env-file", f"{DOCKER_COMPOSE_PATH}/.env",
                "up", parser
            ])
        else:
            print(f"Парсер {parser} уже запущен, пропускаем")

if __name__ == "__main__":
    run_parsers()
