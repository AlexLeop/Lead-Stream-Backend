class ProviderError(RuntimeError):
    """Base error for an external provider call."""


class ProviderNotConfigured(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    pass


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
