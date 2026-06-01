import hashlib
import json

from bs4 import BeautifulSoup

from nia.utils.config import Config


class DOMChangeDetector:
    def __init__(self, redis_conn):
        self.redis = redis_conn
        self.threshold = Config.DOM_SIMILARITY_THRESHOLD

    def compute_signature(self, html: str) -> str:
        structure = self._extract_structure(html)
        structure_str = "|".join(structure)
        return hashlib.md5(structure_str.encode()).hexdigest()

    def compute_similarity(self, old_html: str, new_html: str) -> float:
        old_structure = self._extract_structure(old_html)
        new_structure = self._extract_structure(new_html)
        if not old_structure and not new_structure:
            return 1.0
        if not old_structure or not new_structure:
            return 0.0
        max_len = max(len(old_structure), len(new_structure))
        matches = sum(1 for a, b in zip(old_structure, new_structure) if a == b)
        return matches / max_len

    def _extract_structure(self, html: str) -> list:
        soup = BeautifulSoup(html, "lxml")
        tags = []
        for element in soup.descendants:
            if element.name:
                tags.append(element.name)
        return tags

    def is_page_changed(self, domain: str, new_html: str) -> bool:
        key = f"nia:dom_structure:{domain}"
        data = self.redis.get(key)
        if not data:
            return True
        old_structure = json.loads(data)
        new_structure = self._extract_structure(new_html)
        max_len = max(len(old_structure), len(new_structure))
        if max_len == 0:
            return False
        matches = sum(1 for a, b in zip(old_structure, new_structure) if a == b)
        similarity = matches / max_len
        return similarity < self.threshold

    def update_signature(self, domain: str, html: str):
        structure_key = f"nia:dom_structure:{domain}"
        structure = self._extract_structure(html)
        self.redis.set(structure_key, json.dumps(structure))

    def get_stored_signature(self, domain: str):
        structure_key = f"nia:dom_structure:{domain}"
        data = self.redis.get(structure_key)
        if data:
            structure = json.loads(data)
            structure_str = "|".join(structure)
            return hashlib.md5(structure_str.encode()).hexdigest()
        return None
