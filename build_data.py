import csv
import json
import statistics
import re
import subprocess
from pathlib import Path


# ============================================================
# 基本設定
# ============================================================

RAW_DIR = Path("raw")
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "taiwan_housing.json"

PING_PER_SQM = 3.305785


# ============================================================
# 台灣縣市代碼
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
#
# Dataset 9415
# 家庭收支調查-平均每戶可支配所得按區域別分
# ============================================================

INCOME_DATASET_URL = (
    "https://data.gov.tw/dataset/9415"
)


# 主計總處 CSV
INCOME_CSV_URL = (
    "https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/"
    "232214/006-%E5%B9%B3%E5%9D%87%E6%AF%8F%E6%88%B6%E5%8F%AF%E6%94%AF%E9%85%8D"
    "%E6%89%80%E5%BE%97%E6%8C%89%E5%8D%80%E5%9F%9F%E5%88%A5%E5%88%86.csv"
)


# ============================================================
# 主計總處縣市欄位
# ============================================================

INCOME_CITY_FIELDS = {

    "台北市": "臺北市-元",
    "新北市": "新北市-元",
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
# 數字清理
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

    try:
        return float(value)

    except ValueError:
        return None


# ============================================================
# 縣市名稱標準化
# ============================================================

def normalize_city_name(name):

    if name is None:
        return ""

    return (
        str(name)
        .strip()
        .replace("臺", "台")
    )


# ============================================================
# 從檔名判斷縣市
# ============================================================

def detect_city_from_filename(filename):

    name = filename.upper()

    match = re.match(
        r"([A-Z])_",
        name
    )

    if not match:
        return None

    code = match.group(1)

    return CITY_CODES.get(code)


# ============================================================
# 判斷資料類型
#
# _a = 買賣
# _b = 預售
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
# 讀 CSV
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

            print(
                f"讀取失敗：{filepath}"
            )

            print(e)

            return [], []


    print(
        f"無法讀取：{filepath}"
    )

    return [], []


# ============================================================
# 判斷是否為住宅
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

        if (
            value is not None
            and value > 0
        ):

            return value


    return None


# ============================================================
# 房屋總價
# ============================================================

def get_total_price(row):

    fields = [

        "總價元",
        "交易總價元",
        "總價",

    ]

    for field in fields:

        value = clean_number(
            row.get(field)
        )

        if (
            value is not None
            and value > 0
        ):

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

        if (
            value is not None
            and value > 0
        ):

            return value


    return None


# ============================================================
# 處理買賣
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


        unit_price = get_sale_unit_price(
            row
        )

        if unit_price is None:

            continue


        price_per_ping = (
            unit_price
            * PING_PER_SQM
        )


        if price_per_ping <= 0:

            continue


        total_price = get_total_price(
            row
        )


        key = (
            f"{city}|{district}"
        )


        if key not in result:

            result[key] = {

                "city": city,

                "district": district,

                "prices": [],

                "total_prices": [],

                "rents": [],

            }


        result[key]["prices"].append(
            price_per_ping
        )


        if total_price is not None:

            result[key]["total_prices"].append(
                total_price
            )


        count += 1


    print(
        f"  有效住宅買賣：{count}"
    )


# ============================================================
# 處理租賃
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


        rent = get_rent_value(
            row
        )

        if rent is None:

            continue


        if rent <= 0:

            continue


        key = (
            f"{city}|{district}"
        )


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
# 下載主計總處 CSV
#
# 重要：
# 不再使用 Python urllib
#
# 改用 GitHub Runner 上的 curl
# 避免 urllib SSL CERTIFICATE_VERIFY_FAILED
# ============================================================

def download_income_csv():

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    income_file = (
        RAW_DIR
        / "income_latest.csv"
    )


    print()
    print("=" * 70)
    print("下載主計總處家庭收支資料")
    print("=" * 70)


    print(
        f"資料來源：{INCOME_DATASET_URL}"
    )


    print(
        "使用 curl 下載官方 CSV..."
    )


    command = [

        "curl",

        "-fL",

        "--retry",
        "3",

        "--retry-delay",
        "2",

        "--connect-timeout",
        "30",

        "--max-time",
        "120",

        "-A",
        "Mozilla/5.0",

        "-o",
        str(income_file),

        INCOME_CSV_URL,

    ]


    try:

        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            check=False,

        )


    except FileNotFoundError:

        raise RuntimeError(
            "GitHub Runner 找不到 curl。"
        )


    if result.returncode != 0:

        print()
        print(
            "curl 下載失敗："
        )

        print(
            result.stderr
        )


        raise RuntimeError(
            "無法下載主計總處官方所得資料。"
        )


    if not income_file.exists():

        raise RuntimeError(
            "curl 執行完成，但所得 CSV 不存在。"
        )


    file_size = (
        income_file.stat().st_size
    )


    if file_size == 0:

        raise RuntimeError(
            "所得 CSV 是空檔案。"
        )


    print(
        f"所得資料下載完成。"
    )


    print(
        f"檔案大小：{file_size:,} bytes"
    )


    return income_file


# ============================================================
# 解析所得資料
# ============================================================

