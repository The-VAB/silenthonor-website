// Admin Extended - New Tab Functions

async function loadDisputes() {
  try {
    var res = await fetch(window.API_BASE + "/api/admin/disputes", { credentials: "include" });
    var disputes = await res.json();
    var tbody = document.getElementById("disputes-tbody");
    if (!disputes.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--muted);">No disputes yet.</td></tr>';
      return;
    }
    var html = "";
    for (var i = 0; i < disputes.length; i++) {
      var d = disputes[i];
      var statusClass = d.status === "resolved" ? "status-verified" : d.status === "rejected" ? "status-rejected" : "status-pending";
      html += "<tr>";
      html += "<td>" + (d.user_name || "Unknown") + "<br><span style='font-size: 0.75rem; color: var(--muted);'>" + (d.user_email || "") + "</span></td>";
      html += "<td>" + (d.bureau || "—") + "</td>";
      html += "<td>" + (d.account_name || "—") + "</td>";
      html += "<td><span class='status-badge " + statusClass + "'>" + d.status + "</span></td>";
      html += "<td>" + (d.date_sent ? new Date(d.date_sent).toLocaleDateString() : "—") + "</td>";
      html += "<td><button class='action-btn' onclick='viewDispute(\"" + d.id + "\")'>View</button></td>";
      html += "</tr>";
    }
    tbody.innerHTML = html;
  } catch (e) { console.error("Failed to load disputes:", e); }
}

var counselorsList = [];

async function loadCounselors() {
  try {
    var res = await fetch(window.API_BASE + "/api/admin/counselors", { credentials: "include" });
    counselorsList = await res.json();
    var tbody = document.getElementById("counselors-tbody");

    if (!counselorsList.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--muted);">No counselors yet. Add your first counselor.</td></tr>';
    } else {
      var html = "";
      for (var i = 0; i < counselorsList.length; i++) {
        var c = counselorsList[i];
        var statusClass = c.active ? "status-verified" : "status-rejected";
        html += "<tr>";
        html += "<td>" + c.name + "</td>";
        html += "<td>" + c.email + "</td>";
        html += "<td>" + (c.title || "—") + "</td>";
        html += "<td>" + c.assigned_members + "</td>";
        html += "<td><span class='status-badge " + statusClass + "'>" + (c.active ? "Active" : "Inactive") + "</span></td>";
        html += "<td><button class='action-btn' onclick='editCounselorById(\"" + c.id + "\")'>Edit</button></td>";
        html += "</tr>";
      }
      tbody.innerHTML = html;
    }

    loadMemberAssignments();
  } catch (e) { console.error("Failed to load counselors:", e); }
}

async function loadMemberAssignments() {
  try {
    var res = await fetch(window.API_BASE + "/api/admin/members", { credentials: "include" });
    var members = await res.json();
    var tbody = document.getElementById("assignments-tbody");

    if (!members.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--muted);">No members to assign.</td></tr>';
      return;
    }

    var html = "";
    for (var i = 0; i < members.length; i++) {
      var m = members[i];
      var assignedCounselor = null;
      if (m.assigned_counselor_id) {
        for (var j = 0; j < counselorsList.length; j++) {
          if (counselorsList[j].id === m.assigned_counselor_id) {
            assignedCounselor = counselorsList[j];
            break;
          }
        }
      }
      var counselorName = assignedCounselor ? assignedCounselor.name : '<span style="color: var(--muted);">Not assigned</span>';
      html += "<tr>";
      html += "<td>" + m.first_name + " " + m.last_name + "<br><span style='font-size: 0.75rem; color: var(--muted);'>" + m.email + "</span></td>";
      html += "<td>" + counselorName + "</td>";
      html += "<td>";
      html += "<button class='action-btn primary' onclick='openAssignModal(\"" + m.id + "\", \"" + m.first_name + " " + m.last_name + "\")'>Assign</button>";
      html += "<button class='action-btn' onclick='openNotesModal(\"" + m.id + "\", \"" + m.first_name + " " + m.last_name + "\")'>Notes</button>";
      html += "</td>";
      html += "</tr>";
    }
    tbody.innerHTML = html;
  } catch (e) { console.error("Failed to load assignments:", e); }
}

async function loadWaitlist() {
  try {
    var res = await fetch(window.API_BASE + "/api/admin/waitlist", { credentials: "include" });
    var entries = await res.json();
    var tbody = document.getElementById("waitlist-tbody");

    if (!entries.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--muted);">No waitlist entries.</td></tr>';
      return;
    }

    var html = "";
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      html += "<tr>";
      html += "<td>" + (e.user_name || "Unknown") + "</td>";
      html += "<td>" + (e.user_email || "—") + "</td>";
      html += "<td>" + (e.course_id || "—") + "</td>";
      html += "<td>" + (e.created_at ? new Date(e.created_at).toLocaleDateString() : "—") + "</td>";
      html += "</tr>";
    }
    tbody.innerHTML = html;
  } catch (e) { console.error("Failed to load waitlist:", e); }
}

async function loadMessages() {
  var tbody = document.getElementById("messages-tbody");
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--muted);">Message overview coming soon.</td></tr>';
}

