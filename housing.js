// ========================================
// 台灣行政區房價、租金與所得
// ========================================


const DATA_URL =
    "data/taiwan_housing.json?v=8";


const MAP_URL =
    "https://cdn.jsdelivr.net/npm/taiwan-atlas@2021.9.20/counties-10t.json";


const EXCLUDED = new Set([
    "澎湖縣",
    "金門縣",
    "連江縣"
]);


let housingData = [];

let mapTopology = null;


// ========================================
// 目前選中的縣市
// ========================================

let selectedCityName = "台北市";


// ========================================
// 統一 台 / 臺
// ========================================

function normalizeCityName(name) {

    if (!name) {

        return "";
    }

    return String(name)
        .replaceAll("臺", "台")
        .trim();
}


// ========================================
// 數字格式
// ========================================

function formatNumber(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {

        return "—";
    }


    const number =
        Number(value);


    if (!Number.isFinite(number)) {

        return "—";
    }


    return number.toLocaleString(
        "zh-TW",
        {
            maximumFractionDigits: 0
        }
    );
}


// ========================================
// 房價：元 → 萬元
// ========================================

function formatPrice(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {

        return "—";
    }


    const number =
        Number(value);


    if (!Number.isFinite(number)) {

        return "—";
    }


    const wan =
        number / 10000;


    return wan.toLocaleString(
        "zh-TW",
        {
            minimumFractionDigits: 0,
            maximumFractionDigits: 1
        }
    ) + " 萬";
}


// ========================================
// 房價所得比
// ========================================

function formatRatio(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {

        return "—";
    }


    const number =
        Number(value);


    if (!Number.isFinite(number)) {

        return "—";
    }


    return number.toFixed(1) + " 倍";
}


// ========================================
// 40 年租屋 / 買房比較
// ========================================

function getRecommendation(
    housePrice,
    monthlyRent
) {

    const price =
        Number(housePrice);


    const rent =
        Number(monthlyRent);


    if (
        !Number.isFinite(price) ||
        !Number.isFinite(rent) ||
        rent <= 0
    ) {

        return {

            text: "—",

            className: ""
        };
    }


    // 40 年租金

    const fortyYearRent =
        rent * 12 * 40;


    // 房價與 40 年租金差距

    const difference =
        Math.abs(
            price -
            fortyYearRent
        );


    const differenceRate =
        difference /
        Math.max(
            price,
            fortyYearRent
        );


    // 差距 5% 以內 → 持平

    if (
        differenceRate <= 0.05
    ) {

        return {

            text: "持平",

            className:
                "recommendation-even"
        };
    }


    // 房價比較低

    if (
        price <
        fortyYearRent
    ) {

        return {

            text: "買房",

            className:
                "recommendation-buy"
        };
    }


    // 40 年租金比較低

    return {

        text: "租屋",

        className:
            "recommendation-rent"
    };
}


// ========================================
// 顯示地圖錯誤
// ========================================

function showMapError(
    message
) {

    const container =
        document.getElementById(
            "taiwanMap"
        );


    if (!container) {

        return;
    }


    container.innerHTML = `

        <div style="
            height:100%;
            min-height:300px;
            display:flex;
            align-items:center;
            justify-content:center;
            text-align:center;
            padding:30px;
        ">

            <div>

                <div style="
                    font-size:40px;
                    margin-bottom:12px;
                ">
                    ⚠️
                </div>

                <div style="
                    font-size:18px;
                    font-weight:700;
                    margin-bottom:8px;
                ">
                    地圖載入失敗
                </div>

                <div style="
                    color:#6b7280;
                    font-size:13px;
                ">
                    ${message}
                </div>

            </div>

        </div>

    `;
}


// ========================================
// 讀取房價資料
// ========================================

async function loadHousingData() {

    const response =
        await fetch(
            DATA_URL,
            {
                cache: "no-store"
            }
        );


    if (!response.ok) {

        throw new Error(
            `房價資料載入失敗：HTTP ${response.status}`
        );
    }


    housingData =
        await response.json();


    console.log(
        "房價資料載入完成：",
        housingData
    );


    renderTable(
        "台北市"
    );
}


