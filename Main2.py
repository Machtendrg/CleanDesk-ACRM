import pandas as pd
import requests
import json
from fpdf import FPDF
from datetime import datetime

def query_ollama(endpoint: str, model: str, prompt: str):
    """
    Query the OLLAMA API with a text prompt and return the full response.
    """
    url = f"{endpoint}/api/generate"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": prompt
    }

    try:
        with requests.post(url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()
            full_response = ""
            for line in response.iter_lines(decode_unicode=True):
                if line.strip():
                    try:
                        message = json.loads(line)
                        full_response += message.get("response", "")
                    except json.JSONDecodeError:
                        pass
            return full_response.strip()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

import os

def generate_pdf(employee_name, record_date, notes, ai_response, output_dir):
    """
    Generate a PDF for a failed record with a professional blurb and signature section.
    Ensures the output directory exists before saving the PDF.
    """
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Create the PDF file
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Add header
    pdf.set_font("Arial", style="B", size=14)
    pdf.cell(200, 10, txt="Employee Acknowledgment of Desk Policy Violation", ln=True, align='C')
    pdf.ln(10)

    # Add details about the violation
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Employee Name: {employee_name}", ln=True)
    pdf.cell(200, 10, txt=f"Record Date: {record_date}", ln=True)
    pdf.cell(200, 10, txt=f"Notes: {notes}", ln=True)
    pdf.multi_cell(0, 10, txt=f"AI Response: {ai_response}")
    pdf.ln(10)

    # Add professional acknowledgment blurb
    acknowledgment = (
        "I, the undersigned employee, acknowledge receipt of this notice regarding the "
        "violation of the clean desk policy. I understand the nature of the failure outlined "
        "above and agree to take immediate corrective actions to ensure compliance in the future."
    )
    pdf.multi_cell(0, 10, txt=acknowledgment)
    pdf.ln(10)

    # Add signature section
    pdf.cell(200, 10, txt="Signature: ___________________________", ln=True)
    pdf.cell(200, 10, txt="Date: ______________________________", ln=True)

    # Handle record_date formatting
    try:
        formatted_date = datetime.strptime(record_date, "%d/%m/%Y").strftime("%m-%d-%Y")
    except ValueError:
        # Use a default date if the record_date is invalid
        formatted_date = "Unknown_Date"

    # Format the filename
    file_name = f"{formatted_date}-{employee_name.replace(' ', '_')}-CD.PDF"
    pdf_path = os.path.join(output_dir, file_name)

    # Save the PDF
    pdf.output(pdf_path)
    print(f"PDF generated: {pdf_path}")

    # Save the PDF
    pdf.output(pdf_path)
    print(f"PDF generated: {pdf_path}")


def process_csv_for_pass_fail_and_generate_pdfs(csv_path: str, endpoint: str, model: str, analysis_column: str, output_path: str, pdf_output_dir: str):
    """
    Analyze CSV data to determine pass or fail status, store AI response, and generate PDFs for failed records.
    """
    # Load the CSV file
    data = pd.read_csv(csv_path)

    # Debugging: Print column names
    print(f"Available columns in the CSV: {list(data.columns)}")

    # Check if the column exists
    if analysis_column not in data.columns:
        raise KeyError(f"The specified column '{analysis_column}' does not exist in the CSV.")

    # Ensure the AI_P_F and AI_Response columns exist
    if "AI_P_F" not in data.columns:
        data["AI_P_F"] = ""
    if "AI_Response" not in data.columns:
        data["AI_Response"] = ""

    # Process each record in the specified analysis column
    for index, row in data.iterrows():
        record = row[analysis_column]
        prompt = f"This is a strict Clean Desk report, anything found on the desk is considered a fail, Determine if the following record is a 'Pass' or 'Fail': {record}"
        print(f"Querying LLM for row {index + 1}: {prompt}")

        # Query the AI for analysis
        ai_response = query_ollama(endpoint, model, prompt)
        if ai_response:
            # Assume the AI's response includes "Pass" or "Fail" and extract that
            if "pass" in ai_response.lower():
                pass_fail = "PASSED"
            elif "fail" in ai_response.lower():
                pass_fail = "FAILED"
            else:
                pass_fail = "UNKNOWN"

            # Populate the columns
            data.at[index, "AI_Response"] = ai_response.strip()
            data.at[index, "AI_P_F"] = pass_fail

            # If the record failed, generate a PDF
            if pass_fail == "FAILED":
                employee_name = row.get("Employee_Name", "Unknown")
                record_date = row.get("Record_Date", "Unknown")
                notes = row.get("Notes", "No Notes")
                generate_pdf(employee_name, record_date, notes, ai_response.strip(), pdf_output_dir)

            print(f"Response for row {index + 1}: {ai_response} (Determined: {pass_fail})")
        else:
            # Handle cases where no valid response is received
            data.at[index, "AI_Response"] = "Error or No Response"
            data.at[index, "AI_P_F"] = "UNKNOWN"
            print(f"No valid response for row {index + 1}")

    # Reorder columns to place AI_P_F before AI_Response
    column_order = ["AI_P_F", "AI_Response"] + [col for col in data.columns if col not in ["AI_P_F", "AI_Response"]]
    data = data[column_order]

    # Save the updated CSV
    data.to_csv(output_path, index=False)
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    # Configuration
    csv_file = "CD-AI-TEST.csv"  # Replace with your CSV file path
    output_file = "output_with_ai_pass_fail.csv"
    pdf_output_directory = "pdf_reports"  # Directory to save the PDFs
    api_endpoint = "http://localhost:11434"
    model_name = "llama3.2-vision"
    column_to_analyze = "notes"  # Specify the column for analysis (e.g., Column F)

    # Process the CSV, determine pass/fail status, and generate PDFs for failed records
    process_csv_for_pass_fail_and_generate_pdfs(csv_file, api_endpoint, model_name, column_to_analyze, output_file, pdf_output_directory)
