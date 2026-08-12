let uploadedFiles = [];
let diagnosisData = null;
let chatOpenedFirstTime = false;
let chartInstances = {};
let currentYear = null;
let currentTerritory = '';
let modeloRendered = false;

// DOM references
const uploadZone = document.getElementById("uploadZone");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const uploadBtn = document.getElementById("uploadBtn");
const diagnosticSection = document.getElementById("diagnosticSection");
const diagnosticSummary = document.getElementById("diagnosticSummary");
const diagnosticDetails = document.getElementById("diagnosticDetails");
const applyBtn = document.getElementById("applyBtn");
const landingApplyResult = document.getElementById("landingApplyResult");
const loadingOverlay = document.getElementById("loadingOverlay");
const loadingText = document.getElementById("loadingText");
const chatBubble = document.getElementById("chatBubble");
const chatWindow = document.getElementById("chatWindow");
const chatMessages = document.getElementById("chatMessages");
const userInput = document.getElementById("userInput");
const landingView = document.getElementById("landingView");
const mainApp = document.getElementById("mainApp");
const dashboardView = document.getElementById("dashboardView");
const chatView = document.getElementById("chatView");
const modeloView = document.getElementById("modeloView");

function showToast(message, type) {
    type = type || "error";
    const existing = document.querySelector(".toast-notification");
    if (existing) existing.remove();
    const toast = document.createElement("div");
    toast.className = "toast-notification toast-" + type;
    const icon = type === "error" ? "❌" : type === "success" ? "✅" : "ℹ️";
    toast.innerHTML = '<span class="toast-icon">' + icon + '</span><span class="toast-text">' + message + '</span>';
    document.body.appendChild(toast);
    setTimeout(function () {
        toast.classList.add("toast-fadeout");
        setTimeout(function () { toast.remove(); }, 400);
    }, 4000);
}

function showLoading(message) {
    loadingText.textContent = message || "Procesando...";
    loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
    loadingOverlay.classList.add("hidden");
}

function resetApp() {
    window.location.reload();
}

// ── File Upload ────────────────────────────────

uploadZone.addEventListener("click", function () { fileInput.click(); });
uploadZone.addEventListener("dragover", function (e) { e.preventDefault(); uploadZone.classList.add("drag-over"); });
uploadZone.addEventListener("dragleave", function () { uploadZone.classList.remove("drag-over"); });
uploadZone.addEventListener("drop", function (e) { e.preventDefault(); uploadZone.classList.remove("drag-over"); handleFiles(e.dataTransfer.files); });
fileInput.addEventListener("change", function () { handleFiles(fileInput.files); });

function handleFiles(files) {
    for (let i = 0; i < files.length; i++) {
        const f = files[i];
        const name = f.name.toLowerCase();
        if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) continue;
        uploadedFiles.push(f);
    }
    renderFileList();
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    renderFileList();
}

function renderFileList() {
    if (uploadedFiles.length === 0) {
        fileList.classList.add("hidden");
        uploadBtn.classList.add("hidden");
        return;
    }
    fileList.classList.remove("hidden");
    uploadBtn.classList.remove("hidden");
    let html = "";
    for (let i = 0; i < uploadedFiles.length; i++) {
        const f = uploadedFiles[i];
        const isXlsx = f.name.toLowerCase().endsWith(".xlsx");
        const ext = isXlsx ? "XLSX" : "CSV";
        const size = (f.size / 1024).toFixed(0) + " KB";
        let roleClass = "unknown";
        let roleLabel = "Sin detectar";
        if (f.name.toLowerCase().includes("gl") || f.name.toLowerCase().includes("general")) {
            roleClass = "gl"; roleLabel = "GL";
        } else if (f.name.toLowerCase().includes("chart") || f.name.toLowerCase().includes("cuenta") || f.name.toLowerCase().includes("coa")) {
            roleClass = "coa"; roleLabel = "Plan Cuentas";
        } else if (f.name.toLowerCase().includes("territ") || f.name.toLowerCase().includes("pais") || f.name.toLowerCase().includes("country")) {
            roleClass = "territory"; roleLabel = "Territorios";
        } else if (f.name.toLowerCase().includes("calend") || f.name.toLowerCase().includes("date")) {
            roleClass = "calendar"; roleLabel = "Calendario";
        }
        html += '<div class="file-item">';
        html += '<span class="file-icon">📄</span>';
        html += '<span class="file-name">' + f.name + '</span>';
        html += '<span class="file-role" style="background:' + (isXlsx ? '#e8f5e9' : '#e3f2fd') + ';color:' + (isXlsx ? '#2e7d32' : '#1565c0') + '">' + ext + '</span>';
        html += '<span class="file-size">' + size + '</span>';
        html += '<span class="file-role ' + roleClass + '">' + roleLabel + '</span>';
        html += '<button class="remove-btn" onclick="removeFile(' + i + ')">✕</button>';
        html += '</div>';
    }
    fileList.innerHTML = html;
}

