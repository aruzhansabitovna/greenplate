import re
import sys
import requests
from urllib.parse import urljoin

UBS_PAGE = "https://ubs.antalya.edu.tr/"
# Ищем ссылки вида https://admin.antalya.edu.tr/files/...HAFTALIK_MENU.pdf
PDF_RE = re.compile(r"https?://admin\.antalya\.edu\.tr/files/[^\s\"']+?HAFTALIK[^\"']*?MENU\.pdf", re.IGNORECASE)

def pick_best(urls):
    # Пробуем выбрать “самую новую” по дате в имени файла, если она есть: 8_12_25-12_12_25_HAFTALIK_MENU.pdf
    def score(u):
        m = re.search(r"(\d{1,2})_(\d{1,2})_(\d{2,4})-(\d{1,2})_(\d{1,2})_(\d{2,4})", u)
        if not m:
            return (0, 0, 0, 0, 0, 0)
        d1, m1, y1, d2, m2, y2 = m.groups()
        y2 = int(y2)
        if y2 < 100:  # на всякий случай
            y2 += 2000
        return (y2, int(m2), int(d2), int(y1 if int(y1) > 100 else 2000+int(y1)), int(m1), int(d1))
    return sorted(set(urls), key=score)[-1]

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; GreenPlateBot/1.0)"
    }
    r = requests.get(UBS_PAGE, headers=headers, timeout=30)
    r.raise_for_status()

    found = PDF_RE.findall(r.text)
    if not found:
        # fallback: если UBS не отдал HTML боту — пусть workflow не падает
        sys.stdout.write("https://admin.antalya.edu.tr/files/418/8_12_25-12_12_25_HAFTALIK_MENU.pdf")
        return

    sys.stdout.write(pick_best(found))

if __name__ == "__main__":
    main()
