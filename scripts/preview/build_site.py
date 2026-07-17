#!/usr/bin/env python3
"""Assemble the full Silent Honor staging site into ONE self-contained,
clickable, shareable HTML page (for publishing as a claude.ai Artifact).

- All 5 pages (home, about, services, courses, contact) as routed views
- Per-page CSS scoped under #v-<page> so nothing collides
- global.css + brand fonts (Oswald/Lora/Barlow, latin) + logos inlined
- Client-side router; external links (Jodi's List, Veteran Alliance) work
- No external requests -> renders anywhere, no backend needed
"""
import re, base64, os

ROOT = "/home/user/silenthonor-website"
SCRATCH = "/tmp/claude-0/-home-user-silenthonor-website/8544881a-a91b-53b8-b410-d1799e462658/scratchpad"

# ---- CSS scoper (handles @media recursion; leaves @keyframes/@font-face alone)
def scope_css(css, scope):
    out=[]; i=0; n=len(css)
    while i<n:
        while i<n and css[i] in ' \t\r\n': out.append(css[i]); i+=1
        if i>=n: break
        if css[i]=='/' and i+1<n and css[i+1]=='*':
            e=css.find('*/', i); e = n if e==-1 else e+2; out.append(css[i:e]); i=e; continue
        j=css.find('{', i)
        if j==-1: out.append(css[i:]); break
        prelude=css[i:j].strip()
        depth=0; k=j
        while k<n:
            if css[k]=='{': depth+=1
            elif css[k]=='}':
                depth-=1
                if depth==0: break
            k+=1
        body=css[j+1:k]
        if prelude.startswith('@'):
            at=prelude.split()[0].lower()
            if at in ('@media','@supports'):
                out.append(f"{prelude} {{{scope_css(body, scope)}}}")
            else:
                out.append(f"{prelude} {{{body}}}")
        else:
            sels=[s.strip() for s in prelude.split(',') if s.strip()]
            scoped=', '.join(f"{scope} {s}" for s in sels)
            out.append(f"{scoped} {{{body}}}")
        i=k+1
    return ''.join(out)

def inner(tag_html, tag):
    m=re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', tag_html, re.S)
    return m.group(1) if m else ''

def page_content(html):
    a=html.find('<div class="page-content">')
    b=html.find('<div id="footer-placeholder">')
    seg=html[a+len('<div class="page-content">'):b]
    seg=seg.rstrip()
    if seg.endswith('</div>'): seg=seg[:-6]
    # remove any per-page staging flag (shell provides one)
    seg=re.sub(r'<div class="staging-flag">.*?</div>', '', seg, flags=re.S)
    return seg

def page_scripts(html):
    # inline <script> blocks without src, from body
    body=html[html.find('<body>'):]
    return '\n'.join(m.group(1) for m in re.finditer(r'<script>(.*?)</script>', body, re.S))

# ---- fonts (reuse fonts.css already fetched; embed latin faces as data URIs)
import urllib.request
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def fetch(u): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30).read()
fcss=open(f"{SCRATCH}/fonts.css").read()
faces=[];
for blk in re.split(r'(?=/\*\s*[\w\-\[\] ]+\s*\*/)', fcss):
    if not re.match(r'/\*\s*latin\s*\*/', blk.strip()): continue
    f=re.search(r'@font-face\s*\{.*?\}', blk, re.S)
    if not f: continue
    um=re.search(r'url\((https://[^)]+\.woff2)\)', f.group(0))
    if not um: continue
    data="data:font/woff2;base64,"+base64.b64encode(fetch(um.group(1))).decode()
    faces.append(f.group(0).replace(um.group(1), data))
fonts_inline="\n".join(faces)

# ---- global.css (strip @import + external topo image)
gcss=open(f"{ROOT}/css/global.css").read()
gcss=re.sub(r"@import url\('https://fonts\.googleapis[^']*'\);","",gcss)
gcss=re.sub(r"background-image:\s*url\('https://customer-assets[^']*'\);","background-image:none;",gcss)

# ---- logos
def b64f(p,m): return f"data:{m};base64,"+base64.b64encode(open(p,'rb').read()).decode()
LOGO_SH=b64f(f"{ROOT}/images/silent-honor-logo.png","image/png")
LOGO_VA=b64f(f"{ROOT}/images/veteran-alliance-logo.png","image/png")
ZEFFY="https://www.zeffy.com/en-US/donation-form/8375cf26-7c08-420b-91d8-2bb30723e3b1"