function uploadFiles() {
    if (uploadedFiles.length === 0) return;
    showLoading("Analizando archivos...");
    const formData = new FormData();
    for (let i = 0; i < uploadedFiles.length; i++) formData.append("files", uploadedFiles[i]);
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, 30000);
    fetch("/upload", { method: "POST", body: formData, signal: controller.signal })
        .then(function (r) {
            clearTimeout(timer);
            if (!r.ok) throw new Error("Error HTTP: " + r.status);
            return r.json();
        })
        .then(function (data) {
            diagnosisData = data.diagnosis;
            if (!diagnosisData) throw new Error("El servidor no devolvió un diagnóstico");
            renderDiagnostic(diagnosisData);
        })
        .catch(function (err) {
            showToast("Error al subir archivos: " + err.message, "error");
        })
        .finally(function () {
            hideLoading();
        });
}

function loadSampleData() {
    showLoading("Cargando datos de ejemplo...");
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, 15000);
    fetch("/reset", { method: "POST", signal: controller.signal })
        .then(function (r) {
            clearTimeout(timer);
            if (!r.ok) throw new Error("Error HTTP: " + r.status);
            return r.json();
        })
        .then(function (data) {
            if (data.rows > 0) {
                showMainApp(data);
            } else {
                throw new Error("No hay datos de ejemplo disponibles");
            }
        })
        .catch(function (err) {
            showToast("Error al cargar datos de ejemplo: " + err.message + ". Asegurate de que el servidor esté corriendo.", "error");
        })
        .finally(function () {
            hideLoading();
        });
}

