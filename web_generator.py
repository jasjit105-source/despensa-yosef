import json
import shutil
from pathlib import Path


OUTPUT_DIR = Path(__file__).parent / "output" / "web"


def generate_web_catalog(products: list, categories: list,
                         business_name: str = "Despensa Yosef",
                         whatsapp: str = ""):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "images").mkdir(exist_ok=True)

    for p in products:
        src = p.get("image_path", "")
        if src and Path(src).exists():
            dest = OUTPUT_DIR / "images" / Path(src).name
            if not dest.exists():
                shutil.copy2(src, dest)
            p["web_image"] = f"images/{Path(src).name}"
        else:
            p["web_image"] = ""

    products_json = json.dumps(products, ensure_ascii=False, default=str)
    categories_json = json.dumps(sorted(categories), ensure_ascii=False)

    html = _build_html(products_json, categories_json, business_name, whatsapp)
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")

    netlify_toml = '[build]\n  publish = "."\n\n[[headers]]\n  for = "/*"\n  [headers.values]\n    X-Frame-Options = "DENY"\n    X-Content-Type-Options = "nosniff"\n'
    (OUTPUT_DIR / "netlify.toml").write_text(netlify_toml)

    print(f"  Web catalog saved: {OUTPUT_DIR / 'index.html'}")


