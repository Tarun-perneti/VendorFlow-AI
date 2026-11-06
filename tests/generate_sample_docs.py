"""
generate_sample_docs.py - Create realistic sample PDF documents for testing.

Run from the vendorflow/ directory:
    venv/Scripts/python.exe -m tests.generate_sample_docs

Creates sample documents in tests/sample_docs/:
- registration_certificate.pdf
- tax_certificate.pdf
- bank_statement.pdf
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


SAMPLE_DIR = Path(__file__).parent / "sample_docs"
SAMPLE_DIR.mkdir(exist_ok=True)


def create_registration_certificate():
    """Create a sample certificate of incorporation PDF."""
    filepath = SAMPLE_DIR / "registration_certificate.pdf"
    doc = SimpleDocTemplate(str(filepath), pagesize=A4)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=18, spaceAfter=20, alignment=1,
    )
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"],
        fontSize=14, spaceAfter=10, alignment=1,
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=styles["Normal"],
        fontSize=11, spaceAfter=8,
    )

    elements = []
    elements.append(Paragraph("GOVERNMENT OF INDIA", title_style))
    elements.append(Paragraph("MINISTRY OF CORPORATE AFFAIRS", heading_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("CERTIFICATE OF INCORPORATION", heading_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "This is to certify that the company with the following details "
        "has been duly incorporated under the Companies Act, 2013.",
        body_style,
    ))
    elements.append(Spacer(1, 10))

    data = [
        ["Company Name", "Acme Corp Pvt Ltd"],
        ["CIN", "U12345MH2020PTC123456"],
        ["Date of Incorporation", "15th March 2020"],
        ["Registered Office", "Mumbai, Maharashtra, India"],
        ["Authorized Capital", "INR 10,00,000"],
        ["Paid-up Capital", "INR 5,00,000"],
    ]
    table = Table(data, colWidths=[6 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.9, 0.9, 0.95)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        "Given under my hand at the office of the Registrar of Companies, "
        "Mumbai, on this 15th day of March, 2020.",
        body_style,
    ))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Registrar of Companies", body_style))
    elements.append(Paragraph("Mumbai, Maharashtra", body_style))

    doc.build(elements)
    print(f"  Created: {filepath}")
    return str(filepath)


def create_tax_certificate():
    """Create a sample GST registration certificate PDF."""
    filepath = SAMPLE_DIR / "tax_certificate.pdf"
    doc = SimpleDocTemplate(str(filepath), pagesize=A4)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=16, spaceAfter=15, alignment=1,
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=styles["Normal"],
        fontSize=11, spaceAfter=8,
    )

    elements = []
    elements.append(Paragraph("GOODS AND SERVICES TAX", title_style))
    elements.append(Paragraph("REGISTRATION CERTIFICATE", title_style))
    elements.append(Spacer(1, 20))

    data = [
        ["GSTIN", "29ABCDE1234F1Z5"],
        ["Legal Name", "Acme Corp Pvt Ltd"],
        ["Trade Name", "Acme Corp"],
        ["Constitution", "Private Limited Company"],
        ["State", "Karnataka (29)"],
        ["Date of Registration", "1st April 2020"],
        ["Type of Registration", "Regular"],
        ["PAN", "ABCDE1234F"],
    ]
    table = Table(data, colWidths=[6 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.9, 0.95, 0.9)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "This certificate is issued under the provisions of the "
        "Central Goods and Services Tax Act, 2017.",
        body_style,
    ))

    doc.build(elements)
    print(f"  Created: {filepath}")
    return str(filepath)


def create_bank_statement():
    """Create a sample bank statement PDF."""
    filepath = SAMPLE_DIR / "bank_statement.pdf"
    doc = SimpleDocTemplate(str(filepath), pagesize=A4)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=16, spaceAfter=15, alignment=1,
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=styles["Normal"],
        fontSize=11, spaceAfter=8,
    )

    elements = []
    elements.append(Paragraph("NATIONAL BANK OF INDIA", title_style))
    elements.append(Paragraph("ACCOUNT STATEMENT", title_style))
    elements.append(Spacer(1, 15))

    account_data = [
        ["Account Holder", "Acme Corp Pvt Ltd"],
        ["Account Number", "1234567890123456"],
        ["Account Type", "Current Account"],
        ["Branch", "Mumbai Main Branch"],
        ["IFSC Code", "NBIN0001234"],
        ["Statement Period", "01-Oct-2024 to 31-Oct-2024"],
    ]
    table = Table(account_data, colWidths=[5 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.85, 0.9, 1.0)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Transaction table
    elements.append(Paragraph("Transaction History:", body_style))
    elements.append(Spacer(1, 5))

    txn_data = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["01-Oct", "Opening Balance", "", "", "5,00,000"],
        ["05-Oct", "Client Payment", "", "2,50,000", "7,50,000"],
        ["10-Oct", "Vendor Payment", "1,00,000", "", "6,50,000"],
        ["15-Oct", "Service Revenue", "", "3,00,000", "9,50,000"],
        ["31-Oct", "Closing Balance", "", "", "9,50,000"],
    ]
    txn_table = Table(txn_data, colWidths=[2.5 * cm, 5 * cm, 2.5 * cm, 2.5 * cm, 3 * cm])
    txn_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.9, 1.0)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))
    elements.append(txn_table)

    doc.build(elements)
    print(f"  Created: {filepath}")
    return str(filepath)


def create_mismatched_bank_statement():
    """Create a bank statement with a DIFFERENT company name (for testing)."""
    filepath = SAMPLE_DIR / "bank_statement_mismatch.pdf"
    doc = SimpleDocTemplate(str(filepath), pagesize=A4)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=16, spaceAfter=15, alignment=1,
    )

    elements = []
    elements.append(Paragraph("NATIONAL BANK OF INDIA", title_style))
    elements.append(Paragraph("ACCOUNT STATEMENT", title_style))
    elements.append(Spacer(1, 15))

    account_data = [
        ["Account Holder", "Totally Different Industries LLC"],
        ["Account Number", "9999888877776666"],
        ["Account Type", "Current Account"],
        ["Branch", "Delhi Branch"],
    ]
    table = Table(account_data, colWidths=[5 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    doc.build(elements)
    print(f"  Created: {filepath}")
    return str(filepath)


if __name__ == "__main__":
    print("\n📄 Generating sample test documents...")
    print(f"   Output directory: {SAMPLE_DIR}\n")

    create_registration_certificate()
    create_tax_certificate()
    create_bank_statement()
    create_mismatched_bank_statement()

    print(f"\n✅ All sample documents created in: {SAMPLE_DIR}")

