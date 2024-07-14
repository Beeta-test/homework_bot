import logging
import os
import sys
import time
from contextlib import suppress
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from requests import RequestException
from telebot import TeleBot
from telebot.apihelper import ApiException

from exceptions import APIError, SendMessageError, StatusError


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SOURCE = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

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
    missing_token = [token for token in SOURCE if not globals()[token]]
    if missing_token:
        error_token = ', '.join(missing_token)
        logging.critical(f'Отсутствуют пременные окружения: {error_token}')
        raise TypeError(f'Отсутствуют пременные окружения: {error_token}')


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        logging.debug(f'Начало отправки сообщения: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except (ApiException, RequestException) as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')
        raise SendMessageError(error)


def get_api_answer(timestamp):
    """Получение ответа от API."""
    logging.debug(f'Начало запроса к API: {timestamp}')
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'timestamp': timestamp, 'from_date': timestamp}
        )
        logging.debug('API успешно получен.')
    except RequestException as error:
        error_message = f'Ошибка при запросе к основному API: {error}'
        logging.error(error_message)
        raise APIError(error)
    if response.status_code != HTTPStatus.OK:
        error_message = (f'Неправильный статус: {response.status_code} '
                         f'{response.reason}')
        logging.error(error_message)
        raise APIError(error_message)
    return response.json()


def check_response(response):
    """Проверка корректности ответа от API."""
    logging.debug('Начало проверки ответа от API')
    if not isinstance(response, dict):
        error_message = (f'Ответ API должен быть словарем, '
                         f'а пришел {type(response)}')
        logging.error(error_message)
        raise TypeError(error_message)

    if 'homeworks' not in response:
        error_message = 'В ответе API отсутствует ключ "homeworks"'
        logging.error(error_message)
        raise KeyError(error_message)

    if not isinstance(response['homeworks'], list):
        error_message = (f'Ключ "homeworks" должен содержать список '
                         f'а содержит {type(response["homeworks"])}')
        logging.error(error_message)
        raise TypeError(error_message)
    logging.debug('Завершение проверки ответа от API')
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса проверки работы."""
    logging.debug('Начало првоерки статуса работы.')
    if 'homework_name' not in homework:
        error_message = 'Некорректный ответ: отсутствует ключ "homework_name"'
        logging.error(error_message)
        raise KeyError(error_message)
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = f'Неизвестный статус проверки: {homework_status}'
        logging.error(error_message)
        raise StatusError(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.debug('Проверка статуса работы завершена успешно.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ""

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            else:
                logging.debug('В ответе нет новых статусов.')
            timestamp = response.get('current_date', int(time.time()))
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_error_message:
                with suppress(SendMessageError):
                    send_message(bot, message)
                last_error_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=('%(asctime)s, %(levelname)s,'
                '%(name)s, %(pathname)s, %(message)s'),
        handlers=[StreamHandler(sys.stdout)]
    )
    main()
