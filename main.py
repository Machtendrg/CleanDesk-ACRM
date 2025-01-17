import os
import pandas as pd
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
from tkcalendar import DateEntry  # Import DateEntry for calendar widget
from fpdf import FPDF
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_to_console(console_output, message):
    console_output.insert(tk.END, message + "\n")
    console_output.see(tk.END)
    console_output.update_idletasks()  # Ensure GUI updates immediately

def consolidate_cdnotes(root_directory, output_csv):
    """
    Traverse through subfolders, read cdnotes.csv files, and consolidate the data.

    Args:
        root_directory (str): The root directory containing subfolders.
        output_csv (str): The path to save the consolidated CSV.
    """
    # DataFrame to hold consolidated data
    consolidated_data = pd.DataFrame(columns=["Employee Name", "Record Date", "Note"])

    logging.info(f"Starting to process the root directory: {root_directory}")

    # Traverse through subdirectories
    for subfolder in os.listdir(root_directory):
        subfolder_path = os.path.join(root_directory, subfolder)

        # Skip if it's not a directory
        if not os.path.isdir(subfolder_path):
            logging.info(f"Skipping non-directory item: {subfolder_path}")
            continue

        # Extract employee name from subfolder name
        employee_name = subfolder

        # Path to cdnotes.csv
        cdnotes_path = os.path.join(subfolder_path, "cdnotes.csv")

        # Skip if cdnotes.csv doesn't exist
        if not os.path.isfile(cdnotes_path):
            logging.warning(f"cdnotes.csv not found in {subfolder_path}, skipping...")
            continue

        # Read cdnotes.csv
        try:
            logging.info(f"Processing file: {cdnotes_path}")
            cdnotes_data = pd.read_csv(
                cdnotes_path,
                header=None,
                names=["Record Date", "Note"],
                on_bad_lines="skip",  # Skip problematic rows
            )
        except Exception as e:
            logging.error(f"Error reading {cdnotes_path}: {e}")
            continue

        # Convert "Record Date" column to string (no date filtering)
        cdnotes_data["Record Date"] = cdnotes_data["Record Date"].astype(str)

        # Add employee name column
        cdnotes_data.insert(0, "Employee Name", employee_name)

        # Append to consolidated data
        consolidated_data = pd.concat([consolidated_data, cdnotes_data], ignore_index=True)
        logging.info(f"Successfully processed {cdnotes_path}, added {len(cdnotes_data)} records.")

    # Check if there is data to save
    if consolidated_data.empty:
        logging.info("No data found to consolidate. No file will be generated.")
        return

    # Save consolidated data to CSV
    try:
        consolidated_data.to_csv(output_csv, index=False)
        logging.info(f"Consolidated data saved to {output_csv}")
    except Exception as e:
        logging.error(f"Error saving the consolidated file: {e}")

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
        logging.error(f"An error occurred: {e}")
        return None

def generate_pdf(employee_name, record_date, notes, ai_response, output_dir):
    """
    Generate a PDF for a failed record with a professional blurb and signature section.
    Ensures the output directory exists before saving the PDF.
    """
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

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

    from dateutil.parser import parse  # Add this to your imports

    # Handle record_date formatting
    try:
        formatted_date = parse(record_date).strftime("%m-%d-%Y")
    except Exception:
        formatted_date = "Unknown_Date"
        logging.warning(
            f"Invalid or missing date for {employee_name}, using 'Unknown_Date'. Original value: {record_date}")

    # Format the filename
    file_name = f"{formatted_date}-{employee_name.replace(' ', '_')}-CD.PDF"
    pdf_path = os.path.join(output_dir, file_name)

    # Save the PDF
    pdf.output(pdf_path)
    logging.info(f"PDF generated: {pdf_path}")


