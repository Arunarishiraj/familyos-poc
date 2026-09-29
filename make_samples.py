from PIL import Image, ImageDraw, ImageFont
import pymupdf


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def make_image(lines, path, size=(1000, 520)):
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    f = font(34)
    y = 30
    for line in lines:
        d.text((40, y), line, fill="black", font=f)
        y += 58
    img.save(path)
    return img


# 1. Photo-style bill (IMAGE)
make_image([
    "XYZ POWER LTD - ELECTRICITY BILL",
    "Consumer: Ramesh Kumar",
    "Bill period: August 2026",
    "Amount due: Rs. 2500",
    "Due date: 2026-09-20",
], "sample_inputs/bill_photo.png")

# 2. PDF with a real text layer
doc = pymupdf.open()
page = doc.new_page()
page.insert_text((72, 90), "\n".join([
    "SafeDrive Insurance - Renewal Notice",
    "Policy: Car insurance, vehicle TN 58 AB 1234",
    "Premium: Rs. 14,200",
    "Renew before: 2026-10-15",
]), fontsize=12)
doc.save("sample_inputs/insurance_notice.pdf")

# 3. Scanned-style PDF (image only, no text layer)
img = make_image([
    "CITY CARE HOSPITAL - PRESCRIPTION",
    "Patient: Meera (age 6)",
    "Dr. Anitha, Pediatrics",
    "Paracetamol syrup 5 ml, twice daily, 3 days",
    "Follow-up visit: 2026-10-03",
], "/tmp/scan.png")
img.save("sample_inputs/scanned_prescription.pdf")

# 4. Email
open("sample_inputs/flight_booking.eml", "w").write(
"""From: bookings@skyair.example
To: family@example.com
Subject: Booking confirmed - Madurai to Chennai
Date: Mon, 28 Sep 2026 09:00:00 +0530

Your flight SA 412 from Madurai (IXM) to Chennai (MAA) departs on 2026-10-10 at 07:15.
Passengers: Ramesh Kumar, Meera. Booking reference: QX7P2L.
""")

# 5. Calendar event
open("sample_inputs/school_event.ics", "w").write(
"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Parent-teacher meeting - Class 6
DTSTART:20261005T100000
DTEND:20261005T110000
LOCATION:Sunrise Public School
DESCRIPTION:Discuss Term-1 progress
END:VEVENT
END:VCALENDAR
""")
print("samples created")
