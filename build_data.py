import csv
import json
import statistics
from pathlib import Path


# ============================================================
# 基本路徑
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "raw"

DATA_DIR = BASE_DIR / "data"

OUTPUT_FILE = DATA_DIR / "taiwan_housing.json"

INCOME_RATIO_FILE = RAW_DIR / "income_ratio.csv"


# ============================================================
# 台灣本島縣市
# 不包含澎湖、金門、連江
# ============================================================

TAIWAN_MAIN_ISLAND = {

    "台北市",
    "新北市",
    "桃園市",
    "台中市",
    "台南市",
    "高雄市",

    "基隆市",
    "新竹市",
    "嘉義市",

    "新竹縣",
    "苗栗縣",
    "彰化縣",
    "南投縣",
    "雲林縣",
    "嘉義縣",
    "屏東縣",
    "宜蘭縣",
    "花蓮縣",
    "台東縣"

}


# ============================================================
# 讀取數字
# ============================================================

def to_number(value):

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    value = (
        value
        .replace(",", "")
        .replace(" ", "")
        .replace("元", "")
    )

    try:
        return float(value)

    except ValueError:
        return None


# ============================================================
# 讀取 CSV
# 自動嘗試 UTF-8 / Big5 / CP950
# ============================================================

def read_csv_file(file_path):

    encodings = [
        "utf-8-sig",
        "utf-8",
        "big5",
        "cp950"
    ]

    last_error = None

    for encoding in encodings:

        try:

            with open(
                file_path,
                "r",
                encoding=encoding,
                newline=""
            ) as file:

                return list(
                    csv.DictReader(file)
                )

        except UnicodeDecodeError as error:

            last_error = error


    raise last_error


# ============================================================
# 尋找欄位
# ============================================================

def get_field(row, possible_names):

    # 完全相同
    for name in possible_names:

        if name in row:

            value = row[name]

            if value is not None:

                return value


    # 模糊比對
    for key in row.keys():

        if key is None:
            continue

        for name in possible_names:

            if name in key:

                value = row[key]

                if value is not None:

                    return value


    return None


# ============================================================
# 取得縣市
# ============================================================

def get_city(row):

    value = get_field(
        row,
        [
            "縣市",
            "縣市名稱",
            "縣市別"
        ]
    )

    if value is None:
        return None

    value = str(value).strip()

    if value not in TAIWAN_MAIN_ISLAND:

        return None

    return value


# ============================================================
# 取得行政區
# ============================================================

def get_district(row):

    value = get_field(
        row,
        [
            "鄉鎮市區",
            "鄉鎮市區名稱",
            "行政區"
        ]
    )

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


# ============================================================
# 判斷是否為住宅
# ============================================================

def is_residential(row):

    building_type = get_field(
        row,
        [
            "建物型態",
            "建物型態名稱"
        ]
    )

    purpose = get_field(
        row,
        [
            "主要用途",
            "主要用途名稱"
        ]
    )


    text = ""

    if building_type:
        text += str(building_type)

    if purpose:
        text += str(purpose)


    residential_keywords = [

        "住宅大樓",
        "華廈",
        "公寓",
        "透天厝",
        "套房",
        "住家用",
        "住宅"

    ]


    return any(
        keyword in text
        for keyword in residential_keywords
    )


# ============================================================
# 取得房價單價
#
# 最終統一成「元 / 坪」
# ============================================================

def get_price_per_ping(row):

    # --------------------------------------------------------
    # 先找「元/坪」
    # --------------------------------------------------------

    for field_name in [
        "單價(元/坪)",
        "單價元/坪",
        "單價"
    ]:

        if field_name in row:

            value = to_number(
                row[field_name]
            )

            if value is not None:

                # 有些資料可能是萬元/坪
                if value < 1000:

                    value *= 10000

                return value


    # --------------------------------------------------------
    # 如果是「元/平方公尺」
    # 轉換成元/坪
    #
    # 1 坪 = 3.305785 平方公尺
    # --------------------------------------------------------

    for field_name in [
        "單價(元/平方公尺)",
        "單價元平方公尺"
    ]:

        if field_name in row:

            value = to_number(
                row[field_name]
            )

            if value is not None:

                return value * 3.305785


    return None


# ============================================================
# 取得租金
# ============================================================

def get_monthly_rent(row):

    value = get_field(
        row,
        [
            "租金總額",
            "總額(元/月)",
            "租金總額(元/月)",
            "每月租金"
        ]
    )

    value = to_number(value)

    if value is None:
        return None

    return value


# ============================================================
# 判斷是否為合理房價
# 避免異常資料污染統計
# ============================================================

def valid_price(value):

    if value is None:
        return False

    return (
        10000
        <= value
        <= 3000000
    )


# ============================================================
# 判斷是否為合理租金
# ============================================================

def valid_rent(value):

    if value is None:
        return False

    return (
        500
        <= value
        <= 200000
    )


# ============================================================
# 載入房價所得比
# ============================================================

def load_income_ratio():

    ratios = {}

    if not INCOME_RATIO_FILE.exists():

        print(
            "找不到 income_ratio.csv，"
            "房價所得比將暫時顯示為空值。"
        )

        return ratios


    rows = read_csv_file(
        INCOME_RATIO_FILE
    )


    for row in rows:

        city = (
            row.get("city")
            or row.get("縣市")
            or ""
        ).strip()


        ratio = (
            row.get("ratio")
            or row.get("房價所得比")
        )


        ratio = to_number(ratio)


        if city and ratio is not None:

            ratios[city] = ratio


    return ratios


