var currentUser=null;
var activeConversation=null;
document.addEventListener("DOMContentLoaded",async function(){
try{
var response=await fetch(window.API_BASE+"/api/auth/me",{credentials:"include"});
if(!response.ok){window.location.href="login.html";return;}
currentUser=await response.json();
if(currentUser.role==="admin"){window.location.href="admin.html";return;}
initMessages(currentUser);
}catch(e){console.error("Auth check failed:",e);window.location.href="login.html";}
});
function initMessages(user){
document.getElementById("loading-state").style.display="none";
document.getElementById("messages-content").style.display="block";
var initials=(user.first_name?user.first_name.charAt(0):"")+(user.last_name?user.last_name.charAt(0):"");
document.getElementById("user-avatar").textContent=initials.toUpperCase()||"??";
document.getElementById("user-name").textContent=user.first_name+" "+user.last_name;
loadConversations();
setupEventListeners();
}
async function loadConversations(){
try{
var r=await fetch(window.API_BASE+"/api/messages/conversations",{credentials:"include"});
if(r.ok){
var convos=await r.json();
renderConversations(convos);
if(convos.length>0){selectConversation(convos[0]);}
}
}catch(e){
console.log("Conversations endpoint not available, using fallback");
loadCounselorAsConversation();
}
}
async function loadCounselorAsConversation(){
try{
var r=await fetch(window.API_BASE+"/api/member/counselor",{credentials:"include"});
if(r.ok){
var counselor=await r.json();
if(counselor&&counselor.id){
var convos=[{id:counselor.id,name:counselor.name||"Your Counselor",title:counselor.title||"Certified Financial Counselor",last_message:"Start a conversation",unread:false}];
renderConversations(convos);
selectConversation(convos[0]);
}
}
}catch(e){
document.getElementById("conversations-list").innerHTML="<div class='empty-state'><div class='empty-state-text'>No counselor assigned yet</div></div>";
}
}
function renderConversations(convos){
var c=document.getElementById("conversations-list");
if(!convos||convos.length===0){
c.innerHTML="<div class='empty-state'><div class='empty-state-icon'>&#128172;</div><div class='empty-state-text'>No conversations yet</div></div>";
return;
}
var html="";
for(var i=0;i<convos.length;i++){
var conv=convos[i];
var unreadClass=conv.unread?"conversation-unread":"";
html+="<div class='conversation-item "+unreadClass+"' data-id='"+conv.id+"' onclick='selectConversationById(\""+conv.id+"\")'>";
html+="<div class='conversation-avatar'>&#128100;</div>";
html+="<div class='conversation-info'><div class='conversation-name'>"+(conv.name||"Counselor")+"</div>";
html+="<div class='conversation-preview'>"+(conv.last_message||"No messages yet")+"</div></div></div>";
}
c.innerHTML=html;
}
function selectConversationById(id){
var items=document.querySelectorAll(".conversation-item");
for(var i=0;i<items.length;i++){
if(items[i].dataset.id===id){
selectConversation({id:id,name:items[i].querySelector(".conversation-name").textContent});
items[i].classList.add("active");
}else{
items[i].classList.remove("active");
}
}
}
function selectConversation(conv){
activeConversation=conv;
document.getElementById("recipient-name").textContent=conv.name||"Counselor";
document.getElementById("recipient-status").textContent="Online";
document.getElementById("messages-compose").style.display="block";
loadMessages(conv.id);
}
async function loadMessages(conversationId){
var thread=document.getElementById("messages-thread");
thread.innerHTML="<div class='loading-state'><div class='loading-spinner'></div></div>";
try{
var r=await fetch(window.API_BASE+"/api/messages?conversation_id="+conversationId,{credentials:"include"});
if(r.ok){
var messages=await r.json();
renderMessages(messages);
}else{
thread.innerHTML="<div class='empty-state'><div class='empty-state-icon'>&#128172;</div><div class='empty-state-text'>Start a conversation</div></div>";
}
}catch(e){
thread.innerHTML="<div class='empty-state'><div class='empty-state-icon'>&#128172;</div><div class='empty-state-text'>Send your first message below</div></div>";
}
}
function renderMessages(messages){
var thread=document.getElementById("messages-thread");
if(!messages||messages.length===0){
thread.innerHTML="<div class='empty-state' style='margin-top:3rem;'><div class='empty-state-icon'>&#128172;</div><div class='empty-state-text'>No messages yet. Send one below!</div></div>";
return;
}
var html="";
for(var i=0;i<messages.length;i++){
var m=messages[i];
var isMe=m.from_user_id===currentUser.id;
var bubbleClass=isMe?"sent":"received";
html+="<div class='message-bubble "+bubbleClass+"'>";
html+="<div class='message-content'>"+escapeHtml(m.content)+"</div>";
html+="<div class='message-timestamp'>"+formatMessageTime(m.created_at)+"</div>";
html+="</div>";
}
thread.innerHTML=html+"<div style='clear:both'></div>";
thread.scrollTop=thread.scrollHeight;
}
function setupEventListeners(){
var sendBtn=document.getElementById("compose-send");
var input=document.getElementById("compose-input");
if(sendBtn)sendBtn.addEventListener("click",sendMessage);
if(input){
input.addEventListener("keypress",function(e){
if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage();}
});
}
}
async function sendMessage(){
var input=document.getElementById("compose-input");
var content=input.value.trim();
if(!content||!activeConversation)return;
var sendBtn=document.getElementById("compose-send");
sendBtn.disabled=true;
sendBtn.textContent="Sending...";
try{
var r=await fetch(window.API_BASE+"/api/messages",{
method:"POST",
credentials:"include",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({content:content,to_user_id:activeConversation.id})
});
if(r.ok){
input.value="";
loadMessages(activeConversation.id);
}else{
alert("Failed to send message");
}
}catch(e){
alert("Connection error");
}
sendBtn.disabled=false;
sendBtn.textContent="Send Message";
}
function formatMessageTime(s){
if(!s)return"";
var d=new Date(s);
var now=new Date();
var diff=Math.floor((now-d)/(1000*60*60*24));
if(diff===0)return d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"});
if(diff===1)return"Yesterday "+d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"});
return d.toLocaleDateString("en-US",{month:"short",day:"numeric"})+" "+d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"});
}
function escapeHtml(str){
if(!str)return"";
return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
async function startNewConversation(){
// If counselor already loaded as conversation, just select it
var existing=document.querySelector(".conversation-item");
if(existing){existing.click();return;}
// Load counselor to start conversation
var r=await fetch(window.API_BASE+"/api/member/counselor",{credentials:"include"}).catch(()=>null);
if(r&&r.ok){
var counselor=await r.json();
if(counselor&&counselor.id){
var conv={id:counselor.id,name:counselor.name||"Your Counselor"};
renderConversations([conv]);
selectConversation(conv);
return;
}
}
// No counselor assigned — message admin
var conv={id:"admin",name:"Silent Honor Support"};
renderConversations([conv]);
selectConversation(conv);
}
async function signOut(){
try{await fetch(window.API_BASE+"/api/auth/logout",{method:"POST",credentials:"include"});}catch(e){}
localStorage.removeItem("sh_user");window.location.href="login.html";
}
