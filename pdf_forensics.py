import os
import datetime
import fitz  # PyMuPDF
import pikepdf
from PIL import Image, ImageChops, ImageEnhance
import numpy as np
import io
import json
import glob

class PDFTamperingDetector:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.flags = []
        self.suspicion_score = 0
        self.metadata = {}
        self.font_details = []
        self.report = {
            "file": os.path.basename(pdf_path),
            "timestamp": datetime.datetime.now().isoformat(),
            "flags": [],
            "suspicion_score": 0,
            "details": {}
        }

    def detect(self, verbose=True):
        """Runs all detection modules."""
        if verbose:
            print(f"Analyzing {self.pdf_path}...")
        try:
            self._check_metadata()
        except Exception as e:
            self.flags.append(f"Metadata analysis failed: {str(e)}")
            
        try:
            self._check_structure()
        except Exception as e:
            self.flags.append(f"Structural analysis failed: {str(e)}")
            
        try:
            self._analyze_images()
        except Exception as e:
            self.flags.append(f"Image analysis failed: {str(e)}")

        try:
            self._check_fonts()
        except Exception as e:
            self.flags.append(f"Font analysis failed: {str(e)}")

        self.report["flags"] = self.flags
        self.report["suspicion_score"] = self.suspicion_score
        return self.report

    def _add_flag(self, message, severity=1):
        """Adds a flag and updates suspicion score."""
        self.flags.append(message)
        self.suspicion_score += severity

    def _check_metadata(self):
        """Checks for metadata inconsistencies."""
        try:
            with pikepdf.Pdf.open(self.pdf_path) as pdf:
                docinfo = pdf.docinfo
                
                # Convert pikepdf metadata to standard dict
                meta = {}
                for key, value in docinfo.items():
                    meta[key] = str(value)
                
                self.report["details"]["metadata"] = meta

                # Check 1: CreationDate vs ModDate
                if "/CreationDate" in meta and "/ModDate" in meta:
                    c_date_str = meta["/CreationDate"] # Format: D:YYYYMMDDHHmmSS...
                    m_date_str = meta["/ModDate"]
                    
                    # Basic parsing to checking meaningful difference
                    # Minimal parser for "D:YYYYMMDD"
                    try:
                        c_dt = datetime.datetime.strptime(c_date_str[2:10], "%Y%m%d")
                        m_dt = datetime.datetime.strptime(m_date_str[2:10], "%Y%m%d")
                        diff = abs((m_dt - c_dt).days)
                        
                        if diff > 1: # More than 1 day difference
                             self._add_flag(f"Metadata mismatch: Creation date ({c_date_str}) differs from Modification date ({m_date_str}) by {diff} days.", severity=3)
                        elif c_date_str != m_date_str:
                             self._add_flag(f"Minor metadata mismatch: Creation date differs from Modification date.", severity=1)
                    except:
                        # Fallback if parsing fails
                        if c_date_str != m_date_str:
                             self._add_flag(f"Metadata mismatch: Creation date differs from Modification date.", severity=2)

                # Check 2: Suspicious Producer/Creator
                suspicious_keywords = ["gimp", "photoshop", "ilovepdf", "sejda", "smallpdf", "phantompdf"]
                producer = meta.get("/Producer", "").lower()
                creator = meta.get("/Creator", "").lower()

                for keyword in suspicious_keywords:
                    if keyword in producer or keyword in creator:
                        self._add_flag(f"Suspicious editing tool found in metadata: {keyword} (Producer: {producer}, Creator: {creator})", severity=3)

        except Exception as e:
             self._add_flag(f"Could not read metadata: {str(e)}", severity=1)

    def _check_structure(self):
        """Checks for structural anomalies."""
        try:
            # Check for incremental updates using file analysis or pikepdf
            # If the file has been saved incrementally, it might contain previous versions.
            # A simple heuristic check for '%%EOF' count
            with open(self.pdf_path, 'rb') as f:
                content = f.read()
                eof_count = content.count(b'%%EOF')
                if eof_count > 1:
                    self._add_flag(f"Incremental updates detected (Found {eof_count} EOF markers). File may have been edited.", severity=1)

            # dirty/malformed check logic could go here
                
        except Exception as e:
             self._add_flag(f"Structure check error: {str(e)}", severity=1)

    def _analyze_images(self):
        """Extracts images and performs Error Level Analysis (ELA)."""
        doc = fitz.open(self.pdf_path)
        image_issues = []
        
        for i, page in enumerate(doc):
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                try:
                    # Perform ELA
                    ela_score = self._compute_ela(image_bytes)
                    
                    # Increased threshold to 10.0 based on analysis of scanned receipts (noise floor ~6.5)
                    if ela_score > 10.0: 
                        image_issues.append(f"Page {i+1} Image {img_index}: High ELA score ({ela_score:.2f}), possible manipulation.")
                        self._add_flag(f"Visual anomaly on Page {i+1}: Potential image manipulation detected.", severity=2)
                
                except Exception as e:
                    print(f"Failed to analyze image {img_index} on page {i}: {e}")

        if image_issues:
            self.report["details"]["visual_analysis"] = image_issues

    def _check_fonts(self):
        """Checks for inconsistent fonts, especially in numbers."""
        doc = fitz.open(self.pdf_path)
        fonts = set()
        
        for page in doc:
            font_list = page.get_fonts()
            for f in font_list:
                # f is (xref, ext, type, basefont, name, encoding)
                font_name = f[3]
                fonts.add(font_name)
        
        self.report["details"]["fonts"] = list(fonts)
        
        # Heuristic: If there are multiple fonts and one of them is standard (Helvetica/Arial) 
        # while others are embedded subsets, it MIGHT be edited.
        # But legitimate PDFs often have many fonts.
        # A stronger check is if the file claims to be created by a generator that usually embeds fonts,
        # but we find standard system fonts (often added by simple editors).
        
        # For now, just flag if there are A LOT of different fonts for a small file
        if len(fonts) > 5: # Arbitrary threshold
             # self._add_flag(f"High number of fonts detected ({len(fonts)}). Complex document or pasted text.", severity=0)
             pass
    
    def _compute_ela(self, image_bytes):
        """
        Computes a simple ELA score.
        Resaves the image at 95% JPEG quality and differs it with the original.
        Returns the mean of the difference.
        """
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Save compressed
        compressed_buffer = io.BytesIO()
        original.save(compressed_buffer, 'JPEG', quality=95)
        compressed_buffer.seek(0)
        compressed = Image.open(compressed_buffer).convert("RGB")
        
        # Calculate difference
        diff = ImageChops.difference(original, compressed)
        
        # Enhance for visibility (optional for viewing, but we just need stats)
        # extrema = diff.getextrema()
        # max_diff = max([ex[1] for ex in extrema])
        # scale = 255.0 / max_diff if max_diff > 0 else 1
        # diff = ImageEnhance.Brightness(diff).enhance(scale)

        # Get mean difference
        stat = np.array(diff).mean()
        return stat

