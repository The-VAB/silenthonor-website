var currentUser = null;
var counselorData = null;
var selectedDate = null;
var selectedTime = null;
var currentWeekStart = null;

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
        initCounselor(currentUser);
    } catch (e) {
        console.error("Auth check failed:", e);
        window.location.href = "login.html";
    }
});

function initCounselor(user) {
    var initials = (user.first_name ? user.first_name.charAt(0) : "") + (user.last_name ? user.last_name.charAt(0) : "");
    document.getElementById("user-avatar").textContent = initials.toUpperCase() || "??";
    document.getElementById("user-name").textContent = user.first_name + " " + user.last_name;

    currentWeekStart = getWeekStart(new Date());
    loadCounselor();
}

async function loadCounselor() {
    try {
        var r = await fetch(window.API_BASE + "/api/counselor/assigned", { credentials: "include" });
        if (r.ok) {
            counselorData = await r.json();
            renderCounselor(counselorData);
        } else {
            showNoCounselor();
        }
    } catch (e) {
        console.error("Failed to load counselor:", e);
        showNoCounselor();
    }
}

function renderCounselor(data) {
    document.getElementById("loading-state").style.display = "none";
    document.getElementById("counselor-content").style.display = "block";

    if (!data.id) {
        showNoCounselor();
        return;
    }

    document.getElementById("no-counselor").style.display = "none";
    document.getElementById("counselor-assigned").style.display = "grid";

    // Set counselor info
    var nameParts = (data.name || "Your Counselor").split(" ");
    var initials = nameParts.map(function(n) { return n.charAt(0); }).join("").toUpperCase();
    document.getElementById("counselor-initials").textContent = initials || "??";
    document.getElementById("counselor-name").textContent = data.name || "Your Counselor";
    document.getElementById("counselor-title").textContent = data.title || "Certified Financial Counselor";

    // Specialties
    var specialtiesHtml = "";
    var specialties = data.specialties || ["Credit Repair", "Debt Management", "VA Benefits"];
    for (var i = 0; i < specialties.length; i++) {
        specialtiesHtml += "<span class='specialty-tag'>" + specialties[i] + "</span>";
    }
    document.getElementById("counselor-specialties").innerHTML = specialtiesHtml;

    // Bio
    var bio = data.bio || "Dedicated to helping veterans achieve financial freedom and rebuild their credit through personalized guidance and proven strategies.";
    document.getElementById("counselor-bio").textContent = bio;

    // Load upcoming appointment slots
    renderAppointmentSlots();

    // Load progress notes (if any)
    loadProgressNotes();
}

function showNoCounselor() {
    document.getElementById("loading-state").style.display = "none";
    document.getElementById("counselor-content").style.display = "block";
    document.getElementById("no-counselor").style.display = "block";
    document.getElementById("counselor-assigned").style.display = "none";
}

function renderAppointmentSlots() {
    // Show next 3 available slots (mock data for now)
    var slots = getNextAvailableSlots(3);
    var html = "";

    for (var i = 0; i < slots.length; i++) {
        var slot = slots[i];
        html += "<div class='slot-item'>";
        html += "<span class='slot-time'>" + slot.display + "</span>";
        html += "<button class='slot-book' onclick='bookSlot(\"" + slot.date + "\", \"" + slot.time + "\")'>Book</button>";
        html += "</div>";
    }

    document.getElementById("appointment-slots").innerHTML = html;
}

function getNextAvailableSlots(count) {
    var slots = [];
    var now = new Date();
    var day = new Date(now);
    day.setDate(day.getDate() + 1); // Start from tomorrow

    var times = ["10:00 AM", "2:00 PM", "4:00 PM"];
    var timeIndex = 0;

    while (slots.length < count) {
        // Skip weekends
        if (day.getDay() !== 0 && day.getDay() !== 6) {
            var dayName = day.toLocaleDateString("en-US", { weekday: "short" });
            var dateStr = day.toLocaleDateString("en-US", { month: "short", day: "numeric" });
            slots.push({
                date: day.toISOString().split("T")[0],
                time: times[timeIndex % times.length],
                display: dayName + " " + dateStr + " at " + times[timeIndex % times.length]
            });
            timeIndex++;
        }
        day.setDate(day.getDate() + 1);
    }

    return slots;
}

function bookSlot(date, time) {
    selectedDate = date;
    selectedTime = time;
    confirmAppointment();
}

