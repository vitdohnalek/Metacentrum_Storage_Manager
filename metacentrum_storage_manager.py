import paramiko
import tkinter as tk
import stat
from tkinter import filedialog, messagebox

ssh_client = None
sftp_client = None
current_path = None

def connect_ssh():
    global ssh_client, sftp_client, current_path
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_client.connect(hostname=hostname_entry.get(),
                           username=username_entry.get(),
                           password=password_entry.get())
        sftp_client = ssh_client.open_sftp()
        current_path = f"/storage/brno2/home/{username_entry.get()}"
        messagebox.showinfo("Success", "Connected to MetaCentrum!")
        list_remote_files()
    except Exception as e:
        messagebox.showerror("Connection Error", str(e))


def list_remote_files():
    global current_path
    try:
        entries = sftp_client.listdir_attr(current_path)
        visible_items = []

        if current_path != f"/storage/brno2/home/{username_entry.get()}":
            visible_items.append("⬆️ ..")  # Option to go up

        for attr in entries:
            name = attr.filename
            if name.startswith('.'):
                continue
            if stat.S_ISDIR(attr.st_mode):
                display_name = f"📁 {name}/"
            else:
                display_name = f"📄 {name}"
            visible_items.append(display_name)

        file_listbox.delete(0, tk.END)
        for item in sorted(visible_items, key=lambda x: x.lower()):
            file_listbox.insert(tk.END, item)

    except Exception as e:
        messagebox.showerror("List Error", str(e))


def on_item_double_click(event):
    global current_path
    selection = file_listbox.curselection()
    if not selection:
        return
    item = file_listbox.get(selection[0])

    if item.startswith("📁 "):
        folder_name = item.replace("📁 ", "").rstrip('/')
        current_path += f"/{folder_name}"
        list_remote_files()
    elif item.startswith("⬆️"):
        if current_path != f"/storage/brno2/home/{username_entry.get()}":
            current_path = '/'.join(current_path.rstrip('/').split('/')[:-1])
            list_remote_files()


def download_file():
    selection = file_listbox.curselection()
    if not selection:
        messagebox.showwarning("No file selected", "Please select a file to download.")
        return
    filename = file_listbox.get(selection[0])
    if not filename.startswith("📄 "):
        messagebox.showwarning("Invalid Selection", "Please select a file (not folder).")
        return
    filename = filename.replace("📄 ", "")
    local_dir = filedialog.askdirectory()
    if not local_dir:
        return
    remote_path = f"{current_path}/{filename}"
    local_path = f"{local_dir}/{filename}"
    try:
        sftp_client.get(remote_path, local_path)
        messagebox.showinfo("Success", f"Downloaded to {local_path}")
    except Exception as e:
        messagebox.showerror("Download Error", str(e))

def upload_file():
    local_path = filedialog.askopenfilename()
    if not local_path:
        return
    filename = local_path.split('/')[-1]
    remote_path = f"{current_path}/{filename}"
    try:
        sftp_client.put(local_path, remote_path)
        messagebox.showinfo("Success", f"Uploaded {filename} to MetaCentrum.")
        list_remote_files()
    except Exception as e:
        messagebox.showerror("Upload Error", str(e))


# GUI setup
root = tk.Tk()
root.title("MetaCentrum File Manager")

tk.Label(root, text="Hostname").pack()
hostname_entry = tk.Entry(root)
hostname_entry.insert(0, "skirit.metacentrum.cz")
hostname_entry.pack()

tk.Label(root, text="Username").pack()
username_entry = tk.Entry(root)
username_entry.pack()

tk.Label(root, text="Password").pack()
password_entry = tk.Entry(root, show="*")
password_entry.pack()

tk.Button(root, text="Connect", command=connect_ssh).pack()

file_listbox = tk.Listbox(root, height=20, width=60)
file_listbox.pack()
file_listbox.bind("<Double-Button-1>", on_item_double_click)

tk.Button(root, text="Upload File to Current Folder", command=upload_file).pack()
tk.Button(root, text="Download Selected File", command=download_file).pack()

root.mainloop()