# ---- pages
PAGES=[("home","index-staging.html","Home"),
       ("about","about.html","About"),
       ("services","services-staging.html","Services"),
       ("courses","courses.html","Courses"),
       ("contact","contact.html","Contact")]

# inline any local images referenced in page content
LOCAL_IMG={}
for p in os.listdir(f"{ROOT}/images"):
    ext=p.rsplit('.',1)[-1].lower()
    mime={'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg'}.get(ext)
    if mime: LOCAL_IMG[f"images/{p}"]=b64f(f"{ROOT}/images/{p}", mime)

page_styles=[]; views=[]; scripts=[]
for key,fn,label in PAGES:
    h=open(f"{ROOT}/{fn}").read()
    for ref,data in LOCAL_IMG.items():
        h=h.replace(ref, data)
    page_styles.append(f"/* ===== {key} ===== */\n"+scope_css(inner(h,'style'), f"#v-{key}"))
    active=" active" if key=="home" else ""
    views.append(f'<section id="v-{key}" class="view{active}" role="tabpanel" aria-label="{label}">\n{page_content(h)}\n</section>')
    scripts.append(page_scripts(h))

nav_links="".join(
    f'<a class="nav-link{" active" if k=="home" else ""}" data-view="{k}" href="#{k}">{lbl}</a>'
    for k,_,lbl in PAGES)

navbar=f'''
<nav class="nav">
  <a class="nav-logo" data-view="home" href="#home"><img src="{LOGO_SH}" alt="Silent Honor Foundation" class="nav-logo-img"></a>
  <div class="nav-links" id="nav-links">{nav_links}</div>
  <div class="nav-actions">
    <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle light/dark mode">
      <svg class="theme-icon theme-icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
      <svg class="theme-icon theme-icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
    </button>
    <a href="{ZEFFY}" target="_blank" rel="noopener" class="nav-donate">Donate</a>
    <a href="#" class="btn-outline app-link" style="padding:10px 20px;font-size:0.68rem;">Member Login</a>
    <button class="nav-mobile-toggle" onclick="document.getElementById('nav-links').classList.toggle('open')">&#9776;</button>
  </div>
</nav>'''

footer=f'''
<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <div class="footer-logo"><img src="{LOGO_SH}" alt="Silent Honor Foundation" class="footer-logo-img"></div>
      <p class="footer-mission">Empowering veterans with the financial education, credit counseling, and tools needed to build strong, self-sufficient futures.</p>
      <span class="footer-ein">501(c)(3) &middot; EIN 99-3172064</span>
    </div>
    <div class="footer-col"><h4 class="footer-col-title">Programs</h4><div class="footer-links">
      <a class="footer-link" data-view="courses" href="#courses">Free Courses</a>
      <a class="footer-link" data-view="services" href="#services">Services</a>
      <a class="footer-link" data-view="services" href="#services">Financial Coaching</a>
      <a class="footer-link" data-view="services" href="#services">Credit Education</a></div></div>
    <div class="footer-col"><h4 class="footer-col-title">Organization</h4><div class="footer-links">
      <a class="footer-link" data-view="about" href="#about">About Us</a>
      <a class="footer-link" data-view="about" href="#about">Our Team</a>
      <a class="footer-link" data-view="contact" href="#contact">Contact</a>
      <a class="footer-link" href="{ZEFFY}" target="_blank" rel="noopener">Donate</a></div></div>
    <div class="footer-col"><h4 class="footer-col-title">Members</h4><div class="footer-links">
      <a class="footer-link app-link" href="#">Member Login</a>
      <a class="footer-link app-link" href="#">Become a Member</a>
      <a class="footer-link app-link" href="#">Dashboard</a></div></div>
  </div>
  <div class="footer-partners">
    <p class="footer-partners-line">Insurance built, created, and offered through <a href="https://theveteranalliance.com" target="_blank" rel="noopener">The Veteran Alliance</a>.</p>
    <a href="https://theveteranalliance.com" target="_blank" rel="noopener" class="footer-partners-logo" aria-label="The Veteran Alliance"><img src="{LOGO_VA}" alt="The Veteran Alliance" class="va-logo-img"></a>
    <p class="footer-partners-sub">In direct support and partnership with Corgi.</p>
  </div>
  <div class="footer-bottom">
    <span class="footer-copy">&copy; 2026 Silent Honor Foundation Inc. All rights reserved.</span>
    <div class="footer-legal"><a href="#" class="app-link">Privacy Policy</a><a href="#" class="app-link">Terms of Use</a></div>
  </div>
</footer>'''

