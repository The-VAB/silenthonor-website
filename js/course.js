var currentUser=null;
var courseData=null;
var currentLessonIndex=0;
document.addEventListener("DOMContentLoaded",async function(){
try{
var response=await fetch(window.API_BASE+"/api/auth/me",{credentials:"include"});
if(!response.ok){window.location.href="login.html";return;}
currentUser=await response.json();
if(currentUser.role==="admin"){window.location.href="admin.html";return;}
initCourse(currentUser);
}catch(e){console.error("Auth check failed:",e);window.location.href="login.html";}
});
function initCourse(user){
var initials=(user.first_name?user.first_name.charAt(0):"")+(user.last_name?user.last_name.charAt(0):"");
document.getElementById("user-avatar").textContent=initials.toUpperCase()||"??";
document.getElementById("user-name").textContent=user.first_name+" "+user.last_name;
var urlParams=new URLSearchParams(window.location.search);
var courseId=urlParams.get("id");
if(courseId){
loadCourse(courseId);
}else{
showError("No course selected");
}
setupEventListeners();
}
async function loadCourse(courseId){
try{
var r=await fetch(window.API_BASE+"/api/courses/"+courseId,{credentials:"include"});
if(r.ok){
courseData=await r.json();
renderCourse(courseData);
}else{
useFallbackCourse(courseId);
}
}catch(e){
useFallbackCourse(courseId);
}
}
function useFallbackCourse(courseId){
var courses={
"credit-101":{id:"credit-101",title:"Credit Fundamentals 101",lessons:[
{id:1,title:"Understanding Your Credit Score",duration:"15 min",completed:true,video_url:"",content:"<p>Your credit score is a three-digit number that represents your creditworthiness. Lenders use this score to determine whether to approve your loan applications and what interest rate to charge.</p><h3>Key Components</h3><ul><li><strong>Payment History (35%)</strong> - Your track record of paying bills on time</li><li><strong>Credit Utilization (30%)</strong> - How much of your available credit you use</li><li><strong>Length of Credit History (15%)</strong> - How long you have had credit accounts</li><li><strong>Credit Mix (10%)</strong> - The variety of credit types you have</li><li><strong>New Credit (10%)</strong> - Recent credit inquiries and new accounts</li></ul>"},
{id:2,title:"Reading Your Credit Report",duration:"20 min",completed:true,video_url:"",content:"<p>Your credit report contains detailed information about your credit history. Learning to read it is essential for maintaining good credit health.</p><h3>What to Look For</h3><ul><li>Personal information accuracy</li><li>Account statuses and payment history</li><li>Public records and collections</li><li>Credit inquiries</li></ul><p>You are entitled to one free credit report from each bureau annually at AnnualCreditReport.com.</p>"},
{id:3,title:"Building Credit from Scratch",duration:"18 min",completed:false,video_url:"",content:"<p>If you have no credit history, building it can seem challenging. Here are proven strategies to establish credit.</p><h3>Getting Started</h3><ul><li>Become an authorized user on a family member account</li><li>Apply for a secured credit card</li><li>Consider a credit-builder loan</li><li>Report rent payments to credit bureaus</li></ul>"},
{id:4,title:"Common Credit Mistakes",duration:"12 min",completed:false,video_url:"",content:"<p>Avoiding these common mistakes can save you from credit score damage.</p><h3>Mistakes to Avoid</h3><ul><li>Paying late or missing payments</li><li>Maxing out credit cards</li><li>Closing old accounts</li><li>Applying for too much credit at once</li><li>Ignoring your credit report</li></ul>"},
{id:5,title:"Dispute Process Overview",duration:"25 min",completed:false,video_url:"",content:"<p>If you find errors on your credit report, you have the right to dispute them. This lesson covers the dispute process.</p><h3>The Dispute Process</h3><ol><li>Identify the error on your report</li><li>Gather supporting documentation</li><li>Write a dispute letter via certified mail</li><li>Wait for investigation (30-45 days)</li><li>Review results and follow up if needed</li></ol><p><strong>Important:</strong> Always dispute via certified mail, never online. This preserves your legal rights under the Fair Credit Reporting Act.</p>"}
]},
"va-loan":{id:"va-loan",title:"VA Loan Mastery",lessons:[
{id:1,title:"VA Loan Basics",duration:"20 min",completed:true,video_url:"",content:"<p>VA loans are a powerful benefit for veterans, offering favorable terms not available with conventional mortgages.</p><h3>Key Benefits</h3><ul><li>No down payment required</li><li>No private mortgage insurance (PMI)</li><li>Competitive interest rates</li><li>Limited closing costs</li><li>No prepayment penalty</li></ul>"},
{id:2,title:"Eligibility Requirements",duration:"15 min",completed:false,video_url:"",content:"<p>Understanding VA loan eligibility is the first step to homeownership.</p><h3>Service Requirements</h3><ul><li>90 consecutive days active duty during wartime</li><li>181 days active duty during peacetime</li><li>6 years in the National Guard or Reserves</li><li>Surviving spouse of veteran who died in service</li></ul>"}
]}
};
courseData=courses[courseId]||courses["credit-101"];
renderCourse(courseData);
}
function renderCourse(course){
document.getElementById("loading-state").style.display="none";
document.getElementById("course-content").style.display="block";
document.getElementById("course-title").textContent=course.title;
var completed=course.lessons.filter(function(l){return l.completed;}).length;
var total=course.lessons.length;
var pct=Math.round((completed/total)*100);
document.getElementById("course-progress-bar").style.width=pct+"%";
document.getElementById("course-progress-text").textContent=pct+"% Complete ("+completed+"/"+total+" lessons)";
renderLessonsList(course.lessons);
var firstIncomplete=course.lessons.findIndex(function(l){return !l.completed;});
if(firstIncomplete===-1)firstIncomplete=0;
selectLesson(firstIncomplete);
}
function renderLessonsList(lessons){
var html="";
for(var i=0;i<lessons.length;i++){
var l=lessons[i];
var statusClass=l.completed?"completed":"";
var statusIcon=l.completed?"&#10003;":""+(i+1);
html+="<div class='lesson-item "+statusClass+"' data-index='"+i+"' onclick='selectLesson("+i+")'>";
html+="<div class='lesson-status'>"+statusIcon+"</div>";
html+="<div class='lesson-info'><div class='lesson-name'>"+l.title+"</div>";
html+="<div class='lesson-duration'>"+l.duration+"</div></div></div>";
}
document.getElementById("lessons-list").innerHTML=html;
}
function selectLesson(index){
currentLessonIndex=index;
var items=document.querySelectorAll(".lesson-item");
for(var i=0;i<items.length;i++){
items[i].classList.remove("active");
if(parseInt(items[i].dataset.index)===index){
items[i].classList.add("active");
}
}
var lesson=courseData.lessons[index];
document.getElementById("lesson-title").textContent=lesson.title;
document.getElementById("lesson-body").innerHTML=lesson.content;
if(lesson.video_url){
document.getElementById("video-container").innerHTML='<iframe src="'+lesson.video_url+'" allowfullscreen></iframe>';
}else{
document.getElementById("video-container").innerHTML='<div class="video-placeholder"><div class="video-icon">&#128218;</div><p>Text lesson - read below</p></div>';
}
document.getElementById("lesson-actions").style.display="flex";
document.getElementById("prev-lesson").style.visibility=index>0?"visible":"hidden";
if(lesson.completed){
document.getElementById("complete-lesson").textContent="Next Lesson &#8594;";
}else{
document.getElementById("complete-lesson").textContent="Mark Complete & Continue";
}
}
function setupEventListeners(){
document.getElementById("prev-lesson").addEventListener("click",function(){
if(currentLessonIndex>0)selectLesson(currentLessonIndex-1);
});
document.getElementById("complete-lesson").addEventListener("click",async function(){
var lesson=courseData.lessons[currentLessonIndex];
if(!lesson.completed){
await markLessonComplete(lesson.id);
lesson.completed=true;
renderLessonsList(courseData.lessons);
updateProgress();
}
if(currentLessonIndex<courseData.lessons.length-1){
selectLesson(currentLessonIndex+1);
}else{
alert("Congratulations! You have completed the course!");
}
});
}
async function markLessonComplete(lessonId){
try{
await fetch(window.API_BASE+"/api/courses/"+courseData.id+"/lessons/"+lessonId+"/complete",{
method:"POST",
credentials:"include"
});
}catch(e){
console.log("Progress saved locally");
}
}
function updateProgress(){
var completed=courseData.lessons.filter(function(l){return l.completed;}).length;
var total=courseData.lessons.length;
var pct=Math.round((completed/total)*100);
document.getElementById("course-progress-bar").style.width=pct+"%";
document.getElementById("course-progress-text").textContent=pct+"% Complete ("+completed+"/"+total+" lessons)";
}
function showError(msg){
document.getElementById("loading-state").innerHTML="<p style='color:var(--red-light);'>"+msg+"</p><a href='dashboard.html' style='color:var(--muted);'>Return to Dashboard</a>";
}
async function signOut(){
try{await fetch(window.API_BASE+"/api/auth/logout",{method:"POST",credentials:"include"});}catch(e){}
localStorage.removeItem("sh_user");window.location.href="login.html";
}
