import sys
import paramiko
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit,
    QPushButton, QListWidget, QLabel, QMessageBox,
    QInputDialog, QAbstractItemView, QFileDialog,
    QHBoxLayout, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from stat import S_ISDIR
import time
import os
import re

def remove_ansi_escape_sequences(text):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class SSHBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MetaBrowse")
        self.resize(800, 600)
      
        # Layout and widgets
        layout = QVBoxLayout()

        ceredentials_row = QHBoxLayout()
        upload_download_row = QHBoxLayout()
        manipulate_row = QHBoxLayout()

        self.location_input = QComboBox()
        self.location_map = {
            "brno11-elixir" : "/storage/brno11-elixir/home/{username}",
            "brno12-cerit" : "/storage/brno12-cerit/home/{username}",
            "brno2" : "/storage/brno2/home/{username}",
            "budejovice1" : "/storage/budejovice1/home/{username}",
            "liberec3-tul" : "/storage/liberec3-tul/home/{username}",
            "plzen1" : "/storage/plzen1/home/{username}",
            "praha2-natur" : "/storage/praha2-natur/home/{username}",
            "praha5-elixir" : "/storage/praha5-elixir/home/{username}",
            "pruhonice1-ibot" : "/storage/pruhonice1-ibot/home/{username}",
            "vestec1-elixir" : "/storage/vestec1-elixir/home/{username}"
        }
        self.location_input.addItems(self.location_map.keys())
        self.location_input.setCurrentText("brno2")
        ceredentials_row.addWidget(self.location_input)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        ceredentials_row.addWidget(self.user_input)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password")
        self.pass_input.setEchoMode(QLineEdit.Password)
        ceredentials_row.addWidget(self.pass_input)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_ssh)

        self.status_bar = QLabel("")

        self.upload_button = QPushButton("⬆️ Upload Files")
        self.upload_button.setEnabled(False)  # Enable only when connected
        self.upload_button.clicked.connect(self.upload_files)
        upload_download_row.addWidget(self.upload_button)

        self.download_button = QPushButton("⬇️ Download Files")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_selected_items)
        upload_download_row.addWidget(self.download_button)

        self.rename_button = QPushButton("✏️ Rename")
        self.rename_button.setEnabled(False)
        self.rename_button.clicked.connect(self.rename_selected_item)
        manipulate_row.addWidget(self.rename_button)

        self.mkdir_button = QPushButton("📂 Make New Folder")
        self.mkdir_button.setEnabled(False)
        self.mkdir_button.clicked.connect(self.make_directory)
        manipulate_row.addWidget(self.mkdir_button)

        self.delete_button = QPushButton("🗑️ Delete")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_items)
        manipulate_row.addWidget(self.delete_button)
        
        self.status_label = QLabel("Not connected")
        self.storage_info_label =QLabel("")
        self.file_list = QListWidget()

        # Set multi-selection mode
        self.file_list.setSelectionMode(QAbstractItemView.MultiSelection)

        layout.addLayout(ceredentials_row)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.storage_info_label)
        layout.addWidget(self.file_list)
        layout.addWidget(self.status_bar)
        layout.addLayout(upload_download_row)
        layout.addLayout(manipulate_row)

        self.setLayout(layout)

        self.ssh_client = None
        self.sftp_client = None
        self.current_path = "."
        
        self.file_list.itemDoubleClicked.connect(self.handle_item_double_click)

    def connect_ssh(self):
        location = self.location_input.currentText()
        path_template = self.location_map[location]

        username = self.user_input.text()
        password = self.pass_input.text()
        hostname = "skirit.metacentrum.cz"
        remote_path = path_template.format(username=username)

        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname, username=username, password=password)

            self.sftp_client = self.ssh_client.open_sftp()

            # Get the remote shell output (login banner + quotas)
            stdin, stdout, stderr = self.ssh_client.exec_command('cat /etc/motd || echo ""')
            motd = stdout.read().decode('utf-8')

            # Also try capturing last login or full banner (because MOTD may be empty)
            if not motd.strip():
                stdin, stdout, stderr = self.ssh_client.exec_command('uptime; whoami')  # fallback commands

            # You may instead capture the login banner by forcing a pseudo-terminal:
            # This example captures the welcome message:
            transport = self.ssh_client.get_transport()
            channel = transport.open_session()
            channel.get_pty()
            channel.invoke_shell()

            time.sleep(1)  # wait for server to send banner

            output = ""
            while channel.recv_ready():
                output += channel.recv(1024).decode('utf-8')

            # Parse the output for the line containing your location quotas:
            storage_line = None
            for line in output.splitlines():
                if location in line:
                    storage_line = line
                    break

            if storage_line:
                clean_line = remove_ansi_escape_sequences(storage_line)
                parts = clean_line.split()
                available_space = parts[1]
                used_space = parts[2]
                max_files = parts[3]
                current_files = parts[4]
                self.storage_info_label.setText(
                    f"Available Space: {available_space} Used Space: {used_space} "
                    f"Max File Quota: {max_files} Files Used: {current_files}"
                )
            else:
                self.storage_info_label.setText("Storage info not found.")

            # Enable buttons etc.
            self.upload_button.setEnabled(True)
            self.download_button.setEnabled(True)
            self.rename_button.setEnabled(True)
            self.mkdir_button.setEnabled(True)
            self.delete_button.setEnabled(True)

            self.status_label.setText(f"Connected to {hostname}, browsing {remote_path}")

            self.root_path = remote_path
            self.list_remote_files(remote_path)

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            self.status_label.setText("Connection failed")

    def list_remote_files(self, path):
        self.file_list.clear()
        self.current_path = path
        try:
            files = self.sftp_client.listdir_attr(path)
            entries = []

            
            if path not in ["/", ".", ""] and path != self.root_path:
                entries.append("⬅️ ..")

            for attr in files:
                name = attr.filename
                if name.startswith('.'):
                    continue
                if S_ISDIR(attr.st_mode):
                    display_name = f"📁 {name}/"
                else:
                    display_name = f"📄 {name}"
                entries.append(display_name)

            for entry in sorted(entries, key=lambda x: x.lower()):
                self.file_list.addItem(entry)

        except Exception as e:
            QMessageBox.critical(self, "List Error", str(e))

    def handle_item_double_click(self, item):
        text = item.text()
        if text.startswith("📁"):
            folder_name = text[2:].rstrip("/")  # remove emoji and slash
            new_path = self.current_path.rstrip("/") + "/" + folder_name
            self.list_remote_files(new_path)
        elif text.startswith("⬅️"):
            # Go up one level
            if self.current_path in ["/", ".", ""]:
                return
            parent_path = "/".join(self.current_path.rstrip("/").split("/")[:-1])
            if not parent_path:
                parent_path = "."
            self.list_remote_files(parent_path)

    def upload_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Upload")

        if not file_paths:
            return

        total_files = len(file_paths)

        for i, file_path in enumerate(file_paths, 1):
            local_file_name = os.path.basename(file_path)
            remote_file_path = self.current_path.rstrip("/") + "/" + local_file_name

            self.status_bar.setText(f"Uploading {i}/{total_files}: {local_file_name}")
            QApplication.processEvents()  # Keeps UI responsive

            try:
                self.sftp_client.put(file_path, remote_file_path)
            except Exception as e:
                self.status_bar.setText(f"⚠️ Failed to upload {local_file_name}: {str(e)}")
                return

        self.list_remote_files(self.current_path)
        self.status_bar.setText(f"✅ Uploaded {total_files} file(s) successfully.")

    def download_selected_items(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            self.status_bar.setText("No items selected for download.")
            return

        dest_dir = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if not dest_dir:
            return

        total = len(selected_items)
        for i, item in enumerate(selected_items, 1):
            text = item.text()
            name = text[2:].rstrip("/")  # Remove emoji
            remote_path = f"{self.current_path.rstrip('/')}/{name}"
            local_path = os.path.join(dest_dir, name)

            self.status_bar.setText(f"⬇️ Downloading {i}/{total}: {name}")
            QApplication.processEvents()

            try:
                attr = self.sftp_client.lstat(remote_path)
                if S_ISDIR(attr.st_mode):
                    self.download_folder(remote_path, local_path)
                else:
                    self.sftp_client.get(remote_path, local_path)
            except Exception as e:
                self.status_bar.setText(f"⚠️ Failed to download {name}: {str(e)}")

        self.status_bar.setText(f"✅ Downloaded {total} item(s) to {dest_dir}")

    def download_folder(self, remote_dir, local_dir):
        os.makedirs(local_dir, exist_ok=True)
        for entry in self.sftp_client.listdir_attr(remote_dir):
            name = entry.filename
            remote_path = f"{remote_dir}/{name}"
            local_path = os.path.join(local_dir, name)

            if S_ISDIR(entry.st_mode):
                self.download_folder(remote_path, local_path)
            else:
                self.sftp_client.get(remote_path, local_path)

    def make_directory(self):
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and folder_name:
            try:
                new_path = self.current_path.rstrip("/") + "/" + folder_name
                self.sftp_client.mkdir(new_path)
                self.list_remote_files(self.current_path)
            except Exception as e:
                QMessageBox.critical(self, "Error Creating Folder", str(e))

    def delete_selected_items(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select files or folders to delete.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the selected {len(selected_items)} item(s)?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        for item in selected_items:
            text = item.text()
            name = text[2:].rstrip("/")  # Remove emoji and trailing slash
            path = self.current_path.rstrip("/") + "/" + name
            try:
                if text.startswith("📁"):
                    self.sftp_client.rmdir(path)  # Only works if empty
                else:
                    self.sftp_client.remove(path)
            except Exception as e:
                QMessageBox.warning(self, "Delete Error", f"Failed to delete {name}:\n{str(e)}")

        self.list_remote_files(self.current_path)

    def rename_selected_item(self):
        selected_items = self.file_list.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.information(self, "Invalid Selection", "Please select exactly one file or folder to rename.")
            return

        item = selected_items[0]
        text = item.text()
        current_name = text[2:].rstrip("/")  # Remove emoji and trailing slash
        path = self.current_path.rstrip("/") + "/" + current_name

        # Prompt the user for a new name
        new_name, ok = QInputDialog.getText(self, "Rename", "Enter the new name:", text=current_name)
        
        if not ok or not new_name.strip():
            return  # Don't do anything if the user cancels or enters an empty name

        new_path = self.current_path.rstrip("/") + "/" + new_name.strip()

        try:
            self.sftp_client.rename(path, new_path)  # Rename the file or folder
            self.list_remote_files(self.current_path)
        except Exception as e:
            QMessageBox.warning(self, "Rename Error", f"Failed to rename {current_name}:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    font = QFont()
    font.setPointSize(11)
    app.setFont(font)

    window = SSHBrowser()
    window.show()
    sys.exit(app.exec())
