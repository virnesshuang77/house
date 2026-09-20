import csv
import json
import statistics
import re
from pathlib import Path


RAW_DIR = Path("raw")
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "taiwan_housing.json"

PING_PER_SQM = 3.305785


# 台灣本島縣市
CITY_CODES = {
    "A": "台北市",
    "B": "台中市",
    "C": "基隆市",
    "D": "台南市",
    "E": "高雄市",
    "F": "新北市",
    "G": "宜蘭縣",
    "H": "桃園市",
    "I": "嘉義市",
    "J": "新竹縣",
    "K": "苗栗縣",
    "M": "南投縣",
    "N": "彰化縣",
    "O": "新竹市",
    "P": "雲林縣",
    "Q": "嘉義縣",
    "R": "屏東縣",
    "S": "花蓮縣",
    "T": "台東縣",

    # 離島排除
    "U": None,
    "V": None,
    "W": None,
}


def clean_number(value):

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    value = value.replace(",", "")
    value = value.replace(" ", "")

    try:
        return float(value)
    except ValueError:
        return None


def detect_city_from_filename(filename):

    name = filename.upper()

    match = re.match(r"([A-Z])_", name)

    if not match:
        return None

    code = match.group(1)

    return CITY_CODES.get(code)


def read_csv_file(filepath):

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp950",
    ]

    for encoding in encodings:

        try:

            with open(
                filepath,
                "r",
                encoding=encoding,
                newline=""
            ) as f:

                reader = csv.DictReader(f)

                headers = reader.fieldnames or []

                rows = list(reader)

                return headers, rows

        except UnicodeDecodeError:
            continue

        except Exception as e:

            print(f"讀取失敗：{filepath}")
            print(e)

            return [], []

    return [], []


def is_sales_file(headers):

    headers = set(headers)

    return (
        "交易年月日" in headers
        and "總價元" in headers
        and "單價元平方公尺" in headers
    )


def is_rent_file(headers):

    headers = set(headers)

    # 內政部目前租賃資料
    # 使用「租賃年月日」+「總額元」
    return (
        "租賃年月日" in headers
        and "總額元" in headers
    )


def is_residential(row):

    building_type = str(
        row.get("建物型態", "")
    ).strip()

    main_use = str(
        row.get("主要用途", "")
    ).strip()

    target = str(
        row.get("交易標的", "")
    ).strip()

    text = f"{building_type} {main_use} {target}"

    excluded_keywords = [
        "工廠",
        "廠房",
        "辦公",
        "辦公室",
        "店面",
        "商業",
        "倉庫",
        "墓地",
        "停車位",
        "車位",
    ]

    if any(
        keyword in text
        for keyword in excluded_keywords
    ):
        return False

    residential_keywords = [
        "住宅大樓",
        "華廈",
        "公寓",
        "透天厝",
        "套房",
        "別墅",
        "住宅",
    ]

    if any(
        keyword in text
        for keyword in residential_keywords
    ):
        return True

    if "住家" in main_use:
        return True

    return False


def process_sales_file(filepath, result):

    city = detect_city_from_filename(
        filepath.name
    )

    if not city:
        return

    headers, rows = read_csv_file(filepath)

    if not headers:
        return

    if not is_sales_file(headers):
        return

    print(
        f"處理買賣：{filepath.name} -> {city}"
    )

    count = 0

    for row in rows:

        if not is_residential(row):
            continue

        district = str(
            row.get("鄉鎮市區", "")
        ).strip()

        if not district:
            continue

        unit_price = clean_number(
            row.get("單價元平方公尺")
        )

        if unit_price is None:
            continue

        if unit_price <= 0:
            continue

        price_per_ping = (
            unit_price * PING_PER_SQM
        )

        key = f"{city}|{district}"

        if key not in result:

            result[key] = {
                "city": city,
                "district": district,
                "prices": [],
                "rents": [],
            }

        result[key]["prices"].append(
            price_per_ping
        )

        count += 1

    print(
        f"  有效住宅買賣：{count}"
    )


