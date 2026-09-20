// ========================================
// 台灣房價 / 租金地圖
// ========================================

const DATA_URL = "data/taiwan_housing.json?v=5";

// 台灣 Atlas：內政部行政區界線資料
// 使用已經完成 Mercator 投影的版本
const MAP_URL =
    "https://cdn.jsdelivr.net/npm/taiwan-atlas@2021.9.20/counties-mercator-10t.json";

const EXCLUDED = new Set([
    "澎湖縣",
    "金門縣",
    "連江縣"
]);

let housingData = [];
let mapTopology = null;


// ========================================
// 名稱統一
// ========================================

function normalizeCityName(name) {
    if (!name) return "";

    return String(name)
        .replaceAll("臺", "台")
        .trim();
}


// ========================================
// 格式化數字
// ========================================

function formatNumber(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return number.toLocaleString("zh-TW", {
        maximumFractionDigits: 0
    });
}


function formatRatio(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return number.toFixed(1) + " 倍";
}


// ========================================
// 顯示錯誤
// ========================================

function showMapError(message) {

    const container = document.getElementById("taiwanMap");

    if (!container) return;

    container.innerHTML = `
        <div style="
            height:100%;
            min-height:650px;
            display:flex;
            align-items:center;
            justify-content:center;
            text-align:center;
            padding:30px;
            box-sizing:border-box;
        ">
            <div>
                <div style="
                    font-size:42px;
                    margin-bottom:15px;
                ">⚠️</div>

                <div style="
                    font-size:20px;
                    font-weight:700;
                    margin-bottom:10px;
                ">
                    地圖載入失敗
                </div>

                <div style="
                    color:#777;
                    font-size:14px;
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

    const response = await fetch(DATA_URL, {
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error(
            `房價資料載入失敗 HTTP ${response.status}`
        );
    }

    housingData = await response.json();

    console.log("房價資料：", housingData);

    renderTable();
}


// ========================================
// 讀取地圖
// ========================================

async function loadMap() {

    const container = document.getElementById("taiwanMap");

    if (!container) {
        throw new Error("找不到 #taiwanMap");
    }

    if (typeof d3 === "undefined") {
        throw new Error("D3 沒有成功載入");
    }

    if (typeof topojson === "undefined") {
        throw new Error("TopoJSON 沒有成功載入");
    }

    console.log("開始載入台灣地圖...");

    const response = await fetch(MAP_URL, {
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error(
            `地圖資料載入失敗 HTTP ${response.status}`
        );
    }

    mapTopology = await response.json();

    console.log("地圖資料：", mapTopology);

    drawMap();
}


// ========================================
// 畫地圖
// ========================================

function drawMap() {

    const container = document.getElementById("taiwanMap");

    if (!container) return;

    container.innerHTML = "";

    const width = container.clientWidth || 1000;

    // 手機不要太高
    const height = Math.max(
        560,
        Math.min(700, width * 0.72)
    );

    const svg = d3
        .select(container)
        .append("svg")
        .attr("width", "100%")
        .attr("height", height)
        .attr("viewBox", `0 0 ${width} ${height}`)
        .attr("preserveAspectRatio", "xMidYMid meet");

    // ------------------------------------
    // TopoJSON → GeoJSON
    // ------------------------------------

    if (
        !mapTopology.objects ||
        !mapTopology.objects.counties
    ) {
        throw new Error(
            "地圖資料中找不到 counties"
        );
    }

    const counties = topojson.feature(
        mapTopology,
        mapTopology.objects.counties
    );

    console.log("縣市數量：", counties.features.length);

    // ------------------------------------
    // 已經是 Mercator 投影
    // 使用 identity projection
    // ------------------------------------

    const projection = d3
        .geoIdentity()
        .reflectY(true)
        .fitSize(
            [width - 60, height - 60],
            counties
        );

    const path = d3
        .geoPath()
        .projection(projection);

    // ------------------------------------
    // 地圖群組
    // ------------------------------------

    const mapGroup = svg
        .append("g")
        .attr("transform", "translate(30,30)");

    // ------------------------------------
    // 縣市
    // ------------------------------------

    const countyPaths = mapGroup
        .selectAll(".county")
        .data(
            counties.features.filter(feature => {

                const name =
                    normalizeCityName(
                        feature.properties?.COUNTYNAME
                    );

                return !EXCLUDED.has(name);
            })
        )
        .enter()
        .append("path")
        .attr("class", "county")
        .attr("d", path)
        .attr(
            "data-city",
            d =>
                normalizeCityName(
                    d.properties?.COUNTYNAME
                )
        )
        .attr("fill", "#e8edf2")
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 1.5)
        .style("cursor", "pointer");

    // ------------------------------------
    // hover
    // ------------------------------------

    countyPaths
        .on("mouseenter", function(event, d) {

            const city =
                normalizeCityName(
                    d.properties?.COUNTYNAME
                );

            d3.select(this)
                .attr("fill", "#cbd5e1");

            showTooltip(
                event,
                city
            );
        })
        .on("mousemove", function(event) {

            moveTooltip(event);

        })
        .on("mouseleave", function() {

            d3.select(this)
                .attr("fill", "#e8edf2");

            hideTooltip();

        })
        .on("click", function(event, d) {

            const city =
                normalizeCityName(
                    d.properties?.COUNTYNAME
                );

            selectCity(city);

        });

    // ------------------------------------
    // 縣市名稱
    // ------------------------------------

    mapGroup
        .selectAll(".county-label")
        .data(
            counties.features.filter(feature => {

                const name =
                    normalizeCityName(
                        feature.properties?.COUNTYNAME
                    );

                return !EXCLUDED.has(name);
            })
        )
        .enter()
        .append("text")
        .attr("class", "county-label")
        .attr("transform", d => {

            const centroid =
                path.centroid(d);

            return `translate(${centroid[0]},${centroid[1]})`;
        })
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "middle")
        .style("font-size", "11px")
        .style("font-weight", "600")
        .style("pointer-events", "none")
        .style("fill", "#333")
        .text(d =>
            normalizeCityName(
                d.properties?.COUNTYNAME
            )
        );

    console.log("台灣地圖繪製完成");

    // 預設台北
    selectCity("台北市");
}


// ========================================
// Tooltip
// ========================================

function showTooltip(event, city) {

    const tooltip =
        document.getElementById("mapTooltip");

    if (!tooltip) return;

    tooltip.textContent = city;

    tooltip.style.display = "block";

    moveTooltip(event);
}


function moveTooltip(event) {

    const tooltip =
        document.getElementById("mapTooltip");

    if (!tooltip) return;

    tooltip.style.left =
        `${event.clientX + 12}px`;

    tooltip.style.top =
        `${event.clientY + 12}px`;
}


function hideTooltip() {

    const tooltip =
        document.getElementById("mapTooltip");

    if (!tooltip) return;

    tooltip.style.display = "none";
}


// ========================================
// 選擇城市
// ========================================

function selectCity(city) {

    city = normalizeCityName(city);

    const selected =
        document.getElementById("selectedCity");

    if (selected) {
        selected.textContent = city;
    }

    // 地圖選取狀態
    d3.selectAll(".county")
        .attr("fill", "#e8edf2");

    d3.selectAll(
        `.county[data-city="${CSS.escape(city)}"]`
    )
        .attr("fill", "#94a3b8");

    // 表格
    renderTable(city);
}


// ========================================
// 表格
// ========================================

function renderTable(selectedCity = null) {

    const tbody =
        document.querySelector("#housingTable tbody");

    if (!tbody) return;

    tbody.innerHTML = "";

    if (!Array.isArray(housingData)) {
        return;
    }

    let rows = housingData;

    if (selectedCity) {

        const normalized =
            normalizeCityName(selectedCity);

        rows = housingData.filter(row =>

            normalizeCityName(
                row.city ||
                row.行政區 ||
                row.name
            ) === normalized
        );
    }

    rows.forEach(row => {

        const city =
            normalizeCityName(
                row.city ||
                row.行政區 ||
                row.name
            );

        const medianPrice =
            row.median_total_price ??
            row.median_price_per_ping;

        const rent =
            row.average_monthly_rent;

        const ratio =
            row.price_income_ratio;

        const tr =
            document.createElement("tr");

        tr.innerHTML = `
            <td>${city}</td>

            <td>
                ${
                    medianPrice !== null &&
                    medianPrice !== undefined
                        ? formatNumber(medianPrice) + " 萬"
                        : "—"
                }
            </td>

            <td>
                ${
                    rent !== null &&
                    rent !== undefined
                        ? formatNumber(rent) + " 元"
                        : "—"
                }
            </td>

            <td>
                ${formatRatio(ratio)}
            </td>
        `;

        tbody.appendChild(tr);
    });
}


// ========================================
// 啟動
// ========================================

async function init() {

    try {

        console.log("My Housing 開始啟動");

        await loadHousingData();

        await loadMap();

        console.log("My Housing 啟動完成");

    } catch (error) {

        console.error(
            "網站啟動失敗：",
            error
        );

        showMapError(
            error.message ||
            "請開啟瀏覽器 F12 查看錯誤"
        );
    }
}


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

        clearTimeout(resizeTimer);

        resizeTimer = setTimeout(() => {

            if (mapTopology) {

                try {
                    drawMap();
                } catch (error) {
                    console.error(
                        "重新繪製地圖失敗：",
                        error
                    );
                }

            }

        }, 300);

    }
);