def load_income_data():

    income_file = (
        download_income_csv()
    )


    headers, rows = read_csv_file(
        income_file
    )


    if not headers:

        raise RuntimeError(
            "主計總處所得 CSV 沒有欄位。"
        )


    if not rows:

        raise RuntimeError(
            "主計總處所得 CSV 沒有資料。"
        )


    print()
    print(
        f"所得資料筆數：{len(rows)}"
    )


    # --------------------------------------------------------
    # 找最新年度
    # --------------------------------------------------------

    year_rows = []


    for row in rows:

        year_raw = str(
            row.get("年", "")
        ).strip()


        match = re.search(
            r"(19|20)\d{2}",
            year_raw
        )


        if not match:

            continue


        year = int(
            match.group(0)
        )


        year_rows.append(
            (
                year,
                row
            )
        )


    if not year_rows:

        raise RuntimeError(
            "無法從所得 CSV 判斷年度。"
        )


    latest_year = max(
        year
        for year, row
        in year_rows
    )


    latest_rows = [

        row

        for year, row
        in year_rows

        if year == latest_year

    ]


    if not latest_rows:

        raise RuntimeError(
            "找不到最新年度所得資料。"
        )


    latest_row = latest_rows[-1]


    print(
        f"最新所得年度：{latest_year}"
    )


    # --------------------------------------------------------
    # 各縣市所得
    # --------------------------------------------------------

    income_data = {}


    for city, field in INCOME_CITY_FIELDS.items():

        value = clean_number(
            latest_row.get(field)
        )


        if (
            value is not None
            and value > 0
        ):

            income_data[city] = {

                "income": round(value),

                "year": latest_year,

            }


            print(
                f"  {city}: "
                f"{value:,.0f} 元"
            )


        else:

            print(
                f"  WARNING："
                f"{city} 找不到所得資料"
            )


    print()
    print(
        f"成功取得縣市所得："
        f"{len(income_data)}"
    )


    if len(income_data) < 10:

        raise RuntimeError(
            "成功取得的縣市所得資料過少，"
            "可能是官方 CSV 欄位格式發生變化。"
        )


    return income_data


# ============================================================
# 主程式
# ============================================================

def main():

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    result = {}


    # --------------------------------------------------------
    # 只處理真正的主資料
    #
    # 不再把 build / land / park / schema 等檔案
    # 當成主要 CSV
    # --------------------------------------------------------

    csv_files = []


    for filepath in sorted(
        RAW_DIR.glob("*.csv")
    ):

        file_type = get_file_type(
            filepath.name
        )


        if file_type in (
            "sale",
            "rent",
            "presale"
        ):

            csv_files.append(
                filepath
            )


    print()
    print("=" * 70)
    print("台灣住宅房價 / 租金 / 所得資料建置")
    print("=" * 70)


    print(
        f"找到主要內政部 CSV："
        f"{len(csv_files)} 個"
    )


    sale_files = 0
    rent_files = 0
    presale_files = 0


    # --------------------------------------------------------
    # 處理資料
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
                f"跳過預售屋："
                f"{filepath.name}"
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
    # 取得所得
    # --------------------------------------------------------

    income_data = (
        load_income_data()
    )


    # --------------------------------------------------------
    # 建立 JSON
    # --------------------------------------------------------

    output = []


    for key in sorted(
        result.keys()
    ):

        item = result[key]


        prices = (
            item["prices"]
        )


        total_prices = (
            item["total_prices"]
        )


        rents = (
            item["rents"]
        )


        # ----------------------------------------------------
        # 中位數單價
        # ----------------------------------------------------

        median_price = None


        if prices:

            median_price = round(
                statistics.median(
                    prices
                )
            )


        # ----------------------------------------------------
        # 中位數總價
        # ----------------------------------------------------

        median_total_price = None


        if total_prices:

            median_total_price = round(
                statistics.median(
                    total_prices
                )
            )


        # ----------------------------------------------------
        # 平均租金
        # ----------------------------------------------------

        average_rent = None


        if rents:

            average_rent = round(
                statistics.mean(
                    rents
                )
            )


        # ----------------------------------------------------
        # 所得
        # ----------------------------------------------------

        city = item["city"]


        income_info = (
            income_data.get(city)
        )


        annual_disposable_income = None

        income_year = None

        price_income_ratio = None


        if income_info:

            annual_disposable_income = (
                income_info["income"]
            )


            income_year = (
                income_info["year"]
            )


            # ------------------------------------------------
            # 房價 / 所得
            #
            # 中位數總價
            # ÷
            # 年平均每戶可支配所得
            # ------------------------------------------------

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
        # 沒有任何資料就跳過
        # ----------------------------------------------------

        if (
            median_price is None
            and average_rent is None
        ):

            continue


        output.append({

            "city":
                city,

            "district":
                item["district"],

            "median_price_per_ping":
                median_price,

            "median_total_price":
                median_total_price,

            "average_monthly_rent":
                average_rent,

            "annual_disposable_income":
                annual_disposable_income,

            "income_year":
                income_year,

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

        if (
            item[
                "median_price_per_ping"
            ]
            is not None
        )

    )


    total_price_count = sum(

        1

        for item in output

        if (
            item[
                "median_total_price"
            ]
            is not None
        )

    )


    rent_count = sum(

        1

        for item in output

        if (
            item[
                "average_monthly_rent"
            ]
            is not None
        )

    )


    ratio_count = sum(

        1

        for item in output

        if (
            item[
                "price_income_ratio"
            ]
            is not None
        )

    )


    print()
    print("=" * 70)
    print("完成！")
    print("=" * 70)


    print(
        f"行政區資料筆數："
        f"{len(output)}"
    )


    print(
        f"有房價資料："
        f"{price_count}"
    )


    print(
        f"有房屋總價資料："
        f"{total_price_count}"
    )


    print(
        f"有租金資料："
        f"{rent_count}"
    )


    print(
        f"有房價所得比："
        f"{ratio_count}"
    )


    print(
        f"輸出："
        f"{OUTPUT_FILE}"
    )


    print("=" * 70)


# ============================================================
# 執行
# ============================================================

if __name__ == "__main__":

    main()
