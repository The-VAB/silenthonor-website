var currentUser = null;
var creditHistory = [];

document.addEventListener("DOMContentLoaded", async function() {
    try {
        var response = await fetch(window.API_BASE + "/api/auth/me", { credentials: "include" });
        if (!response.ok) {
            window.location.href = "login.html";
            return;
        }
        currentUser = await response.json();
        if (currentUser.role === "admin") {
            window.location.href = "admin.html";
            return;
        }
        initCreditTracker(currentUser);
    } catch (e) {
        console.error("Auth check failed:", e);
        window.location.href = "login.html";
    }
});

function initCreditTracker(user) {
    var initials = (user.first_name ? user.first_name.charAt(0) : "") + (user.last_name ? user.last_name.charAt(0) : "");
    document.getElementById("user-avatar").textContent = initials.toUpperCase() || "??";
    document.getElementById("user-name").textContent = user.first_name + " " + user.last_name;

    // Set default date to today
    document.getElementById("score-date").value = new Date().toISOString().split("T")[0];

    loadCreditHistory();
}

async function loadCreditHistory() {
    try {
        var r = await fetch(window.API_BASE + "/api/credit/history", { credentials: "include" });
        if (r.ok) {
            creditHistory = await r.json();
            renderCurrentScores();
            renderHistory();
            renderChart();
        }
    } catch (e) {
        console.error("Failed to load credit history:", e);
    }

    document.getElementById("loading-state").style.display = "none";
    document.getElementById("credit-content").style.display = "block";
}

function renderCurrentScores() {
    // Get latest scores for each bureau
    var latestEquifax = null;
    var latestExperian = null;
    var latestTransunion = null;

    for (var i = 0; i < creditHistory.length; i++) {
        var entry = creditHistory[i];
        if (entry.equifax && !latestEquifax) {
            latestEquifax = { score: entry.equifax, date: entry.date };
        }
        if (entry.experian && !latestExperian) {
            latestExperian = { score: entry.experian, date: entry.date };
        }
        if (entry.transunion && !latestTransunion) {
            latestTransunion = { score: entry.transunion, date: entry.date };
        }
    }

    // Update display
    updateScoreDisplay("equifax", latestEquifax);
    updateScoreDisplay("experian", latestExperian);
    updateScoreDisplay("transunion", latestTransunion);
}

function updateScoreDisplay(bureau, data) {
    var valueEl = document.getElementById("current-" + bureau);
    var dateEl = document.getElementById("date-" + bureau);

    if (data && data.score) {
        valueEl.textContent = data.score;
        valueEl.className = "score-value " + getScoreClass(data.score);
        dateEl.textContent = formatDate(data.date);
    } else {
        valueEl.textContent = "—";
        valueEl.className = "score-value";
        dateEl.textContent = "No data yet";
    }
}

function getScoreClass(score) {
    if (score < 580) return "score-poor";
    if (score < 670) return "score-fair";
    if (score < 740) return "score-good";
    if (score < 800) return "score-verygood";
    return "score-excellent";
}