// ========================================
// 讀取地圖
// ========================================

async function loadMap() {

    const container =
        document.getElementById(
            "taiwanMap"
        );


    if (!container) {

        throw new Error(
            "找不到 #taiwanMap"
        );
    }


    if (
        typeof d3 ===
        "undefined"
    ) {

        throw new Error(
            "D3 沒有成功載入"
        );
    }


    if (
        typeof topojson ===
        "undefined"
    ) {

        throw new Error(
            "TopoJSON 沒有成功載入"
        );
    }


    const response =
        await fetch(
            MAP_URL,
            {
                cache: "no-store"
            }
        );


    if (!response.ok) {

        throw new Error(
            `地圖資料載入失敗：HTTP ${response.status}`
        );
    }


    mapTopology =
        await response.json();


    console.log(
        "地圖資料載入完成：",
        mapTopology
    );


    drawMap();
}


// ========================================
// 畫地圖
// ========================================

function drawMap() {

    const container =
        document.getElementById(
            "taiwanMap"
        );


    if (!container) {

        return;
    }


    container.innerHTML = "";


    const width =
        container.clientWidth ||
        1000;


    const height =
        container.clientHeight ||
        380;


    // ====================================
    // SVG
    // ====================================

    const svg =
        d3
            .select(container)
            .append("svg")
            .attr(
                "width",
                "100%"
            )
            .attr(
                "height",
                "100%"
            )
            .attr(
                "viewBox",
                `0 0 ${width} ${height}`
            )
            .attr(
                "preserveAspectRatio",
                "xMidYMid meet"
            );


    // ====================================
    // 檢查 counties
    // ====================================

    if (
        !mapTopology.objects ||
        !mapTopology.objects.counties
    ) {

        throw new Error(
            "地圖資料找不到 counties"
        );
    }


    // ====================================
    // TopoJSON → GeoJSON
    // ====================================

    const counties =
        topojson.feature(
            mapTopology,
            mapTopology.objects.counties
        );


    // ====================================
    // 排除離島
    // ====================================

    const taiwanCounties =
        counties.features.filter(
            feature => {

                const city =
                    normalizeCityName(
                        feature.properties
                            ?.COUNTYNAME
                    );


                return !EXCLUDED.has(
                    city
                );
            }
        );


    // ====================================
    // D3 Mercator
    // ====================================

    const projection =
        d3
            .geoMercator()
            .fitSize(
                [
                    width - 60,
                    height - 30
                ],
                {
                    type:
                        "FeatureCollection",

                    features:
                        taiwanCounties
                }
            );


    const path =
        d3
            .geoPath()
            .projection(
                projection
            );


    // ====================================
    // 地圖群組
    // ====================================

    const mapGroup =
        svg
            .append("g");


    // ====================================
    // 縣市
    // ====================================

    const countyPaths =
        mapGroup
            .selectAll(".county")
            .data(
                taiwanCounties
            )
            .enter()
            .append("path");


    countyPaths

        .attr(
            "class",
            "county"
        )

        .attr(
            "d",
            path
        )

        .attr(
            "data-city",
            d =>
                normalizeCityName(
                    d.properties
                        ?.COUNTYNAME
                )
        )

        .attr(
            "fill",
            "#e8edf2"
        )

        .attr(
            "stroke",
            "#ffffff"
        )

        .attr(
            "stroke-width",
            1.5
        )

        .style(
            "cursor",
            "pointer"
        );


    // ====================================
    // 滑鼠移入 → 亮藍色
    // ====================================

    countyPaths.on(
        "mouseenter",
        function(event, d) {

            const city =
                normalizeCityName(
                    d.properties
                        ?.COUNTYNAME
                );


            d3.select(this)

                .attr(
                    "fill",
                    "#3b82f6"
                )

                .attr(
                    "stroke-width",
                    2
                );


            showTooltip(
                event,
                city
            );
        }
    );


    // ====================================
    // 滑鼠移動
    // ====================================

    countyPaths.on(
        "mousemove",
        function(event) {

            moveTooltip(
                event
            );
        }
    );


    // ====================================
    // 滑鼠離開
    // ====================================

    countyPaths.on(
        "mouseleave",
        function() {

            const currentCity =
                normalizeCityName(
                    d3.select(this)
                        .attr(
                            "data-city"
                        )
                );


            // 如果是目前選中的縣市
            // 保持深藍色

            if (
                currentCity ===
                selectedCityName
            ) {

                d3.select(this)

                    .attr(
                        "fill",
                        "#2563eb"
                    )

                    .attr(
                        "stroke-width",
                        2
                    );

            } else {

                d3.select(this)

                    .attr(
                        "fill",
                        "#e8edf2"
                    )

                    .attr(
                        "stroke-width",
                        1.5
                    );
            }


            hideTooltip();
        }
    );


    // ====================================
    // 點擊縣市
    // ====================================

    countyPaths.on(
        "click",
        function(event, d) {

            const city =
                normalizeCityName(
                    d.properties
                        ?.COUNTYNAME
                );


            selectCity(
                city
            );
        }
    );


    // ====================================
    // 縣市名稱
    // ====================================

    mapGroup

        .selectAll(
            ".county-label"
        )

        .data(
            taiwanCounties
        )

        .enter()

        .append("text")

        .attr(
            "class",
            "county-label"
        )

        .attr(
            "transform",
            d => {

                const centroid =
                    path.centroid(d);


                return `
                    translate(
                        ${centroid[0]},
                        ${centroid[1]}
                    )
                `;
            }
        )

        .attr(
            "text-anchor",
            "middle"
        )

        .attr(
            "dominant-baseline",
            "middle"
        )

        .style(
            "font-size",
            "10px"
        )

        .style(
            "font-weight",
            "600"
        )

        .style(
            "fill",
            "#374151"
        )

        .style(
            "pointer-events",
            "none"
        )

        .text(
            d =>
                normalizeCityName(
                    d.properties
                        ?.COUNTYNAME
                )
        );


    // ====================================
    // 預設台北
    // ====================================

    selectCity(
        "台北市"
    );
}