def process_rent_file(filepath, result):

    city = detect_city_from_filename(
        filepath.name
    )

    if not city:
        return

    headers, rows = read_csv_file(filepath)

    if not headers:
        return

    if not is_rent_file(headers):
        return

    print(
        f"處理租賃：{filepath.name} -> {city}"
    )

    count = 0

    for row in rows:

        if not is_residential(row):
            continue

        district = str(
            row.get("鄉鎮市區", "")
        ).strip()

        if not district:
            continue

        # 官方租賃資料目前使用「總額元」
        rent = clean_number(
            row.get("總額元")
        )

        if rent is None:
            continue

        if rent <= 0:
            continue

        key = f"{city}|{district}"

        if key not in result:

            result[key] = {
                "city": city,
                "district": district,
                "prices": [],
                "rents": [],
            }

        result[key]["rents"].append(
            rent
        )

        count += 1

    print(
        f"  有效住宅租賃：{count}"
    )


def load_income_ratio():

    filepath = RAW_DIR / "income_ratio.csv"

    ratios = {}

    if not filepath.exists():

        print(
            "找不到 raw/income_ratio.csv"
        )

        return ratios

    with open(
        filepath,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            city = str(
                row.get("city", "")
            ).strip()

            value = clean_number(
                row.get("ratio")
            )

            if city and value is not None:

                ratios[city] = value

    return ratios


def main():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {}

    csv_files = sorted(
        RAW_DIR.glob("*.csv")
    )

    csv_files = [
        f
        for f in csv_files
        if f.name != "income_ratio.csv"
    ]

    print("=" * 60)
    print("台灣住宅房價 / 租金資料建置")
    print("=" * 60)

    print(
        f"找到 CSV：{len(csv_files)} 個"
    )

    if not csv_files:

        print(
            "錯誤：raw 資料夾沒有 CSV"
        )

        OUTPUT_FILE.write_text(
            "[]",
            encoding="utf-8"
        )

        return

    for filepath in csv_files:

        headers, _ = read_csv_file(
            filepath
        )

        if not headers:
            continue

        if is_sales_file(headers):

            process_sales_file(
                filepath,
                result
            )

        elif is_rent_file(headers):

            process_rent_file(
                filepath,
                result
            )

        else:

            print(
                f"無法辨識：{filepath.name}"
            )


    income_ratios = load_income_ratio()

    output = []

    for key in sorted(result.keys()):

        item = result[key]

        prices = item["prices"]
        rents = item["rents"]

        median_price = None
        average_rent = None

        if prices:

            median_price = round(
                statistics.median(prices)
            )

        if rents:

            average_rent = round(
                statistics.mean(rents)
            )

        ratio = income_ratios.get(
            item["city"]
        )

        if (
            median_price is None
            and average_rent is None
        ):
            continue

        output.append({

            "city": item["city"],

            "district": item["district"],

            "median_price_per_ping":
                median_price,

            "average_monthly_rent":
                average_rent,

            "price_income_ratio":
                ratio,
        })


    output.sort(
        key=lambda x: (
            x["city"],
            x["district"]
        )
    )


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )


    print()
    print("=" * 60)
    print("完成！")
    print(
        f"行政區資料筆數：{len(output)}"
    )
    print(
        f"輸出：{OUTPUT_FILE}"
    )
    print("=" * 60)


    rent_count = sum(
        1
        for x in output
        if x["average_monthly_rent"]
        is not None
    )

    price_count = sum(
        1
        for x in output
        if x["median_price_per_ping"]
        is not None
    )

    ratio_count = sum(
        1
        for x in output
        if x["price_income_ratio"]
        is not None
    )

    print(
        f"有房價資料：{price_count}"
    )

    print(
        f"有租金資料：{rent_count}"
    )

    print(
        f"有房價所得比：{ratio_count}"
    )


if __name__ == "__main__":
    main()
