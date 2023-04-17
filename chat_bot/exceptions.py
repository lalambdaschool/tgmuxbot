class MyException(Exception):
    pass


class NoAdminChat(MyException):
    pass


class NoTopicsAdminChat(MyException):
    message = "Сделайте чат с топиками"


class NoTopicRightsAdminChat(MyException):
    message = "У бота нет права менеджерить топики"
