"""Локальный воркaround: подмена DNS для api.telegram.org.

Нужен, когда системный резолвер отдаёт недоступный IP (см. README,
разлок «Бот не может соединиться с Telegram»). Включается переменной
TG_API_IP в bot/.env; на рабочем хостинге (bothost) не используется.
"""
import socket

_orig = socket.getaddrinfo


def install(host: str, ip: str) -> None:
    """Все запросы getaddrinfo к `host` возвращают фиксированный `ip`."""

    def _patched(host_, port, *args, **kwargs):
        if host_ == host:
            host_ = ip
        return _orig(host_, port, *args, **kwargs)

    socket.getaddrinfo = _patched


def uninstall() -> None:
    socket.getaddrinfo = _orig
