class StatusError(Exception):
    """Ошибка статуса."""

    def __str__(self) -> str:
        """Переопределение."""
        return 'Неизвестный статус проверки'


class APIError(Exception):
    """Ошибка сервера API."""

    def __str__(self) -> str:
        """Переопределение."""
        return 'Ошибка при запросе к основному API'


class SendMessageError(Exception):
    """Ошибка при отправке сообщения в Telegram."""

    def __str__(self) -> str:
        """Переопределение."""
        return 'Ошибка при отправке сообщения'


class TokenError(Exception):
    """Ошибка токена."""

    def __str__(self) -> str:
        """Переопределение."""
        return 'Не найден какой-то токен.'
