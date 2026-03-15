"""
MessMate QR Code Generator (generate_qr.py)
-------------------------------------------
This utility script generates a printable PNG QR Code containing the live URL 
for the deployed MessMate application. This allows students to easily access 
the feedback form by scanning the printed QR code in the mess hall.
"""

import qrcode
import sys

# Change this to your live Render/Railway URL when deployed
LIVE_URL = "https://your-messmate-app.onrender.com"

def generate_qr(url):
    print(f"Generating QR code for: {url}")
    
    # Configure QR code for high reliability/readability
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M, # M = 15% error correction
        box_size=10, # Large enough to scan from far
        border=4, # Quiet zone required for reliable scanning
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
    url_to_use = LIVE_URL
    # Allow overriding URL via command line
    if len(sys.argv) > 1:
        url_to_use = sys.argv[1]
        
    generate_qr(url_to_use)