function renderDiagnostic(diag) {
    diagnosticSection.classList.remove("hidden");
    applyBtn.classList.remove("hidden");
    const summary = diag.summary;
    let sumHtml = '<div class="diag-summary-item critical"><div class="diag-count">' + summary.critical + '</div><div class="diag-label">Críticos</div></div>';
    sumHtml += '<div class="diag-summary-item warning"><div class="diag-count">' + summary.warnings + '</div><div class="diag-label">Advertencias</div></div>';
    sumHtml += '<div class="diag-summary-item info"><div class="diag-count">' + summary.info + '</div><div class="diag-label">Informativos</div></div>';
    sumHtml += '<div class="diag-summary-item"><div class="diag-count" style="color:#2c3e50">' + summary.total_files + '</div><div class="diag-label">Archivos</div></div>';
    diagnosticSummary.innerHTML = sumHtml;

    let detailHtml = "";
    const files = diag.files || {};
    const fileNames = Object.keys(files);
    for (let fi = 0; fi < fileNames.length; fi++) {
        const fname = fileNames[fi], fd = files[fname];
        if (fd.status === "error") {
            detailHtml += '<div class="diag-card card-critical"><div class="diag-card-header"><span class="diag-card-icon">🔴</span><span class="diag-card-title">Error al leer ' + fname + '</span></div><div class="diag-card-detail">' + fd.error + '</div></div>';
            continue;
        }
        const roleName = fd.role ? fd.role.name : "Desconocido";
        const roleId = fd.role ? fd.role.id : "unknown";
        detailHtml += '<div class="diag-file-group">';
        detailHtml += '<div class="diag-file-group-header"><span class="fg-icon">📄</span><span class="fg-name">' + fname + '</span><span class="fg-role">' + roleName + '</span><span class="fg-meta">' + fd.rows + ' filas · ' + fd.column_count + ' columnas</span></div>';
        detailHtml += '<div class="diag-file-group-body"><div class="diag-columns-pill">';
        for (let ci = 0; ci < fd.columns.length; ci++) detailHtml += '<span class="col-pill">' + fd.columns[ci] + '</span>';
        detailHtml += '</div>';
        const issues = fd.issues || [];
        for (let ii = 0; ii < issues.length; ii++) {
            const iss = issues[ii];
            detailHtml += '<div class="diag-card card-' + iss.severity + '"><div class="diag-card-header"><span class="diag-card-icon">' + (iss.icon || "ℹ️") + '</span><span class="diag-card-title">' + iss.title + '</span></div><div class="diag-card-detail">' + iss.detail + '</div></div>';
        }
        detailHtml += '</div></div>';
    }
    const rels = diag.relationships || [];
    if (rels.length > 0) {
        detailHtml += '<div class="diag-relations-section"><div class="diag-relations-header"><span class="rl-icon">🔗</span><span class="rl-title">Relaciones entre tablas</span><span class="rl-count">' + rels.length + ' detectadas</span></div><div class="diag-relations-body">';
        for (let ri = 0; ri < rels.length; ri++) {
            const r = rels[ri];
            detailHtml += '<div class="rel-item"><span>' + r.from + '</span><span class="rel-arrow">⟷</span><span>' + r.to + '</span><span class="rel-col">' + r.column + '</span></div>';
        }
        detailHtml += '</div></div>';
    }
    diagnosticDetails.innerHTML = detailHtml;
    diagnosticSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function applyETL() {
    showLoading("Aplicando correcciones ETL...");
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, 30000);
    fetch("/apply", { method: "POST", signal: controller.signal })
        .then(function (r) {
            clearTimeout(timer);
            if (!r.ok) throw new Error("Error HTTP: " + r.status);
            return r.json();
        })
        .then(function (data) {
            showMainApp(data);
        })
        .catch(function (err) {
            showToast("Error al aplicar ETL: " + err.message, "error");
        })
        .finally(function () {
            hideLoading();
        });
    return false;
}

function showMainApp(data) {
    landingView.classList.add("hidden");
    mainApp.classList.remove("hidden");
    applyBtn.classList.add("hidden");
    const compactResult = document.querySelector("#chatView .apply-result-compact");
    if (compactResult) {
        compactResult.classList.remove("hidden");
        let html = "<h3>✅ Datos listos</h3><ul>";
        html += "<li>" + data.rows + " registros procesados</li>";
        if (data.etl_summary) {
            html += "<li>" + data.etl_summary.original_rows + " → " + data.etl_summary.final_rows + "</li>";
            html += "<li>" + data.etl_summary.duplicates_removed + " duplicados</li>";
            html += "<li>" + data.etl_summary.nulls_removed + " nulos</li>";
        }
        html += "</ul>";
        compactResult.innerHTML = html;
    }
    switchView('dashboard');
    initFilters();
    refreshDashboard();
}

// ── View Toggle ────────────────────────────────

function switchView(view) {
    document.querySelectorAll(".app-view").forEach(function (el) { el.classList.add("hidden"); });
    document.querySelectorAll(".view-btn[data-view]").forEach(function (btn) { btn.classList.remove("active"); });

    chatWindow.classList.add("hidden");
    chatWindow.classList.remove("chat-maximized");
    chatBubble.classList.remove("hidden");

    if (view === "chat") {
        chatView.classList.remove("hidden");
        document.querySelector('.view-btn[data-view="chat"]').classList.add("active");
        chatWindow.classList.add("chat-maximized");
        chatWindow.classList.remove("hidden");
    } else if (view === "dashboard") {
        dashboardView.classList.remove("hidden");
        document.querySelector('.view-btn[data-view="dashboard"]').classList.add("active");
    } else if (view === "modelo") {
        modeloView.classList.remove("hidden");
        document.querySelector('.view-btn[data-view="modelo"]').classList.add("active");
        if (!modeloRendered) {
            modeloRendered = true;
            renderModelViewer();
        }
    }
}

// ── Filters ────────────────────────────────────

