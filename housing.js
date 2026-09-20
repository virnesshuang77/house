// ========================================
// 台灣買房租屋比較網
// housing.js
// ========================================

const DATA_URL =
    "data/taiwan_housing.json?v=10";

const MAP_URL =
    "https://cdn.jsdelivr.net/npm/taiwan-atlas@2021.9.20/counties-10t.json";


// ========================================
// 排除離島
// ========================================

const EXCLUDED = new Set([
    "澎湖縣",
    "金門縣",
    "連江縣"
]);


// ========================================
// 全域變數
// ========================================

let housingData = [];

let mapTopology = null;

let selectedCityName = "台北市";

let resizeTimer = null;


// ========================================
// 統一縣市名稱
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

    const number = Number(value);

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
// 房價：元 → 萬
// ========================================

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

    const wan = number / 10000;

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

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return number.toFixed(1) + " 倍";
}


// ========================================
// 40 年買房 / 租屋簡單比較
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


    const fortyYearRent =
        rent * 12 * 40;


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


    if (
        differenceRate <= 0.05
    ) {

        return {
            text: "持平",
            className:
                "recommendation-even"
        };
    }


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


    return {
        text: "租屋",
        className:
            "recommendation-rent"
    };
}


// ========================================
// 載入房價資料
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


    const data =
        await response.json();


    if (
        !Array.isArray(data)
    ) {

        throw new Error(
            "房價資料格式錯誤"
        );
    }


    housingData = data;


    console.log(
        "房價資料載入完成：",
        housingData
    );


    console.log(
        `共有 ${housingData.length} 筆行政區資料`
    );


    // 預設台北市
    renderTable("台北市");
}


// ========================================
// 載入地圖資料
// ========================================

async function loadMap() {

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


    drawMap();
}


// ========================================
// 取得地圖 SVG
//
// 你的 index.html 已經有：
// <svg id="taiwanMap"></svg>
//
// 所以這裡絕對不能再建立第二個 SVG。
// ========================================

function getMapSvg() {

    const container =
        document.getElementById(
            "taiwanMap"
        );


    if (!container) {

        throw new Error(
            "找不到 #taiwanMap"
        );
    }


    const svg =
        d3.select(container);


    // 確保是 SVG
    if (
        container.tagName.toLowerCase()
        !== "svg"
    ) {

        throw new Error(
            "#taiwanMap 必須是 SVG"
        );
    }


    return {
        element: container,
        selection: svg
    };
}


// ========================================
// 建立地圖
// ========================================

function drawMap() {

    if (!mapTopology) {
        return;
    }


    const {
        element,
        selection: svg
    } = getMapSvg();


    // 清空舊地圖
    svg.selectAll("*").remove();


    // 實際尺寸
    const width =
        element.clientWidth ||
        1000;


    const height =
        element.clientHeight ||
        380;


    // 修正 SVG ViewBox
    svg
        .attr(
            "viewBox",
            `0 0 ${width} ${height}`
        )
        .attr(
            "preserveAspectRatio",
            "xMidYMid meet"
        );


    // ====================================
    // 取得縣市
    // ====================================

    const counties =
        topojson.feature(
            mapTopology,
            mapTopology.objects.counties
        );


    // ====================================
    // 只保留台灣本島
    // ====================================

    const taiwanCounties =
        counties.features.filter(
            feature => {

                const city =
                    normalizeCityName(
                        feature
                            .properties
                            ?.COUNTYNAME
                    );


                return !EXCLUDED.has(
                    city
                );
            }
        );


    if (
        taiwanCounties.length === 0
    ) {

        throw new Error(
            "找不到台灣本島縣市地圖資料"
        );
    }


    // ====================================
    // GeoJSON FeatureCollection
    // ====================================

    const mainlandFeatureCollection = {
        type: "FeatureCollection",
        features: taiwanCounties
    };


    // ====================================
    // 地圖投影
    //
    // 重要：
    // 只對台灣本島 fit，
    // 不讓澎湖、金門、連江把台灣縮小。
    // ====================================

    const projection =
        d3
            .geoMercator()
            .fitExtent(
                [
                    [20, 10],
                    [
                        width - 20,
                        height - 10
                    ]
                ],
                mainlandFeatureCollection
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
            .append("g")
            .attr(
                "class",
                "taiwan-map-group"
            );


    // ====================================
    // 縣市
    // ====================================

    const countyPaths =
        mapGroup
            .selectAll(
                ".county"
            )
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
            d => {

                const city =
                    normalizeCityName(
                        d.properties
                            ?.COUNTYNAME
                    );


                return city ===
                    selectedCityName
                    ? "#2563eb"
                    : "#dbeafe";
            }
        )

        .attr(
            "stroke",
            "#ffffff"
        )

        .attr(
            "stroke-width",
            d => {

                const city =
                    normalizeCityName(
                        d.properties
                            ?.COUNTYNAME
                    );


                return city ===
                    selectedCityName
                    ? 2
                    : 1.2;
            }
        )

        .style(
            "cursor",
            "pointer"
        );


    // ====================================
    // 滑鼠移入
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
                        "#dbeafe"
                    )
                    .attr(
                        "stroke-width",
                        1.2
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


    console.log(
        "台灣地圖繪製完成"
    );
}


// ========================================
// Tooltip
// ========================================

