var currentUser = null;
var disputes = [];
var currentFilter = "all";
var currentDisputeId = null;

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
        initDisputeTracker(currentUser);
    } catch (e) {
        console.error("Auth check failed:", e);
        window.location.href = "login.html";
    }
});

function initDisputeTracker(user) {
    var initials = (user.first_name ? user.first_name.charAt(0) : "") + (user.last_name ? user.last_name.charAt(0) : "");
    document.getElementById("user-avatar").textContent = initials.toUpperCase() || "??";
    document.getElementById("user-name").textContent = user.first_name + " " + user.last_name;

    loadDisputes();
}

async function loadDisputes() {
    try {
        var r = await fetch(window.API_BASE + "/api/disputes", { credentials: "include" });
        if (r.ok) {
            disputes = await r.json();
            renderDisputes();
            updateStats();
        }
    } catch (e) {
        console.error("Failed to load disputes:", e);
    }

    document.getElementById("loading-state").style.display = "none";
    document.getElementById("disputes-content").style.display = "block";
}

function updateStats() {
    var total = disputes.length;
    var pending = disputes.filter(function(d) { return d.status === "pending" || d.status === "sent"; }).length;
    var resolved = disputes.filter(function(d) { return d.status === "resolved"; }).length;
    var escalated = disputes.filter(function(d) { return d.status === "escalated"; }).length;

    document.getElementById("stat-total").textContent = total;
    document.getElementById("stat-pending").textContent = pending;
    document.getElementById("stat-resolved").textContent = resolved;
    document.getElementById("stat-escalated").textContent = escalated;
}

function filterDisputes(filter) {
    currentFilter = filter;

    // Update active tab
    var tabs = document.querySelectorAll(".filter-tab");
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].classList.remove("active");
        if (tabs[i].textContent.toLowerCase().indexOf(filter) !== -1 || (filter === "all" && tabs[i].textContent === "All")) {
            tabs[i].classList.add("active");
        }
    }

    renderDisputes();
}

function renderDisputes() {
    var filtered = disputes;

    if (currentFilter !== "all") {
        filtered = disputes.filter(function(d) {
            return d.status === currentFilter;
        });
    }

    var container = document.getElementById("disputes-list");

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">&#128221;</div><h3>No Disputes</h3><p>' +
            (currentFilter === "all" ? 'Start tracking your credit report disputes by clicking the "New Dispute" button above.' : 'No disputes match this filter.') +
            '</p></div>';
        return;
    }

    var html = "";
    for (var i = 0; i < filtered.length; i++) {
        var d = filtered[i];
        html += renderDisputeCard(d);
    }

    container.innerHTML = html;
}

function renderDisputeCard(d) {
    var statusClass = "status-" + d.status;
    var statusText = getStatusText(d.status);
    var reasonText = getReasonText(d.dispute_reason);

    var html = "<div class='dispute-card' onclick='viewDispute(\"" + d.id + "\")'>";
    html += "<div class='dispute-card-header'>";
    html += "<div><div class='dispute-account'>" + (d.account_name || "Unnamed Account") + "</div>";
    html += "<div class='dispute-bureau'>" + (d.bureau || "Bureau not specified") + (d.account_number ? " - xxxx" + d.account_number : "") + "</div></div>";
    html += "<span class='dispute-status " + statusClass + "'>" + statusText + "</span>";
    html += "</div>";

    if (reasonText) {
        html += "<div class='dispute-reason'>" + reasonText + "</div>";
    }

    html += "<div class='dispute-card-footer'>";
    if (d.date_sent) {
        html += "<div class='dispute-date'>Sent: " + formatDate(d.date_sent) + "</div>";
    } else {
        html += "<div class='dispute-date'>Created: " + formatDate(d.created_at) + "</div>";
    }
    if (d.tracking_number) {
        html += "<div class='dispute-tracking'>" + d.tracking_number + "</div>";
    }
    html += "</div></div>";

    return html;
}

function getStatusText(status) {
    var statuses = {
        "draft": "Draft",
        "sent": "Sent",
        "pending": "Awaiting Response",
        "resolved": "Resolved",
        "escalated": "Needs Follow-up"
    };
    return statuses[status] || status;
}

function getReasonText(reason) {
    var reasons = {
        "not_mine": "Account not mine",
        "paid": "Account paid but showing balance",
        "wrong_amount": "Incorrect balance amount",
        "wrong_status": "Incorrect account status",
        "duplicate": "Duplicate listing",
        "outdated": "Outdated information (7+ years)",
        "identity_theft": "Identity theft",
        "other": "Other"
    };
    return reasons[reason] || reason || "";
}

