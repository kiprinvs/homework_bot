import logging
import os
import requests
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv
from telebot import apihelper, TeleBot

from exceptions import RequestError, TokenError, UnknownHomeworkStatusError

load_dotenv()

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
    """Проверка наличия переменных окружения."""
    SOURCE = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
    missing_variables = [token for token in SOURCE if not globals()[token]]

    if missing_variables:
        miss_tokens = ', '.join(missing_variables)
        message = (
            f'Бот остановлен. Отсутствуют переменные окружения - {miss_tokens}'
        )
        logging.critical(message)
        raise TokenError(message)


def send_message(bot, message):
    """Отправка сообщения."""
    logging.debug('Попытка отправки сообщения.')

    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение успешно отправлено.')
    except (requests.RequestException, apihelper.ApiException) as error:
        logging.error(f'Ошибка отправки сообщения {error}')


def get_api_answer(timestamp):
    """Запрос к API."""
    params = {'from_date': timestamp}
    logging.debug(
        f'Отправляю запрос к API - {ENDPOINT}. Параметры запроса: {params}.')

    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        logging.debug('Запрос успешно отправлен.')
    except requests.RequestException as error:
        raise RequestError(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. {error}'
            f' Параметры запроса: {params}.'
        )

    if response.status_code != HTTPStatus.OK:
        raise RequestError(
            f'Сбой в работе программы: Код ответа API: {response.status_code}.'
            f' Причина: {response.reason}'
        )

    return response.json()


def check_response(response):
    """Проверка корректности ответа API."""
    logging.debug('Начинаем проверку ответа API.')

    if not isinstance(response, dict):
        raise TypeError(f'API передал не словарь. Передан {type(response)}.')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks.')

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise TypeError(
            f'В homework передан не список. Передан {type(homeworks)}.'
        )

    logging.debug('Проверка ответа API прошла успешно.')
    return homeworks


def parse_status(homework):
    """Получение статуса домашней работы."""
    logging.debug('Начало проверки статуса работы.')

    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name.')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status.')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise UnknownHomeworkStatusError(
            f'Неизвестный статус домашней работы - {homework_status}.'
        )

    logging.debug('Проверка статуса работы прошла успешно.')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                current_status = parse_status(homeworks[0])
                send_message(bot, current_status)
                last_message_error = ''
            else:
                logging.debug('Новый статус проверки работы отсутствует.')

            timestamp = response.get(
                'current_date', int(time.time())
            )

        except Exception as error:
            current_message_error = f'Сбой в работе программы: {error}.'
            logging.error(current_message_error, exc_info=True)

            if last_message_error != current_message_error:
                send_message(TELEGRAM_CHAT_ID, current_message_error)
                last_message_error = current_message_error

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    handler_file = logging.FileHandler(
        'program.log', encoding='utf_8', mode='w'
    )
    handler_stream = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s [%(levelname)s] %(message)s %(funcName)s - %(lineno)d'
        ),
        handlers=[handler_file, handler_stream]
    )
    main()
