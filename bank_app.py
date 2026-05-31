#!/usr/bin/env python3
"""
Credit Dispute Tool - Bank Employee Version
Double-click to run. Simple form. No CSV editing needed.
Includes 6-month trial and commercial licensing.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import csv
import os
import json
import sys
from datetime import datetime, timedelta


def secure_delete(file_path: str) -> None:
    """Overwrite a file three times with random data before deleting it."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return

    size = os.path.getsize(abs_path)
    try:
        with open(abs_path, 'r+b') as handle:
            for _ in range(3):
                handle.seek(0)
                handle.write(os.urandom(size))
                handle.flush()
                os.fsync(handle.fileno())
    except OSError:
        pass

    try:
        os.remove(abs_path)
    except OSError:
        pass


def encrypt_metro2_file(filepath, key_file=None):
    """Optionally encrypt the Metro 2 output file with a bank-provided key."""
    # This would let banks store encrypted files
    # Encryption implementation can be added here when the bank provides key handling requirements.
    return filepath

# ============================================================
# TRIAL AND LICENSE MANAGEMENT
# ============================================================

TRIAL_DAYS = 180  # 6 months trial

def check_trial_status():
    """Check if trial period has expired. Returns (is_valid, days_remaining, message)"""

    trial_file = "trial_status.json"
    
    # If trial file doesn't exist, this is first run
    if not os.path.exists(trial_file):
        trial_start = datetime.now()
        with open(trial_file, 'w') as f:
            json.dump({'start_date': trial_start.isoformat()}, f)
        return True, TRIAL_DAYS, f"Trial started! {TRIAL_DAYS} days remaining."
    
    # Trial file exists - check if expired
    with open(trial_file, 'r') as f:
        data = json.load(f)
        start_date = datetime.fromisoformat(data['start_date'])
        days_used = (datetime.now() - start_date).days
        days_left = TRIAL_DAYS - days_used
        
        if days_left > 0:
            return True, days_left, f"Trial active: {days_left} days remaining."
        else:
            return False, 0, "Trial expired. Please purchase a license."

def check_license():
    """Check if a valid commercial license exists"""
    license_file = "license.key"
    if not os.path.exists(license_file):
        return False
    
    with open(license_file, 'r') as f:
        key = f.read().strip()
    
    # Simple validation - any key starting with "LIC-" is considered valid
    return key.startswith("LIC-") and len(key) > 10

def save_license(key):
    """Save a license key to file"""
    with open("license.key", 'w') as f:
        f.write(key)


# ============================================================
# MAIN APPLICATION CLASS
# ============================================================