def scan_directory(directory_path):
    print(f"Scanning directory: {directory_path}")
    pdf_files = glob.glob(os.path.join(directory_path, "*.pdf"))
    results = []

    print(f"{'Filename':<40} | {'Score':<5} | {'Verdict':<20}")
    print("-" * 75)

    for pdf_file in pdf_files:
        detector = PDFTamperingDetector(pdf_file)
        report = detector.detect(verbose=False)
        
        score = report["suspicion_score"]
        if score == 0:
            verdict = "Safe"
        elif score <= 2:
            verdict = "Suspicious"
        else:
            verdict = "Likely Tampered"

        results.append({
            "file": os.path.basename(pdf_file),
            "score": score,
            "verdict": verdict,
            "flags": report["flags"]
        })

        print(f"{os.path.basename(pdf_file):<40} | {score:<5} | {verdict:<20}")

    # Save detailed results to JSON
    output_file = os.path.join(directory_path, "forensic_report.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=4)
    print(f"\nDetailed report saved to {output_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_forensics.py <path_to_pdf_or_directory>")
    else:
        path = sys.argv[1]
        if os.path.isdir(path):
            scan_directory(path)
        elif os.path.isfile(path):
            detector = PDFTamperingDetector(path)
            report = detector.detect()
            print(json.dumps(report, indent=4))
        else:
            print("File or directory not found.")