function getTooltipElement() {

    let tooltip =
        document.getElementById(
            "mapTooltip"
        );


    // 如果 index.html 沒有 tooltip，
    // 自動建立一個。
    if (!tooltip) {

        tooltip =
            document.createElement(
                "div"
            );


        tooltip.id =
            "mapTooltip";


        tooltip.style.position =
            "fixed";


        tooltip.style.display =
            "none";


        tooltip.style.zIndex =
            "9999";


        tooltip.style.padding =
            "8px 12px";


        tooltip.style.background =
            "rgba(17, 24, 39, 0.92)";


        tooltip.style.color =
            "#ffffff";


        tooltip.style.borderRadius =
            "7px";


        tooltip.style.fontSize =
            "13px";


        tooltip.style.pointerEvents =
            "none";


        tooltip.style.whiteSpace =
            "nowrap";


        document.body.appendChild(
            tooltip
        );
    }


    return tooltip;
}


function showTooltip(
    event,
    city
) {

    const tooltip =
        getTooltipElement();


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


    if (!city) {
        return;
    }


    selectedCityName =
        city;


    console.log(
        "目前選擇縣市：",
        city
    );


    // ====================================
    // 更新表格標題
    // ====================================

    const tableTitle =
        document.getElementById(
            "tableTitle"
        );


    if (tableTitle) {

        tableTitle.textContent =
            `${city}住宅市場資料`;
    }


    // ====================================
    // 更新地圖顏色
    // ====================================

    d3.selectAll(
        ".county"
    )
        .attr(
            "fill",
            function() {

                const mapCity =
                    normalizeCityName(
                        d3.select(this)
                            .attr(
                                "data-city"
                            )
                    );


                return mapCity === city
                    ? "#2563eb"
                    : "#dbeafe";
            }
        )
        .attr(
            "stroke-width",
            function() {

                const mapCity =
                    normalizeCityName(
                        d3.select(this)
                            .attr(
                                "data-city"
                            )
                    );


                return mapCity === city
                    ? 2
                    : 1.2;
            }
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

    // ====================================
    // 你的 index.html 是：
    //
    // <tbody id="housingTableBody">
    //
    // 所以直接找這個 ID。
    // ====================================

    const tbody =
        document.getElementById(
            "housingTableBody"
        );


    if (!tbody) {

        console.error(
            "找不到 #housingTableBody"
        );

        return;
    }


    tbody.innerHTML = "";


    const normalizedCity =
        normalizeCityName(
            selectedCity
        );


    // ====================================
    // city 篩選
    //
    // district 顯示行政區
    // ====================================

    const rows =
        housingData.filter(
            row => {

                const rowCity =
                    normalizeCityName(
                        row.city
                    );


                return (
                    rowCity ===
                    normalizedCity
                );
            }
        );


    console.log(
        `${normalizedCity} 行政區資料：`,
        rows
    );


    // ====================================
    // 行政區排序
    // ====================================

    rows.sort(
        (a, b) => {

            const districtA =
                String(
                    a.district || ""
                );


            const districtB =
                String(
                    b.district || ""
                );


            return districtA.localeCompare(
                districtB,
                "zh-Hant"
            );
        }
    );


    // ====================================
    // 建立表格
    // ====================================

    rows.forEach(
        row => {

            // 行政區
            const district =
                row.district ||
                "—";


            // 中位數房價
            const medianPrice =
                row.median_total_price;


            // 平均租金
            const rent =
                row.average_monthly_rent;


            // 房價所得比
            const ratio =
                row.price_income_ratio;


            // 建議
            const recommendation =
                getRecommendation(
                    medianPrice,
                    rent
                );


            const tr =
                document.createElement(
                    "tr"
                );


            tr.innerHTML = `

                <td>
                    ${district}
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
                    class="${recommendation.className}"
                >
                    ${recommendation.text}
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
                的行政區資料
            </td>

        `;


        tbody.appendChild(
            tr
        );
    }
}


// ========================================
// 地圖錯誤
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


    // SVG 裡面不能直接塞 div，
    // 所以用 SVG text 顯示錯誤。

    const svg =
        d3.select(
            container
        );


    svg.selectAll("*")
        .remove();


    const width =
        container.clientWidth ||
        1000;


    const height =
        container.clientHeight ||
        380;


    svg
        .attr(
            "viewBox",
            `0 0 ${width} ${height}`
        );


    svg.append("text")
        .attr(
            "x",
            width / 2
        )
        .attr(
            "y",
            height / 2 - 10
        )
        .attr(
            "text-anchor",
            "middle"
        )
        .style(
            "font-size",
            "18px"
        )
        .style(
            "font-weight",
            "700"
        )
        .text(
            "地圖載入失敗"
        );


    svg.append("text")
        .attr(
            "x",
            width / 2
        )
        .attr(
            "y",
            height / 2 + 20
        )
        .attr(
            "text-anchor",
            "middle"
        )
        .style(
            "font-size",
            "13px"
        )
        .style(
            "fill",
            "#6b7280"
        )
        .text(
            message
        );
}


// ========================================
// 初始化
// ========================================

async function init() {

    console.log(
        "台灣買房租屋比較網開始啟動"
    );


    // ====================================
    // 房價資料
    // ====================================

    try {

        await loadHousingData();

    } catch (error) {

        console.error(
            "房價資料載入失敗：",
            error
        );


        const tbody =
            document.getElementById(
                "housingTableBody"
            );


        if (tbody) {

            tbody.innerHTML = `

                <tr>

                    <td
                        colspan="5"
                        style="
                            text-align:center;
                            padding:30px;
                            color:#dc2626;
                        "
                    >
                        房價資料載入失敗
                    </td>

                </tr>

            `;
        }
    }


    // ====================================
    // 地圖
    // ====================================

    try {

        await loadMap();

    } catch (error) {

        console.error(
            "地圖載入失敗：",
            error
        );


        showMapError(
            error.message ||
            "請重新整理網頁"
        );
    }


    console.log(
        "台灣買房租屋比較網啟動完成"
    );
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
