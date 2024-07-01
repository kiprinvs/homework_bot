class RequestError(Exception):
    """Исключение для ошибок при запросе к API."""

    pass


class UnknownHomeworkStatusError(Exception):
    """Исключение для неизвестного статуса домашней работы."""

    pass


class TokenError(Exception):
    """Исключение для отсутствия переменных окружения."""

    pass
