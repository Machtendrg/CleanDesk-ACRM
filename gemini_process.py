import os
import pandas as pd
from datetime import datetime
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkcalendar import DateEntry  # Import DateEntry for calendar widget
from fpdf import FPDF
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_to_console(console_output, message):
    """
    Logs a message to the console output widget in the GUI.

    Args:
        console_output: The tkinter ScrolledText widget.
        message: The message to log.
    """
    if isinstance(console_output, ScrolledText):  # Ensure it's a valid widget
        console_output.insert(tk.END, message + "\n")
        console_output.see(tk.END)
        console_output.update_idletasks()  # Ensure GUI updates immediately
    else:
        logging.error("Invalid console_output passed to log_to_console.")


def consolidate_cdnotes(root_directory, output_csv):
    consolidated_data = pd.DataFrame(columns=["Employee Name", "Record Date", "Note", "Location"])

    logging.info(f"Starting to process the root directory: {root_directory}")

    for subfolder in os.listdir(root_directory):
        subfolder_path = os.path.join(root_directory, subfolder)

        if not os.path.isdir(subfolder_path):
            logging.info(f"Skipping non-directory item: {subfolder_path}")
            continue

        employee_name = subfolder
        cdnotes_path = os.path.join(subfolder_path, "cdnotes.csv")
        wfboxfile_path = os.path.join(subfolder_path, "wfboxfile.txt")

        if not os.path.isfile(cdnotes_path):
            logging.warning(f"cdnotes.csv not found in {subfolder_path}, skipping...")
            continue

        location = "Unknown Location"
        if os.path.isfile(wfboxfile_path):
            try:
                with open(wfboxfile_path, "r") as wfboxfile:
                    location = wfboxfile.read().strip()
            except Exception as e:
                logging.error(f"Error reading wfboxfile.txt in {subfolder_path}: {e}")

        try:
            logging.info(f"Processing file: {cdnotes_path}")
            cdnotes_data = pd.read_csv(
                cdnotes_path,
                header=None,
                names=["Record Date", "Note"],
                on_bad_lines="skip",
            )
            cdnotes_data["Record Date"] = cdnotes_data["Record Date"].astype(str)
            cdnotes_data["Employee Name"] = employee_name
            cdnotes_data["Location"] = location

            consolidated_data = pd.concat([consolidated_data, cdnotes_data], ignore_index=True)
            logging.info(f"Successfully processed {cdnotes_path}, added {len(cdnotes_data)} records.")
        except Exception as e:
            logging.error(f"Error reading {cdnotes_path}: {e}")

    if consolidated_data.empty:
        logging.info("No data found to consolidate. No file will be generated.")
        return

    try:
        consolidated_data.to_csv(output_csv, index=False)
        logging.info(f"Consolidated data saved to {output_csv}")
    except Exception as e:
        logging.error(f"Error saving the consolidated file: {e}")


def query_gemini(endpoint: str, api_key: str, model: str, prompt: str):
    """
    Query the Gemini API with a text prompt and return the full response.

    Args:
        endpoint (str): The Gemini API endpoint.
        api_key (str): Your Gemini API key.
        model (str): The name of the Gemini model to use.
        prompt (str): The text prompt to send.

    Returns:
        str: The AI response from Gemini.
    """
    url = f"{endpoint}/v1beta/models/{model}:generateContent"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("candidates", [{}])[0].get("content", "").strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error querying Gemini: {e}")
        return None



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
        formatted_date = datetime.strptime(record_date, "%Y-%m-%d").strftime("%m-%d-%Y")
    except (ValueError, TypeError):
        logging.warning(f"Invalid or missing date for {employee_name}, using 'Unknown_Date'. Original value: {record_date}")
        formatted_date = "Unknown_Date"

    # Format the filename
    file_name = f"{formatted_date}-{employee_name.replace(' ', '_')}-CD.PDF"
    pdf_path = os.path.join(output_dir, file_name)

    # Save the PDF
    pdf.output(pdf_path)
    logging.info(f"PDF generated: {pdf_path}")

import subprocess


def save_csv_report(data, start_date, end_date, console_output, open_file=False):
    """
    Save the `output_with_ai.csv` report with a custom name and optionally open it.

    Args:
        data (DataFrame): The DataFrame to save.
        start_date (str): Start date in MM-DD-YYYY format.
        end_date (str): End date in MM-DD-YYYY format.
        console_output (ScrolledText): Console output widget for logging.
        open_file (bool): Whether to open the saved file automatically.
    """
    # Define the filename with the custom format
    filename = f"Clean_Desk_Report-{start_date.replace('/', '-')}-{end_date.replace('/', '-')}.csv"

    try:
        # Load the `output_with_ai.csv` file instead of `data`
        output_data = pd.read_csv("output_with_ai.csv")

        # Save the `output_with_ai.csv` content with the new name
        output_data.to_csv(filename, index=False)
        log_to_console(console_output, f"Results saved to {filename}")

        if open_file:
            # Open the saved file in the default viewer
            subprocess.run(["start", filename], shell=True, check=True)
            log_to_console(console_output, f"Opening file: {filename}")
    except Exception as e:
        log_to_console(console_output, f"Error saving or opening the file: {e}")


