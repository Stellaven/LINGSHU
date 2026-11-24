class ServiceException(Exception):
    """自定义服务异常"""

    def __init__(
            self,
            message: str,
    ):
        super().__init__(message)
        self.message = message


class BusinessError(ServiceException):
    """业务异常：携带业务错误码与HTTP状态码，由全局异常处理器统一返回

    默认按鉴权失败处理（40101/401），非鉴权场景请显式传入 code 与 status_code。
    """

    def __init__(self, message: str, code: int = 40101, status_code: int = 401):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
