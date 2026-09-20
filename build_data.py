import csv
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import median


# ============================================================
# 基本路徑
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "raw"

DATA_DIR = BASE_DIR / "data"

OUTPUT_FILE = DATA_DIR / "taiwan_housing.json"


DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 行政院主計總處
# 家庭收支調查－平均每戶可支配所得按區域別分
# ============================================================

INCOME_CSV_URL = (
    "https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/232214/"
    "006-%E5%B9%B3%E5%9D%87%E6%AF%8F%E6%88%B6%E5%8F%AF%E6%94%AF%E9%85%8D"
    "%E6%89%80%E5%BE%97%E6%8C%89%E5%8D%80%E5%9F%9F%E5%88%A5%E5%88%86.csv"
)


# ============================================================
# 內政部實價登錄縣市代碼
#
# A = 台北市
# B = 台中市
# C = 基隆市
# D = 台南市
# E = 高雄市
# F = 新北市
# G = 宜蘭縣
# H = 桃園市
# I = 嘉義市
# J = 新竹縣
# K = 苗栗縣
# M = 南投縣
# N = 彰化縣
# O = 新竹市
# P = 雲林縣
# Q = 嘉義縣
# T = 屏東縣
# U = 花蓮縣
# V = 台東縣
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
# 排除離島
# ============================================================

EXCLUDED_CITIES = {

    "澎湖縣",

    "金門縣",

    "連江縣",
}


# ============================================================
# 住宅建物型態
# ============================================================

RESIDENTIAL_KEYWORDS = (

    "住宅大樓",

    "華廈",

    "公寓",

    "透天厝",

    "套房",

    "別墅",

    "住宅",
)


# ============================================================
# 排除非住宅
# ============================================================

EXCLUDED_KEYWORDS = (

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
)


# ============================================================
# 文字清理
# ============================================================

def normalize_text(value):

    if value is None:

        return ""

    return (
        str(value)
        .replace("\ufeff", "")
        .strip()
    )


# ============================================================
# 台 / 臺 統一
# ============================================================

def normalize_city_name(value):

    return (
        normalize_text(value)
        .replace("臺", "台")
    )


# ============================================================
# 數字清理
# ============================================================

def clean_number(value):

    text = normalize_text(value)

    if not text:

        return None

    text = (
        text
        .replace(",", "")
        .replace(" ", "")
        .replace("元", "")
        .replace("平方公尺", "")
    )

    try:

        return float(text)

    except ValueError:

        return None


# ============================================================
# 取得欄位
# ============================================================

def get_field(row, names):

    for name in names:

        if name in row:

            return row[name]

    return ""


# ============================================================
# 讀取 CSV
# ============================================================

def read_csv_file(path):

    encodings = (

        "utf-8-sig",

        "utf-8",

        "cp950",

        "big5",
    )

    last_error = None


    for encoding in encodings:

        try:

            with open(
                path,
                "r",
                encoding=encoding,
                newline=""
            ) as f:

                reader = csv.DictReader(f)

                return list(reader)

        except (
            UnicodeDecodeError,
            UnicodeError
        ) as exc:

            last_error = exc


    raise RuntimeError(
        f"無法讀取 CSV：{path}\n"
        f"{last_error}"
    )


# ============================================================
# 從檔名取得縣市
# ============================================================

def get_city_from_filename(path):

    match = re.match(
        r"^([A-Z])",
        path.name.upper()
    )


    if not match:

        return None


    code = match.group(1)


    city = CITY_CODES.get(
        code
    )


    if city in EXCLUDED_CITIES:

        return None


    return city


# ============================================================
# 取得真正的行政區
#
# 官方欄位：
# 鄉鎮市區
#
# 例如：
# 板橋區
# 中和區
# 三重區
# 新莊區
# ============================================================

def get_district(row):

    district = get_field(
        row,
        (
            "鄉鎮市區",

            "district",

            "District",
        )
    )


    return normalize_text(
        district
    )


# ============================================================
# 判斷是否住宅
# ============================================================