class DisputeApp:
    def __init__(self, root, trial_days_left=None):
        self.root = root
        self.root.title("Credit Dispute Tool - Bank Use Only")
        self.root.update_idletasks()

        # Use half screen size, centered on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        default_width = screen_width // 2
        default_height = screen_height // 2
        x = (screen_width - default_width) // 2
        y = (screen_height - default_height) // 2
        self.root.geometry(f"{default_width}x{default_height}+{x}+{y}")
        self.root.minsize(600, 500)
        self.root.resizable(True, True)
        self.root.configure(bg='#f0f0f0')
        
        # Store trial days left for reminder
        self.trial_days_left = trial_days_left
        
        # Storage for multiple disputes
        self.disputes = []
        self.save_location = tk.StringVar(value=os.getcwd())
        
        self.create_widgets()
        
        # Show trial reminder if in trial mode
        if trial_days_left is not None and trial_days_left > 0:
            self.show_trial_reminder()
    
    def show_trial_reminder(self):
        """Show a reminder about trial days left"""
        reminder = tk.Toplevel(self.root)
        reminder.title("Trial Reminder")
        reminder.geometry("500x350")
        reminder.resizable(True, True)
        reminder.grab_set()
        
        # Center the window on screen
        reminder.update_idletasks()
        x = (reminder.winfo_screenwidth() // 2) - (500 // 2)
        y = (reminder.winfo_screenheight() // 2) - (350 // 2)
        reminder.geometry(f"+{x}+{y}")
        
        # Main frame with padding
        main_frame = tk.Frame(reminder, padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        label = tk.Label(main_frame, text="⚠️ TRIAL PERIOD ACTIVE ⚠️", font=('Arial', 16, 'bold'), fg='orange')
        label.pack(pady=(0, 15))
        
        # Message with proper word wrapping
        msg_text = f"You have {self.trial_days_left} days remaining in your free trial.\n\nAfter {TRIAL_DAYS} days, you will need to purchase a commercial license.\n\nContact: contact@clearwatercodes.com"
        
        msg = tk.Label(main_frame, text=msg_text, font=('Arial', 10), wraplength=420, justify='center')
        msg.pack(pady=15, fill='both', expand=True)
        
        # OK button
        ok_btn = tk.Button(main_frame, text="OK", command=reminder.destroy, width=15, height=1, bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'))
        ok_btn.pack(pady=10)
    
    def create_widgets(self):
        # Title
        title = tk.Label(self.root, text="Credit Dispute Entry", font=('Arial', 20, 'bold'), bg='#f0f0f0')
        title.pack(pady=10)
        
        # Main frame
        main_frame = ttk.LabelFrame(self.root, text="Customer Dispute Information", padding=10)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Customer Information Section
        ttk.Label(main_frame, text="CUSTOMER INFORMATION", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(10,5))
        
        row = 1
        ttk.Label(main_frame, text="Full Name:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.name = ttk.Entry(main_frame, width=40)
        self.name.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="SSN:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.ssn = ttk.Entry(main_frame, width=40)
        self.ssn.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="Date of Birth (YYYYMMDD):").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.dob = ttk.Entry(main_frame, width=40)
        self.dob.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="Address:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.address = ttk.Entry(main_frame, width=40)
        self.address.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="City:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.city = ttk.Entry(main_frame, width=40)
        self.city.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="State (2 letters):").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.state = ttk.Entry(main_frame, width=40)
        self.state.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="ZIP Code:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.zipcode = ttk.Entry(main_frame, width=40)
        self.zipcode.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        # Account Information Section
        row += 1
        ttk.Label(main_frame, text="ACCOUNT INFORMATION", font=('Arial', 12, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(20,5))
        
        row += 1
        ttk.Label(main_frame, text="Account Number:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.account = ttk.Entry(main_frame, width=40)
        self.account.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="Date Opened (YYYYMMDD):").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.date_opened = ttk.Entry(main_frame, width=40)
        self.date_opened.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="Credit Limit:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.credit_limit = ttk.Entry(main_frame, width=40)
        self.credit_limit.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="Current Balance:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.balance = ttk.Entry(main_frame, width=40)
        self.balance.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        # Dispute Information Section
        row += 1
        ttk.Label(main_frame, text="DISPUTE INFORMATION", font=('Arial', 12, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(20,5))
        
        row += 1
        ttk.Label(main_frame, text="Dispute Type:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.dispute_type = ttk.Combobox(main_frame, values=[
            "01 - Paid in full",
            "02 - Never late", 
            "03 - Not my account",
            "04 - Balance incorrect"
        ], width=37)
        self.dispute_type.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        row += 1
        ttk.Label(main_frame, text="Effective Date (YYYYMMDD):").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.effective_date = ttk.Entry(main_frame, width=40)
        self.effective_date.insert(0, datetime.now().strftime('%Y%m%d'))
        self.effective_date.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        
        # Save Location Section
        row += 1
        ttk.Label(main_frame, text="SAVE LOCATION", font=('Arial', 12, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(20,5))
        
        row += 1
        ttk.Label(main_frame, text="Save to:").grid(row=row, column=0, sticky='e', padx=5, pady=5)
        self.location_entry = ttk.Entry(main_frame, textvariable=self.save_location, width=35)
        self.location_entry.grid(row=row, column=1, sticky='w', padx=5, pady=5)
        ttk.Button(main_frame, text="Browse...", command=self.choose_location).grid(row=row, column=2, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row+1, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Add Another Dispute", command=self.add_dispute).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Generate Metro 2 File", command=self.generate_file).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Clear Form", command=self.clear_form).pack(side='left', padx=10)
        
        # Dispute list display
        self.list_frame = ttk.LabelFrame(self.root, text="Pending Disputes", padding=10)
        self.list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        self.dispute_listbox = tk.Listbox(self.list_frame, height=6)
        self.dispute_listbox.pack(fill='both', expand=True)
    
    def choose_location(self):
        """Open folder browser dialog"""
        folder = filedialog.askdirectory(title="Select Save Location")
        if folder:
            self.save_location.set(folder)
    
    def add_dispute(self):
        # Collect data from form
        dispute = {
            'customer_name': self.name.get(),
            'ssn': self.ssn.get(),
            'date_of_birth': self.dob.get(),
            'address': self.address.get(),
            'city': self.city.get(),
            'state': self.state.get(),
            'zip': self.zipcode.get(),
            'account_number': self.account.get(),
            'date_opened': self.date_opened.get(),
            'credit_limit': int(self.credit_limit.get()) if self.credit_limit.get() else 0,
            'current_balance': int(self.balance.get()) if self.balance.get() else 0,
            'dispute_type': self.dispute_type.get()[:2] if self.dispute_type.get() else '',
            'effective_date': self.effective_date.get(),
            'metro2_id': '3',
            'portfolio_type': '10',
            'account_type': '4',
            'amount_past_due': 0,
            'scheduled_payment': 0,
            'payment_rating': '0',
            'payment_history_24': '0' * 24,
            'compliance_code': 'XD',
        }
        
        if not dispute['customer_name']:
            messagebox.showerror("Error", "Customer Name is required")
            return
        
        self.disputes.append(dispute)
        self.dispute_listbox.insert(tk.END, f"{dispute['customer_name']} - {dispute['account_number']} - {dispute['dispute_type']}")
        self.clear_form()
        messagebox.showinfo("Success", f"Dispute for {dispute['customer_name']} added")
    
    def generate_file(self):
        if not self.disputes:
            messagebox.showerror("Error", "No disputes to generate")
            return
        
        # Get save location
        save_folder = self.save_location.get()
        if not os.path.exists(save_folder):
            messagebox.showerror("Error", f"Save location does not exist: {save_folder}")
            return
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = os.path.join(save_folder, f"disputes_{timestamp}.csv")
        output_file = os.path.join(save_folder, f"metro2_{timestamp}.dat")
        
        # Save to CSV
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.disputes[0].keys())
            writer.writeheader()
            writer.writerows(self.disputes)
        
        # Run the CLI tool
        cmd = ["python3", "cli.py", "generate", "--input", csv_file, "--output", output_file, "--bank", "Bank Customer"]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            messagebox.showinfo("Success", f"Metro 2 file created:\n{output_file}\n\nFile is ready to upload to credit bureau.")
            # Clear disputes after successful generation
            self.disputes.clear()
            self.dispute_listbox.delete(0, tk.END)
        else:
            messagebox.showerror("Error", f"Failed: {result.stderr}")
        
        # Cleanup temp CSV with secure overwrite
        if os.path.exists(csv_file):
            secure_delete(csv_file)
    
    def clear_form(self):
        self.name.delete(0, tk.END)
        self.ssn.delete(0, tk.END)
        self.dob.delete(0, tk.END)
        self.address.delete(0, tk.END)
        self.city.delete(0, tk.END)
        self.state.delete(0, tk.END)
        self.zipcode.delete(0, tk.END)
        self.account.delete(0, tk.END)
        self.date_opened.delete(0, tk.END)
        self.credit_limit.delete(0, tk.END)
        self.balance.delete(0, tk.END)
        self.dispute_type.set('')
        self.effective_date.delete(0, tk.END)
        self.effective_date.insert(0, datetime.now().strftime('%Y%m%d'))


# ============================================================
# LICENSE ACTIVATION SCREEN
# ============================================================

class LicenseScreen:
    """Screen shown when trial expires and no license is present"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Credit Dispute Tool - License Required")
        self.root.geometry("500x350")
        self.root.configure(bg='#f0f0f0')
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title = tk.Label(self.root, text="TRIAL EXPIRED", font=('Arial', 18, 'bold'), fg='red', bg='#f0f0f0')
        title.pack(pady=30)
        
        # Message
        msg = tk.Label(self.root, text="Your 6-month free trial has ended.\n\nPlease purchase a commercial license to continue using this tool.\n\nContact: contact@clearwatercodes.com", 
                      bg='#f0f0f0', justify='center')
        msg.pack(pady=20)
        
        # License entry
        tk.Label(self.root, text="Enter License Key:", bg='#f0f0f0').pack()
        self.key_entry = tk.Entry(self.root, width=40)
        self.key_entry.pack(pady=5)
        
        # Buttons
        btn_frame = tk.Frame(self.root, bg='#f0f0f0')
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Activate License", command=self.activate_license, bg='green', fg='white', padx=20).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Exit", command=self.root.destroy, bg='red', fg='white', padx=20).pack(side='left', padx=10)
    
    def activate_license(self):
        key = self.key_entry.get().strip()
        if key.startswith("LIC-") and len(key) > 10:
            save_license(key)
            messagebox.showinfo("Success", "License activated! The application will now restart.")
            self.root.destroy()
            # Restart the app
            os.system('python3 bank_app.py')
            sys.exit()
        else:
            messagebox.showerror("Error", "Invalid license key.\n\nLicense keys start with 'LIC-' and are at least 11 characters.")


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # Check trial status
    trial_active, days_left, trial_message = check_trial_status()
    
    # Check for commercial license
    has_license = check_license()
    
    if not trial_active and not has_license:
        # Trial expired and no license - show license screen
        root = tk.Tk()
        license_screen = LicenseScreen(root)
        root.mainloop()
    else:
        # Trial active or license present - show main app
        root = tk.Tk()
        
        # Pass trial days left to show reminder if in trial
        trial_days = days_left if trial_active and not has_license else None
        app = DisputeApp(root, trial_days_left=trial_days)
        
        # Update window title to show trial status
        if trial_active and not has_license:
            root.title(f"Credit Dispute Tool - Trial ({days_left} days left)")
        
        root.mainloop()