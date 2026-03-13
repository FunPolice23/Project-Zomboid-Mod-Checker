# gui_themes.py - All color schemes in one place (easy to expand forever)

THEME_STYLES = {
    "Dark Classic": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #1e1e2e; color: #cdd6f4; }
        QLabel { font-size: 14px; }
        QPushButton { background-color: #2ecc71; color: black; font-weight: bold; border-radius: 8px; padding: 12px; font-size: 14px; }
        QPushButton:hover { background-color: #27ae60; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #161622; border: 2px solid #45475a; border-radius: 8px; padding: 8px; }
        QTreeWidget::item:selected { background-color: #3e3e5e; }
    """,
    "Light Clean": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #f8f9fa; color: #212529; }
        QLabel { font-size: 14px; }
        QPushButton { background-color: #28a745; color: white; font-weight: bold; border-radius: 8px; padding: 12px; font-size: 14px; }
        QPushButton:hover { background-color: #218838; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #ffffff; border: 2px solid #ced4da; border-radius: 8px; padding: 8px; }
        QTreeWidget::item:selected { background-color: #d1ecf1; }
    """,
    "Blue Ocean Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #0a2540; color: #a5d6ff; }
        QPushButton { background-color: #00b4d8; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #0f3d5e; border: 2px solid #00b4d8; }
    """,
    "Blue Ocean Light": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #e0f2fe; color: #0c4a6e; }
        QPushButton { background-color: #0284c8; color: white; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #bae6fd; border: 2px solid #0284c8; }
    """,
    "Green Forest Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #0f3a1f; color: #b5f5b5; }
        QPushButton { background-color: #34d399; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #1a4f2f; border: 2px solid #34d399; }
    """,
    "Green Forest Light": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #f0fdf4; color: #166534; }
        QPushButton { background-color: #16a34a; color: white; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #dcfce7; border: 2px solid #16a34a; }
    """,
    "Purple Midnight Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2a1f3d; color: #d8b4ff; }
        QPushButton { background-color: #a855f7; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3a2a4f; border: 2px solid #a855f7; }
    """,
    "Purple Midnight Light": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #f3e8ff; color: #4c1d95; }
        QPushButton { background-color: #9333ea; color: white; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #ede9fe; border: 2px solid #9333ea; }
    """,
    "Red Crimson Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c0f0f; color: #ff9999; }
        QPushButton { background-color: #e63939; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3d1a1a; border: 2px solid #e63939; }
    """,
    "Red Crimson Light": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #fff0f0; color: #8b0000; }
        QPushButton { background-color: #c8102e; color: white; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #ffe0e0; border: 2px solid #c8102e; }
    """,
    "Cyber Neon Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #0a0a1f; color: #00ffcc; }
        QPushButton { background-color: #ff00aa; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #1a1a3a; border: 2px solid #00ffcc; }
    """,
    "Cyber Neon Light": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #f0f8ff; color: #006666; }
        QPushButton { background-color: #ff3399; color: white; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #e0f0ff; border: 2px solid #006666; }
    """,
    "Orange Sunset Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c1f10; color: #ffd4a3; }
        QPushButton { background-color: #ff8c00; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3d2a1a; border: 2px solid #ff8c00; }
        QTreeWidget::item:selected { background-color: #ff8c00; color: black; }
    """,
    "Teal Ocean Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #0f2c2c; color: #a3ffdd; }
        QPushButton { background-color: #00b894; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #1a3f3f; border: 2px solid #00b894; }
    """,
    "Pink Neon Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c0f1f; color: #ffb3e6; }
        QPushButton { background-color: #ff69b4; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3f1a2c; border: 2px solid #ff69b4; }
    """,
    "Slate Gray Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #1f252c; color: #d1d9e6; }
        QPushButton { background-color: #778899; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #2c333f; border: 2px solid #778899; }
    """,
    "Yellow Amber Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c240f; color: #ffe6a3; }
        QPushButton { background-color: #ffb300; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3f331a; border: 2px solid #ffb300; }
    """,
    "Violet Royal Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #1f0f2c; color: #d8b4ff; }
        QPushButton { background-color: #8a2be2; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #2c1a3f; border: 2px solid #8a2be2; }
    """,
    "Emerald Deep Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #0f2c1f; color: #a3ffcc; }
        QPushButton { background-color: #00c853; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #1a3f2c; border: 2px solid #00c853; }
    """,
    "Crimson Blood Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c0f0f; color: #ff9999; }
        QPushButton { background-color: #c8102e; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3f1a1a; border: 2px solid #c8102e; }
    """,
    "Purple Teal Fusion Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #1f0f2c; color: #a3ffdd; }
        QPushButton { background-color: #8a2be2; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #2c1a3f; border: 2px solid #00b894; }
        QTreeWidget::item:selected { background-color: #00b894; color: black; }
    """,
    "Crimson Gold Ember Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c0f0f; color: #ffe6a3; }
        QPushButton { background-color: #c8102e; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3f1a1a; border: 2px solid #ffb300; }
    """,
    "Teal Violet Nebula Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #0f2c2c; color: #d8b4ff; }
        QPushButton { background-color: #00b894; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #1a3f3f; border: 2px solid #8a2be2; }
    """,
    "Amber Cyan Spark Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c240f; color: #a3f0ff; }
        QPushButton { background-color: #ffb300; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3f331a; border: 2px solid #00b4d8; }
    """,
    "Neon Pink Green Mix Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c0f1f; color: #b5f5b5; }
        QPushButton { background-color: #ff69b4; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3f1a2c; border: 2px solid #34d399; }
    """,
    "Slate Red Steel Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #1f252c; color: #ff9999; }
        QPushButton { background-color: #778899; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #2c333f; border: 2px solid #c8102e; }
    """,
    "Ocean Emerald Wave Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #0a2540; color: #a3ffcc; }
        QPushButton { background-color: #00b4d8; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #0f3d5e; border: 2px solid #00c853; }
    """,
    "Sunset Violet Horizon Dark": """
        QMainWindow, QTabWidget, QWidget, QGroupBox { background-color: #2c1f10; color: #d8b4ff; }
        QPushButton { background-color: #ff8c00; color: black; font-weight: bold; border-radius: 8px; }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget, QSlider { background-color: #3d2a1a; border: 2px solid #8a2be2; }
    """
}