spa_css='''
/* SPA chrome */
.view{display:none;}
.view.active{display:block;}
.staging-flag{position:fixed;top:76px;left:0;right:0;z-index:99;background:linear-gradient(90deg,var(--gold-light),var(--gold));color:#0B1220;font-family:var(--font-display);font-size:0.65rem;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;text-align:center;padding:6px;}
body{padding-top:0;}
.sh-toast{position:fixed;bottom:2rem;left:50%;transform:translateX(-50%) translateY(120%);background:var(--navy-mid);border:1px solid var(--border);border-left:3px solid var(--gold);color:var(--white);padding:1rem 1.4rem;font-family:var(--font-ui);font-size:0.85rem;border-radius:6px;z-index:9999;box-shadow:0 8px 30px rgba(0,0,0,0.3);transition:transform .3s ease;max-width:90vw;}
.sh-toast.show{transform:translateX(-50%) translateY(0);}
'''

router_js=r'''
// theme
function toggleTheme(){var r=document.documentElement;var n=r.getAttribute('data-theme')==='light'?'dark':'light';r.setAttribute('data-theme',n);try{localStorage.setItem('sh-theme',n);}catch(e){}}
(function(){try{var t=localStorage.getItem('sh-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);}catch(e){}})();

// toast
function toast(msg){var t=document.createElement('div');t.className='sh-toast';t.textContent=msg;document.body.appendChild(t);requestAnimationFrame(function(){t.classList.add('show');});setTimeout(function(){t.classList.remove('show');setTimeout(function(){t.remove();},350);},2600);}

// reveal + counters within a view
function activateView(v){
  v.querySelectorAll('.reveal').forEach(function(el){el.classList.add('visible');});
  v.querySelectorAll('[data-count]').forEach(function(el){
    if(el.dataset.done)return;el.dataset.done='1';
    var target=parseInt(el.dataset.count),start=null;
    function step(ts){if(!start)start=ts;var p=Math.min((ts-start)/1600,1);var e=1-Math.pow(1-p,3);el.textContent=Math.floor(target*e).toLocaleString();if(p<1)requestAnimationFrame(step);}
    requestAnimationFrame(step);
  });
}

var VIEWS=['home','about','services','courses','contact'];
function route(key,hash){
  if(VIEWS.indexOf(key)<0)key='home';
  document.querySelectorAll('.view').forEach(function(v){v.classList.toggle('active',v.id==='v-'+key);});
  document.querySelectorAll('.nav-link').forEach(function(a){a.classList.toggle('active',a.dataset.view===key);});
  var v=document.getElementById('v-'+key);
  activateView(v);
  document.getElementById('nav-links').classList.remove('open');
  if(hash){var t=v.querySelector(hash);if(t){t.scrollIntoView({behavior:'smooth'});return;}}
  window.scrollTo({top:0,behavior:'auto'});
}

// link delegation
document.addEventListener('click',function(e){
  var a=e.target.closest('a,button');
  if(!a)return;
  if(a.classList.contains('app-link')){e.preventDefault();toast('Staging preview — member sign-up, login, and donation flows go live on the deployed site.');return;}
  var dv=a.getAttribute('data-view');
  if(dv){e.preventDefault();var h=a.getAttribute('href')||'';var hash=h.indexOf('#')>=0&&h.length>1&&h!=='#'+dv?('#'+h.split('#')[1]):null;location.hash=dv;route(dv,hash);return;}
  var href=a.getAttribute('href')||'';
  // internal .html links inside content
  var m=href.match(/^(index|about|services|courses|contact)\.html(?:#(.+))?$/);
  if(m){e.preventDefault();var key=m[1]==='index'?'home':m[1];location.hash=key;route(key,m[2]?('#'+m[2]):null);return;}
  if(/^(signup|login|dashboard|donate)\.html/.test(href)){e.preventDefault();toast('Staging preview — member sign-up, login, and donation flows go live on the deployed site.');return;}
  if(href.charAt(0)==='#'&&href.length>1){var cur=document.querySelector('.view.active');var t=cur&&cur.querySelector(href);if(t){e.preventDefault();t.scrollIntoView({behavior:'smooth'});}return;}
  // external http(s) links: let them open normally
});

// intercept any form submit (no backend in preview)
document.addEventListener('submit',function(e){e.preventDefault();toast('Staging preview — this form connects to the backend on the deployed site.');});

// donate amount buttons
document.addEventListener('click',function(e){var b=e.target.closest('.amt-btn');if(b){document.querySelectorAll('.amt-btn').forEach(function(x){x.classList.remove('active');});b.classList.add('active');}});

// journey pills (declared-signal personalization)
var JV=['veteran','business','supporter'];
function applyJourney(j){
  document.body.setAttribute('data-journey',j||'');
  document.querySelectorAll('[data-applies-to]').forEach(function(el){
    var tags=el.getAttribute('data-applies-to').split(/\s+/);
    var ok=!j||tags.indexOf('all')>=0||tags.indexOf(j)>=0;
    el.classList.toggle('journey-hidden',!ok);
  });
  document.querySelectorAll('[data-emphasize-for]').forEach(function(el){el.classList.toggle('journey-emphasis',!!j&&el.getAttribute('data-emphasize-for')===j);});
  document.querySelectorAll('.journey-pill').forEach(function(p){p.classList.toggle('active',p.dataset.journey===j);});
}
document.addEventListener('click',function(e){var p=e.target.closest('.journey-pill');if(!p)return;var cur=p.dataset.journey;var isOn=p.classList.contains('active');var next=isOn?null:cur;try{next?localStorage.setItem('sh-journey',next):localStorage.removeItem('sh-journey');}catch(err){}applyJourney(next);});

// topo background
function buildTopo(){var svg=document.querySelector('.topo-bg svg');if(!svg)return;var w=window.innerWidth,h=Math.max(window.innerHeight*2,1600),el=[];var lines=Math.floor(h/30);for(var i=0;i<lines;i++){var by=i*30,pts=[],seg=Math.ceil(w/24);for(var j=0;j<=seg;j++){var x=j*24;var y=by+Math.sin(j*0.06+i*0.35)*24+Math.cos(j*0.1+i*0.2)*14;pts.push((j===0?'M':'L')+' '+x.toFixed(1)+' '+y.toFixed(1));}el.push('<path d="'+pts.join(' ')+'" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="0.8"/>');}svg.innerHTML=el.join('');svg.setAttribute('viewBox','0 0 '+w+' '+h);svg.setAttribute('preserveAspectRatio','xMidYMin slice');}

// init
document.addEventListener('DOMContentLoaded',function(){
  buildTopo();
  try{var sj=localStorage.getItem('sh-journey');if(JV.indexOf(sj)>=0)applyJourney(sj);}catch(e){}
  var key=(location.hash||'#home').slice(1);
  route(VIEWS.indexOf(key)>=0?key:'home',null);
});
window.addEventListener('hashchange',function(){var key=(location.hash||'#home').slice(1);if(VIEWS.indexOf(key)>=0)route(key,null);});
'''

