from typing import Dict, List

from excel_parser import SOWData
from db import Database


def load_user_sow_data(db: Database, user_id: int) -> List[SOWData]:
    raw_data = db.load_user_sow_data(user_id)
    result = []
    for item in raw_data:
        if item["monthly_values"]:
            result.append(SOWData(
                name=item["name"],
                sow_type=item["sow_type"],
                monthly_values=item["monthly_values"],
            ))
    return result


def save_sow_data_for_user(db: Database, user_id: int, sow_list: List[SOWData]):
    for sow in sow_list:
        assets = db.list_assets(user_id)
        existing = None
        for a in assets:
            if a["name"] == sow.name and a["sow_type"] == sow.sow_type:
                existing = a
                break

        if existing:
            db.batch_set_monthly_values(user_id, existing["id"], sow.monthly_values)
        else:
            asset_id = db.create_asset(user_id, sow.name, sow.sow_type)
            db.batch_set_monthly_values(user_id, asset_id, sow.monthly_values)