def process_csv_for_pass_fail_and_generate_pdfs(
    csv_path: str, endpoint: str, model: str, analysis_column: str,
    output_path: str, pdf_output_dir: str, console_output, generate_pdfs, api_key: str
):

    data = pd.read_csv(csv_path)

    logging.info(f"Available columns in the CSV: {list(data.columns)}")
    log_to_console(console_output, f"Available columns in the CSV: {list(data.columns)}")

    if analysis_column not in data.columns:
        raise KeyError(f"The specified column '{analysis_column}' does not exist in the CSV.")

    if "AI_P_F" not in data.columns:
        data["AI_P_F"] = ""
    if "AI_Response" not in data.columns:
        data["AI_Response"] = ""

    log_to_console(console_output, f"Processing {len(data)} records...")

    for index, row in data.iterrows():
        record = row[analysis_column]
        prompt = (
            f"This is a strict Clean Desk report. Anything found on the desk is considered a fail, except when "
            f"the desk is explicitly described as 'Desk clean - meets compliance', which should be marked as a pass. "
            f"Determine if the following record is a 'Pass' or 'Fail': {record}"
        )
        logging.info(f"Querying Gemini for row {index + 1}: {prompt}")
        log_to_console(console_output, f"Querying Gemini for record {index + 1} out of {len(data)}...")

        ai_response = query_gemini(endpoint, api_key, model, prompt)
        if ai_response:
            if "pass" in ai_response.lower():
                pass_fail = "PASSED"
                compliant = "YES"
            elif "fail" in ai_response.lower():
                pass_fail = "FAILED"
                compliant = "NO"
            else:
                pass_fail = "UNKNOWN"
                compliant = "UNKNOWN"

            data.at[index, "AI_Response"] = ai_response.strip()
            data.at[index, "AI_P_F"] = pass_fail
            data.at[index, "Compliant"] = compliant

            if pass_fail == "FAILED" and generate_pdfs:
                employee_name = row.get("Employee Name", "Unknown")
                record_date = row.get("Record Date", "Unknown")
                notes = row.get("Note", "No Notes")
                generate_pdf(employee_name, record_date, notes, ai_response.strip(), pdf_output_dir)

            log_to_console(console_output, f"Response for record {index + 1}: {ai_response} (Determined: {pass_fail})")
        else:
            data.at[index, "AI_Response"] = "Error or No Response"
            data.at[index, "AI_P_F"] = "UNKNOWN"
            data.at[index, "Compliant"] = "UNKNOWN"
            log_to_console(console_output, f"No valid response for record {index + 1}")

    data.rename(columns={"Record Date": "Last Clean Desk Date"}, inplace=True)

    required_columns = [
        "Employee Name", "Last Clean Desk Date", "Location", "Compliant", "Note", "AI_Response"
    ]
    for column in required_columns:
        if column not in data.columns:
            data[column] = "Unknown"

    data = data[required_columns]

    try:
        data.to_csv(output_path, index=False)
        logging.info(f"Results saved to {output_path}")
        log_to_console(console_output, f"Results saved to {output_path}")
    except Exception as e:
        log_to_console(console_output, f"Error saving the file: {e}")

    # Rename "Record Date" to "Last Clean Desk Date"
    if "Record Date" in data.columns:
        data.rename(columns={"Record Date": "Last Clean Desk Date"}, inplace=True)

    # Ensure the columns are in the correct order
    required_columns = [
        "Employee Name",
        "Last Clean Desk Date",
        "Location",
        "Compliant",
        "Note",
        "AI_Response",
    ]
    for column in required_columns:
        if column not in data.columns:
            data[column] = "Unknown" if column in ["Location", "Compliant"] else ""

    # Reorder columns
    data = data[required_columns]

    try:
        data.to_csv(output_path, index=False)
        logging.info(f"Results saved to {output_path}")
        log_to_console(console_output, f"Results saved to {output_path}")
    except Exception as e:
        log_to_console(console_output, f"Error saving the processed file: {e}")