def process_csv_for_pass_fail_and_generate_pdfs(csv_path: str, endpoint: str, model: str, analysis_column: str, output_path: str, pdf_output_dir: str, console_output):
    """
    Analyze CSV data to determine pass or fail status, store AI response, and generate PDFs for failed records.
    """
    # Load the CSV file
    data = pd.read_csv(csv_path)

    # Debugging: Print column names
    logging.info(f"Available columns in the CSV: {list(data.columns)}")
    log_to_console(console_output, f"Available columns in the CSV: {list(data.columns)}")

    # Check if the column exists
    if analysis_column not in data.columns:
        raise KeyError(f"The specified column '{analysis_column}' does not exist in the CSV.")

    # Ensure the AI_P_F and AI_Response columns exist
    if "AI_P_F" not in data.columns:
        data["AI_P_F"] = ""
    if "AI_Response" not in data.columns:
        data["AI_Response"] = ""

    log_to_console(console_output, f"Processing {len(data)} records...")

    # Process each record in the specified analysis column
    for index, row in data.iterrows():
        record = row[analysis_column]
        prompt = (
            f"This is a strict Clean Desk report. Anything found on the desk is considered a fail, except when "
            f"the desk is explicitly described as 'Desk clean - meets compliance', which should be marked as a pass. "
            f"Determine if the following record is a 'Pass' or 'Fail': {record}"
        )
        logging.info(f"Querying LLM for row {index + 1}: {prompt}")
        log_to_console(console_output, f"Querying LLM for row {index + 1}...")

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
                employee_name = row.get("Employee Name", "Unknown")
                record_date = row.get("Record Date", "Unknown")
                notes = row.get("Note", "No Notes")
                generate_pdf(employee_name, record_date, notes, ai_response.strip(), pdf_output_dir)

            logging.info(f"Response for row {index + 1}: {ai_response} (Determined: {pass_fail})")
            log_to_console(console_output, f"Response for row {index + 1}: {pass_fail}")
        else:
            # Handle cases where no valid response is received
            data.at[index, "AI_Response"] = "Error or No Response"
            data.at[index, "AI_P_F"] = "UNKNOWN"
            logging.warning(f"No valid response for row {index + 1}")
            log_to_console(console_output, f"No valid response for row {index + 1}")

    # Reorder columns to place AI_P_F before AI_Response
    column_order = ["AI_P_F", "AI_Response"] + [col for col in data.columns if col not in ["AI_P_F", "AI_Response"]]
    data = data[column_order]

    # Save the updated CSV
    data.to_csv(output_path, index=False)
    logging.info(f"Results saved to {output_path}")
    log_to_console(console_output, f"Results saved to {output_path}")

def run_ai_on_csv(input_csv, start_date, end_date, console_output):
    """
    Filter the input CSV by date range and run AI analysis.

    Args:
        input_csv (str): Path to the input CSV file.
        start_date (str): Start date in MM-DD-YYYY format.
        end_date (str): End date in MM-DD-YYYY format.
        console_output (ScrolledText): Console output widget for logging.
    """
    try:
        data = pd.read_csv(input_csv)
        log_to_console(console_output, f"Loaded data from {input_csv}")
        logging.info(f"Loaded data from {input_csv}")

        # Convert "Record Date" to datetime for filtering
        data["Record Date"] = pd.to_datetime(data["Record Date"], format="%m-%d-%Y", errors="coerce")

        # Filter by date range
        start_date = datetime.strptime(start_date, "%m-%d-%Y")
        end_date = datetime.strptime(end_date, "%m-%d-%Y")
        filtered_data = data[(data["Record Date"] >= start_date) & (data["Record Date"] <= end_date)]

        if filtered_data.empty:
            log_to_console(console_output, "No records found in the specified date range.")
            logging.info("No records found in the specified date range.")
            return

        log_to_console(console_output, f"Filtered data to {len(filtered_data)} records within date range.")
        logging.info(f"Filtered data to {len(filtered_data)} records within date range.")

        # Save filtered data to a temporary file for AI processing
        filtered_csv_path = "ai_processed_data.csv"
        filtered_data.to_csv(filtered_csv_path, index=False)

        # Run AI processing on the filtered data
        pdf_output_dir = "pdf_reports"
        endpoint = "http://172.16.2.222:11434"
        model = "llama3.2-vision"
        analysis_column = "Note"

        process_csv_for_pass_fail_and_generate_pdfs(
            filtered_csv_path, endpoint, model, analysis_column, "output_with_ai.csv", pdf_output_dir, console_output
        )

    except Exception as e:
        log_to_console(console_output, f"Error: {e}")
        logging.error(f"Error: {e}")

def run_gui():
    """Run the GUI for the tool."""
    root = tk.Tk()
    root.title("AI Compliance Tool")
    root.geometry("800x350")

    # GUI Elements
    frame = tk.Frame(root)
    frame.pack(pady=10)

    tk.Label(frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5)
    start_date_entry = DateEntry(frame, date_pattern="mm-dd-yyyy")
    start_date_entry.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(frame, text="End Date:").grid(row=1, column=0, padx=5, pady=5)
    end_date_entry = DateEntry(frame, date_pattern="mm-dd-yyyy")
    end_date_entry.grid(row=1, column=1, padx=5, pady=5)

    console_output = ScrolledText(root, height=10, width=95)
    console_output.pack(pady=10)



    def run_ai():
        input_csv = "consolidated_cdnotes.csv"
        start_date = start_date_entry.get()
        end_date = end_date_entry.get()
        run_ai_on_csv(input_csv, start_date, end_date, console_output)

    def consolidate_and_log():
        root_directory = r"M:\\IT\\IT - Ramez -\\00 - Sam\\Compliance Tool\\Database\\Templates"
        output_csv = "consolidated_cdnotes.csv"
        log_to_console(console_output, f"Using hardcoded directory: {root_directory}\n")
        logging.info(f"Using hardcoded directory: {root_directory}")
        consolidate_cdnotes(root_directory, output_csv)

    tk.Button(frame, text="Consolidate Data", command=consolidate_and_log).grid(row=2, column=0, padx=5, pady=5)
    tk.Button(frame, text="Run AI", command=run_ai).grid(row=2, column=1, padx=5, pady=5)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
