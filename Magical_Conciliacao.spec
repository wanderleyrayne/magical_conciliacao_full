# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('assets', 'assets'), ('core', 'core'), ('database', 'database'), ('ui', 'ui'), ('utils', 'utils'), ('config_inicial.json', '.'), ('setup_inicial.py', '.')]
hiddenimports = ['openpyxl', 'et_xmlfile', 'openpyxl.cell._writer', 'rapidfuzz', 'rapidfuzz.fuzz', 'rapidfuzz.process', 'requests', 'numpy', 'numpy.core', 'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog', 'tkinter.scrolledtext', 'reportlab', 'reportlab.lib', 'reportlab.lib.pagesizes', 'reportlab.lib.colors', 'reportlab.lib.units', 'reportlab.lib.styles', 'reportlab.lib.enums', 'reportlab.platypus', 'reportlab.platypus.tables', 'reportlab.platypus.paragraph', 'reportlab.pdfgen', 'reportlab.pdfgen.canvas']
datas += collect_data_files('openpyxl')
datas += collect_data_files('reportlab')
hiddenimports += collect_submodules('pandas')
hiddenimports += collect_submodules('openpyxl')
hiddenimports += collect_submodules('numpy')
hiddenimports += collect_submodules('reportlab')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Magical_Conciliacao',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
