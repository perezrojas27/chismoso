"""Excepciones tipadas para fallos del biométrico / fuente de eventos."""


class BiometricError(Exception):
    """Error base del módulo biométrico."""

    def __init__(self, message: str, *, code: str = "biometric_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ConnectionErrorBiometric(BiometricError):
    def __init__(self, message: str = "No se pudo conectar al dispositivo biométrico") -> None:
        super().__init__(message, code="connection_error")


class AuthenticationErrorBiometric(BiometricError):
    def __init__(self, message: str = "Credenciales inválidas en el dispositivo") -> None:
        super().__init__(message, code="auth_error")


class EmptyResponseError(BiometricError):
    def __init__(self, message: str = "El dispositivo no devolvió eventos") -> None:
        super().__init__(message, code="empty_response")


class DeviceProtocolError(BiometricError):
    def __init__(self, message: str = "Respuesta inválida del dispositivo") -> None:
        super().__init__(message, code="protocol_error")
