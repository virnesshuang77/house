import csv
import json
import statistics
import re
import urllib.request
from pathlib import Path


RAW_DIR = Path("raw")
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "taiwan_housing.json"

PING_PER_SQM = 3.305785


# ============================================================
# 行政區 / 縣市代碼
# ============================================================

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


# ============================================================
# 主計總處
# 平均每戶可支配所得按區域別分
# ============================================================

INCOME_URL = (
    "https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/"
    "232214/006-%E5%B9%B3%E5%9D%87%E6%AF%8F%E6%88%B6%E5%8F%AF%E6%94%AF%E9%85%8D"
    "%E6%89%80%E5%BE%97%E6%8C%89%E5%8D%80%E5%9F%9F%E5%88%A5%E5%88%86.csv"
)


# 主計總處 CSV 欄位名稱
INCOME_CITY_FIELDS = {
    "新北市": "新北市-元",
    "台北市": "臺北市-元",
    "桃園市": "桃園市-元",
    "台中市": "臺中市-元",
    "台南市": "臺南市-元",
    "高雄市": "高雄市-元",
    "宜蘭縣": "宜蘭縣-元",
    "新竹縣": "新竹縣-元",
    "苗栗縣": "苗栗縣-元",
    "彰化縣": "彰化縣-元",
    "南投縣": "南投縣-元",
    "雲林縣": "雲林縣-元",
    "嘉義縣": "嘉義縣-元",
    "屏東縣": "屏東縣-元",
    "台東縣": "臺東縣-元",
    "花蓮縣": "花蓮縣-元",
    "基隆市": "基隆市-元",
    "新竹市": "新竹市-元",
    "嘉義市": "嘉義市-元",
}


# ============================================================
# 基本工具
# ============================================================

def clean_number(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    value = value.replace(",", "")
    value = value.replace(" ", "")
    value = value.replace("　", "")

    # 有些政府 CSV 可能使用「—」
    if value in ["-", "—", "－", "..", "..."]:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def normalize_city_name(city):
    """
    統一 台 / 臺
    """
    if not city:
        return city

    city = str(city).strip()

    replacements = {
        "臺北市": "台北市",
        "臺中市": "台中市",
        "臺南市": "台南市",
        "臺東縣": "台東縣",
    }

    return replacements.get(city, city)


# ============================================================
# 從檔名判斷縣市
# ============================================================

def detect_city_from_filename(filename):

    name = filename.upper()

    match = re.match(r"([A-Z])_", name)

    if not match:
        return None

    code = match.group(1)

    return CITY_CODES.get(code)


# ============================================================
# 判斷 CSV 類型
#
# _a = 買賣
# _b = 預售屋
# _c = 租賃
# ============================================================

def get_file_type(filename):

    name = filename.lower()

    if "_lvr_land_c.csv" in name:
        return "rent"

    if "_lvr_land_a.csv" in name:
        return "sale"

    if "_lvr_land_b.csv" in name:
        return "presale"

    return None


# ============================================================
# CSV 讀取
# ============================================================

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


# ============================================================
# 住宅判斷
# ============================================================

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


# ============================================================
# 行政區
# ============================================================

def get_district(row):

    return str(
        row.get("鄉鎮市區", "")
    ).strip()


# ============================================================
# 房屋單價
# ============================================================

def get_sale_unit_price(row):

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


# ============================================================
# 房屋總價
# ============================================================

def get_sale_total_price(row):

    fields = [
        "總價元",
        "總價",
    ]

    for field in fields:

        value = clean_number(
            row.get(field)
        )

        if value is not None and value > 0:
            return value

    return None


# ============================================================
# 租金
# ============================================================

def get_rent_value(row):

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


# ============================================================
# 處理買賣資料
# ============================================================

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

        total_price = get_sale_total_price(row)

        # 至少要有單價或總價
        if (
            unit_price is None
            and total_price is None
        ):
            continue

        key = f"{city}|{district}"

        if key not in result:

            result[key] = {
                "city": city,
                "district": district,
                "prices": [],
                "total_prices": [],
                "rents": [],
            }

        # 每坪價格
        if unit_price is not None:

            price_per_ping = (
                unit_price
                * PING_PER_SQM
            )

            if price_per_ping > 0:

                result[key]["prices"].append(
                    price_per_ping
                )

        # 房屋總價
        if total_price is not None:

            result[key]["total_prices"].append(
                total_price
            )

        count += 1

    print(
        f"  有效住宅買賣：{count}"
    )


# ============================================================
# 處理租賃資料
# ============================================================

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
                "total_prices": [],
                "rents": [],
            }

        result[key]["rents"].append(
            rent
        )

        count += 1

    print(
        f"  有效住宅租賃：{count}"
    )


# ============================================================
# 下載主計總處所得資料
# ============================================================

