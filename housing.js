const tableBody = document.getElementById("tableBody");
const citySelect = document.getElementById("citySelect");
const searchInput = document.getElementById("searchInput");
const count = document.getElementById("count");

let housingData = [];


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


function createCitySelect() {

    const cities = [
        ...new Set(
            housingData.map(item => item.city)
        )
    ];

    cities.sort(
        (a, b) => a.localeCompare(b, "zh-TW")
    );

    cities.forEach(city => {

        const option =
            document.createElement("option");

        option.value = city;

        option.textContent = city;

        citySelect.appendChild(option);

    });
}


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


    count.textContent =
        `共 ${filteredData.length} 個行政區`;


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


    tableBody.innerHTML =
        filteredData.map(item => {

            const districtName =
                `${item.city}${item.district}`;


            /*
             * 租金欄位
             *
             * 目前 JSON：
             * average_monthly_rent
             *
             * 同時支援舊名稱：
             * average_rent
             */

            const rent =
                item.average_monthly_rent ??
                item.average_rent ??
                null;


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
                            rent
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


async function loadHousingData() {

    try {

        /*
         * 加版本號避免 GitHub Pages / 瀏覽器快取舊 JS
         */

        const response =
            await fetch(
                "data/taiwan_housing.json?v=2"
            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );

        }


        housingData =
            await response.json();


        if (!Array.isArray(housingData)) {

            throw new Error(
                "taiwan_housing.json 必須是陣列"
            );

        }


        createCitySelect();

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


searchInput.addEventListener(
    "input",
    renderTable
);


citySelect.addEventListener(
    "change",
    renderTable
);


loadHousingData();