def _build_html(products_json, categories_json, business_name, whatsapp):
    wa_link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}" if whatsapp else "#"

    return f'''<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{business_name} - Premium Kosher Grocery Catalog</title>
<meta name="description" content="{business_name} - Premium kosher grocery products catalog. Order via WhatsApp.">
<meta property="og:title" content="{business_name} - Kosher Grocery Catalog">
<meta property="og:description" content="Browse our premium kosher grocery catalog and order via WhatsApp.">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;900&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
--green:#1B4332;--green-mid:#2D6A4F;--green-light:#40916C;
--gold:#D4AF37;--gold-light:#F5E6A3;--gold-dark:#B8960F;
--black:#1A1A1A;--white:#FFFFFF;--off-white:#FAFAFA;
--gray:#6B7280;--gray-light:#E5E7EB;--shadow:0 2px 16px rgba(0,0,0,0.08);
}}
body{{font-family:'Inter',sans-serif;background:var(--off-white);color:var(--black);line-height:1.6}}
.header{{background:var(--green);padding:0;position:sticky;top:0;z-index:100;box-shadow:0 4px 20px rgba(0,0,0,0.3)}}
.header-top{{display:flex;align-items:center;justify-content:space-between;max-width:1400px;margin:0 auto;padding:16px 24px}}
.logo{{display:flex;align-items:center;gap:12px;text-decoration:none}}
.logo-icon{{font-size:28px;color:var(--gold)}}
.logo-text{{font-family:'Playfair Display',serif;font-size:26px;font-weight:700;color:var(--gold);letter-spacing:2px}}
.logo-sub{{font-size:11px;color:rgba(255,255,255,0.7);letter-spacing:3px;text-transform:uppercase}}
.header-actions{{display:flex;gap:12px;align-items:center}}
.wa-btn{{display:inline-flex;align-items:center;gap:8px;background:#25D366;color:#fff;padding:10px 20px;border-radius:25px;text-decoration:none;font-weight:600;font-size:14px;transition:all .3s}}
.wa-btn:hover{{background:#128C7E;transform:translateY(-1px)}}
.search-bar{{background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);border-radius:25px;padding:10px 20px;color:#fff;font-size:14px;width:280px;outline:none;transition:all .3s}}
.search-bar::placeholder{{color:rgba(255,255,255,0.5)}}
.search-bar:focus{{background:rgba(255,255,255,0.2);border-color:var(--gold)}}
.nav{{background:var(--green-mid);border-top:1px solid rgba(255,255,255,0.1)}}
.nav-inner{{max-width:1400px;margin:0 auto;display:flex;gap:0;overflow-x:auto;padding:0 16px;-webkit-overflow-scrolling:touch}}
.nav-inner::-webkit-scrollbar{{height:3px}}
.nav-inner::-webkit-scrollbar-thumb{{background:var(--gold);border-radius:3px}}
.nav-btn{{background:none;border:none;color:rgba(255,255,255,0.8);padding:12px 18px;font-size:13px;font-weight:500;cursor:pointer;white-space:nowrap;transition:all .2s;border-bottom:2px solid transparent;font-family:'Inter',sans-serif}}
.nav-btn:hover,.nav-btn.active{{color:var(--gold);border-bottom-color:var(--gold)}}
.hero{{background:linear-gradient(135deg,var(--green) 0%,var(--green-mid) 100%);padding:48px 24px;text-align:center}}
.hero h1{{font-family:'Playfair Display',serif;font-size:42px;color:var(--gold);margin-bottom:8px;font-weight:700}}
.hero p{{color:rgba(255,255,255,0.8);font-size:16px;max-width:600px;margin:0 auto}}
.hero-divider{{width:80px;height:2px;background:var(--gold);margin:16px auto}}
.stats{{display:flex;justify-content:center;gap:40px;margin-top:24px}}
.stat{{text-align:center}}
.stat-num{{font-family:'Playfair Display',serif;font-size:28px;color:var(--gold);font-weight:700}}
.stat-label{{font-size:12px;color:rgba(255,255,255,0.6);text-transform:uppercase;letter-spacing:1px}}
.container{{max-width:1400px;margin:0 auto;padding:24px}}
.section-title{{font-family:'Playfair Display',serif;font-size:24px;color:var(--green);margin:32px 0 20px;padding-bottom:8px;border-bottom:2px solid var(--gold);display:inline-block}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:24px;margin-bottom:40px}}
.card{{background:var(--white);border-radius:12px;overflow:hidden;box-shadow:var(--shadow);transition:all .3s;border:1px solid var(--gray-light);position:relative}}
.card:hover{{transform:translateY(-4px);box-shadow:0 8px 30px rgba(0,0,0,0.12)}}
.card-badge{{position:absolute;top:12px;right:12px;background:var(--green);color:var(--gold);padding:4px 12px;border-radius:20px;font-size:11px;font-weight:600;letter-spacing:.5px}}
.card-img-wrap{{width:100%;aspect-ratio:1;background:#f3f4f6;display:flex;align-items:center;justify-content:center;overflow:hidden;border-bottom:1px solid var(--gray-light)}}
.card-img-wrap img{{max-width:85%;max-height:85%;object-fit:contain;transition:transform .3s}}
.card:hover .card-img-wrap img{{transform:scale(1.05)}}
.no-img{{color:var(--gray);font-size:14px}}
.card-body{{padding:16px}}
.card-hebrew{{font-size:16px;color:var(--green);font-weight:600;text-align:right;direction:rtl;margin-bottom:4px;min-height:24px}}
.card-name{{font-size:14px;font-weight:600;color:var(--black);margin-bottom:6px;line-height:1.3}}
.card-meta{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:var(--gray)}}
.card-size{{background:var(--off-white);padding:2px 8px;border-radius:4px}}
.card-footer{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--off-white);border-top:1px solid var(--gray-light)}}
.card-price{{font-family:'Playfair Display',serif;font-size:22px;color:var(--green);font-weight:700}}
.card-wa{{background:var(--green);color:var(--gold);border:none;padding:8px 16px;border-radius:20px;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;text-decoration:none;display:inline-flex;align-items:center;gap:4px}}
.card-wa:hover{{background:var(--gold);color:var(--green)}}
.footer{{background:var(--green);color:var(--white);padding:40px 24px;margin-top:60px}}
.footer-inner{{max-width:1400px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:20px}}
.footer-brand{{font-family:'Playfair Display',serif;font-size:24px;color:var(--gold)}}
.footer-text{{color:rgba(255,255,255,0.6);font-size:13px}}
.no-results{{text-align:center;padding:60px;color:var(--gray);font-size:18px}}
.count-badge{{background:var(--gold);color:var(--green);padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700;margin-left:8px}}
@media(max-width:768px){{
  .header-top{{flex-direction:column;gap:12px;text-align:center}}
  .search-bar{{width:100%}}
  .hero h1{{font-size:28px}}
  .stats{{gap:20px}}
  .grid{{grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}}
  .footer-inner{{flex-direction:column;text-align:center}}
}}
@media print{{
  .header,.nav,.hero,.footer,.card-wa,.search-bar,.wa-btn{{display:none!important}}
  .grid{{grid-template-columns:repeat(3,1fr)!important;gap:8px!important}}
  .card{{break-inside:avoid;box-shadow:none!important;border:1px solid #ddd!important}}
  .card:hover{{transform:none!important}}
}}
</style>
</head>
<body>
<header class="header">
  <div class="header-top">
    <a href="#" class="logo">
      <span class="logo-icon">✡</span>
      <div>
        <div class="logo-text">{business_name.upper()}</div>
        <div class="logo-sub">Premium Kosher Grocery</div>
      </div>
    </a>
    <div class="header-actions">
      <input type="text" class="search-bar" id="searchInput" placeholder="Search products...">
      <a href="{wa_link}" target="_blank" class="wa-btn">&#9742; WhatsApp</a>
    </div>
  </div>
  <nav class="nav">
    <div class="nav-inner" id="navCategories">
      <button class="nav-btn active" onclick="filterCategory('all')">All Products</button>
    </div>
  </nav>
</header>

<section class="hero">
  <h1>✡ {business_name} ✡</h1>
  <div class="hero-divider"></div>
  <p>Premium kosher grocery products delivered to your door</p>
  <div class="stats">
    <div class="stat"><div class="stat-num" id="totalProducts">0</div><div class="stat-label">Products</div></div>
    <div class="stat"><div class="stat-num" id="totalCategories">0</div><div class="stat-label">Categories</div></div>
    <div class="stat"><div class="stat-num" id="totalBrands">0</div><div class="stat-label">Brands</div></div>
  </div>
</section>

<main class="container" id="catalogContainer"></main>

<footer class="footer">
  <div class="footer-inner">
    <div>
      <div class="footer-brand">✡ {business_name.upper()}</div>
      <div class="footer-text">Premium Kosher Grocery Catalog</div>
    </div>
    <div class="footer-text">Quality products for your home</div>
  </div>
</footer>

<script>
const PRODUCTS = {products_json};
const CATEGORIES = {categories_json};
const WA_LINK = "{wa_link}";
let currentCategory = "all";
let searchTerm = "";

function init() {{
  document.getElementById("totalProducts").textContent = PRODUCTS.length;
  document.getElementById("totalCategories").textContent = CATEGORIES.length;
  const brands = new Set(PRODUCTS.map(p => (p.name || "").split(" ")[0]));
  document.getElementById("totalBrands").textContent = brands.size;
  const nav = document.getElementById("navCategories");
  CATEGORIES.forEach(cat => {{
    const btn = document.createElement("button");
    btn.className = "nav-btn";
    btn.textContent = cat;
    btn.onclick = () => filterCategory(cat);
    nav.appendChild(btn);
  }});
  renderProducts();
  document.getElementById("searchInput").addEventListener("input", e => {{
    searchTerm = e.target.value.toLowerCase();
    renderProducts();
  }});
}}

function filterCategory(cat) {{
  currentCategory = cat;
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  event.target.classList.add("active");
  renderProducts();
}}

function renderProducts() {{
  let filtered = PRODUCTS;
  if (currentCategory !== "all") filtered = filtered.filter(p => p.category === currentCategory);
  if (searchTerm) filtered = filtered.filter(p =>
    (p.name || "").toLowerCase().includes(searchTerm) ||
    (p.hebrew_name || "").includes(searchTerm) ||
    (p.category || "").toLowerCase().includes(searchTerm) ||
    (p.upc || "").includes(searchTerm)
  );

  const container = document.getElementById("catalogContainer");
  if (!filtered.length) {{
    container.innerHTML = '<div class="no-results">No products found</div>';
    return;
  }}

  const grouped = {{}};
  filtered.forEach(p => {{
    const cat = p.category || "General";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(p);
  }});

  let html = "";
  Object.keys(grouped).sort().forEach(cat => {{
    html += `<h2 class="section-title">${{cat}}<span class="count-badge">${{grouped[cat].length}}</span></h2>`;
    html += '<div class="grid">';
    grouped[cat].forEach(p => {{
      const imgHtml = p.web_image
        ? `<img src="${{p.web_image}}" alt="${{p.name}}" loading="lazy">`
        : `<div class="no-img">No Image</div>`;
      const waMsg = encodeURIComponent(`Hi, I'd like to order:\\n${{p.name}}\\nPrice: $${{(p.retail_price||0).toFixed(2)}}\\nSize: ${{p.size||'N/A'}}`);
      const waUrl = WA_LINK !== "#" ? `${{WA_LINK}}?text=${{waMsg}}` : "#";
      html += `
      <div class="card">
        <span class="card-badge">${{p.category || 'Grocery'}}</span>
        <div class="card-img-wrap">${{imgHtml}}</div>
        <div class="card-body">
          <div class="card-hebrew">${{p.hebrew_name || ''}}</div>
          <div class="card-name">${{p.name || 'Unknown Product'}}</div>
          <div class="card-meta">
            <span class="card-size">${{p.size || ''}}</span>
            <span>UPC: ${{p.upc || 'N/A'}}</span>
          </div>
        </div>
        <div class="card-footer">
          <span class="card-price">$${{(p.retail_price||0).toFixed(2)}}</span>
          <a href="${{waUrl}}" target="_blank" class="card-wa">&#9742; Order</a>
        </div>
      </div>`;
    }});
    html += '</div>';
  }});
  container.innerHTML = html;
}}

init();
</script>
</body>
</html>'''
