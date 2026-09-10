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
