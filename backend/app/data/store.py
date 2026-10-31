from functools import lru_cache

from app.data.generator import generate
from app.data.models import Dataset


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    return generate()