def is_residential(row):

    building_type = normalize_text(
        get_field(
            row,
            (
                "建物型態",

                "rps11",
            )
        )
    )


    main_use = normalize_text(
        get_field(
            row,
            (
                "主要用途",

                "rps12",
            )
        )
    )


    combined = (
        building_type
        + " "
        + main_use
    )


    # ----------------------------------------
    # 排除非住宅
    # ----------------------------------------

    for keyword in EXCLUDED_KEYWORDS:

        if keyword in combined:

            return False


    # ----------------------------------------
    # 建物型態
    # ----------------------------------------

    for keyword in RESIDENTIAL_KEYWORDS:

        if keyword in building_type:

            return True


    # ----------------------------------------
    # 主要用途
    # ----------------------------------------

    if "住家" in main_use:

        return True


    if "住宅" in main_use:

        return True


    return False


# ============================================================
# 找真正的 CSV
#
# 非常重要：
#
# 只抓：
#
# A_lvr_land_a.csv
# A_lvr_land_b.csv
# A_lvr_land_c.csv
#
# 不抓：
#
# A_lvr_land_a_build.csv
# A_lvr_land_a_land.csv
# A_lvr_land_a_park.csv
# ============================================================

def find_csv_files(kind):

    files = []


    for path in RAW_DIR.rglob("*.csv"):

        name = path.name.lower()


        city = get_city_from_filename(
            path
        )


        if not city:

            continue


        # ----------------------------------------
        # 房價
        #
        # a = 買賣
        # b = 預售
        # ----------------------------------------

        if kind == "sales":

            if re.match(
                r"^[a-z]_lvr_land_[ab]\.csv$",
                name
            ):

                files.append(
                    path
                )


        # ----------------------------------------
        # 租金
        #
        # c = 租賃
        # ----------------------------------------

        elif kind == "rent":

            if re.match(
                r"^[a-z]_lvr_land_c\.csv$",
                name
            ):

                files.append(
                    path
                )


    return sorted(
        files
    )


# ============================================================
# 收集房價資料
#
# key：
#
# (city, district)
#
# 例如：
#
# ("新北市", "板橋區")
# ("新北市", "中和區")
# ("新北市", "三重區")
# ============================================================

def collect_sales_data():

    result = defaultdict(
        lambda: {

            "prices": [],

            "price_per_ping": [],
        }
    )


    files = find_csv_files(
        "sales"
    )


    print(
        f"找到房價 CSV：{len(files)} 個"
    )


    for path in files:

        city = get_city_from_filename(
            path
        )


        print(
            f"處理房價：{path.name}"
        )


        rows = read_csv_file(
            path
        )


        for row in rows:

            # ------------------------------------
            # 行政區
            # ------------------------------------

            district = get_district(
                row
            )


            if not district:

                continue


            # ------------------------------------
            # 住宅
            # ------------------------------------

            if not is_residential(
                row
            ):

                continue


            # ------------------------------------
            # 總價
            # ------------------------------------

            total_price = clean_number(
                get_field(
                    row,
                    (
                        "總價元",

                        "總價",
                    )
                )
            )


            # ------------------------------------
            # 單價
            # ------------------------------------

            unit_price = clean_number(
                get_field(
                    row,
                    (
                        "單價元平方公尺",

                        "單價",
                    )
                )
            )


            if (
                total_price is None
                or total_price <= 0
            ):

                continue


            key = (
                city,
                district
            )


            result[key][
                "prices"
            ].append(
                total_price
            )


            # ------------------------------------
            # 元 / 平方公尺
            #
            # →
            #
            # 元 / 坪
            # ------------------------------------

            if (
                unit_price is not None
                and unit_price > 0
            ):

                price_per_ping = (
                    unit_price
                    * 3.305785
                )


                result[key][
                    "price_per_ping"
                ].append(
                    price_per_ping
                )


    return result


# ============================================================
# 收集租金
#
# key：
#
# (city, district)
# ============================================================

