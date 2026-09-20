import csv
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from statistics import median
from collections import defaultdict


# ============================================================
# 路徑
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "raw"

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(
    exist_ok=True
)

OUTPUT_FILE = (
    DATA_DIR /
    "taiwan_housing.json"
)


# ============================================================
# 官方主計總處所得資料
# ============================================================

INCOME_CSV_URL = (
    "https://ws.dgbas.gov.tw/001/Upload/461/relfile/11525/"
    "232214/006-%E5%B9%B3%E5%9D%87%E6%AF%8F%E6%88%B6%E5%8F%AF%E6%94%AF%E9%85%8D"
    "%E6%89%80%E5%BE%97%E6%8C%89%E5%8D%80%E5%9F%9F%E5%88%A5%E5%88%86.csv"
)


# ============================================================
# 縣市代碼
# 內政部實價登錄檔名第一碼
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


# 排除離島
EXCLUDED_CITIES = {
    "澎湖縣",
    "金門縣",
    "連江縣",
}


# ============================================================
# 住宅關鍵字
# ============================================================

RESIDENTIAL_KEYWORDS = [

    "住宅大樓",

    "華廈",

    "公寓",

    "透天厝",

    "套房",

    "別墅",

    "住宅",

]


EXCLUDED_KEYWORDS = [

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


# ============================================================
# 中文數字 / 欄位工具
# ============================================================

def normalize_text(value):

    if value is None:
        return ""

    return str(value).strip()


def normalize_city_name(value):

    value = normalize_text(value)

    return value.replace(
        "臺",
        "台"
    )


def clean_number(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = (
        text
        .replace(",", "")
        .replace(" ", "")
        .replace("\ufeff", "")
    )

    try:

        return float(text)

    except ValueError:

        return None


# ============================================================
# CSV 讀取
# ============================================================

def read_csv_file(path):

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp950",
        "big5",
    ]

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

                rows = list(reader)

                return rows

        except Exception as e:

            last_error = e

    raise RuntimeError(
        f"無法讀取 CSV：{path}\n{last_error}"
    )


# ============================================================
# 找欄位
# ============================================================

def get_field(row, names):

    for name in names:

        if name in row:

            return row[name]

    return ""


# ============================================================
# 判斷住宅
# ============================================================

def is_residential(row):

    building_type = normalize_text(
        get_field(
            row,
            [
                "建物型態",
                "rps11",
                "建物型態"
            ]
        )
    )

    main_use = normalize_text(
        get_field(
            row,
            [
                "主要用途",
                "rps12",
                "主要用途"
            ]
        )
    )


    # 先排除非住宅
    for keyword in EXCLUDED_KEYWORDS:

        if (
            keyword in building_type
            or keyword in main_use
        ):

            return False


    # 建物型態
    for keyword in RESIDENTIAL_KEYWORDS:

        if keyword in building_type:

            return True


    # 主要用途
    if "住家" in main_use:

        return True


    if "住宅" in main_use:

        return True


    return False


# ============================================================
# 取得行政區
# ============================================================

def get_district(row):

    district = normalize_text(
        get_field(
            row,
            [
                "鄉鎮市區",
                "district",
                "District",
                "rps00",
            ]
        )
    )


    # 清理 BOM
    district = district.replace(
        "\ufeff",
        ""
    ).strip()


    return district


# ============================================================
# 從檔名取得縣市
# ============================================================

def get_city_from_filename(path):

    name = path.name.upper()

    # 例如：
    # A_lvr_land_a.csv
    # A_lvr_land_b.csv
    # A_lvr_land_c.csv

    match = re.match(
        r"^([A-Z])",
        name
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
# 找房價 CSV
# ============================================================

def get_sales_files():

    files = []

    for path in RAW_DIR.rglob("*.csv"):

        name = path.name.lower()

        # a = 買賣
        # b = 預售
        if (
            "_a" in name
            or "_b" in name
        ):

            city = get_city_from_filename(
                path
            )

            if city:

                files.append(
                    path
                )

    return files


# ============================================================
# 找租賃 CSV
# ============================================================

def get_rent_files():

    files = []

    for path in RAW_DIR.rglob("*.csv"):

        name = path.name.lower()

        # c = 租賃
        if "_c" in name:

            city = get_city_from_filename(
                path
            )

            if city:

                files.append(
                    path
                )

    return files


# ============================================================
# 房價資料
# key = (city, district)
# ============================================================

def collect_sales_data():

    result = defaultdict(
        lambda: {

            "prices": [],

            "price_per_ping": []

        }
    )


    files = get_sales_files()


    print(
        f"找到房價 CSV：{len(files)} 個"
    )


    for path in files:

        city = get_city_from_filename(
            path
        )


        if not city:
            continue


        print(
            f"處理房價：{path.name}"
        )


        rows = read_csv_file(
            path
        )


        for row in rows:

            district = get_district(
                row
            )


            if not district:

                continue


            if not is_residential(
                row
            ):

                continue


            total_price = clean_number(
                get_field(
                    row,
                    [
                        "總價元",
                        "rps21",
                        "總價"
                    ]
                )
            )


            unit_price = clean_number(
                get_field(
                    row,
                    [
                        "單價元平方公尺",
                        "rps22",
                        "單價元平方公尺"
                    ]
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


            if (
                unit_price is not None
                and unit_price > 0
            ):

                # 每平方公尺
                # → 每坪
                ping_price = (
                    unit_price *
                    3.305785
                )


                result[key][
                    "price_per_ping"
                ].append(
                    ping_price
                )


    return result


# ============================================================
# 租金資料
# key = (city, district)
# ============================================================

def collect_rent_data():

    result = defaultdict(
        list
    )


    files = get_rent_files()


    print(
        f"找到租金 CSV：{len(files)} 個"
    )


    for path in files:

        city = get_city_from_filename(
            path
        )


        if not city:
            continue


        print(
            f"處理租金：{path.name}"
        )


        rows = read_csv_file(
            path
        )


        for row in rows:

            district = get_district(
                row
            )


            if not district:

                continue


            if not is_residential(
                row
            ):

                continue


            rent = clean_number(
                get_field(
                    row,
                    [
                        "總額元",
                        "rps22",
                        "總額"
                    ]
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
# 下載主計總處所得
# ============================================================

def download_income_csv():

    temp_dir = Path(
        tempfile.mkdtemp()
    )
    income_file = temp_dir / "income.csv"

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


    return income_file


# ============================================================
# 讀取所得
# ============================================================

def load_income_data():

    income_file =
        download_income_csv()


    rows =
        read_csv_file(
            income_file
        )


    if not rows:

        raise RuntimeError(
            "主計總處所得 CSV 沒有資料"
        )


    latest = rows[-1]


    year_value = get_field(
        latest,
        [
            "年",
            "year",
            "Year"
        ]
    )


    year_text =
        normalize_text(
            year_value
        )


    income_map = {}


    for key, value in latest.items():

        if not key:

            continue


        if "元" not in key:

            continue


        city_name =
            key.replace(
                "-元",
                ""
            ).strip()


        city_name =
            normalize_city_name(
                city_name
            )


        number =
            clean_number(
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
        "所得資料年份：",
        year_text
    )


    print(
        "所得資料：",
        income_map
    )


    return (
        income_map,
        year_text
    )


# ============================================================
# 產生最終 JSON
# ============================================================

def build_output():

    sales =
        collect_sales_data()


    rents =
        collect_rent_data()


    income_map, income_year =
        load_income_data()


    # 所有「縣市 + 行政區」
    all_keys =
        set(sales.keys()) |
        set(rents.keys())


    output = []


    for city, district in sorted(
        all_keys,
        key=lambda x: (
            x[0],
            x[1]
        )
    ):

        sales_info =
            sales.get(
                (city, district),
                {}
            )


        prices =
            sales_info.get(
                "prices",
                []
            )


        price_per_ping =
            sales_info.get(
                "price_per_ping",
                []
            )


        rent_values =
            rents.get(
                (city, district),
                []
            )


        if not prices:

            continue


        median_total_price =
            median(
                prices
            )


        median_price_per_ping =
            median(
                price_per_ping
            ) if price_per_ping else None


        average_monthly_rent = (
            sum(rent_values) /
            len(rent_values)
            if rent_values
            else None
        )


        annual_income =
            income_map.get(
                city
            )


        price_income_ratio = None


        if (
            annual_income
            and annual_income > 0
        ):

            price_income_ratio = (
                median_total_price /
                annual_income
            )


        item = {

            "city":
                city,

            "district":
                district,

            "median_total_price":
                round(
                    median_total_price,
                    0
                ),

            "median_price_per_ping":
                round(
                    median_price_per_ping,
                    0
                )
                if median_price_per_ping
                else None,

            "average_monthly_rent":
                round(
                    average_monthly_rent,
                    0
                )
                if average_monthly_rent
                else None,

            "annual_disposable_income":
                round(
                    annual_income,
                    0
                )
                if annual_income
                else None,

            "income_year":
                income_year,

            "price_income_ratio":
                round(
                    price_income_ratio,
                    2
                )
                if price_income_ratio
                else None,
        }


        output.append(
            item
        )


    # ========================================================
    # 寫 JSON
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


    print()
    print(
        "========================================"
    )

    print(
        f"完成：{OUTPUT_FILE}"
    )

    print(
        f"資料筆數：{len(output)}"
    )

    print(
        "========================================"
    )


    # ========================================================
    # 檢查行政區
    # ========================================================

    cities = defaultdict(
        list
    )


    for item in output:

        cities[
            item["city"]
        ].append(
            item["district"]
        )


    for city in sorted(cities):

        print(
            f"{city}："
            f"{len(cities[city])} 個行政區"
        )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    build_output()