def download_income_csv():

    print()
    print("=" * 70)
    print("下載主計總處：平均每戶可支配所得")
    print("=" * 70)

    try:

        request = urllib.request.Request(
            INCOME_URL,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            data = response.read()

        if not data:

            print("所得資料下載失敗：空檔案")

            return None

        print(
            f"所得資料下載完成：{len(data):,} bytes"
        )

        return data

    except Exception as e:

        print("所得資料下載失敗：")
        print(e)

        return None


# ============================================================
# 解析主計總處所得資料
# ============================================================

def load_income_data():

    data = download_income_csv()

    if data is None:
        return {}

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp950",
    ]

    text = None

    for encoding in encodings:

        try:

            text = data.decode(encoding)

            break

        except UnicodeDecodeError:

            continue

    if text is None:

        print("無法解析主計總處所得 CSV")

        return {}

    lines = text.splitlines()

    if not lines:

        return {}

    reader = csv.DictReader(lines)

    rows = list(reader)

    if not rows:

        print("所得 CSV 沒有資料")

        return {}

    # --------------------------------------------------------
    # 找最新年份
    # --------------------------------------------------------

    year_field = None

    if reader.fieldnames:

        for field in reader.fieldnames:

            clean_field = str(field).strip()

            if clean_field in [
                "年",
                "年度",
                "年份",
            ]:

                year_field = field

                break

    if year_field is None:

        print("找不到所得資料的年份欄位")

        return {}

    latest_year = None

    for row in rows:

        value = clean_number(
            row.get(year_field)
        )

        if value is None:
            continue

        year = int(value)

        if (
            latest_year is None
            or year > latest_year
        ):

            latest_year = year

    if latest_year is None:

        print("找不到最新所得年度")

        return {}

    print(
        f"主計總處最新所得年度：{latest_year}"
    )

    latest_row = None

    for row in rows:

        value = clean_number(
            row.get(year_field)
        )

        if value is None:
            continue

        if int(value) == latest_year:

            latest_row = row

            break

    if latest_row is None:

        return {}

    # --------------------------------------------------------
    # 讀取各縣市所得
    # --------------------------------------------------------

    incomes = {}

    for city, field in INCOME_CITY_FIELDS.items():

        value = clean_number(
            latest_row.get(field)
        )

        if value is not None and value > 0:

            incomes[city] = {
                "year": latest_year,
                "annual_disposable_income": round(
                    value
                ),
            }

    print(
        f"成功取得縣市所得：{len(incomes)}"
    )

    return incomes


# ============================================================
# 主程式
# ============================================================

def main():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {}

    csv_files = sorted(
        RAW_DIR.glob("*.csv")
    )

    # 不處理舊版 income_ratio.csv
    csv_files = [
        f
        for f in csv_files
        if f.name != "income_ratio.csv"
    ]

    print("=" * 70)
    print("台灣住宅房價 / 租金 / 所得資料建置")
    print("=" * 70)

    print(
        f"找到 CSV：{len(csv_files)} 個"
    )

    sale_files = 0
    rent_files = 0
    presale_files = 0

    # --------------------------------------------------------
    # 處理內政部資料
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 取得官方所得
    # --------------------------------------------------------

    incomes = load_income_data()

    # --------------------------------------------------------
    # 建立 JSON
    # --------------------------------------------------------

    output = []

    for key in sorted(result.keys()):

        item = result[key]

        prices = item["prices"]

        total_prices = item["total_prices"]

        rents = item["rents"]

        # ----------------------------------------------------
        # 中位數每坪價格
        # ----------------------------------------------------

        median_price = None

        if prices:

            median_price = round(
                statistics.median(prices)
            )

        # ----------------------------------------------------
        # 中位數房屋總價
        # ----------------------------------------------------

        median_total_price = None

        if total_prices:

            median_total_price = round(
                statistics.median(total_prices)
            )

        # ----------------------------------------------------
        # 平均租金
        # ----------------------------------------------------

        average_rent = None

        if rents:

            average_rent = round(
                statistics.mean(rents)
            )

        # ----------------------------------------------------
        # 各縣市平均每戶可支配所得
        # ----------------------------------------------------

        income_info = incomes.get(
            item["city"]
        )

        annual_disposable_income = None
        income_year = None

        if income_info:

            annual_disposable_income = (
                income_info[
                    "annual_disposable_income"
                ]
            )

            income_year = income_info[
                "year"
            ]

        # ----------------------------------------------------
        # 房價所得比
        #
        # = 行政區住宅成交中位總價
        #   /
        #   該縣市平均每戶年可支配所得
        # ----------------------------------------------------

        price_income_ratio = None

        if (
            median_total_price is not None
            and annual_disposable_income is not None
            and annual_disposable_income > 0
        ):

            price_income_ratio = round(
                median_total_price
                / annual_disposable_income,
                2
            )

        # ----------------------------------------------------
        # 如果完全沒有房價與租金
        # 就不輸出
        # ----------------------------------------------------

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

            # 房價
            "median_price_per_ping":
                median_price,

            # 房屋中位總價
            "median_total_price":
                median_total_price,

            # 租金
            "average_monthly_rent":
                average_rent,

            # 所得
            "annual_disposable_income":
                annual_disposable_income,

            # 所得資料年度
            "income_year":
                income_year,

            # 房價所得比
            "price_income_ratio":
                price_income_ratio,

        })

    # --------------------------------------------------------
    # 排序
    # --------------------------------------------------------

    output.sort(
        key=lambda x: (
            x["city"],
            x["district"]
        )
    )

    # --------------------------------------------------------
    # 輸出 JSON
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 統計
    # --------------------------------------------------------

    price_count = sum(
        1
        for item in output
        if item[
            "median_price_per_ping"
        ] is not None
    )

    total_price_count = sum(
        1
        for item in output
        if item[
            "median_total_price"
        ] is not None
    )

    rent_count = sum(
        1
        for item in output
        if item[
            "average_monthly_rent"
        ] is not None
    )

    income_count = sum(
        1
        for item in output
        if item[
            "annual_disposable_income"
        ] is not None
    )

    ratio_count = sum(
        1
        for item in output
        if item[
            "price_income_ratio"
        ] is not None
    )

    # --------------------------------------------------------
    # 完成
    # --------------------------------------------------------

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
        f"有房屋總價資料：{total_price_count}"
    )

    print(
        f"有租金資料：{rent_count}"
    )

    print(
        f"有所得資料：{income_count}"
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