function formatDate(dateStr) {
    if (!dateStr) return "N/A";
    var d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// Modal Functions
function openDisputeModal(dispute) {
    document.getElementById("dispute-modal-title").textContent = dispute ? "Edit Dispute" : "New Dispute";
    document.getElementById("dispute-id").value = dispute ? dispute.id : "";
    document.getElementById("dispute-bureau").value = dispute ? dispute.bureau : "";
    document.getElementById("dispute-status").value = dispute ? dispute.status : "draft";
    document.getElementById("dispute-account-name").value = dispute ? dispute.account_name : "";
    document.getElementById("dispute-account-number").value = dispute ? dispute.account_number : "";
    document.getElementById("dispute-reason").value = dispute ? dispute.dispute_reason : "";
    document.getElementById("dispute-date-sent").value = dispute && dispute.date_sent ? dispute.date_sent.split("T")[0] : "";
    document.getElementById("dispute-tracking").value = dispute ? dispute.tracking_number || "" : "";
    document.getElementById("dispute-date-response").value = dispute && dispute.date_response ? dispute.date_response.split("T")[0] : "";
    document.getElementById("dispute-outcome").value = dispute ? dispute.response_outcome || "" : "";
    document.getElementById("dispute-notes").value = dispute ? dispute.notes || "" : "";

    document.getElementById("delete-dispute-btn").style.display = dispute ? "inline-block" : "none";
    document.getElementById("dispute-modal").style.display = "flex";
}

function closeDisputeModal() {
    document.getElementById("dispute-modal").style.display = "none";
}

async function saveDispute() {
    var id = document.getElementById("dispute-id").value;
    var payload = {
        bureau: document.getElementById("dispute-bureau").value,
        status: document.getElementById("dispute-status").value,
        account_name: document.getElementById("dispute-account-name").value,
        account_number: document.getElementById("dispute-account-number").value,
        dispute_reason: document.getElementById("dispute-reason").value,
        date_sent: document.getElementById("dispute-date-sent").value || null,
        tracking_number: document.getElementById("dispute-tracking").value,
        date_response: document.getElementById("dispute-date-response").value || null,
        response_outcome: document.getElementById("dispute-outcome").value || null,
        notes: document.getElementById("dispute-notes").value
    };

    if (!payload.bureau || !payload.account_name) {
        alert("Bureau and account name are required.");
        return;
    }

    try {
        var url = id ? window.API_BASE + "/api/disputes/" + id : window.API_BASE + "/api/disputes";
        var method = id ? "PUT" : "POST";

        var r = await fetch(url, {
            method: method,
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (r.ok) {
            closeDisputeModal();
            loadDisputes();
        } else {
            alert("Failed to save dispute.");
        }
    } catch (e) {
        alert("Connection error.");
    }
}

async function deleteDispute() {
    var id = document.getElementById("dispute-id").value;
    if (!id) return;

    if (!confirm("Are you sure you want to delete this dispute?")) return;

    try {
        var r = await fetch(window.API_BASE + "/api/disputes/" + id, {
            method: "DELETE",
            credentials: "include"
        });

        if (r.ok) {
            closeDisputeModal();
            loadDisputes();
        } else {
            alert("Failed to delete dispute.");
        }
    } catch (e) {
        alert("Connection error.");
    }
}

function viewDispute(id) {
    currentDisputeId = id;
    var dispute = null;
    for (var i = 0; i < disputes.length; i++) {
        if (disputes[i].id === id) {
            dispute = disputes[i];
            break;
        }
    }

    if (!dispute) return;

    var html = "";
    html += "<div class='detail-row'><div class='detail-label'>Bureau</div><div class='detail-value'>" + (dispute.bureau || "N/A") + "</div></div>";
    html += "<div class='detail-row'><div class='detail-label'>Account</div><div class='detail-value'>" + (dispute.account_name || "N/A") + (dispute.account_number ? " (xxxx" + dispute.account_number + ")" : "") + "</div></div>";
    html += "<div class='detail-row'><div class='detail-label'>Status</div><div class='detail-value'><span class='dispute-status status-" + dispute.status + "'>" + getStatusText(dispute.status) + "</span></div></div>";
    html += "<div class='detail-row'><div class='detail-label'>Reason</div><div class='detail-value'>" + getReasonText(dispute.dispute_reason) + "</div></div>";

    if (dispute.date_sent) {
        html += "<div class='detail-row'><div class='detail-label'>Date Sent</div><div class='detail-value'>" + formatDate(dispute.date_sent) + "</div></div>";
    }
    if (dispute.tracking_number) {
        html += "<div class='detail-row'><div class='detail-label'>Tracking #</div><div class='detail-value' style='font-family: monospace;'>" + dispute.tracking_number + "</div></div>";
    }
    if (dispute.date_response) {
        html += "<div class='detail-row'><div class='detail-label'>Response Date</div><div class='detail-value'>" + formatDate(dispute.date_response) + "</div></div>";
    }
    if (dispute.response_outcome) {
        html += "<div class='detail-row'><div class='detail-label'>Outcome</div><div class='detail-value'>" + dispute.response_outcome + "</div></div>";
    }
    if (dispute.notes) {
        html += "<div class='detail-row'><div class='detail-label'>Notes</div><div class='detail-value'>" + dispute.notes + "</div></div>";
    }

    document.getElementById("detail-content").innerHTML = html;
    document.getElementById("detail-modal").style.display = "flex";
}

function closeDetailModal() {
    document.getElementById("detail-modal").style.display = "none";
    currentDisputeId = null;
}

function editCurrentDispute() {
    if (!currentDisputeId) return;

    var dispute = null;
    for (var i = 0; i < disputes.length; i++) {
        if (disputes[i].id === currentDisputeId) {
            dispute = disputes[i];
            break;
        }
    }

    closeDetailModal();
    if (dispute) {
        openDisputeModal(dispute);
    }
}

async function signOut() {
    try {
        await fetch(window.API_BASE + "/api/auth/logout", { method: "POST", credentials: "include" });
    } catch (e) {}
    localStorage.removeItem("sh_user");
    window.location.href = "login.html";
}
