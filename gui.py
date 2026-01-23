import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys

# Import Verified Engines
import hsbc_tagger
import banamex_tagger
import bbva_tagger
import santander
import monex_tagger
import db_tagger
import ocr_utils
import detector

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Bank Statement Tagger Pro")
        self.geometry("700x500")

        # --- Grid Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- Header ---
        self.label = ctk.CTkLabel(self, text="Bank Statement Tagger", font=ctk.CTkFont(size=20, weight="bold"))
        self.label.grid(row=0, column=0, padx=20, pady=20)

        # --- File Selection ---
        self.selection_frame = ctk.CTkFrame(self)
        self.selection_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.selection_frame.grid_columnconfigure(0, weight=1)

        self.btn_select = ctk.CTkButton(self.selection_frame, text="Select PDF Files", command=self.select_files)
        self.btn_select.grid(row=0, column=0, padx=10, pady=10)

        self.file_label = ctk.CTkLabel(self.selection_frame, text="No files selected")
        self.file_label.grid(row=0, column=1, padx=10, pady=10)

        # --- Configuration ---
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        ctk.CTkLabel(self.config_frame, text="Tag Prefix Pattern:").pack(side="left", padx=10)
        self.entry_prefix = ctk.CTkEntry(self.config_frame, width=200, placeholder_text="[BANK]_[CURR]_TAG")
        self.entry_prefix.pack(side="left", padx=10)
        self.entry_prefix.insert(0, "[BANK]_[CURR]_TAG")
        
        ctk.CTkLabel(self.config_frame, text="(Use [BANK], [CURR] as placeholders)").pack(side="left", padx=10)

        # --- Console Output ---
        self.textbox = ctk.CTkTextbox(self, width=600, height=200)
        self.textbox.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.textbox.insert("0.0", "Welcome! Select bank statements to begin.\n")

        # --- Action Buttons ---
        self.btn_process = ctk.CTkButton(self, text="Start Tagging", command=self.start_processing_thread, state="disabled")
        self.btn_process.grid(row=4, column=0, padx=20, pady=20)

        self.selected_files = []

    def log(self, message):
        self.textbox.insert("end", f"{message}\n")
        self.textbox.see("end")

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        if files:
            self.selected_files = list(files)
            self.file_label.configure(text=f"{len(files)} files selected")
            self.btn_process.configure(state="normal")
            self.log(f"Selected {len(files)} files.")

    def process_all(self):
        self.btn_process.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        
        pattern = self.entry_prefix.get().strip()
        if not pattern: pattern = "[BANK]_[CURR]_TAG"
        
        for f in self.selected_files:
            filename = os.path.basename(f)
            
            # Detect Bank and Currency
            bank, currency = detector.detect_bank_and_currency(f)
            
            # Generate Prefix
            prefix = pattern.replace("[BANK]", bank).replace("[CURR]", currency)
            
            self.log(f"\n🚀 Processing: {filename}")
            self.log(f"   ℹ️  Bank: {bank}, Currency: {currency} -> Prefix: {prefix}")
            
            try:
                if bank == "HSBC":
                    coords, actual_pdf = hsbc_tagger.get_transaction_coordinates(f)
                    if coords:
                        hsbc_tagger.create_tagged_pdf(actual_pdf, coords, prefix)
                        self.log(f"   ✅ Done: Found {len(coords)} movements.")
                    else:
                        self.log("   ❌ No movements found.")

                elif bank == "DB":
                    coords, actual_pdf = db_tagger.get_transaction_coordinates(f)
                    if coords:
                        db_tagger.create_tagged_pdf(actual_pdf, coords, prefix)
                        self.log(f"   ✅ Done: Found {len(coords)} movements.")
                    else:
                        self.log("   ❌ No movements found.")

                elif bank == "BANAMEX":
                    banamex_tagger.process_file(f, prefix)
                    self.log("   ✅ Done.")

                elif bank == "BBVA":
                    bbva_tagger.process_file(f, prefix)
                    self.log("   ✅ Done.")

                elif bank == "SANTANDER":
                    santander.process_file(f, prefix)
                    self.log("   ✅ Done.")

                elif bank == "MONEX":
                    monex_tagger.process_file(f, prefix)
                    self.log("   ✅ Done.")
                
                else:
                    self.log(f"   ⚠️ Could not identify supported bank for {filename}. (Detected: {bank})")

            except Exception as e:
                self.log(f"   ❌ Error: {e}")

        self.log("\n✨ ALL TASKS COMPLETED.")
        self.btn_process.configure(state="normal")
        self.btn_select.configure(state="normal")
        messagebox.showinfo("Success", "All selected files have been processed.")

    def start_processing_thread(self):
        thread = threading.Thread(target=self.process_all)
        thread.start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
