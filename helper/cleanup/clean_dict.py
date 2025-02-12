from datetime import datetime


def clean_dict(data: dict) -> dict:
    """
    Removes key-value pairs where the value is None and formats datetime values.

    Args:
        data (dict): Input dictionary.

    Returns:
        dict: Cleaned dictionary.
    """
    return {
        k: (v.strftime('%Y-%m-%d') if isinstance(v, datetime) else v)
        for k, v in data.items() if v is not None
    }
