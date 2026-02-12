# PDF Tampering Detection

A Python-based forensic tool to detect potential tampering in PDF documents, such as modified reimbursement receipts or fake invoices.

## Features

This tool performs three levels of analysis to flag suspicious files:

1.  **Metadata Analysis**:
    *   Checks for inconsistencies between Creation and Modification dates.
    *   Flags suspicious "Producer" or "Creator" tools often used for editing (e.g., GIMP, Photoshop, Sejda, iLovePDF).
    *   **Severity**: High if modification date is >24 hours after creation.

2.  **Structural Analysis**:
    *   Detects "Incremental Updates" (file changes appended to the end), which strongly indicate post-creation editing.

3.  **Visual Analysis (Error Level Analysis - ELA)**:
    *   Extracts images from the PDF.
    *   Performs Error Level Analysis to detect compression artifacts.
    *   Identifies potential splicing (e.g., pasting a fake number or text onto a scanned document).
    *   **Note**: Tuned for scanned documents to reduce false positives from logos.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/psraghothamrao8/pdf-tampering.git
    cd pdf-tampering
    ```

2.  **Install Dependencies**:
    It is recommended to use a virtual environment.
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Single File Scan
To analyze a specific PDF:
```bash
python pdf_forensics.py path/to/document.pdf
```

### Directory Scan
To scan an entire folder of PDFs and generate a report:
```bash
python pdf_forensics.py path/to/folder/
```

**Output**:
*   Prints a summary table to the console.
*   Saves a detailed `forensic_report.json` in the scanned folder.

## Output Explanation

The tool provides a **Suspicion Score** and a **Verdict**:

| Score | Verdict | Meaning |
| :--- | :--- | :--- |
| **0** | **Safe** | No obvious signs of tampering found. |
| **1-2** | **Suspicious** | Minor anomalies (e.g., metadata mismatch) found. Manual review recommended. |
| **> 3** | **Likely Tampered** | Strong indicators of editing (e.g., major date mismatch, known editing tool, spliced images). |

## Disclaimer
This tool provides probabilistic detection based on common forensic indicators. A "Safe" verdict does not guarantee authenticity, and a "Tampered" verdict does not prove malicious intent (e.g., a file might be re-saved in a different viewer). Always perform manual verification for critical documents.
