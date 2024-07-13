import requests
import os
import logging
import sys
from logging import StreamHandler
import time

from telebot import TeleBot
from dotenv import load_dotenv

from exceptions import (
    StatusError,
    APIError,
    SendMessageError,
)


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[StreamHandler(sys.stdout)]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия необходимых переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logging.critical('Отсутствуют пременные окружения!')
        raise TypeError('Отсутствуют пременные окружения!')
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')
        raise SendMessageError()


def get_api_answer(timestamp):
    """Получение ответа от API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'timestamp': timestamp, 'from_date': 0}
        )
        if response.status_code != 200:
            raise APIError(f'Неправильный статус: {response.status_code}')
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise APIError()
    return response.json()


def check_response(response):
    """Проверка корректности ответа от API."""
    if not isinstance(response, dict):
        logging.error('Некорректный ответ: ожидается словарь')
        raise TypeError('Ответ API должен быть словарем')

    if 'homeworks' not in response:
        logging.error('Некорректный ответ: отсутствует ключ "homeworks"')
        raise KeyError('В ответе API отсутствует ключ "homeworks"')

    if not isinstance(response['homeworks'], list):
        logging.error('Ключ "homeworks" должен содержать список')
        raise TypeError('Ключ "homeworks" должен содержать список')

    return response['homeworks']


def parse_status(homework):
    """Проверка статуса проверки работы."""
    if 'homework_name' not in homework:
        logging.error('Некорректный ответ: отсутствует ключ "homework_name"')
        raise KeyError('Нет названия домашки')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
    else:
        logging.error(f'Неизвестный статус проверки: {homework_status}')
        raise StatusError
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logging.debug('В ответе нет новых статусов.')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            try:
                send_message(bot, message)
            except SendMessageError:
                logging.error('Не удалось отправить сообщение в Telegram.')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
