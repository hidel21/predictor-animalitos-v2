"""Identidad de animales y tiempos compartida por entrenamiento e inferencia."""
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import hashlib
import re
import unicodedata

from .constantes import ANIMALITOS
from .historial_client import HistorialData

CARACAS = ZoneInfo("America/Caracas")
CODES = tuple(ANIMALITOS)
CODE_INDEX = {code: i for i, code in enumerate(CODES)}


def _plain(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", str(value))
                           if unicodedata.category(c) != "Mn").casefold().split())


_NAMES = {_plain(name): code for code, name in ANIMALITOS.items()}


def animal_code(value):
    """Devuelve código canónico; rechaza nombres desconocidos o contradictorios."""
    raw = str(value).strip()
    if raw in CODES:
        return raw
    if raw.isdigit():
        code = str(int(raw))
        return code if code in CODES else None
    if _plain(raw) in _NAMES:
        return _NAMES[_plain(raw)]
    match = re.fullmatch(r"(\d{1,2})\s*[-:]?\s+(.+)", raw)
    if match:
        code = animal_code(match[1])
        return code if code is not None and _NAMES.get(_plain(match[2])) == code else None
    return None


def draw_time(value):
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    for fmt in ("%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(str(value).strip().upper(), fmt).time()
        except ValueError:
            pass
    raise ValueError(f"Hora inválida: {value!r}")


def draw_datetime(fecha, hora):
    day = fecha if isinstance(fecha, date) else date.fromisoformat(str(fecha))
    return datetime.combine(day, draw_time(hora))


def local_datetime(value):
    return value.astimezone(CARACAS).replace(tzinfo=None) if value.tzinfo else value


@dataclass(frozen=True)
class Draw:
    timestamp: datetime
    code: str


def ordered_draws(data, before=None):
    """Normaliza el historial sin depender del orden de inserción del diccionario."""
    before = local_datetime(before) if before is not None else None
    by_time = {}
    for (fecha, hora), value in data.tabla.items():
        stamp = draw_datetime(fecha, hora)
        code = animal_code(value)
        if code is None or (before is not None and stamp >= before):
            continue
        if stamp in by_time and by_time[stamp] != code:
            raise ValueError(f"Resultados contradictorios para {stamp.isoformat()}")
        by_time[stamp] = code
    return [Draw(stamp, code) for stamp, code in sorted(by_time.items())]


def as_history(draws):
    return HistorialData(
        dias=sorted({d.timestamp.date().isoformat() for d in draws}),
        horas=sorted({d.timestamp.strftime("%I:%M %p") for d in draws}, key=draw_time),
        tabla={(d.timestamp.date().isoformat(), d.timestamp.strftime("%I:%M %p")):
               ANIMALITOS[d.code] for d in draws},
    )


def history_digest(draws):
    return hashlib.sha256("\n".join(f"{d.timestamp.isoformat()}|{d.code}" for d in draws).encode()).hexdigest()


def next_draw(data, now=None):
    """Próximo horario observado en los últimos 30 días, en hora de Caracas.

    No inventa horarios nocturnos. Es inferido, no un calendario oficial.
    """
    now = local_datetime(now or datetime.now(CARACAS))
    draws = ordered_draws(data, before=now)
    if not draws:
        raise ValueError("No hay horarios observados para inferir el siguiente sorteo.")
    cutoff = draws[-1].timestamp - timedelta(days=30)
    hours = sorted({d.timestamp.time() for d in draws if d.timestamp >= cutoff})
    for offset in range(8):
        for hour in hours:
            target = datetime.combine(now.date() + timedelta(days=offset), hour)
            if target > now:
                return target
    raise ValueError("No se pudo determinar un horario futuro.")