function initFilters() {
    fetch("/resumen").then(function (r) { return r.json(); }).then(function (data) {
        const anos = data.anos || [];
        const slicer = document.getElementById("yearSlicer");
        let html = '<button class="filter-slicer-btn active" data-year="" onclick="selectYear(this, \'\')">Todos</button>';
        anos.forEach(function (a) {
            html += '<button class="filter-slicer-btn" data-year="' + a + '" onclick="selectYear(this, ' + a + ')">' + a + '</button>';
        });
        slicer.innerHTML = html;

        const paises = data.paises || [];
        const sel = document.getElementById("territorySelect");
        paises.forEach(function (p) {
            const opt = document.createElement("option");
            opt.value = p;
            opt.textContent = p;
            sel.appendChild(opt);
        });
    }).catch(function () {});
}

function selectYear(btn, year) {
    document.querySelectorAll(".filter-slicer-btn").forEach(function (b) { b.classList.remove("active"); });
    btn.classList.add("active");
    currentYear = year || null;
    refreshDashboard();
}

function refreshDashboard() {
    currentTerritory = document.getElementById("territorySelect").value;
    renderDashboard(currentYear, currentTerritory);
}

// ── Dashboard ──────────────────────────────────

function renderDashboard(year, territory) {
    let url = "/dashboard?";
    if (year) url += "year=" + year + "&";
    if (territory) url += "territory=" + encodeURIComponent(territory);
    const kpiGrid = document.getElementById("kpiGrid");
    const chartGrid = document.getElementById("chartGrid");
    const accountsBody = document.getElementById("accountsBody");

    kpiGrid.innerHTML = '<div class="kpi-dash-card" style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:40px"><div class="spinner" style="margin:0 auto 10px"></div>Cargando...</div>';

    fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) {
                kpiGrid.innerHTML = '<div class="kpi-dash-card" style="grid-column:1/-1;text-align:center;color:var(--color-critical)">' + data.error + '</div>';
                chartGrid.innerHTML = '';
                accountsBody.innerHTML = '';
                return;
            }

            const periodText = year ? "Año " + year : "General";
            if (territory) periodText += " · " + territory;
            document.getElementById("dashPeriod").textContent = periodText;

            // KPIs
            let kpiHtml = "";
            (data.kpis || []).forEach(function (k) {
                const colorClass = k.color ? " kpi-" + k.color : "";
                let vsHtml = "";
                if (k.vs_prev) {
                    vsHtml = '<div class="kpi-dash-vs ' + k.vs_color + '">' + k.vs_prev + ' vs año ant.</div>';
                }
                kpiHtml += '<div class="kpi-dash-card' + colorClass + '">';
                kpiHtml += '<div class="kpi-dash-icon">' + (k.icon || "📊") + '</div>';
                kpiHtml += '<div class="kpi-dash-value">' + k.value + '</div>';
                kpiHtml += '<div class="kpi-dash-label">' + k.label + '</div>';
                kpiHtml += vsHtml;
                kpiHtml += '</div>';
            });
            kpiGrid.innerHTML = kpiHtml;

            // Charts
            let chartHtml = "";
            (data.charts || []).forEach(function (ch, idx) {
                const isFull = ch.type === "line" ? " chart-card-full" : "";
                chartHtml += '<div class="chart-card' + isFull + '">';
                chartHtml += '<h4>' + ch.title + '</h4>';
                chartHtml += '<canvas id="chart-' + idx + '"></canvas></div>';
            });
            chartGrid.innerHTML = chartHtml;

            // Initialize Chart.js after DOM update
            setTimeout(function () { initCharts(data.charts); }, 50);

            // Top accounts table
            let tbodyHtml = "";
            (data.top_accounts || []).forEach(function (r, i) {
                tbodyHtml += '<tr>';
                tbodyHtml += '<td class="rank-col">' + (i + 1) + '</td>';
                tbodyHtml += '<td>' + (r.SubAccount || "-") + '</td>';
                tbodyHtml += '<td>' + (r.SubClass || "-") + '</td>';
                tbodyHtml += '<td>' + (r.Country || "-") + '</td>';
                tbodyHtml += '<td class="amt-col">$' + (r.Amount_abs || 0).toLocaleString(undefined, {minimumFractionDigits: 2}) + '</td>';
                tbodyHtml += '</tr>';
            });
            accountsBody.innerHTML = tbodyHtml || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:20px">Sin datos</td></tr>';
        })
        .catch(function () {
            kpiGrid.innerHTML = '<div class="kpi-dash-card" style="grid-column:1/-1;text-align:center;color:var(--color-critical)">Error al cargar dashboard</div>';
        });
}

