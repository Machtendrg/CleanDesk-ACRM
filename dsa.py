import os
import pandas as pd
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
from tkcalendar import DateEntry  # Import DateEntry for calendar widget


def consolidate_cdnotes(root_directory, output_csv):
    """
    Traverse through subfolders, read cdnotes.csv files, and consolidate the data.

    Args:
        root_directory (str): The root directory containing subfolders.
        output_csv (str): The path to save the consolidated CSV.
    """
    # DataFrame to hold consolidated data
    consolidated_data = pd.DataFrame(columns=["Employee Name", "Record Date", "Note"])

    print(f"Starting to process the root directory: {root_directory}")

    # Traverse through subdirectories
    for subfolder in os.listdir(root_directory):
        subfolder_path = os.path.join(root_directory, subfolder)

        # Skip if it's not a directory
        if not os.path.isdir(subfolder_path):
            print(f"Skipping non-directory item: {subfolder_path}")
            continue

        # Extract employee name from subfolder name
        employee_name = subfolder

        # Path to cdnotes.csv
        cdnotes_path = os.path.join(subfolder_path, "cdnotes.csv")

        # Skip if cdnotes.csv doesn't exist
        if not os.path.isfile(cdnotes_path):
            print(f"cdnotes.csv not found in {subfolder_path}, skipping...")
            continue

        # Read cdnotes.csv
        try:
            print(f"Processing file: {cdnotes_path}")
            cdnotes_data = pd.read_csv(
                cdnotes_path,
                header=None,
                names=["Record Date", "Note"],
                on_bad_lines="skip",  # Skip problematic rows
            )
        except Exception as e:
            print(f"Error reading {cdnotes_path}: {e}")
            continue

        # Convert "Record Date" column to string (no date filtering)
        cdnotes_data["Record Date"] = cdnotes_data["Record Date"].astype(str)

        # Add employee name column
        cdnotes_data.insert(0, "Employee Name", employee_name)

        # Append to consolidated data
        consolidated_data = pd.concat([consolidated_data, cdnotes_data], ignore_index=True)
        print(f"Successfully processed {cdnotes_path}, added {len(cdnotes_data)} records.")

    # Check if there is data to save
    if consolidated_data.empty:
        print("No data found to consolidate. No file will be generated.")
        return

    # Save consolidated data to CSV
    try:
        consolidated_data.to_csv(output_csv, index=False)
        print(f"Consolidated data saved to {output_csv}")
    except Exception as e:
        print(f"Error saving the consolidated file: {e}")


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
        console_output.insert(tk.END, f"Loaded data from {input_csv}\n")

        # Convert "Record Date" to datetime for filtering
        data["Record Date"] = pd.to_datetime(data["Record Date"], format="%m-%d-%Y", errors="coerce")

        # Filter by date range
        start_date = datetime.strptime(start_date, "%m-%d-%Y")
        end_date = datetime.strptime(end_date, "%m-%d-%Y")
        filtered_data = data[(data["Record Date"] >= start_date) & (data["Record Date"] <= end_date)]

        if filtered_data.empty:
            console_output.insert(tk.END, "No records found in the specified date range.\n")
            return

        console_output.insert(tk.END, f"Filtered data to {len(filtered_data)} records within date range.\n")

        # Simulate AI processing
        filtered_data["AI_Result"] = "Processed by AI"
        output_file = "ai_processed_data.csv"
        filtered_data.to_csv(output_file, index=False)
        console_output.insert(tk.END, f"AI processed data saved to {output_file}\n")

    except Exception as e:
        console_output.insert(tk.END, f"Error: {e}\n")


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
        console_output.insert(tk.END, f"Using hardcoded directory: {root_directory}\n")
        consolidate_cdnotes(root_directory, output_csv)

    tk.Button(frame, text="Consolidate Data", command=consolidate_and_log).grid(row=2, column=0, padx=5, pady=5)
    tk.Button(frame, text="Run AI", command=run_ai).grid(row=2, column=1, padx=5, pady=5)

    root.mainloop()


if __name__ == "__main__":
    run_gui()
