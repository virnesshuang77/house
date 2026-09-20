import csv
import json
import statistics
import re
from pathlib import Path


RAW_DIR = Path("raw")
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "taiwan_housing.json"

PING_PER_SQM = 3.305785


# 內政部實價登錄檔名前綴 → 縣市
#
# A 台北市
# B 台中市
# C 基隆市
# D 台南市
# E 高雄市
# F 新北市
# G 宜蘭縣
# H 桃園市
# I 嘉義市
# J 新竹縣
# K 苗栗縣
# M 南投縣
# N 彰化縣
# O 新竹市
# P 雲林縣
# Q 嘉義縣
# T 屏東縣
# U 花蓮縣
# V 台東縣
#
# W 金門
# X 澎湖
# Z 連江
#
# 台灣本島只保留到 V。
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
    "T": "屏東縣",
    "U": "花蓮縣",
    "V": "台東縣",
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


def get_file_type(filename):

    """
    依照內政部實價登錄檔名判斷資料類型。

    _a = 買賣
    _b = 預售屋
    _c = 租賃
    """

    name = filename.lower()

    if "_lvr_land_c.csv" in name:
        return "rent"

    if "_lvr_land_a.csv" in name:
        return "sale"

    if "_lvr_land_b.csv" in name:
        return "presale"

    return None


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

    print(f"無法讀取：{filepath}")

    return [], []


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

    text = (
        building_type
        + " "
        + main_use
        + " "
        + target
    )

    # 明確排除
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

    # 住宅
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


def get_district(row):

    return str(
        row.get("鄉鎮市區", "")
    ).strip()


def get_sale_unit_price(row):

    # 目前官方欄位
    fields = [
        "單價元平方公尺",
        "單價每平方公尺",
    ]

    for field in fields:

        value = clean_number(
            row.get(field)
        )

        if value is not None and value > 0:
            return value

    return None


def get_rent_value(row):

    # 目前官方租賃資料使用「總額元」
    fields = [
        "總額元",
        "租金總額",
        "每月租金",
        "租金",
    ]

    for field in fields:

        value = clean_number(
            row.get(field)
        )

        if value is not None and value > 0:
            return value

    return None


def process_sale_file(filepath, result):

    city = detect_city_from_filename(
        filepath.name
    )

    if not city:
        print(
            f"跳過非本島縣市：{filepath.name}"
        )
        return

    headers, rows = read_csv_file(
        filepath
    )

    if not headers:
        return

    print(
        f"處理買賣：{filepath.name} -> {city}"
    )

    count = 0

    for row in rows:

        if not is_residential(row):
            continue

        district = get_district(row)

        if not district:
            continue

        unit_price = get_sale_unit_price(row)

        if unit_price is None:
            continue

        price_per_ping = (
            unit_price
            * PING_PER_SQM
        )

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
        print(
            f"跳過非本島縣市：{filepath.name}"
        )
        return

    headers, rows = read_csv_file(
        filepath
    )

    if not headers:
        return

    print(
        f"處理租賃：{filepath.name} -> {city}"
    )

    count = 0

    for row in rows:

        if not is_residential(row):
            continue

        district = get_district(row)

        if not district:
            continue

        rent = get_rent_value(row)

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

    # 不處理所得表
    csv_files = [
        f
        for f in csv_files
        if f.name != "income_ratio.csv"
    ]

    print("=" * 70)
    print("台灣住宅房價 / 租金資料建置")
    print("=" * 70)

    print(
        f"找到 CSV：{len(csv_files)} 個"
    )

    sale_files = 0
    rent_files = 0
    presale_files = 0

    for filepath in csv_files:

        file_type = get_file_type(
            filepath.name
        )

        if file_type == "sale":

            sale_files += 1

            process_sale_file(
                filepath,
                result
            )

        elif file_type == "rent":

            rent_files += 1

            process_rent_file(
                filepath,
                result
            )

        elif file_type == "presale":

            presale_files += 1

            print(
                f"跳過預售屋：{filepath.name}"
            )

        else:

            print(
                f"跳過其他檔案：{filepath.name}"
            )


    print()
    print(
        f"買賣主檔：{sale_files}"
    )

    print(
        f"租賃主檔：{rent_files}"
    )

    print(
        f"預售屋主檔：{presale_files}"
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

            "city":
                item["city"],

            "district":
                item["district"],

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


    price_count = sum(
        1
        for item in output
        if item[
            "median_price_per_ping"
        ] is not None
    )

    rent_count = sum(
        1
        for item in output
        if item[
            "average_monthly_rent"
        ] is not None
    )

    ratio_count = sum(
        1
        for item in output
        if item[
            "price_income_ratio"
        ] is not None
    )


    print()
    print("=" * 70)
    print("完成！")
    print("=" * 70)

    print(
        f"行政區資料筆數：{len(output)}"
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

    print(
        f"輸出：{OUTPUT_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