async function loadProgressNotes() {
    // Notes would come from an API endpoint if counselor has added them
    // For now, show placeholder
    var notesContainer = document.getElementById("progress-notes");

    // Mock notes for demonstration
    var mockNotes = [
        { date: "2025-05-15", content: "Initial assessment completed. Member has 3 collections to dispute." },
        { date: "2025-05-10", content: "Enrolled in Credit 101 course. Strong motivation to improve credit." }
    ];

    if (mockNotes.length === 0) {
        notesContainer.innerHTML = "<p class='muted-text'>Your counselor will add notes as you progress through your credit repair journey.</p>";
        return;
    }

    var html = "";
    for (var i = 0; i < mockNotes.length; i++) {
        var note = mockNotes[i];
        var date = new Date(note.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        html += "<div class='note-item'>";
        html += "<div class='note-date'>" + date + "</div>";
        html += "<div class='note-content'>" + note.content + "</div>";
        html += "</div>";
    }

    notesContainer.innerHTML = html;
}

// Schedule Modal
function showScheduleModal() {
    document.getElementById("schedule-modal").style.display = "flex";
    renderWeek();
}

function closeModal() {
    document.getElementById("schedule-modal").style.display = "none";
    selectedDate = null;
    selectedTime = null;
    document.getElementById("confirm-btn").disabled = true;
}

function getWeekStart(date) {
    var d = new Date(date);
    var day = d.getDay();
    var diff = d.getDate() - day + (day === 0 ? -6 : 1); // Monday
    return new Date(d.setDate(diff));
}

function renderWeek() {
    var daysGrid = document.getElementById("days-grid");
    var weekLabel = document.getElementById("week-label");

    var today = new Date();
    today.setHours(0, 0, 0, 0);

    var weekEnd = new Date(currentWeekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);

    var startStr = currentWeekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    var endStr = weekEnd.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    weekLabel.textContent = startStr + " - " + endStr;

    var dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    var html = "";

    for (var i = 0; i < 7; i++) {
        var d = new Date(currentWeekStart);
        d.setDate(d.getDate() + i);

        var isPast = d < today;
        var isWeekend = i >= 5; // Sat, Sun
        var disabled = isPast || isWeekend;
        var dateStr = d.toISOString().split("T")[0];
        var isSelected = selectedDate === dateStr;

        html += "<button class='day-btn" + (isSelected ? " selected" : "") + "' ";
        html += "onclick='selectDate(\"" + dateStr + "\")' ";
        html += disabled ? "disabled" : "";
        html += ">";
        html += "<span class='day-label'>" + dayNames[i] + "</span>";
        html += "<span class='day-num'>" + d.getDate() + "</span>";
        html += "</button>";
    }

    daysGrid.innerHTML = html;

    if (selectedDate) {
        renderTimeSlots();
    }
}

function prevWeek() {
    currentWeekStart.setDate(currentWeekStart.getDate() - 7);
    renderWeek();
}

function nextWeek() {
    currentWeekStart.setDate(currentWeekStart.getDate() + 7);
    renderWeek();
}

function selectDate(dateStr) {
    selectedDate = dateStr;
    selectedTime = null;
    document.getElementById("confirm-btn").disabled = true;
    renderWeek();
    renderTimeSlots();
}

function renderTimeSlots() {
    var container = document.getElementById("time-slots");
    var times = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"];

    var html = "";
    for (var i = 0; i < times.length; i++) {
        var isSelected = selectedTime === times[i];
        html += "<button class='time-btn" + (isSelected ? " selected" : "") + "' ";
        html += "onclick='selectTime(\"" + times[i] + "\")'>";
        html += times[i];
        html += "</button>";
    }

    container.innerHTML = html;
}

function selectTime(time) {
    selectedTime = time;
    document.getElementById("confirm-btn").disabled = false;
    renderTimeSlots();
}

async function confirmAppointment() {
    if (!selectedDate || !selectedTime) {
        alert("Please select a date and time.");
        return;
    }

    var dateObj = new Date(selectedDate);
    var dateDisplay = dateObj.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

    // In production, this would POST to an appointments API
    alert("Appointment requested for " + dateDisplay + " at " + selectedTime + ". Your counselor will confirm shortly.");

    closeModal();
}

// Call Request Modal
function requestCall() {
    document.getElementById("call-modal").style.display = "flex";
}

function closeCallModal() {
    document.getElementById("call-modal").style.display = "none";
}

async function submitCallRequest() {
    var timePreference = document.querySelector('input[name="call-time"]:checked').value;
    var notes = document.getElementById("call-notes").value;

    // In production, this would POST to a call requests API
    alert("Call request submitted! Your counselor will call you " + getTimePreferenceText(timePreference) + ".");

    closeCallModal();
}

function getTimePreferenceText(pref) {
    switch (pref) {
        case "asap": return "as soon as possible";
        case "morning": return "in the morning (9am - 12pm)";
        case "afternoon": return "in the afternoon (12pm - 5pm)";
        case "evening": return "in the evening (5pm - 8pm)";
        default: return "soon";
    }
}

async function signOut() {
    try {
        await fetch(window.API_BASE + "/api/auth/logout", { method: "POST", credentials: "include" });
    } catch (e) {}
    localStorage.removeItem("sh_user");
    window.location.href = "login.html";
}
