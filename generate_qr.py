"""
MessMate QR Code Generator (generate_qr.py)
--------------------------------------------
Generates a printable PNG QR code for the deployed MessMate application.
Students scan this QR code in the mess hall to open the feedback form.

Usage:
  python generate_qr.py                              # Uses LIVE_URL variable
  python generate_qr.py https://your-url.onrender.com  # Override via CLI arg

Output: messmate_qr.png (30% error correction — robust for printed posters)
"""

import qrcode
import sys

# ── Configuration ─────────────────────────────────────────────────────────────
# Change this to your actual deployed Render URL before generating
LIVE_URL = "https://your-messmate-app.onrender.com"


def generate_qr(url):
    """Generate and save a high-quality QR code PNG for the given URL."""

    # CRITICAL: Guard against generating a QR code with the placeholder URL
    if "your-messmate-app" in url or not url.startswith("https://"):
        print("⚠️  ERROR: Update LIVE_URL before generating the QR code!")
        print(f"   Current URL: {url}")
        print("   Edit LIVE_URL in generate_qr.py or pass the URL as a CLI argument:")
        print("   python generate_qr.py https://your-real-url.onrender.com")
        sys.exit(1)

    print(f"Generating QR code for: {url}")

    # Configure QR code with high error correction for printed posters
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% correction — most robust
        box_size=10,
        border=4,
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    filename = "messmate_qr.png"
    img.save(filename)

    print(f"✅ QR code saved as {filename}")
    print(f"✅ Point it to: {url}")
    print("\nPrint this and stick it on the mess notice board! 📢")


if __name__ == "__main__":
    # Allow command-line override of the URL
    url_to_use = LIVE_URL
    if len(sys.argv) > 1:
        url_to_use = sys.argv[1]

    generate_qr(url_to_use)
