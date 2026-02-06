import logging


class InfoWarningErrorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):  # noqa
        if record.levelno == logging.INFO:
            return record.getMessage()
        return f"{record.levelname}: {record.getMessage()}"


def setup_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    debug_handler = logging.StreamHandler()
    debug_handler.setLevel(logging.DEBUG)

    debug_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | "
        "%(filename)s:%(lineno)d | %(funcName)s() | %(message)s"
    )

    debug_handler.setFormatter(debug_formatter)
    debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)

    info_handler = logging.StreamHandler()
    info_handler.setLevel(logging.INFO)

    info_handler.setFormatter(InfoWarningErrorFormatter())
    info_handler.addFilter(lambda record: record.levelno >= logging.INFO)

    logger.addHandler(debug_handler)
    logger.addHandler(info_handler)
