# ClearFlow Finance Desktop

ClearFlow opens in its own window and works offline using the operating system’s webview. It starts with an empty ledger.

## Downloads

- [ClearFlow Desktop ZIP](downloads/ClearFlow-Desktop.zip) for Windows and macOS with Python.
- [ClearFlow 3.0.1 Debian package](downloads/clearflow-finance_3.0.1_all.deb) for Debian 13.

## Debian 13

Install the package with your package installer or run:

    sudo apt install ./clearflow-finance_3.0.1_all.deb

Launch **ClearFlow Finance** from the application menu.

## Windows and macOS

The source bundle requires Python 3.10 or newer. Windows requires the Microsoft Edge WebView2 Runtime. macOS uses the system WebKit webview. Extract the ZIP, open a terminal in the extracted folder, and run:

    python -m pip install -r requirements.txt
    python clearflow.py

Use python3 on macOS if that’s how Python is installed. A graphical Linux session can also run the source with GTK 3, PyGObject, and WebKitGTK 4.1.

## Move an existing ledger

1. Open the original ClearFlow in the browser profile where you tracked your finances.
2. In Settings, select **Export JSON Backup**.
3. In desktop Settings, select **Import JSON Backup** and confirm the restore.

## Storage and recovery

Settings shows the path to the active ledger. ClearFlow saves changes to ledger.json and keeps one previous version in ledger.previous.json. **Restore previous version** lets you roll back. If the active file is unreadable, the recovery screen lets you restore a backup. ClearFlow archives the original bytes when you confirm the restore. Use **Export JSON Backup** to keep an independent copy. The ledger files are unencrypted JSON.

ClearFlow.html can also run in a browser. Browser data depends on the URL or origin, so export from the original app before moving or replacing the HTML file.
