"""Domain errors. The API maps each to its HTTP status with the message as `detail`."""


class AppError(Exception):
    status = 400


class NotFound(AppError):
    status = 404


class Conflict(AppError):
    status = 409


class Invalid(AppError):
    status = 422
