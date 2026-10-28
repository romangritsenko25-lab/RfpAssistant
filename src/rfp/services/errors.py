"""Domain errors raised by the service layer; the HTTP layer maps them to status codes."""


class ServiceError(Exception):
    """Base class: the message is safe to show to the user."""


class NotFoundError(ServiceError):
    """The requested object does not exist."""


class ConflictError(ServiceError):
    """The object is in a state that does not allow the operation."""


class InvalidInputError(ServiceError):
    """The input is unusable (unsupported file, no questions found, empty edit)."""