function formatDate(dateStr) {
    if (!dateStr) return "N/A";
    var d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function renderHistory() {
    var tbody = document.getElementById("history-tbody");

    if (creditHistory.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-row">No scores logged yet. Click "Log Score" to add your first entry.</td></tr>';
        return;
    }

    var html = "";
    for (var i = 0; i < creditHistory.length; i++) {
        var entry = creditHistory[i];
        html += "<tr>";
        html += "<td>" + formatDate(entry.date) + "</td>";
        html += "<td>" + renderScoreCell(entry.equifax) + "</td>";
        html += "<td>" + renderScoreCell(entry.experian) + "</td>";
        html += "<td>" + renderScoreCell(entry.transunion) + "</td>";
        html += "<td>" + (entry.source || "manual") + "</td>";
        html += "<td><button class='delete-btn' onclick='deleteScore(\"" + entry.id + "\")'>Delete</button></td>";
        html += "</tr>";
    }

    tbody.innerHTML = html;
}

function renderScoreCell(score) {
    if (!score) return '<span style="color: var(--muted);">—</span>';
    return '<span class="' + getScoreClass(score) + '">' + score + '</span>';
}

function renderChart() {
    var container = document.getElementById("chart-container");

    if (creditHistory.length < 2) {
        container.innerHTML = '<div class="chart-empty"><p>Log at least 2 entries to see your progress chart</p></div>';
        return;
    }

    // Get last 12 entries, reversed for chronological order
    var entries = creditHistory.slice(0, 12).reverse();

    // Find min/max for scaling
    var allScores = [];
    for (var i = 0; i < entries.length; i++) {
        if (entries[i].equifax) allScores.push(entries[i].equifax);
        if (entries[i].experian) allScores.push(entries[i].experian);
        if (entries[i].transunion) allScores.push(entries[i].transunion);
    }

    if (allScores.length === 0) {
        container.innerHTML = '<div class="chart-empty"><p>No score data to display</p></div>';
        return;
    }

    var minScore = Math.max(300, Math.min.apply(null, allScores) - 50);
    var maxScore = Math.min(850, Math.max.apply(null, allScores) + 50);
    var range = maxScore - minScore;

    // Build chart HTML
    var html = '<div class="chart-lines">';

    // Y-axis labels
    html += '<div class="chart-y-axis">';
    html += '<span>' + maxScore + '</span>';
    html += '<span>' + Math.round(minScore + range * 0.75) + '</span>';
    html += '<span>' + Math.round(minScore + range * 0.5) + '</span>';
    html += '<span>' + Math.round(minScore + range * 0.25) + '</span>';
    html += '<span>' + minScore + '</span>';
    html += '</div>';

    // Chart points
    html += '<div class="chart-points">';
    var width = 100 / (entries.length - 1);

    for (var i = 0; i < entries.length; i++) {
        var entry = entries[i];
        var x = i * width;

        if (entry.equifax) {
            var y = 100 - ((entry.equifax - minScore) / range * 100);
            html += '<div class="chart-point equifax" style="left: ' + x + '%; top: ' + y + '%" title="Equifax: ' + entry.equifax + '"></div>';
        }
        if (entry.experian) {
            var y = 100 - ((entry.experian - minScore) / range * 100);
            html += '<div class="chart-point experian" style="left: ' + x + '%; top: ' + y + '%" title="Experian: ' + entry.experian + '"></div>';
        }
        if (entry.transunion) {
            var y = 100 - ((entry.transunion - minScore) / range * 100);
            html += '<div class="chart-point transunion" style="left: ' + x + '%; top: ' + y + '%" title="TransUnion: ' + entry.transunion + '"></div>';
        }
    }

    html += '</div></div>';

    // Legend
    html += '<div class="chart-legend">';
    html += '<div class="legend-item"><div class="legend-dot equifax"></div><span>Equifax</span></div>';
    html += '<div class="legend-item"><div class="legend-dot experian"></div><span>Experian</span></div>';
    html += '<div class="legend-item"><div class="legend-dot transunion"></div><span>TransUnion</span></div>';
    html += '</div>';

    container.innerHTML = html;
}

// Modal Functions
function openScoreModal() {
    document.getElementById("score-modal-title").textContent = "Log Credit Scores";
    document.getElementById("score-id").value = "";
    document.getElementById("score-date").value = new Date().toISOString().split("T")[0];
    document.getElementById("score-equifax").value = "";
    document.getElementById("score-experian").value = "";
    document.getElementById("score-transunion").value = "";
    document.getElementById("score-source").value = "manual";
    document.getElementById("score-notes").value = "";
    document.getElementById("score-modal").style.display = "flex";
}

function closeScoreModal() {
    document.getElementById("score-modal").style.display = "none";
}

async function saveScore() {
    var equifax = document.getElementById("score-equifax").value;
    var experian = document.getElementById("score-experian").value;
    var transunion = document.getElementById("score-transunion").value;

    // Validate at least one score
    if (!equifax && !experian && !transunion) {
        alert("Please enter at least one credit score.");
        return;
    }

    // Validate score ranges
    function validateScore(score, name) {
        if (score && (parseInt(score) < 300 || parseInt(score) > 850)) {
            alert(name + " score must be between 300 and 850.");
            return false;
        }
        return true;
    }

    if (!validateScore(equifax, "Equifax") ||
        !validateScore(experian, "Experian") ||
        !validateScore(transunion, "TransUnion")) {
        return;
    }

    var payload = {
        date: document.getElementById("score-date").value,
        equifax: equifax ? parseInt(equifax) : null,
        experian: experian ? parseInt(experian) : null,
        transunion: transunion ? parseInt(transunion) : null,
        source: document.getElementById("score-source").value,
        notes: document.getElementById("score-notes").value
    };

    try {
        var r = await fetch(window.API_BASE + "/api/credit/score", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (r.ok) {
            closeScoreModal();
            loadCreditHistory();
        } else {
            alert("Failed to save score.");
        }
    } catch (e) {
        alert("Connection error.");
    }
}

async function deleteScore(id) {
    if (!confirm("Are you sure you want to delete this score entry?")) return;

    try {
        var r = await fetch(window.API_BASE + "/api/credit/" + id, {
            method: "DELETE",
            credentials: "include"
        });

        if (r.ok) {
            loadCreditHistory();
        } else {
            alert("Failed to delete score.");
        }
    } catch (e) {
        alert("Connection error.");
    }
}

async function signOut() {
    try {
        await fetch(window.API_BASE + "/api/auth/logout", { method: "POST", credentials: "include" });
    } catch (e) {}
    localStorage.removeItem("sh_user");
    window.location.href = "login.html";
}