// ========================================
// Tooltip
// ========================================

function showTooltip(
    event,
    city
) {

    const tooltip =
        document.getElementById(
            "mapTooltip"
        );


    if (!tooltip) {

        return;
    }


    tooltip.textContent =
        city;


    tooltip.style.display =
        "block";


    moveTooltip(
        event
    );
}


function moveTooltip(
    event
) {

    const tooltip =
        document.getElementById(
            "mapTooltip"
        );


    if (!tooltip) {

        return;
    }


    tooltip.style.left =
        `${event.clientX + 12}px`;


    tooltip.style.top =
        `${event.clientY + 12}px`;
}


function hideTooltip() {

    const tooltip =
        document.getElementById(
            "mapTooltip"
        );


    if (!tooltip) {

        return;
    }


    tooltip.style.display =
        "none";
}


// ========================================
// 選擇縣市
// ========================================

function selectCity(
    city
) {

    city =
        normalizeCityName(
            city
        );


    // 記住目前縣市

    selectedCityName =
        city;


    // ====================================
    // 更新表格標題
    // ====================================

    const tableTitle =
        document.querySelector(
            ".table-header h2"
        );


    if (tableTitle) {

        tableTitle.textContent =
            `${city}住宅市場資料`;
    }


    // ====================================
    // 所有縣市恢復灰色
    // ====================================

    d3.selectAll(
        ".county"
    )

        .attr(
            "fill",
            "#e8edf2"
        )

        .attr(
            "stroke-width",
            1.5
        );


    // ====================================
    // 選中的縣市 → 深藍
    // ====================================

    d3.selectAll(
        ".county"
    )

        .filter(
            function() {

                return (
                    normalizeCityName(
                        d3.select(this)
                            .attr(
                                "data-city"
                            )
                    ) === city
                );
            }
        )

        .attr(
            "fill",
            "#2563eb"
        )

        .attr(
            "stroke-width",
            2
        );


    // ====================================
    // 更新表格
    // ====================================

    renderTable(
        city
    );
}


