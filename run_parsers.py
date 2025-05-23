import os
import subprocess
import psycopg2  # Используем PostgreSQL
from datetime import datetime, timedelta, timezone
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
    now = datetime.now(timezone.utc)  # Добавляем временную зону
    
    cursor.execute(f"SELECT database_name, update_period FROM {DB_TABLE}")
    parsers = cursor.fetchall()
    
    to_run = []
    print("\nИнформация о парсерах:")
    print("-" * 50)
    
    for database_name, update_period in parsers:
        cursor.execute(
            "SELECT last_run FROM parser_logs "
            "WHERE parser_name = %s "
            "ORDER BY last_run DESC LIMIT 1",
            (database_name,)
        )
        result = cursor.fetchone()
        last_run = result[0].astimezone(timezone.utc) if result else None
        
        base_time = last_run or datetime(2024, 1, 1, tzinfo=timezone.utc)
        cron = convert_update_period_to_cron(update_period)
        
        if cron:
            cron_iter = croniter.croniter(cron, base_time)
            next_run = cron_iter.get_next(datetime).astimezone(timezone.utc)
            
            print(f"Парсер: {database_name}")
            print(f"Период обновления: {update_period}")
            print(f"Последний запуск: {last_run if last_run else 'Никогда'}")
            print(f"Следующий запуск: {next_run}")
            print(f"Текущее время: {now}")
            print("-" * 30)
            
            if next_run <= now and (now - base_time).total_seconds() > 60:
                to_run.append(database_name)
                print(f"Парсер {database_name} будет запущен")
            else:
                print(f"Парсер {database_name} не требует запуска")
    
    print(f"\nВсего парсеров для запуска: {len(to_run)}")
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
    # Выводим текущие настройки окружения
    print("Текущие настройки окружения:")
    print(f"DB_HOST: {DB_HOST}")
    print(f"DB_NAME: {DB_NAME}")
    print(f"DB_USER: {DB_USER}")
    print(f"DB_TABLE: {DB_TABLE}")
    print(f"DOCKER_COMPOSE_PATH: {DOCKER_COMPOSE_PATH}")
    print("-" * 50)

    parsers = get_parsers_to_run()
    for parser in parsers:
        if not is_container_running(parser):
            command = [
                "docker", "compose",
                "-f", f"{DOCKER_COMPOSE_PATH}/docker-compose.yml",
                "up", "-d", parser
            ]
            print(f"Запускаем парсер {parser}")
            print(f"Выполняемая команда: {' '.join(command)}")
            subprocess.run(command)
            update_parser_log(parser)
        else:
            print(f"Парсер {parser} уже запущен, пропускаем")


def update_parser_log(parser_name):
    """Обновляет время последнего запуска парсера"""
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO parser_logs (parser_name) VALUES (%s)",
        (parser_name,)
    )
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    run_parsers()
