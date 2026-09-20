const tableBody = document.getElementById("tableBody");
const citySelect = document.getElementById("citySelect");
const searchInput = document.getElementById("searchInput");
const count = document.getElementById("count");

let housingData = [];


/*
========================================================
格式化數字
========================================================
*/

function formatNumber(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    return Number(value).toLocaleString("zh-TW");
}


/*
========================================================
格式化房價
========================================================
*/

function formatPrice(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    return formatNumber(value) + " 元/坪";
}


/*
========================================================
格式化租金
========================================================
*/

function formatRent(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    return formatNumber(value) + " 元/月";
}


/*
========================================================
格式化房價所得比
========================================================
*/

function formatIncomeRatio(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    return Number(value).toFixed(1) + " 倍";
}


/*
========================================================
建立縣市選單
========================================================
*/

function createCitySelect() {

    const cities = [
        ...new Set(
            housingData.map(item => item.city)
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


/*
========================================================
顯示表格
========================================================
*/

function renderTable() {

    const selectedCity =
        citySelect.value;

    const keyword =
        searchInput.value
            .trim()
            .toLowerCase();


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


    /*
    ================================================
    顯示筆數
    ================================================
    */

    count.textContent =
        `共 ${filteredData.length} 個行政區`;


    /*
    ================================================
    沒有資料
    ================================================
    */

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


    /*
    ================================================
    建立表格
    ================================================
    */

    tableBody.innerHTML =
        filteredData.map(item => {

            const districtName =
                `${item.city}${item.district}`;


            return `

                <tr>

                    <td>
                        ${districtName}
                    </td>


                    <td class="number">

                        ${formatPrice(
                            item.median_price_per_ping
                        )}

                    </td>


                    <td class="number">

                        ${formatRent(
                            item.average_monthly_rent
                        )}

                    </td>


                    <td class="number">

                        ${formatIncomeRatio(
                            item.price_income_ratio
                        )}

                    </td>

                </tr>

            `;

        }).join("");

}


/*
========================================================
讀取 JSON
========================================================
*/

async function loadHousingData() {

    try {

        const response =
            await fetch(
                "data/taiwan_housing.json"
            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );

        }


        housingData =
            await response.json();


        /*
        ============================================
        防止 JSON 格式錯誤
        ============================================
        */

        if (!Array.isArray(housingData)) {

            throw new Error(
                "taiwan_housing.json 必須是陣列"
            );

        }


        /*
        ============================================
        建立縣市選單
        ============================================
        */

        createCitySelect();


        /*
        ============================================
        顯示資料
        ============================================
        */

        renderTable();

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
                </td>

            </tr>

        `;

    }

}


/*
========================================================
搜尋事件
========================================================
*/

searchInput.addEventListener(
    "input",
    renderTable
);


/*
========================================================
縣市篩選事件
========================================================
*/

citySelect.addEventListener(
    "change",
    renderTable
);


/*
========================================================
開始載入
========================================================
*/

loadHousingData();
