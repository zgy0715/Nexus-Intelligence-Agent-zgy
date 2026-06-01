from datetime import datetime
from uuid import uuid4

from nia.storage.database import DatabaseManager


class DataVersionControl:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def compare_and_record(self, old_data: dict, new_data: dict, crawled_data_id: str) -> list[dict]:
        versions_col = self.db_manager.get_collection("data_versions")

        max_version_doc = versions_col.find_one(
            {"crawled_data_id": crawled_data_id},
            sort=[("version_number", -1)],
        )
        next_version = (max_version_doc["version_number"] + 1) if max_version_doc else 1

        changes: list[dict] = []
        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            if old_val != new_val:
                doc = {
                    "id": str(uuid4()),
                    "crawled_data_id": crawled_data_id,
                    "field_name": key,
                    "old_value": str(old_val) if old_val is not None else None,
                    "new_value": str(new_val) if new_val is not None else None,
                    "version_number": next_version,
                    "created_at": datetime.utcnow(),
                }
                changes.append(doc)

        if changes:
            versions_col.insert_many(changes)

        return changes

    def get_history(self, url: str) -> list[dict]:
        crawled_col = self.db_manager.get_collection("crawled_data")
        versions_col = self.db_manager.get_collection("data_versions")

        crawled_doc = crawled_col.find_one({"url": url})
        if crawled_doc is None:
            return []

        versions = list(
            versions_col.find({"crawled_data_id": crawled_doc["id"]}).sort("created_at", 1)
        )
        return versions

    def get_diff(self, crawled_data_id: str, version1: int, version2: int) -> dict:
        versions_col = self.db_manager.get_collection("data_versions")

        v1_docs = list(
            versions_col.find({
                "crawled_data_id": crawled_data_id,
                "version_number": version1,
            })
        )
        v1_entries = {doc["field_name"]: doc for doc in v1_docs}

        v2_docs = list(
            versions_col.find({
                "crawled_data_id": crawled_data_id,
                "version_number": version2,
            })
        )
        v2_entries = {doc["field_name"]: doc for doc in v2_docs}

        all_fields = set(v1_entries.keys()) | set(v2_entries.keys())
        diff: dict = {}
        for field_name in all_fields:
            v1_entry = v1_entries.get(field_name)
            v2_entry = v2_entries.get(field_name)
            diff[field_name] = {
                "version1": {
                    "old_value": v1_entry["old_value"] if v1_entry else None,
                    "new_value": v1_entry["new_value"] if v1_entry else None,
                },
                "version2": {
                    "old_value": v2_entry["old_value"] if v2_entry else None,
                    "new_value": v2_entry["new_value"] if v2_entry else None,
                },
            }

        return diff