def run_ai_on_csv(input_csv, start_date, end_date, console_output, generate_pdfs, gemini_endpoint, gemini_model, api_key):
    """
    Filter the input CSV by date range and run AI analysis.

    Args:
        input_csv (str): Path to the input CSV file.
        start_date (str): Start date in MM-DD-YYYY format.
        end_date (str): End date in MM-DD-YYYY format.
        console_output (ScrolledText): Console output widget for logging.
        generate_pdfs (bool): Whether to generate PDFs for failed records.
        gemini_endpoint (str): Gemini API endpoint.
        gemini_model (str): Gemini model to use.
        api_key (str): Gemini API key.
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
        process_csv_for_pass_fail_and_generate_pdfs(
            filtered_csv_path, gemini_endpoint, gemini_model, "Note", "output_with_ai.csv",
            "pdf_reports", console_output, generate_pdfs, api_key
        )

    except Exception as e:
        log_to_console(console_output, f"Error: {e}")
        logging.error(f"Error: {e}")


def run_gui():
    """Run the GUI for the tool."""
    root = tk.Tk()
    root.title("ACRM Compliance Clean Desk Report")
    root.geometry("800x500")

    # GUI Elements
    frame = tk.Frame(root)
    frame.pack(pady=10)

    # Add a block of text above the other GUI elements
    text_block = tk.Label(
        root,
        text=(
            "When processing data, this program may look unresponsive.\n"
            "Please allow the program to complete the task when the run\n"
            "button is pressed.\n"
            "Click 'Run Report' to start processing your data."
        ),
        justify="center",  # Align the text to the center
        wraplength=600,  # Set the maximum width for text wrapping
        font=("Arial", 12, "bold")  # Set font style and size
    )
    text_block.pack(pady=10)  # Add some padding around the text block

    tk.Label(frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5)
    start_date_entry = DateEntry(frame, date_pattern="mm-dd-yyyy")
    start_date_entry.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(frame, text="End Date:").grid(row=1, column=0, padx=5, pady=5)
    end_date_entry = DateEntry(frame, date_pattern="mm-dd-yyyy")
    end_date_entry.grid(row=1, column=1, padx=5, pady=5)

    # Add a toggle for generating PDFs
    generate_pdfs_var = tk.BooleanVar(value=True)
    tk.Checkbutton(frame, text="Generate PDFs", variable=generate_pdfs_var).grid(row=2, column=0, columnspan=2, pady=5)

    console_output = ScrolledText(root, height=10, width=95)
    console_output.pack(pady=10)

    # Buttons for saving the report
    save_button = tk.Button(
        frame,
        text="Save Report",
        command=lambda: save_csv_report(None, start_date_entry.get(), end_date_entry.get(), console_output)
    )
    save_button.grid(row=4, column=0, padx=5, pady=5)

    save_and_open_button = tk.Button(
        frame,
        text="Save and Open Report",
        command=lambda: save_csv_report(None, start_date_entry.get(), end_date_entry.get(), console_output,
                                        open_file=True)
    )
    save_and_open_button.grid(row=4, column=1, padx=5, pady=5)

    # Gemini Configuration
    gemini_endpoint = "https://generativelanguage.googleapis.com/"
    api_key = "AIzaSyB6E0q8qe_pwctfbkqjfVo1J4o-dEvbn2k"  # Replace with your actual Gemini API key
    gemini_model = "gemini-1.5-flash"  # Replace with the Gemini model you want to use

    # Automatically consolidate data on startup
    root_directory = r"M:\\IT\\IT - Ramez -\\00 - Sam\\Compliance Tool\\Database\\Templates"
    output_csv = "consolidated_cdnotes.csv"
    log_to_console(console_output, f"Using hardcoded directory: {root_directory}")
    consolidate_cdnotes(root_directory, output_csv)

    def run_ai():
        input_csv = "consolidated_cdnotes.csv"
        start_date = start_date_entry.get()
        end_date = end_date_entry.get()
        generate_pdfs = generate_pdfs_var.get()

        # Ensure console_output is the correct ScrolledText widget
        if isinstance(console_output, ScrolledText):
            run_ai_on_csv(
                input_csv,
                start_date,
                end_date,
                console_output,
                generate_pdfs,
                gemini_endpoint,
                gemini_model,
                api_key
            )
        else:
            logging.error("console_output is not a ScrolledText widget.")

    tk.Button(frame, text="Run Report", command=run_ai).grid(row=3, column=0, columnspan=2, pady=10)

    root.mainloop()

    def run_ai():
        input_csv = "consolidated_cdnotes.csv"
        start_date = start_date_entry.get()
        end_date = end_date_entry.get()
        generate_pdfs = generate_pdfs_var.get()

        # Ensure console_output is the correct ScrolledText widget
        if isinstance(console_output, ScrolledText):
            run_ai_on_csv(input_csv, start_date, end_date, console_output, generate_pdfs, endpoint, model,
                          api_key)
        else:
            logging.error("console_output is not a ScrolledText widget.")

    tk.Button(frame, text="Run Report", command=run_ai).grid(row=3, column=0, columnspan=2, pady=10)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
