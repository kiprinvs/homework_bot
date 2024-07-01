import logging
import os
import requests
import time
from http import HTTPStatus

from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import RequestError, TokenError, UnknownHomeworkStatusError

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s [%(levelname)s] %(message)s',
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
    """Проверка наличия переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

    if not all(tokens):
        message = 'Отсутствует переменная окружения'
        logging.critical(message)
        raise TokenError(message)

    return all(tokens)


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено.')
    except requests.RequestException as error:
        logging.error(f'Ошибка отправки сообщения {error}')


def get_api_answer(timestamp):
    """Запрос к API."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except Exception as error:
        logging.error(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. {error}'
        )
        raise RequestError

    if response.status_code != HTTPStatus.OK:
        logging.error(
            f'Сбой в работе программы: Код ответа API: {response.status_code}.'
        )
        raise RequestError('Ошибка ответа от сервера.')

    return response.json()


def check_response(response):
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        raise TypeError('API передал не словарь.')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks.')

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise TypeError('В homework передан не список.')

    if not homeworks:
        logging.debug('Список домашних работ пуст.')
    return homeworks


def parse_status(homework):
    """Получение статуса домашней работы."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError('Отсутствует ключ homework_name или status.')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS or homework_status is None:
        raise UnknownHomeworkStatusError('Неизвестный статус домашней работы.')

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_status = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                current_status = parse_status(homeworks[0])
            else:
                current_status = 'Ревьюер еще не начал проверку Вашей работы.'

            if current_status != old_status:
                send_message(bot, current_status)
                old_status = current_status

        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logging.error(message, exc_info=True)
            bot.send_message(TELEGRAM_CHAT_ID, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
