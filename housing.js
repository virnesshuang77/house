const tableBody = document.getElementById("tableBody");
const citySelect = document.getElementById("citySelect");
const searchInput = document.getElementById("searchInput");
const count = document.getElementById("count");

let housingData = [];


// ============================================================
// 格式化數字
// ============================================================

function formatNumber(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return number.toLocaleString("zh-TW");
}


// ============================================================
// 格式化房價
// ============================================================

function formatPrice(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return formatNumber(number) + " 元/坪";
}


// ============================================================
// 格式化租金
// ============================================================

function formatRent(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return formatNumber(number) + " 元/月";
}


// ============================================================
// 格式化房價所得比
// ============================================================

function formatIncomeRatio(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return number.toFixed(2) + " 倍";
}


// ============================================================
// 建立縣市選單
// ============================================================

function createCitySelect() {

    // 避免重複建立選項
    citySelect.innerHTML = `
        <option value="">
            全部縣市
        </option>
    `;

    const cities = [
        ...new Set(
            housingData
                .map(item => item.city)
                .filter(city => city)
        )
    ];

    cities.sort((a, b) =>
        a.localeCompare(b, "zh-TW")
    );

    cities.forEach(city => {

        const option =
            document.createElement("option");

        option.value = city;

        option.textContent = city;

        citySelect.appendChild(option);

    });
}


// ============================================================
// 顯示表格
// ============================================================

function renderTable() {

    const selectedCity =
        citySelect.value;

    const keyword =
        searchInput.value
            .trim()
            .toLowerCase();


    // --------------------------------------------------------
    // 篩選
    // --------------------------------------------------------

    const filteredData =
        housingData.filter(item => {

            const cityMatch =
                !selectedCity ||
                item.city === selectedCity;


            const districtName =
                `${item.city}${item.district}`;


            const keywordMatch =
                !keyword ||
                districtName
                    .toLowerCase()
                    .includes(keyword);


            return cityMatch && keywordMatch;

        });


    // --------------------------------------------------------
    // 顯示筆數
    // --------------------------------------------------------

    count.textContent =
        `共 ${filteredData.length} 個行政區`;


    // --------------------------------------------------------
    // 沒有搜尋結果
    // --------------------------------------------------------

    if (filteredData.length === 0) {

        tableBody.innerHTML = `

            <tr>

                <td
                    colspan="4"
                    class="empty"
                >
                    找不到符合的行政區
                </td>

            </tr>

        `;

        return;
    }


    // --------------------------------------------------------
    // 建立表格
    // --------------------------------------------------------

    tableBody.innerHTML =
        filteredData.map(item => {

            const districtName =
                `${item.city}${item.district}`;


            return `

                <tr>

                    <!-- 行政區 -->

                    <td>
                        ${districtName}
                    </td>


                    <!-- 中位數房價 -->

                    <td class="number">

                        ${formatPrice(
                            item.median_price_per_ping
                        )}

                    </td>


                    <!-- 平均租金 -->

                    <td class="number">

                        ${formatRent(
                            item.average_monthly_rent
                        )}

                    </td>


                    <!-- 房價所得比 -->

                    <td class="number">

                        ${formatIncomeRatio(
                            item.price_income_ratio
                        )}

                    </td>

                </tr>

            `;

        }).join("");

}


// ============================================================
// 讀取 JSON
// ============================================================

async function loadHousingData() {

    try {

        /*
         * 加 ?v=3
         * 避免 GitHub Pages / 瀏覽器繼續使用舊 JSON
         */

        const response =
            await fetch(
                "data/taiwan_housing.json?v=3",
                {
                    cache: "no-store"
                }
            );


        // ----------------------------------------------------
        // HTTP 錯誤
        // ----------------------------------------------------

        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );

        }


        // ----------------------------------------------------
        // 解析 JSON
        // ----------------------------------------------------

        housingData =
            await response.json();


        // ----------------------------------------------------
        // 確認 JSON 是陣列
        // ----------------------------------------------------

        if (!Array.isArray(housingData)) {

            throw new Error(
                "taiwan_housing.json 必須是陣列"
            );

        }


        // ----------------------------------------------------
        // 確認資料不是空的
        // ----------------------------------------------------

        if (housingData.length === 0) {

            throw new Error(
                "taiwan_housing.json 沒有任何資料"
            );

        }


        // ----------------------------------------------------
        // 建立縣市選單
        // ----------------------------------------------------

        createCitySelect();


        // ----------------------------------------------------
        // 顯示資料
        // ----------------------------------------------------

        renderTable();


        // ----------------------------------------------------
        // 開發測試資訊
        // ----------------------------------------------------

        console.log(
            `成功載入 ${housingData.length} 個行政區`
        );


        console.log(
            "第一筆資料：",
            housingData[0]
        );

    }


    catch (error) {

        console.error(
            "讀取房價資料失敗：",
            error
        );


        count.textContent = "";


        tableBody.innerHTML = `

            <tr>

                <td
                    colspan="4"
                    class="empty"
                >

                    房價資料載入失敗

                    <br>

                    <small>
                        請稍後重新整理頁面
                    </small>

                </td>

            </tr>

        `;

    }

}


// ============================================================
// 搜尋事件
// ============================================================

searchInput.addEventListener(
    "input",
    renderTable
);


// ============================================================
// 縣市篩選事件
// ============================================================

citySelect.addEventListener(
    "change",
    renderTable
);


// ============================================================
// 開始載入
// ============================================================

loadHousingData();