// Counselor CRUD
function openCounselorModal(counselor) {
  document.getElementById("counselor-modal-title").textContent = counselor ? "Edit Counselor" : "Add Counselor";
  document.getElementById("counselor-id").value = counselor ? counselor.id : "";
  var nameParts = counselor && counselor.name ? counselor.name.split(" ") : ["", ""];
  document.getElementById("counselor-first-name").value = nameParts[0] || "";
  document.getElementById("counselor-last-name").value = nameParts.slice(1).join(" ") || "";
  document.getElementById("counselor-email").value = counselor ? counselor.email : "";
  document.getElementById("counselor-title").value = counselor ? counselor.title || "" : "";
  document.getElementById("counselor-bio").value = counselor ? counselor.bio || "" : "";
  document.getElementById("counselor-specialties").value = counselor && counselor.specialties ? counselor.specialties.join(", ") : "";
  document.getElementById("counselor-modal").classList.add("open");
}

function closeCounselorModal() {
  document.getElementById("counselor-modal").classList.remove("open");
}

function editCounselorById(id) {
  for (var i = 0; i < counselorsList.length; i++) {
    if (counselorsList[i].id === id) {
      openCounselorModal(counselorsList[i]);
      return;
    }
  }
}

async function saveCounselor() {
  var payload = {
    first_name: document.getElementById("counselor-first-name").value,
    last_name: document.getElementById("counselor-last-name").value,
    email: document.getElementById("counselor-email").value,
    title: document.getElementById("counselor-title").value,
    bio: document.getElementById("counselor-bio").value,
    specialties: document.getElementById("counselor-specialties").value.split(",").map(function(s) { return s.trim(); }).filter(function(s) { return s; })
  };

  if (!payload.email) {
    alert("Email is required.");
    return;
  }

  try {
    var res = await fetch(window.API_BASE + "/api/admin/counselors", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      closeCounselorModal();
      loadCounselors();
    } else {
      alert("Failed to save counselor.");
    }
  } catch (e) {
    alert("Connection error.");
  }
}

// Assignment Modal
var assignMemberId = null;

async function openAssignModal(memberId, memberName) {
  assignMemberId = memberId;
  document.getElementById("assign-member-id").value = memberId;
  document.getElementById("assign-member-info").innerHTML = "<strong>Assigning counselor to:</strong> " + memberName;

  var select = document.getElementById("assign-counselor-select");
  var html = '<option value="">-- Select Counselor --</option>';
  for (var i = 0; i < counselorsList.length; i++) {
    html += '<option value="' + counselorsList[i].id + '">' + counselorsList[i].name + '</option>';
  }
  select.innerHTML = html;

  document.getElementById("assign-modal").classList.add("open");
}

function closeAssignModal() {
  assignMemberId = null;
  document.getElementById("assign-modal").classList.remove("open");
}

async function confirmAssign() {
  var counselorId = document.getElementById("assign-counselor-select").value;
  if (!counselorId || !assignMemberId) {
    alert("Please select a counselor.");
    return;
  }

  try {
    var res = await fetch(window.API_BASE + "/api/admin/counselors/" + counselorId + "/assign/" + assignMemberId, {
      method: "POST",
      credentials: "include"
    });

    if (res.ok) {
      closeAssignModal();
      loadCounselors();
    } else {
      alert("Failed to assign counselor.");
    }
  } catch (e) {
    alert("Connection error.");
  }
}

// Notes Modal
var notesMemberId = null;
var notesMemberName = "";

async function openNotesModal(memberId, memberName) {
  notesMemberId = memberId;
  notesMemberName = memberName;
  document.getElementById("notes-member-id").value = memberId;
  document.getElementById("notes-member-info").innerHTML = "<strong>Notes for:</strong> " + memberName;
  document.getElementById("new-note-content").value = "";

  try {
    var res = await fetch(window.API_BASE + "/api/admin/members/" + memberId + "/notes", { credentials: "include" });
    var notes = await res.json();
    var notesList = document.getElementById("notes-list");

    if (!notes.length) {
      notesList.innerHTML = '<div class="empty-state" style="padding: 1rem;">No notes yet.</div>';
    } else {
      var html = "";
      for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        html += "<div style='padding: 0.75rem; background: rgba(0,0,0,0.2); margin-bottom: 0.5rem; border-left: 2px solid var(--red);'>";
        html += "<div style='font-size: 0.7rem; color: var(--muted); margin-bottom: 0.25rem;'>";
        html += new Date(n.created_at).toLocaleString() + " — " + n.note_type + " — " + n.created_by;
        html += "</div>";
        html += "<div style='font-size: 0.85rem;'>" + n.content + "</div>";
        html += "</div>";
      }
      notesList.innerHTML = html;
    }
  } catch (e) {
    document.getElementById("notes-list").innerHTML = '<div class="empty-state" style="padding: 1rem;">Failed to load notes.</div>';
  }

  document.getElementById("notes-modal").classList.add("open");
}

function closeNotesModal() {
  notesMemberId = null;
  document.getElementById("notes-modal").classList.remove("open");
}

async function saveNote() {
  if (!notesMemberId) return;

  var content = document.getElementById("new-note-content").value.trim();
  var noteType = document.getElementById("new-note-type").value;

  if (!content) {
    alert("Please enter a note.");
    return;
  }

  try {
    var res = await fetch(window.API_BASE + "/api/admin/members/" + notesMemberId + "/notes", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: content, note_type: noteType })
    });

    if (res.ok) {
      document.getElementById("new-note-content").value = "";
      openNotesModal(notesMemberId, notesMemberName);
    } else {
      alert("Failed to save note.");
    }
  } catch (e) {
    alert("Connection error.");
  }
}

function viewDispute(id) {
  alert("Dispute details view coming soon.");
}
