import os
import time
from reportlab.pdfgen import canvas
import pikepdf
from pdf_forensics import PDFTamperingDetector
import json
from PIL import Image
import random

def create_clean_pdf(filename):
    c = canvas.Canvas(filename)
    c.drawString(100, 750, "This is a clean PDF.")
    c.save()

def create_tampered_pdf(original, tampered):
    # 1. Modify Metadata to trigger suspicion
    with pikepdf.open(original) as pdf:
        with pdf.open_metadata() as meta:
            meta["dc:creator"] = "GIMP" # Trigger keyword detection
            meta["xmp:CreatorTool"] = "GIMP 2.10"
        pdf.save(tampered)
    
    # 2. Simulate incremental save (re-saving with pikepdf does this by default if not linearizing, 
    # but let's just use the modified one)
    
    # Manually modify mod date in the file to be different from creation (if not already handled by pikepdf)
    # Actually, pikepdf updates ModDate automatically, so if we wait a second, it should differ.
    time.sleep(2)
    with pikepdf.open(tampered, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/ModDate"] = pikepdf.Name("/D:20250101000000+00'00'") # Fake old date or just different
        pdf.save(tampered)

def create_ela_test_pdf(filename):
    print("Generating visual manipulation test case...")
    # 1. Create a background with random noise (high entropy) to simulate a photo/scan
    img = Image.new('RGB', (400, 400), color='white')
    pixels = img.load()
    for i in range(400):
        for j in range(400):
             # Random noise
            pixels[i,j] = (random.randint(200,250), random.randint(200,250), random.randint(200,250))
    
    # Save base as High Quality
    img.save("temp_base.jpg", quality=95)
    base = Image.open("temp_base.jpg")

    # 2. Create a "patch" (e.g., a fake number) and save it with DIFFERENT quality
    patch = Image.new('RGB', (100, 50), color=(255, 255, 200)) # Yellowish fake note
    patch.save("temp_patch.jpg", quality=50) # Low quality to create ELA disparity
    patch_loaded = Image.open("temp_patch.jpg")
    
    # 3. Paste the low-quality patch onto the high-quality base
    base.paste(patch_loaded, (100, 100))
    
    # 4. Save the final result. Key: Save as PNG or high-quality JPG to preserve the artifact difference?
    # If we save this final composition as JPG, it re-compresses everything.
    # However, the low-quality artifacts in the patch are now "baked in" as image data.
    # When we re-save at High Quality, those artifacts persist.
    base.save("temp_tampered_final.jpg", quality=98)

    # 5. Put into PDF
    c = canvas.Canvas(filename)
    c.drawString(50, 750, "Visual Tampering Test (ELA)")
    c.drawImage("temp_tampered_final.jpg", 50, 300, width=300, height=300)
    c.save()

    # Cleanup
    for f in ["temp_base.jpg", "temp_patch.jpg", "temp_tampered_final.jpg"]:
        if os.path.exists(f): os.remove(f)

def test_detection():
    clean_file = "clean_test.pdf"
    tampered_file = "tampered_test.pdf"
    ela_file = "ela_test.pdf"

    try:
        print("Creating clean PDF...")
        create_clean_pdf(clean_file)
        
        print("Creating tampered PDF (Metadata/Structure)...")
        create_tampered_pdf(clean_file, tampered_file)

        create_ela_test_pdf(ela_file)

        print("-" * 20)
        print("Testing Clean PDF:")
        print(json.dumps(PDFTamperingDetector(clean_file).detect(verbose=False), indent=2))
        
        print("-" * 20)
        print("Testing Metadata Tampered PDF:")
        print(json.dumps(PDFTamperingDetector(tampered_file).detect(verbose=False), indent=2))

        print("-" * 20)
        print("Testing Visual Tampered PDF (ELA):")
        report_ela = PDFTamperingDetector(ela_file).detect(verbose=False)
        print(json.dumps(report_ela, indent=2))

        print("\nNote: ELA allows detecting if an image was composed of parts with different compression levels.")
        
    finally:
        # Cleanup
        # if os.path.exists(clean_file):
        #     os.remove(clean_file)
        # if os.path.exists(tampered_file):
        #     os.remove(tampered_file)
        pass

if __name__ == "__main__":
    test_detection()
