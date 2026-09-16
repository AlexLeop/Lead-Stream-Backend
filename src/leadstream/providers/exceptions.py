class ProviderError(RuntimeError):
    """Base error for an external provider call."""


class ProviderNotConfigured(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    def __init__(self, message: str, *, retry_after_seconds: int = 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(1, min(retry_after_seconds, 300))


class ProviderBudgetExceeded(ProviderError):
    pass


class ProviderCircuitOpen(ProviderError):
    pass


class ProviderTemporaryError(ProviderError):
    pass


class ProviderPermanentError(ProviderError):
    pass


class ProviderPending(ProviderError):
    """Operação remota em curso; consultar novamente sem iniciar outra execução."""


class ProviderSubmissionUncertain(ProviderPermanentError):
    """Envio sem confirmação: não repetir automaticamente uma operação cobrável."""
