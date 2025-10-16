"""
Add Fake Data for testing
"""

import random
from src.db.sqlite import DB

farsi_digits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"]
letters = ["ب", "ج", "د", "س", "ص", "ط", "ق", "ل", "م", "ن", "و", "ه", "ی"]


def random_plate():
    return (
        random.choice(farsi_digits)
        + random.choice(farsi_digits)
        + random.choice(letters)
        + "".join(random.choice(farsi_digits) for _ in range(5))
    )


def insert_fake_plates(db):
    for vid in range(1, 1001):
        plate_text = random_plate()
        db.insert_plate(vid, plate_text)


if __name__ == "__main__":
    db = DB()
    insert_fake_plates(db)
    db.stop()