# ============================================================
# 掃描原始 CSV
# ============================================================

def load_raw_data():

    buy_data = []

    rent_data = []


    csv_files = sorted(
        RAW_DIR.glob("*.csv")
    )


    # income_ratio.csv 不算實價登錄
    csv_files = [
        file
        for file in csv_files
        if file.name != "income_ratio.csv"
    ]


    print(
        f"找到 {len(csv_files)} 個 CSV 檔案"
    )


    for file_path in csv_files:

        print(
            f"讀取：{file_path.name}"
        )


        try:

            rows = read_csv_file(
                file_path
            )

        except Exception as error:

            print(
                f"讀取失敗：{error}"
            )

            continue


        if not rows:
            continue


        # ----------------------------------------------------
        # 根據欄位判斷買賣或租賃
        # ----------------------------------------------------

        keys = " ".join(
            rows[0].keys()
        )


        if (
            "租金" in keys
            or "租賃" in keys
        ):

            rent_data.extend(rows)

            print(
                f"  → 租賃資料：{len(rows)} 筆"
            )


        else:

            buy_data.extend(rows)

            print(
                f"  → 買賣資料：{len(rows)} 筆"
            )


    return buy_data, rent_data


# ============================================================
# 建立房價資料
# ============================================================

def build_price_data(rows):

    result = {}


    for row in rows:

        city = get_city(row)

        if city is None:
            continue


        district = get_district(row)

        if district is None:
            continue


        if not is_residential(row):
            continue


        price = get_price_per_ping(row)


        if not valid_price(price):
            continue


        key = (
            city,
            district
        )


        if key not in result:

            result[key] = []


        result[key].append(price)


    return result


# ============================================================
# 建立租金資料
# ============================================================

def build_rent_data(rows):

    result = {}


    for row in rows:

        city = get_city(row)

        if city is None:
            continue


        district = get_district(row)

        if district is None:
            continue


        if not is_residential(row):
            continue


        rent = get_monthly_rent(row)


        if not valid_rent(rent):
            continue


        key = (
            city,
            district
        )


        if key not in result:

            result[key] = []


        result[key].append(rent)


    return result


# ============================================================
# 建立最終 JSON
# ============================================================

def create_output(
    price_data,
    rent_data,
    income_ratios
):

    all_keys = set()

    all_keys.update(
        price_data.keys()
    )

    all_keys.update(
        rent_data.keys()
    )


    output = []


    for city, district in sorted(
        all_keys,
        key=lambda x: (
            x[0],
            x[1]
        )
    ):

        prices = price_data.get(
            (city, district),
            []
        )


        rents = rent_data.get(
            (city, district),
            []
        )


        # ----------------------------------------------------
        # 房價：中位數
        # ----------------------------------------------------

        median_price = None

        if prices:

            median_price = round(
                statistics.median(
                    prices
                )
            )


        # ----------------------------------------------------
        # 租金：平均值
        # ----------------------------------------------------

        average_rent = None

        if rents:

            average_rent = round(
                statistics.mean(
                    rents
                )
            )


        # ----------------------------------------------------
        # 房價所得比
        #
        # 官方目前主要提供縣市層級，
        # 所以行政區沿用所屬縣市值。
        # ----------------------------------------------------

        income_ratio = income_ratios.get(
            city
        )


        item = {

            "city": city,

            "district": district,

            "median_price_per_ping":
                median_price,

            "average_monthly_rent":
                average_rent,

            "price_income_ratio":
                income_ratio,

            "price_sample_count":
                len(prices),

            "rent_sample_count":
                len(rents)

        }


        output.append(item)


    return output


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 60)
    print("台灣行政區房價資料建立程式")
    print("=" * 60)
    print()


    # --------------------------------------------------------
    # 建立資料夾
    # --------------------------------------------------------

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # --------------------------------------------------------
    # 讀取原始資料
    # --------------------------------------------------------

    buy_rows, rent_rows = load_raw_data()


    print()
    print(
        f"買賣資料總筆數：{len(buy_rows):,}"
    )

    print(
        f"租賃資料總筆數：{len(rent_rows):,}"
    )


    # --------------------------------------------------------
    # 房價
    # --------------------------------------------------------

    print()
    print("開始整理房價...")


    price_data = build_price_data(
        buy_rows
    )


    print(
        f"房價行政區數：{len(price_data)}"
    )


    # --------------------------------------------------------
    # 租金
    # --------------------------------------------------------

    print()
    print("開始整理租金...")


    rent_data = build_rent_data(
        rent_rows
    )


    print(
        f"租金行政區數：{len(rent_data)}"
    )


    # --------------------------------------------------------
    # 房價所得比
    # --------------------------------------------------------

    income_ratios = load_income_ratio()


    # --------------------------------------------------------
    # 建立最終資料
    # --------------------------------------------------------

    output = create_output(
        price_data,
        rent_data,
        income_ratios
    )


    # --------------------------------------------------------
    # 輸出 JSON
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )


    print()
    print("=" * 60)
    print("完成！")
    print("=" * 60)
    print()
    print(
        f"輸出檔案：{OUTPUT_FILE}"
    )
    print(
        f"行政區資料：{len(output)} 筆"
    )
    print()


# ============================================================
# 執行
# ============================================================

if __name__ == "__main__":

    main()
