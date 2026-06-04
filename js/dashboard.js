var currentUser=null;
document.addEventListener("DOMContentLoaded",async function(){
try{
var response=await fetch(window.API_BASE+"/api/auth/me",{credentials:"include"});
if(!response.ok){window.location.href="login.html";return;}
currentUser=await response.json();
if(currentUser.role==="admin"){window.location.href="admin.html";return;}
initDashboard(currentUser);
}catch(e){console.error("Auth check failed:",e);window.location.href="login.html";}
});
function initDashboard(user){
document.getElementById("loading-state").style.display="none";
document.getElementById("dashboard-content").style.display="block";
var initials=(user.first_name?user.first_name.charAt(0):"")+(user.last_name?user.last_name.charAt(0):"");
document.getElementById("user-avatar").textContent=initials.toUpperCase()||"??";
document.getElementById("user-name").textContent=user.first_name+" "+user.last_name;
document.getElementById("welcome-name").textContent=user.first_name;
if(user.created_at){var d=new Date(user.created_at);document.getElementById("stat-member-since").textContent=d.toLocaleString("default",{month:"short"})+" "+d.getFullYear();}
if(user.dd214_uploaded||user.dd214_verified){document.getElementById("dd214-alert").style.display="none";}
loadDashboardData();
setupDD214Upload();
setupEventListeners();
}
async function loadDashboardData(){
try{var r=await fetch(window.API_BASE+"/api/courses/progress",{credentials:"include"});if(r.ok){var d=await r.json();document.getElementById("stat-courses").textContent=d.active_count||0;}}catch(e){}
try{var r=await fetch(window.API_BASE+"/api/disputes",{credentials:"include"});if(r.ok){var d=await r.json();document.getElementById("stat-disputes").textContent=d.length||0;renderDisputes(d);}}catch(e){}
try{var r=await fetch(window.API_BASE+"/api/messages",{credentials:"include"});if(r.ok){var d=await r.json();renderMessages(d.slice(0,3));}}catch(e){}
try{var r=await fetch(window.API_BASE+"/api/credit/latest",{credentials:"include"});if(r.ok){var d=await r.json();if(d.change){document.getElementById("stat-credit").textContent=(d.change>0?"+":"")+d.change;document.getElementById("stat-credit").className=d.change>=0?"stat-value positive":"stat-value";}}}catch(e){}
try{var r=await fetch(window.API_BASE+"/api/counselor/assigned",{credentials:"include"});if(r.ok){var d=await r.json();if(d&&d.name){document.getElementById("counselor-name").textContent=d.name;document.getElementById("counselor-title").textContent=d.title||"Certified Financial Counselor";}}}catch(e){}
}
function renderDisputes(disputes){
var c=document.getElementById("disputes-list");if(!disputes||disputes.length===0)return;
var html="";for(var i=0;i<Math.min(disputes.length,3);i++){var d=disputes[i];var sc=d.status?d.status.toLowerCase().replace(/\s+/g,"-"):"pending";html+="<div class='dispute-item'><div class='dispute-info'><h4>"+(d.creditor||"Unknown")+"</h4><div class='dispute-meta'>Filed "+formatDate(d.created_at)+" - "+(d.bureau||"All Bureaus")+"</div></div><span class='dispute-status "+sc+"'>"+(d.status||"Pending")+"</span></div>";}
c.innerHTML=html;
}
function renderMessages(messages){
var c=document.getElementById("messages-list");if(!messages||messages.length===0)return;
var html="";for(var i=0;i<messages.length;i++){var m=messages[i];var uc=m.is_read?"":"message-unread";html+="<div class='message-item "+uc+"'><div class='message-header'><span class='message-from'>"+(m.from_name||"Counselor")+"</span><span class='message-time'>"+formatTime(m.created_at)+"</span></div><div class='message-preview'>"+truncate(m.content,80)+"</div></div>";}
c.innerHTML=html;
}
function formatDate(s){if(!s)return"Unknown";return new Date(s).toLocaleDateString("en-US",{month:"short",day:"numeric"});}
function formatTime(s){if(!s)return"";var d=new Date(s),n=new Date(),diff=Math.floor((n-d)/(1000*60*60*24));if(diff===0)return d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"});if(diff===1)return"Yesterday";if(diff<7)return d.toLocaleDateString("en-US",{weekday:"short"});return d.toLocaleDateString("en-US",{month:"short",day:"numeric"});}
function truncate(s,l){if(!s)return"";return s.length>l?s.substring(0,l)+"...":s;}
function setupDD214Upload(){
var dd214Input=document.getElementById("dd214-input");
var dd214Upload=document.getElementById("dd214-upload");
if(!dd214Input||!dd214Upload)return;
dd214Upload.addEventListener("click",function(){dd214Input.click();});
dd214Input.addEventListener("change",async function(e){var f=e.target.files[0];if(f)await uploadDD214(f);});
dd214Upload.addEventListener("dragover",function(e){e.preventDefault();dd214Upload.classList.add("dragover");});
dd214Upload.addEventListener("dragleave",function(){dd214Upload.classList.remove("dragover");});
dd214Upload.addEventListener("drop",async function(e){e.preventDefault();dd214Upload.classList.remove("dragover");var f=e.dataTransfer.files[0];if(f)await uploadDD214(f);});
}
async function uploadDD214(file){
var dd214Upload=document.getElementById("dd214-upload");
var fd=new FormData();fd.append("file",file);
dd214Upload.innerHTML="<div class='dd214-upload-text'>Uploading...</div>";
try{
var r=await fetch(window.API_BASE+"/api/documents/dd214",{method:"POST",credentials:"include",body:fd});
if(r.ok){dd214Upload.style.display="none";document.getElementById("dd214-status").classList.add("show");}
else{var e=await r.json();alert(e.detail||"Upload failed.");resetDD214Upload();}
}catch(e){alert("Connection error.");resetDD214Upload();}
}
function resetDD214Upload(){
var dd214Upload=document.getElementById("dd214-upload");
dd214Upload.innerHTML="<div class='dd214-upload-icon'>&#128196;</div><div class='dd214-upload-text'>Click to upload or drag and drop</div><div class='dd214-upload-hint'>PDF, JPG, or PNG up to 10MB</div>";
}
function setupEventListeners(){
var waitlistBtn=document.getElementById("waitlist-debt");
if(waitlistBtn)waitlistBtn.addEventListener("click",function(){joinWaitlist("debt-freedom");});
var sendBtn=document.getElementById("send-quick-msg");
if(sendBtn)sendBtn.addEventListener("click",sendQuickMessage);
var msgInput=document.getElementById("quick-message");
if(msgInput)msgInput.addEventListener("keypress",function(e){if(e.key==="Enter")sendQuickMessage();});
}
async function joinWaitlist(id){
try{var r=await fetch(window.API_BASE+"/api/courses/"+id+"/waitlist",{method:"POST",credentials:"include"});if(r.ok)alert("Added to waitlist!");}catch(e){alert("Could not join waitlist.");}
}
async function sendQuickMessage(){
var i=document.getElementById("quick-message");var c=i.value.trim();if(!c)return;
try{var r=await fetch(window.API_BASE+"/api/messages",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({content:c})});if(r.ok){i.value="";alert("Message sent!");}}catch(e){alert("Could not send message.");}
}
async function signOut(){
try{await fetch(window.API_BASE+"/api/auth/logout",{method:"POST",credentials:"include"});}catch(e){}
localStorage.removeItem("sh_user");window.location.href="login.html";
}