function initCharts(charts) {
    // Destroy previous instances
    Object.keys(chartInstances).forEach(function (key) {
        if (chartInstances[key]) chartInstances[key].destroy();
    });
    chartInstances = {};

    const colors = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#34495e"];
    (charts || []).forEach(function (ch, idx) {
        const canvas = document.getElementById("chart-" + idx);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const config = { type: ch.type, data: { labels: ch.labels, datasets: [] }, options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { display: ch.type !== "bar", position: "bottom", labels: { boxWidth: 12, padding: 8, font: { size: 10 } } } } } };

        if (ch.type === "doughnut") {
            config.data.datasets = [{ data: ch.values, backgroundColor: colors.slice(0, ch.labels.length), borderWidth: 1 }];
        } else if (ch.type === "bar") {
            config.data.datasets = [{ label: "Monto ($)", data: ch.values, backgroundColor: colors.slice(0, ch.labels.length).map(function (c) { return c + "CC"; }), borderColor: colors.slice(0, ch.labels.length), borderWidth: 1, borderRadius: 4 }];
            config.options.scales = { y: { beginAtZero: true, ticks: { callback: function (v) { return "$" + v.toLocaleString(); }, font: { size: 9 } } }, x: { ticks: { font: { size: 9 } } } };
            config.options.plugins.legend.display = false;
        } else if (ch.type === "line") {
            config.data.datasets = [{ label: "Monto ($)", data: ch.values, borderColor: "#3498db", backgroundColor: "rgba(52,152,219,0.1)", fill: true, tension: 0.3, pointRadius: 3, pointBackgroundColor: "#3498db" }];
            config.options.scales = { y: { beginAtZero: true, ticks: { callback: function (v) { return "$" + v.toLocaleString(); }, font: { size: 9 } } }, x: { ticks: { font: { size: 8 }, maxTicksLimit: 10 } } };
            config.options.plugins.legend.display = false;
        }

        try {
            chartInstances["chart-" + idx] = new Chart(ctx, config);
        } catch (e) {}
    });
}

// ── Main Chat ──────────────────────────────────

function showChatBubble() {
    chatBubble.classList.remove("hidden");
}

function toggleChat() {
    var isHidden = chatWindow.classList.contains("hidden");
    if (isHidden) {
        chatWindow.classList.remove("hidden");
        userInput.focus();
        if (!chatOpenedFirstTime) {
            chatOpenedFirstTime = true;
            renderSuggestions();
        }
    } else {
        chatWindow.classList.add("hidden");
    }
}

function renderSuggestions() {
    const list = document.getElementById("suggestionsList");
    list.innerHTML = '<div class="suggestion-chip" style="grid-column:1/-1;justify-content:center;color:var(--text-muted)">Cargando sugerencias...</div>';

    fetch("/suggestions")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            const items = data.suggestions || [];
            const cats = {};
            items.forEach(function (q) {
                const cat = q.category || "general";
                if (!cats[cat]) cats[cat] = [];
                cats[cat].push(q);
            });
            let html = "";
            const catLabels = {
                ventas: "💰 Ventas", gastos: "💸 Gastos", neto: "📈 Resultado",
                pais: "🌍 País/Región", pais_menor: "🌍 País/Región",
                cuenta: "🏦 Cuentas", cuenta_menor: "🏦 Cuentas",
                cuentas_mas_usadas: "🧾 Cuentas",
                mensual: "📅 Por mes", territorio: "🗺️ Territorio",
                resumen: "📊 Resumen", dashboard: "📊 Dashboard",
                modelo: "🔗 Modelo", etl: "🛠️ ETL",
                grafico: "📈 Gráficos", anomalia: "⚠️ Anomalías",
                prediccion: "🔮 Predicción", comparativa: "⚖️ Comparativa",
                general: "💡 Generales",
            };
            Object.keys(cats).forEach(function (cat) {
                const label = catLabels[cat] || "💡 " + cat;
                html += '<div class="suggestion-group-label">' + label + '</div>';
                cats[cat].forEach(function (q) {
                    const escaped = q.text.replace(/'/g, "\\'");
                    html += '<div class="suggestion-chip" onclick="sendSuggestion(\'' + escaped + '\')">';
                    html += '<span class="chip-icon">' + (q.icon || "💡") + '</span><span>' + q.text + '</span></div>';
                });
            });
            list.innerHTML = html || '<div class="suggestion-chip" style="grid-column:1/-1;justify-content:center;color:var(--text-muted)">Sin sugerencias</div>';
        })
        .catch(function () {
            list.innerHTML = '<div class="suggestion-chip" style="grid-column:1/-1;justify-content:center;color:var(--color-critical)">🔌 Sin conexión al servidor</div>';
        });
}

