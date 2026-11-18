"""
สร้างบทความใหม่ด้วย Gemini แล้วเพิ่มลิงก์ลงใน index.html  (BangkokBangkok.NET)

วิธีใช้:
    set GEMINI_API_KEY=xxxx            (Windows)  /  export GEMINI_API_KEY=xxxx  (Mac/Linux)
    python scripts/new_article.py "หัวข้อบทความ"

ใช้แค่ Python มาตรฐาน ไม่ต้อง pip install อะไรเพิ่ม
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "ajarn-champ-thitipol-ai-speaker-chiang-mai-origin.html"   # หน้าต้นแบบ (หัว/เมนู/ฟุตเตอร์)
INDEX = ROOT / "index.html"
MARKER = "<!-- NEW_ARTICLE_INSERTION_POINT -->"      # จุดที่การ์ดบทความใหม่จะถูกแทรกใน index.html
IMAGE_URL = "https://famast.com/genimgg.php?g="      # บริการสร้างรูปที่เว็บใช้อยู่แล้ว

# ลองตามลำดับ: ถ้ารุ่นแรกใช้ไม่ได้ (ถูกปิดแล้ว) จะลองรุ่นถัดไปให้อัตโนมัติ
# เปลี่ยนได้ด้วย env GEMINI_MODEL เช่น  GEMINI_MODEL=gemini-2.5-flash
MODELS = [m for m in [os.environ.get("GEMINI_MODEL")] if m] + [
    "gemini-2.0-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
]

PROMPT = """คุณคือ อาจารย์แชมป์ ธิติพล เทียมจันทร์ ผู้ก่อตั้ง BrandingChamp ที่ปรึกษาการตลาดออนไลน์ และวิทยากรด้าน AI Marketing
เขียนบทความลงเว็บข่าวการตลาด ธุรกิจ เทคโนโลยี BangkokBangkok.NET

หัวข้อ: "{title}"
- ภาษาไทย ยาวประมาณ 1,200-1,800 คำ เล่าแบบมืออาชีพแต่เป็นกันเอง ใช้สรรพนาม "ผม"
- มีข้อมูล ตัวอย่างกรณีศึกษาธุรกิจไทย และคำแนะนำที่ผู้อ่านนำไปทำได้จริง
- ไม่กล่าวอ้างตัวเลขหรือข้อเท็จจริงที่ไม่แน่ใจว่าจริง
- ใส่คีย์เวิร์ดหลักของหัวข้อแบบเป็นธรรมชาติ
{notes}
ตอบเป็น JSON เท่านั้น ตามโครงสร้างนี้:
{{
  "slug": "ชื่อไฟล์ภาษาอังกฤษตัวเล็ก คั่นด้วยขีด สื่อความหมายของหัวข้อ 3-7 คำ เช่น ai-marketing-for-sme",
  "title": "หัวข้อหลัก H1 (ใกล้เคียงหัวข้อที่ให้มา)",
  "subtitle": "หัวข้อรอง H2 ที่ขยายความ น่าคลิก",
  "meta_description": "คำอธิบาย 140-160 ตัวอักษร",
  "keywords": "คีย์เวิร์ด 5-8 คำ คั่นด้วยจุลภาค",
  "paragraphs": ["ย่อหน้าที่ 1", "ย่อหน้าที่ 2", "..."],
  "image_prompts": ["prompt รูปภาษาอังกฤษ 3 อัน สำหรับรูปบน กลาง และท้ายบทความ เช่น Thai business owner using AI dashboard in modern Bangkok office, photorealistic, vertical"]
}}

