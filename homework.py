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
        raise APIError(f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise APIError(f'Неправильный статус: {response.status_code} '
                       f'{response.reason}')
    return response.json()


def check_response(response):
    """Проверка корректности ответа от API."""
    logging.debug('Начало проверки ответа от API')
    if not isinstance(response, dict):
        raise TypeError(f'Ответ API должен быть словарем, '
                        f'а пришел {type(response)}')

    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ "homeworks"')

    if not isinstance(response['homeworks'], list):
        raise TypeError(f'Ключ "homeworks" должен содержать список '
                        f'а содержит {type(response["homeworks"])}')
    logging.debug('Завершение проверки ответа от API')
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса проверки работы."""
    logging.debug('Начало првоерки статуса работы.')
    assert 'homework_name' in homework
    if 'homework_name' not in homework:
        raise KeyError('Некорректный ответ: отсутствует ключ "homework_name"')
    homework_name = homework.get('homework_name')
    assert 'status' in homework
    if 'status' not in homework:
        # Я не совсем понял, поэтому оставил проверку через
        # assert(но в нём тогда надо указать еще ошибку, на сколько я помню)
        # и через if,
        # в прошом ревью у меня была проверка просто через if для 'name',
        # но ты ответил, что я не сделал проверку для обоих ключей,
        # может имел в виду только для 'status'
        raise KeyError('Некорректный ответ: отсутствует ключ "status"')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise StatusError(f'Неизвестный статус проверки: {homework_status}')
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
                last_error_message = ""
            else:
                logging.debug('В ответе нет новых статусов.')
            timestamp = response.get('current_date', int(time.time()))
        except SendMessageError as send_error:
            message = f'Сбой в работе программы: {send_error}'
            if send_error != last_error_message:
                with suppress(SendMessageError):
                    send_message(bot, message)
                last_error_message = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(error)
            if error != last_error_message:
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