def collect_rent_data():

    result = defaultdict(
        list
    )


    files = find_csv_files(
        "rent"
    )


    print(
        f"找到租金 CSV：{len(files)} 個"
    )


    for path in files:

        city = get_city_from_filename(
            path
        )


        print(
            f"處理租金：{path.name}"
        )


        rows = read_csv_file(
            path
        )


        for row in rows:

            # ------------------------------------
            # 行政區
            # ------------------------------------

            district = get_district(
                row
            )


            if not district:

                continue


            # ------------------------------------
            # 住宅
            # ------------------------------------

            if not is_residential(
                row
            ):

                continue


            # ------------------------------------
            # 月租金
            # ------------------------------------

            rent = clean_number(
                get_field(
                    row,
                    (
                        "總額元",

                        "總額",
                    )
                )
            )


            if (
                rent is None
                or rent <= 0
            ):

                continue


            key = (
                city,
                district
            )


            result[key].append(
                rent
            )


    return result


# ============================================================
# 下載主計總處所得 CSV
# ============================================================

def download_income_csv():

    temp_dir = Path(
        tempfile.mkdtemp()
    )


    income_file = (
        temp_dir /
        "income.csv"
    )


    command = [

        "curl",

        "-k",

        "-f",

        "-L",

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


    print(
        "下載主計總處所得資料..."
    )


    subprocess.run(
        command,
        check=True
    )


    if (
        not income_file.exists()
        or income_file.stat().st_size == 0
    ):

        raise RuntimeError(
            "主計總處所得 CSV "
            "下載後是空檔案"
        )


    return income_file


# ============================================================
# 讀取主計總處所得
# ============================================================

def load_income_data():

    income_file = (
        download_income_csv()
    )


    rows = read_csv_file(
        income_file
    )


    if not rows:

        raise RuntimeError(
            "主計總處所得 CSV 沒有資料"
        )


    # ----------------------------------------
    # 找最新一筆年份
    # ----------------------------------------

    latest = None


    for row in reversed(rows):

        year_value = get_field(
            row,
            (
                "年",

                "year",

                "Year",
            )
        )


        if normalize_text(
            year_value
        ):

            latest = row

            break


    if latest is None:

        raise RuntimeError(
            "找不到主計總處所得年份"
        )


    year_text = normalize_text(
        get_field(
            latest,
            (
                "年",

                "year",

                "Year",
            )
        )
    )


    income_map = {}


    # ----------------------------------------
    # 各縣市所得
    # ----------------------------------------

    for key, value in latest.items():

        key = normalize_text(
            key
        )


        if not key:

            continue


        if "元" not in key:

            continue


        city_name = (
            key
            .replace(
                "-元",
                ""
            )
            .strip()
        )


        city_name = normalize_city_name(
            city_name
        )


        number = clean_number(
            value
        )


        if (
            number is None
            or number <= 0
        ):

            continue


        income_map[
            city_name
        ] = number


    print(
        f"所得資料年份：{year_text}"
    )


    print(
        f"所得資料城市數："
        f"{len(income_map)}"
    )


    return (
        income_map,
        year_text
    )


# ============================================================
# 建立 JSON
# ============================================================

def build_output():

    print()
    print("=" * 60)
    print("開始建立台灣住宅資料")
    print("=" * 60)
    print()


    # ========================================================
    # 房價
    # ========================================================

    sales = collect_sales_data()


    # ========================================================
    # 租金
    # ========================================================

    rents = collect_rent_data()


    # ========================================================
    # 所得
    # ========================================================

    (
        income_map,
        income_year
    ) = load_income_data()


    # ========================================================
    # 所有行政區
    # ========================================================

    all_keys = (
        set(sales.keys())
        |
        set(rents.keys())
    )


    output = []


    # ========================================================
    # 每一個縣市 / 行政區
    # ========================================================

    for city, district in sorted(
        all_keys,
        key=lambda item: (
            item[0],
            item[1]
        )
    ):

        sales_info = sales.get(
            (
                city,
                district
            ),
            {}
        )


        prices = sales_info.get(
            "prices",
            []
        )


        price_per_ping = (
            sales_info.get(
                "price_per_ping",
                []
            )
        )


        rent_values = rents.get(
            (
                city,
                district
            ),
            []
        )


        # ----------------------------------------
        # 沒有房價資料
        # ----------------------------------------

        if not prices:

            continue


        # ----------------------------------------
        # 中位數房價
        # ----------------------------------------

        median_total_price = median(
            prices
        )


        # ----------------------------------------
        # 中位數每坪價格
        # ----------------------------------------

        median_price_per_ping = (

            median(
                price_per_ping
            )

            if price_per_ping

            else None
        )


        # ----------------------------------------
        # 平均月租
        # ----------------------------------------

        average_monthly_rent = (

            sum(rent_values)
            /
            len(rent_values)

            if rent_values

            else None
        )


        # ----------------------------------------
        # 縣市平均每戶可支配所得
        # ----------------------------------------

        annual_income = (
            income_map.get(
                city
            )
        )


        # ----------------------------------------
        # 房價所得比
        # ----------------------------------------

        price_income_ratio = None


        if (
            annual_income is not None
            and annual_income > 0
        ):

            price_income_ratio = (
                median_total_price
                /
                annual_income
            )


        # ====================================================
        # JSON
        # ====================================================

        item = {

            # 縣市
            "city":
                city,

            # 真正行政區
            "district":
                district,

            # 中位數房價
            "median_total_price":
                round(
                    median_total_price
                ),

            # 中位數每坪
            "median_price_per_ping":

                (
                    round(
                        median_price_per_ping
                    )

                    if
                    median_price_per_ping
                    is not None

                    else None
                ),

            # 平均月租
            "average_monthly_rent":

                (
                    round(
                        average_monthly_rent
                    )

                    if
                    average_monthly_rent
                    is not None

                    else None
                ),

            # 年可支配所得
            "annual_disposable_income":

                (
                    round(
                        annual_income
                    )

                    if
                    annual_income is not None

                    else None
                ),

            # 所得年份
            "income_year":
                income_year,

            # 房價所得比
            "price_income_ratio":

                (
                    round(
                        price_income_ratio,
                        2
                    )

                    if
                    price_income_ratio
                    is not None

                    else None
                ),
        }


        output.append(
            item
        )


    # ========================================================
    # 最終檢查
    # ========================================================

    if not output:

        raise RuntimeError(
            "沒有產生任何住宅行政區資料。"
            "請檢查 raw CSV。"
        )


    # ========================================================
    # 寫入 JSON
    # ========================================================

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


    # ========================================================
    # 統計
    # ========================================================

    print()
    print("=" * 60)

    print(
        f"完成：{OUTPUT_FILE}"
    )

    print(
        f"資料筆數：{len(output)}"
    )

    print("=" * 60)


    # ========================================================
    # 各縣市行政區統計
    # ========================================================

    city_counts = defaultdict(
        set
    )


    for item in output:

        city_counts[
            item["city"]
        ].add(
            item["district"]
        )


    print()
    print(
        "各縣市行政區數量："
    )


    for city in sorted(
        city_counts
    ):

        districts = sorted(
            city_counts[city]
        )


        print(
            f"{city}："
            f"{len(districts)} 個"
        )


        print(
            "  "
            +
            "、".join(
                districts
            )
        )


    # ========================================================
    # 檢查新北市
    # ========================================================

    print()
    print(
        "新北市行政區檢查："
    )


    new_taipei = [

        item["district"]

        for item in output

        if item["city"] == "新北市"
    ]


    print(
        "、".join(
            sorted(
                new_taipei
            )
        )
    )


    # ========================================================
    # 檢查桃園市
    # ========================================================

    print()
    print(
        "桃園市行政區檢查："
    )


    taoyuan = [

        item["district"]

        for item in output

        if item["city"] == "桃園市"
    ]


    print(
        "、".join(
            sorted(
                taoyuan
            )
        )
    )


    # ========================================================
    # 前 10 筆
    # ========================================================

    print()
    print(
        "前 10 筆資料："
    )


    for item in output[:10]:

        print(
            f"{item['city']} / "
            f"{item['district']} / "
            f"{item['median_total_price']} / "
            f"{item['average_monthly_rent']} / "
            f"{item['price_income_ratio']}"
        )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    build_output()
