import sys
import stat
import paramiko
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

class MetaCentrumClient(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MetaCentrum File Manager")
        self.setMinimumWidth(600)

        self.ssh_client = None
        self.sftp_client = None
        self.current_path = ""

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Connection fields
        self.hostname_input = QLineEdit("skirit.metacentrum.cz")
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        layout.addWidget(QLabel("Hostname:"))
        layout.addWidget(self.hostname_input)
        layout.addWidget(QLabel("Username:"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self.password_input)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_ssh)
        layout.addWidget(self.connect_btn)

        # File list
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.navigate_or_select)
        layout.addWidget(self.file_list)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.download_btn = QPushButton("Download Selected File")
        self.download_btn.clicked.connect(self.download_file)
        btn_layout.addWidget(self.download_btn)

        self.upload_btn = QPushButton("Upload File to Current Folder")
        self.upload_btn.clicked.connect(self.upload_file)
        btn_layout.addWidget(self.upload_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def connect_ssh(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.ssh_client.connect(
                hostname=self.hostname_input.text(),
                username=self.username_input.text(),
                password=self.password_input.text()
            )
            self.sftp_client = self.ssh_client.open_sftp()
            self.current_path = f"/storage/brno2/home/{self.username_input.text()}"
            QMessageBox.information(self, "Success", "Connected to MetaCentrum!")
            self.list_remote_files()
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def list_remote_files(self):
        try:
            entries = self.sftp_client.listdir_attr(self.current_path)
            self.file_list.clear()
            self.file_list.addItem("⬆️ ..")  # For going up a directory
            for attr in sorted(entries, key=lambda x: x.filename.lower()):
                if attr.filename.startswith('.'):
                    continue
                name = attr.filename + ('/' if stat.S_ISDIR(attr.st_mode) else '')
                icon = "📁" if stat.S_ISDIR(attr.st_mode) else "📄"
                self.file_list.addItem(f"{icon} {name}")
        except Exception as e:
            QMessageBox.critical(self, "List Error", str(e))

    def navigate_or_select(self, item):
        text = item.text()[2:].strip()
        if text == "..":
            if self.current_path != "/":
                self.current_path = '/'.join(self.current_path.rstrip('/').split('/')[:-1]) or "/"
                self.list_remote_files()
        elif text.endswith('/'):
            self.current_path = f"{self.current_path.rstrip('/')}/{text.rstrip('/')}"
            self.list_remote_files()

    def download_file(self):
        item = self.file_list.currentItem()
        if not item or item.text().startswith("📁") or item.text().startswith("⬆️"):
            QMessageBox.warning(self, "Invalid selection", "Please select a file to download.")
            return
        filename = item.text()[2:].strip()
        local_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if not local_dir:
            return
        remote_path = f"{self.current_path}/{filename}"
        local_path = f"{local_dir}/{filename}"
        try:
            self.sftp_client.get(remote_path, local_path)
            QMessageBox.information(self, "Success", f"Downloaded to {local_path}")
        except Exception as e:
            QMessageBox.critical(self, "Download Error", str(e))

    def upload_file(self):
        local_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if not local_path:
            return
        filename = local_path.split('/')[-1]
        remote_path = f"{self.current_path}/{filename}"
        try:
            self.sftp_client.put(local_path, remote_path)
            QMessageBox.information(self, "Success", f"Uploaded {filename} to MetaCentrum.")
            self.list_remote_files()
        except Exception as e:
            QMessageBox.critical(self, "Upload Error", str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MetaCentrumClient()
    window.show()
    sys.exit(app.exec())