// ========================================
// 產生表格
// ========================================

function renderTable(
    selectedCity = "台北市"
) {

    const tbody =
        document.querySelector(
            "#housingTable tbody"
        );


    if (!tbody) {

        return;
    }


    tbody.innerHTML = "";


    if (
        !Array.isArray(
            housingData
        )
    ) {

        return;
    }


    const normalizedCity =
        normalizeCityName(
            selectedCity
        );


    // ====================================
    // 找到該縣市資料
    // ====================================

    const rows =
        housingData.filter(
            row => {

                const city =
                    normalizeCityName(
                        row.city ||
                        row.行政區 ||
                        row.name
                    );


                return (
                    city ===
                    normalizedCity
                );
            }
        );


    console.log(
        `${normalizedCity} 資料：`,
        rows
    );


    // ====================================
    // 產生表格
    // ====================================

    rows.forEach(
        row => {

            const city =
                normalizeCityName(
                    row.city ||
                    row.行政區 ||
                    row.name
                );


            // ----------------------------
            // 中位數房價
            // ----------------------------

            const medianPrice =
                row.median_total_price;


            // ----------------------------
            // 平均租金
            // ----------------------------

            const rent =
                row.average_monthly_rent;


            // ----------------------------
            // 房價所得比
            // ----------------------------

            const ratio =
                row.price_income_ratio;


            // ----------------------------
            // 40 年建議
            // ----------------------------

            const recommendation =
                getRecommendation(
                    medianPrice,
                    rent
                );


            // ----------------------------
            // TR
            // ----------------------------

            const tr =
                document.createElement(
                    "tr"
                );


            tr.innerHTML = `

                <td>
                    ${city}
                </td>


                <td>
                    ${formatPrice(
                        medianPrice
                    )}
                </td>


                <td>
                    ${
                        rent !== null &&
                        rent !== undefined
                            ? formatNumber(
                                rent
                              ) + " 元"
                            : "—"
                    }
                </td>


                <td>
                    ${formatRatio(
                        ratio
                    )}
                </td>


                <td
                    class="${
                        recommendation.className
                    }"
                >
                    ${
                        recommendation.text
                    }
                </td>

            `;


            tbody.appendChild(
                tr
            );
        }
    );


    // ====================================
    // 沒有資料
    // ====================================

    if (
        rows.length === 0
    ) {

        const tr =
            document.createElement(
                "tr"
            );


        tr.innerHTML = `

            <td
                colspan="5"
                style="
                    text-align:center;
                    padding:30px;
                    color:#6b7280;
                "
            >
                目前沒有
                ${normalizedCity}
                的資料
            </td>

        `;


        tbody.appendChild(
            tr
        );
    }
}


// ========================================
// 啟動
// ========================================

async function init() {

    try {

        console.log(
            "My Housing 開始啟動"
        );


        await loadHousingData();


        await loadMap();


        console.log(
            "My Housing 啟動完成"
        );


    } catch (error) {

        console.error(
            "My Housing 啟動失敗：",
            error
        );


        showMapError(
            error.message ||
            "請開啟瀏覽器 F12 查看錯誤"
        );
    }
}


// ========================================
// DOM Ready
// ========================================

document.addEventListener(
    "DOMContentLoaded",
    init
);


// ========================================
// 視窗縮放
// ========================================

let resizeTimer = null;


window.addEventListener(
    "resize",
    () => {

        clearTimeout(
            resizeTimer
        );


        resizeTimer =
            setTimeout(
                () => {

                    if (
                        !mapTopology
                    ) {

                        return;
                    }


                    try {

                        drawMap();

                    } catch (error) {

                        console.error(
                            "地圖重新繪製失敗：",
                            error
                        );
                    }

                },
                300
            );
    }
);
