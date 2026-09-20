import csv
import json
import os
import re
import statistics
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

    # 以下排除離島
    "U": None,  # 澎湖縣
    "V": None,  # 金門縣
    "W": None,  # 連江縣
}


def clean_number(value):
    """把 CSV 裡的數字轉成 float。"""
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
    """
    從內政部實價登錄檔名判斷縣市。

    例如：
    A_lvr_land_a.csv -> 台北市
    F_lvr_land_a.csv -> 新北市
    H_lvr_land_a.csv -> 桃園市
    """

    name = filename.upper()

    match = re.match(r"([A-W])_", name)

    if not match:
        return None

    code = match.group(1)

    return CITY_CODES.get(code)


def is_sales_file(headers):
    """判斷是不是買賣資料。"""

    headers = set(headers)

    return (
        "交易年月日" in headers
        and "總價元" in headers
        and "單價元平方公尺" in headers
    )


def is_rent_file(headers):
    """判斷是不是租賃資料。"""

    headers = set(headers)

    return (
        "租賃年月日" in headers
        and (
            "租金總額" in headers
            or "每月租金" in headers
            or "租金" in headers
        )
    )


def is_residential(row):
    """
    判斷是否屬於住宅用途。
    """

    building_type = str(row.get("建物型態", "")).strip()
    main_use = str(row.get("主要用途", "")).strip()
    target = str(row.get("交易標的", "")).strip()

    text = f"{building_type} {main_use} {target}"

    # 明確排除比較不像住宅的用途
    excluded_keywords = [
        "工廠",
        "廠房",
        "辦公",
        "辦公室",
        "店面",
        "商業",
        "倉庫",
        "農舍",
        "墓地",
        "停車位",
        "車位",
    ]

    if any(keyword in text for keyword in excluded_keywords):
        return False

    # 常見住宅型態
    residential_keywords = [
        "住宅大樓",
        "華廈",
        "公寓",
        "透天厝",
        "套房",
        "別墅",
        "住宅",
    ]

    if any(keyword in text for keyword in residential_keywords):
        return True

    # 主要用途如果明確包含住家
    if "住家" in main_use:
        return True

    return False


def read_csv_file(filepath):
    """
    讀取內政部 UTF-8 CSV。
    """

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
                newline="",
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

    print(f"無法判斷編碼：{filepath}")

    return [], []


def process_sales_file(filepath, result):

    city = detect_city_from_filename(filepath.name)

    if not city:
        print(f"跳過離島或無法辨識縣市：{filepath.name}")
        return

    headers, rows = read_csv_file(filepath)

    if not headers:
        return

    if not is_sales_file(headers):
        return

    print(f"處理買賣：{filepath.name} -> {city}")

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

        # 元/平方公尺 -> 元/坪
        price_per_ping = unit_price * PING_PER_SQM

        if price_per_ping <= 0:
            continue

        key = f"{city}|{district}"

        if key not in result:
            result[key] = {
                "city": city,
                "district": district,
                "prices": [],
                "rents": [],
            }

        result[key]["prices"].append(price_per_ping)

        count += 1

    print(f"  有效住宅買賣：{count}")


def find_rent_value(row):

    possible_fields = [
        "租金總額",
        "每月租金",
        "租金",
        "租金總價",
    ]

    for field in possible_fields:

        if field not in row:
            continue

        value = clean_number(row.get(field))

        if value is not None and value > 0:
            return value

    return None


def process_rent_file(filepath, result):

    city = detect_city_from_filename(filepath.name)

    if not city:
        print(f"跳過離島或無法辨識縣市：{filepath.name}")
        return

    headers, rows = read_csv_file(filepath)

    if not headers:
        return

    if not is_rent_file(headers):
        return

    print(f"處理租賃：{filepath.name} -> {city}")

    count = 0

    for row in rows:

        if not is_residential(row):
            continue

        district = str(
            row.get("鄉鎮市區", "")
        ).strip()

        if not district:
            continue

        rent = find_rent_value(row)

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

        result[key]["rents"].append(rent)

        count += 1

    print(f"  有效住宅租賃：{count}")


def load_income_ratio():

    filepath = RAW_DIR / "income_ratio.csv"

    ratios = {}

    if not filepath.exists():
        print("找不到 raw/income_ratio.csv")
        return ratios

    with open(
        filepath,
        "r",
        encoding="utf-8-sig",
        newline="",
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

    # 排除收入倍率 CSV
    csv_files = [
        f
        for f in csv_files
        if f.name != "income_ratio.csv"
    ]

    print("=" * 60)
    print("台灣住宅房價 / 租金資料建置")
    print("=" * 60)

    print(f"找到 CSV：{len(csv_files)} 個")

    if not csv_files:
        print("錯誤：raw 資料夾沒有實價登錄 CSV")
        OUTPUT_FILE.write_text(
            "[]",
            encoding="utf-8"
        )
        return

    for filepath in csv_files:

        headers, _ = read_csv_file(filepath)

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
                f"無法辨識資料類型：{filepath.name}"
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

        # 至少要有房價或租金資料
        if (
            median_price is None
            and average_rent is None
        ):
            continue

        output.append({
            "city": item["city"],
            "district": item["district"],
            "median_price_per_ping": median_price,
            "average_monthly_rent": average_rent,
            "price_income_ratio": ratio,
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
    print(f"完成！")
    print(f"行政區資料筆數：{len(output)}")
    print(f"輸出：{OUTPUT_FILE}")
    print("=" * 60)

    if len(output) == 0:
        print()
        print("警告：最後產生 0 筆資料")
        print("請檢查 raw/ 裡面的 CSV 是否正確下載。")


if __name__ == "__main__":
    main()