function toggleSuggestions() {
    const panel = document.getElementById("chatSuggestions");
    if (panel.classList.contains("hidden")) {
        panel.classList.remove("hidden");
        renderSuggestions();
    } else {
        panel.classList.add("hidden");
    }
}

function sendSuggestion(text) {
    document.getElementById("userInput").value = text;
    sendMessage();
}

function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    addMessage(message, "user");
    userInput.value = "";
    const sendBtn = document.getElementById("sendBtn");
    sendBtn.disabled = true;
    userInput.disabled = true;
    const typing = addTypingIndicator();

    fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: message }),
    })
        .then(function (response) {
            if (!response.ok) throw new Error("Error HTTP: " + response.status);
            return response.json();
        })
        .then(function (data) {
            typing.remove();
            const text = data.answer || "";
            addMessageWithExtra(text, "bot", data);
        })
        .catch(function () {
            typing.remove();
            addMessage("Error al conectar con el servidor.", "bot");
        })
        .finally(function () {
            sendBtn.disabled = false;
            userInput.disabled = false;
            userInput.focus();
        });
}

function addMessage(text, sender) { addMessageWithExtra(text, sender, {}); }

function addMessageWithExtra(text, sender, extra) {
    const div = document.createElement("div");
    div.className = "message " + sender + "-message";
    const content = document.createElement("div");
    content.className = "message-content";
    const textDiv = document.createElement("div");
    let iaBadge = "";
    if (text.includes('<sup') && text.includes('✨ IA')) {
        const badgeStart = text.indexOf('<sup');
        textDiv.textContent = text.substring(0, badgeStart).trim();
        iaBadge = text.substring(badgeStart);
    } else {
        textDiv.textContent = text;
    }
    content.appendChild(textDiv);
    if (iaBadge) {
        const badgeDiv = document.createElement("div");
        badgeDiv.innerHTML = iaBadge;
        content.appendChild(badgeDiv);
    }

    if (extra.dashboard) {
        const dashDiv = document.createElement("div");
        dashDiv.className = "dashboard-inline";
        const kpis = extra.dashboard.kpis || [];
        if (kpis.length > 0) {
            const kpiRow = document.createElement("div");
            kpiRow.className = "kpi-row";
            kpis.forEach(function (k) {
                const card = document.createElement("div");
                card.className = "kpi-card" + (k.color ? " kpi-" + k.color : "");
                card.innerHTML = '<div class="kpi-icon">' + (k.icon || "") + '</div><div class="kpi-value">' + k.value + '</div><div class="kpi-label">' + k.label + '</div>';
                kpiRow.appendChild(card);
            });
            dashDiv.appendChild(kpiRow);
        }
        const charts = extra.dashboard.charts || [];
        charts.forEach(function (ch) {
            const chartBox = document.createElement("div");
            chartBox.className = "dashboard-chart";
            chartBox.innerHTML = "<h4>" + ch.title + "</h4>";
            const barContainer = document.createElement("div");
            barContainer.className = "mini-bar-container";
            const maxVal = Math.max.apply(null, ch.values);
            ch.labels.forEach(function (l, i) {
                const pct = maxVal > 0 ? ((ch.values[i] / maxVal) * 100).toFixed(0) : 0;
                const bar = document.createElement("div");
                bar.className = "mini-bar";
                bar.innerHTML = '<span class="mini-bar-label">' + l + '</span><div class="mini-bar-track"><div class="mini-bar-fill" style="width:' + pct + '%"></div></div><span class="mini-bar-val">$' + Number(ch.values[i]).toLocaleString() + '</span>';
                barContainer.appendChild(bar);
            });
            chartBox.appendChild(barContainer);
            dashDiv.appendChild(chartBox);
        });
        content.appendChild(dashDiv);
    }

    if (extra.chart_base64) {
        const imgDiv = document.createElement("div");
        imgDiv.className = "chart-inline";
        const img = document.createElement("img");
        img.src = "data:image/png;base64," + extra.chart_base64;
        img.alt = "Gráfico";
        img.style.maxWidth = "100%";
        img.style.borderRadius = "8px";
        img.style.marginTop = "8px";
        imgDiv.appendChild(img);
        content.appendChild(imgDiv);
    }

    div.appendChild(content);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

function addTypingIndicator() {
    const div = document.createElement("div");
    div.className = "message bot-message";
    div.innerHTML = '<div class="message-content">Escribiendo...</div>';
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

// ── Model Viewer (HTML Schema) ─────────────────

function renderModelViewer() {
    const container = document.getElementById("modeloSchema");
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)"><div class="spinner" style="margin:0 auto 10px"></div>Cargando modelo...</div>';

    fetch("/modelo")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            const tablas = data.tablas || [];
            const columnasPorTabla = data.columnas_por_tabla || {};
            const relaciones = data.relaciones || [];
            if (tablas.length === 0) { container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px">No hay datos del modelo</div>'; return; }

            const colors = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12"];
            let tableCards = "";
            tablas.forEach(function (t, idx) {
                const cols = columnasPorTabla[t] || [];
                let rowsHtml = "";
                cols.forEach(function (c) {
                    const isKey = c.toLowerCase().includes("_key") || c.toLowerCase().includes("_code") || c.toLowerCase().includes("_id") || c === "Date";
                    rowsHtml += '<div class="modelo-table-col">';
                    if (isKey) rowsHtml += '<span class="mt-col-key">🔑</span>';
                    rowsHtml += c + '</div>';
                });
                const borderColor = colors[idx % colors.length];
                tableCards += '<div class="modelo-table-card" style="border-top:3px solid ' + borderColor + '">';
                tableCards += '<div class="modelo-table-header" style="background:' + borderColor + '"><span class="mt-name">📄 ' + t + '</span><span class="mt-count">' + cols.length + ' cols</span></div>';
                tableCards += '<div class="modelo-table-body">' + rowsHtml + '</div></div>';
            });

            let relHtml = "";
            relaciones.forEach(function (r) {
                relHtml += '<div class="modelo-rel-item">';
                relHtml += '<span class="modelo-rel-table">' + r.from + '</span>';
                relHtml += '<span class="modelo-rel-col">' + r.column + '</span>';
                relHtml += '<span class="modelo-rel-arrow">⟷</span>';
                relHtml += '<span class="modelo-rel-col">' + r.column + '</span>';
                relHtml += '<span class="modelo-rel-table">' + r.to + '</span>';
                relHtml += '</div>';
            });

            let html = '<div class="modelo-tables-grid">' + tableCards + '</div>';
            if (relaciones.length > 0) {
                html += '<div class="modelo-relations"><div class="modelo-relations-title">🔗 Relaciones</div>' + relHtml + '</div>';
            }
            container.innerHTML = html;
        })
        .catch(function () {
            container.innerHTML = '<div style="text-align:center;color:var(--color-critical);padding:40px">Error al cargar el modelo</div>';
        });
}

// ── Theme ──────────────────────────────────────

function toggleTheme() {
    const body = document.body;
    const btn = document.getElementById("themeToggle");
    body.classList.toggle("dark-mode");
    btn.textContent = body.classList.contains("dark-mode") ? "☀️" : "🌙";
    localStorage.setItem("gl-theme", body.classList.contains("dark-mode") ? "dark" : "light");
}

function loadTheme() {
    const saved = localStorage.getItem("gl-theme");
    const btn = document.getElementById("themeToggle");
    if (saved === "dark") { document.body.classList.add("dark-mode"); btn.textContent = "☀️"; }
    else { btn.textContent = "🌙"; }
}

document.addEventListener("DOMContentLoaded", function () {
    loadTheme();
    userInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") sendMessage();
    });
});
