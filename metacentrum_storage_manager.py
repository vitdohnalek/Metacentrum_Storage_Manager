import sys
import paramiko
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit,
    QPushButton, QListWidget, QLabel, QMessageBox,
    QInputDialog, QAbstractItemView, QFileDialog
)
from PySide6.QtCore import Qt
from stat import S_ISDIR
import os


class SSHBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metacentrum SSH Browser - Phase 1")
        self.resize(800, 600)
      
        # Layout and widgets
        layout = QVBoxLayout()

        self.host_input = QLineEdit()
        self.host_input.setText("skirit.metacentrum.cz")

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password")
        self.pass_input.setEchoMode(QLineEdit.Password)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_ssh)

        self.status_bar = QLabel("")

        self.upload_button = QPushButton("⬆️ Upload Files")
        self.upload_button.setEnabled(False)  # Enable only when connected
        self.upload_button.clicked.connect(self.upload_files)

        self.download_button = QPushButton("⬇️ Download")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_selected_items)
        
        self.rename_button = QPushButton("✏️ Rename")
        self.rename_button.setEnabled(False)
        self.rename_button.clicked.connect(self.rename_selected_item)

        self.mkdir_button = QPushButton("📂 Make New Folder")
        self.mkdir_button.setEnabled(False)
        self.mkdir_button.clicked.connect(self.make_directory)

        self.delete_button = QPushButton("🗑️ Delete")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_items)
        
        self.status_label = QLabel("Not connected")
        self.file_list = QListWidget()

        # Set multi-selection mode
        self.file_list.setSelectionMode(QAbstractItemView.MultiSelection)

        layout.addWidget(self.host_input)
        layout.addWidget(self.user_input)
        layout.addWidget(self.pass_input)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.file_list)
        layout.addWidget(self.status_bar)
        layout.addWidget(self.upload_button)
        layout.addWidget(self.download_button)
        layout.addWidget(self.rename_button)
        layout.addWidget(self.mkdir_button)
        layout.addWidget(self.delete_button)

        self.setLayout(layout)

        self.ssh_client = None
        self.sftp_client = None
        self.current_path = "."
        
        self.file_list.itemDoubleClicked.connect(self.handle_item_double_click)

    def connect_ssh(self):
        hostname = self.host_input.text()
        username = self.user_input.text()
        password = self.pass_input.text()

        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname, username=username, password=password)

            self.sftp_client = self.ssh_client.open_sftp()
            
            self.upload_button.setEnabled(True)
            self.download_button.setEnabled(True)
            self.rename_button.setEnabled(True)
            self.mkdir_button.setEnabled(True)
            self.delete_button.setEnabled(True)

            self.status_label.setText(f"Connected to {hostname}")

            self.list_remote_files(".")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            self.status_label.setText("Connection failed")

    def list_remote_files(self, path):
        self.file_list.clear()
        self.current_path = path
        try:
            files = self.sftp_client.listdir_attr(path)
            entries = []

            # Add ".." to go up unless we're at root
            if path not in ["/", ".", ""]:
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
    window = SSHBrowser()
    window.show()
    sys.exit(app.exec())