# page inline scripts (amt buttons handled globally; keep others but they mostly re-bind — safe)
page_js="\n".join("try{"+s+"}catch(e){}" for s in scripts if s.strip() and 'amt-btn' not in s)

# charset-independent escaping so it renders under any charset
def esc_html(s): return ''.join(c if ord(c)<128 else f'&#{ord(c)};' for c in s)
def esc_css(s):  return ''.join(c if ord(c)<128 else f'\\{ord(c):06X}' for c in s)
def esc_js(s):   return ''.join(c if ord(c)<128 else c.encode('unicode_escape').decode() for c in s)

css_full = esc_css(f"{fonts_inline}\n{gcss}\n{spa_css}\n{''.join(page_styles)}")
html_full = esc_html(f'{navbar}\n<div class="staging-flag">Staging Preview &mdash; Not Live &middot; Silent Honor Foundation</div>\n<main class="page-content">\n{"".join(views)}\n</main>\n{footer}')
js_full = esc_js(f"{router_js}\n{page_js}")

doc = f'''<style>
{css_full}
</style>

<div class="topo-bg"><svg xmlns="http://www.w3.org/2000/svg"></svg></div>
{html_full}

<script>
{js_full}
</script>
'''

out=f"{ROOT}/site-preview.html"
open(out,"w").write(doc)
print(f"wrote {out} ({os.path.getsize(out)//1024} KB)")
