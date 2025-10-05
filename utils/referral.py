import random
import string
from typing import Literal


class RefLink:
    def __init__(self):
        pass
    def _random_ref_code(self, size: int) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=size))
    
    def generate_ref_code(self, codes: list[str], role: Literal["user", "partner"], size: int = 10) -> str:
        while True:
            code = self._random_ref_code(size)
            if role == "partner":
                code = "part" + code + "ner"
            if code not in codes:
                return code
        