กติกา:
- paragraphs มี 5-7 ย่อหน้า แต่ละย่อหน้ายาว เป็นข้อความล้วน ห้ามมี HTML หรือ markdown
- image_prompts มี 3 อัน เป็นภาษาอังกฤษ ไม่มีตัวหนังสือในรูป
"""


# ---------------------------------------------------------------- Gemini

def call_gemini(title: str, notes: str = "") -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("ไม่พบ GEMINI_API_KEY  (ขอฟรีได้ที่ https://aistudio.google.com/apikey)")

    notes = f"- ความต้องการเพิ่มเติมจากผู้สั่ง (ทำตามนี้ด้วย): {notes}\n" if notes else ""
    body = json.dumps({
        "contents": [{"parts": [{"text": PROMPT.format(title=title, notes=notes)}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
    }).encode("utf-8")

    last_error = ""
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(4):
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = json.load(r)
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"ใช้โมเดล: {model}")
                return parse_json(text)
            except urllib.error.HTTPError as e:
                last_error = f"{model}: HTTP {e.code} {e.read()[:300]!r}"
                if e.code in (429, 500, 503):          # ติดโควต้า/เซิร์ฟเวอร์ยุ่ง → รอแล้วลองใหม่
                    wait = 20 * (attempt + 1)
                    print(f"{model} ตอบ {e.code} รอ {wait} วินาที แล้วลองใหม่...")
                    time.sleep(wait)
                    continue
                print(f"{model} ใช้ไม่ได้ (HTTP {e.code}) → ลองรุ่นถัดไป")
                break                                   # 400/403/404 → ข้ามไปรุ่นถัดไป
            except (KeyError, IndexError, ValueError) as e:
                last_error = f"{model}: คำตอบผิดรูปแบบ ({e})"
                print(last_error + " → ลองใหม่")
    sys.exit("เรียก Gemini ไม่สำเร็จ: " + last_error)


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    data = json.loads(text)
    for field in ("title", "subtitle", "paragraphs"):
        if not data.get(field):
            raise ValueError(f"ไม่มีช่อง {field}")
    return data


# ---------------------------------------------------------------- helpers

def esc(s) -> str:
    return html.escape(str(s or "").strip(), quote=True)


def plain(s) -> str:
    """ตัด HTML/markdown ที่ AI อาจแอบใส่มา ให้เหลือข้อความล้วน"""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", str(s or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[*#`]+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def make_filename(a: dict, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(a.get("slug") or "").lower()).strip("-")[:70]
    if not slug:                                        # ไม่มี slug อังกฤษ → ใช้ชื่อไทยจากหัวข้อ
        slug = re.sub(r'[\\/:*?"<>|#%&{}$!\'@+`=“”‘’,.()\[\]]', " ", title)
        slug = re.sub(r"\s+", "-", slug.strip()).strip("-")[:70] or "article"
    name, n = slug, 2
    while (ROOT / f"{name}.html").exists():             # ชื่อซ้ำ → เติมเลขท้าย
        name, n = f"{slug}-{n}", n + 1
    return f"{name}.html"


def image_tag(prompt: str, alt: str, style: str) -> str:
    src = IMAGE_URL + urllib.parse.quote_plus(plain(prompt) or "Thai business marketing, photorealistic")
    return f'<img src="{esc(src)}" {style} alt="{esc(alt)}" title="{esc(alt)}">'


# ---------------------------------------------------------------- build article

def build_article(a: dict) -> tuple[str, str]:
    page = TEMPLATE.read_text(encoding="utf-8")
    title, subtitle = plain(a["title"]), plain(a["subtitle"])
    paragraphs = [esc(plain(p)) for p in a["paragraphs"] if plain(p)]
    prompts = (list(a.get("image_prompts") or []) + [f"{title}, Thai business, photorealistic"] * 3)[:3]
    img = lambda p: image_tag(p, subtitle, 'style="width:98%; height:auto;"')

    page = re.sub(r"<title>.*?</title>",
                  lambda m: f"<title>{esc(title)} | BangkokBangkok.NET</title>", page, 1, re.S)
    page = re.sub(r'<meta name="keywords" content="[^"]*">',
                  lambda m: f'<meta name="keywords" content="{esc(a.get("keywords") or title)}">\n'
                            f'  <meta name="description" content="{esc(a.get("meta_description") or subtitle)}">',
                  page, 1)

    # เนื้อหา: รูปบน → H1 → H2 → ย่อหน้า (รูปกลางหลังย่อหน้าแรก) → รูปท้าย  ตามรูปแบบบทความเดิม
    body = [f"<center>{img(prompts[0])}</center>", "<br/>",
            f"<h1>{esc(title)}</h1>", "<br/>",
            f"<h2>{esc(subtitle)}</h2>", "<br/>", "<p>"]
    for i, p in enumerate(paragraphs):
        body.append(p)
        if i == 0:
            body += ["<br/><br/><br/>", f"<center>{img(prompts[1])}</center>", "<br/><br/><br/>"]
        elif i < len(paragraphs) - 1:
            body.append("<br/><br/><br/><br/>")
    body += ["<br/><br/><br/>", f"<center>{img(prompts[2])}</center>", "</p>"]
    content = '<div class="content">\n<div class="container">\n<br/>\n' + "\n".join(body) + "\n</div>\n</div>\n"

    start = page.index('<div class="content">')
    end = page.index("<!--==============================footer")
    page = page[:start] + content + "    " + page[end:]

    excerpt = plain(a["paragraphs"][0])
    excerpt = (excerpt[:150] + "...") if len(excerpt) > 150 else excerpt
    return page, build_card(title, subtitle, excerpt, prompts[0])


# ---------------------------------------------------------------- update index.html

def build_card(title, subtitle, excerpt, prompt, filename="{FILE}") -> str:
    return f"""
				<li class="clearfix">
                    <div class="scale_image_container">
					                        <a href="./{filename}">
											{image_tag(prompt, subtitle, 'class="scale_image"')}
											</a>
					                      </div>
                    <div class="wrapper">
                      <div class="post_text">
			      <h3 class="post_title"><a href="./{filename}">{esc(title)}</a></h3>
				<p>{esc(excerpt)}</p>
                      </div>
                    </div>
                  </li>"""


def update_index(card: str) -> None:
    index = INDEX.read_text(encoding="utf-8")
    if MARKER not in index:
        sys.exit(f"ไม่พบ {MARKER} ใน index.html")
    index = index.replace(MARKER, MARKER + card, 1)     # การ์ดใหม่อยู่บนสุดเสมอ
    INDEX.write_text(index, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- main

def main():
    if hasattr(sys.stdout, "reconfigure"):   # ให้แสดงภาษาไทยได้ใน Windows console
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    title = " ".join(sys.argv[1:]).strip() or os.environ.get("ARTICLE_TITLE", "").strip()
    if not title:
        sys.exit('ใส่หัวข้อด้วย เช่น  python scripts/new_article.py "AI Marketing สำหรับ SME"')
    notes = os.environ.get("ARTICLE_NOTES", "").strip()

    print(f"กำลังเขียนบทความ: {title}")
    article = call_gemini(title, notes)

    filename = make_filename(article, title)
    page, card = build_article(article)
    (ROOT / filename).write_text(page, encoding="utf-8", newline="\n")
    print(f"สร้างไฟล์แล้ว: {filename}")

    update_index(card.replace("{FILE}", urllib.parse.quote(filename)))
    print("อัปเดต index.html แล้ว")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"filename={filename}\n")


if __name__ == "__main__":
    main()
