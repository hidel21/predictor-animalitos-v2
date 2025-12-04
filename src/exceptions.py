class PredictorError(Exception):
    """Excepción base para errores del predictor."""
    pass

class ScrapingError(PredictorError):
    """Error al extraer datos de la web."""
    pass

class ConnectionError(PredictorError):
    """Error de conexión con el servidor."""
    pass

class DateRangeError(PredictorError):
    """Error en el rango de fechas."""
    pass
